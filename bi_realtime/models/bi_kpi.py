



# -*- coding: utf-8 -*-
"""
bi_kpi.py — Modèle KPI amélioré v6
CORRECTIONS:
  - BiKpiHistory.get_kpis_with_comparison et batch_refresh_by_dashboard et action_get_drill_data
    étaient sur BiKpiHistory au lieu de BiKpi → déplacés sur BiKpi (bonne classe)
  - _send_alert_email utilise mail.mail (pas de dépendance 'mail' nécessaire si core installé)
  - Cache mémoire thread-safe
  - Validation domain robuste
"""
from odoo import models, fields, api
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import ValidationError
import json
import logging
import csv
import io
import base64
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

# Cache simple en mémoire (KPI id -> (value, timestamp))
_KPI_CACHE = {}
_CACHE_TTL = 10  # secondes

# Dernières valeurs agrégées Spark (tables kpi_*) par libellé KPI Odoo
_PIPELINE_KPI_SQL = {
    'CA Total': (
        "SELECT COALESCE(total_revenue, 0) FROM kpi_sales "
        "ORDER BY window_start DESC LIMIT 1"
    ),
    'Chiffre d\'affaires total': (
        "SELECT COALESCE(total_revenue, 0) FROM kpi_sales "
        "ORDER BY window_start DESC LIMIT 1"
    ),
    'Nb Commandes': (
        "SELECT COALESCE(order_count, 0) FROM kpi_sales "
        "ORDER BY window_start DESC LIMIT 1"
    ),
    'Nombre de commandes': (
        "SELECT COALESCE(order_count, 0) FROM kpi_sales "
        "ORDER BY window_start DESC LIMIT 1"
    ),
    'Valeur Moyenne Commande': (
        "SELECT COALESCE(avg_order_value, 0) FROM kpi_sales "
        "ORDER BY window_start DESC LIMIT 1"
    ),
    'Valeur moyenne commande': (
        "SELECT COALESCE(avg_order_value, 0) FROM kpi_sales "
        "ORDER BY window_start DESC LIMIT 1"
    ),
    'Impayés en cours': (
        "SELECT COALESCE(SUM(total_residual), 0) FROM kpi_invoices "
        "WHERE payment_state = 'not_paid' "
        "AND window_start = (SELECT MAX(window_start) FROM kpi_invoices)"
    ),
    'Chiffre d\'affaires facturé': (
        "SELECT COALESCE(SUM(total_amount), 0) FROM kpi_invoices "
        "WHERE move_type = 'out_invoice' "
        "AND window_start = (SELECT MAX(window_start) FROM kpi_invoices)"
    ),
    'Pipeline total': (
        "SELECT COALESCE(pipeline_total, 0) FROM kpi_crm "
        "ORDER BY window_start DESC LIMIT 1"
    ),
    'Opportunités actives': (
        "SELECT COALESCE(lead_count, 0) FROM kpi_crm "
        "ORDER BY window_start DESC LIMIT 1"
    ),
    'Ventes du jour': (
        "SELECT COALESCE(total_sales, 0) FROM kpi_pos "
        "ORDER BY window_start DESC LIMIT 1"
    ),
    'Nombre transactions': (
        "SELECT COALESCE(transaction_count, 0) FROM kpi_pos "
        "ORDER BY window_start DESC LIMIT 1"
    ),
    'Panier moyen': (
        "SELECT COALESCE(avg_basket, 0) FROM kpi_pos "
        "ORDER BY window_start DESC LIMIT 1"
    ),
    'Montant achats fournisseurs': (
        "SELECT COALESCE(total_amount, 0) FROM kpi_purchases "
        "ORDER BY window_start DESC LIMIT 1"
    ),
    'Nb bons de commande': (
        "SELECT COALESCE(order_count, 0) FROM kpi_purchases "
        "ORDER BY window_start DESC LIMIT 1"
    ),
}


def _mapped_scalar_to_floats(raw_values):
    """Extrait des nombres depuis record.mapped() (Monetary, Decimal, etc.)."""
    try:
        from decimal import Decimal
    except ImportError:
        Decimal = None  # noqa: N806
    out = []
    for v in raw_values:
        if v is None or v is False:
            continue
        if hasattr(v, '_name') and hasattr(v, 'ids'):
            continue
        if isinstance(v, (int, float)):
            out.append(float(v))
            continue
        if Decimal is not None and isinstance(v, Decimal):
            out.append(float(v))
            continue
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


class BiKpi(models.Model):
    _name = 'bi.kpi'
    _description = 'KPI BI'
    _order = 'sequence, name'
    # FIX: _inherit = [] retiré — inutile et peut causer des warnings

    name = fields.Char(string='Nom', required=True)
    dashboard_id = fields.Many2one('bi.dashboard', string='Dashboard',
                                   ondelete='cascade', required=True)

    # Source des données
    source = fields.Selection([
        ('odoo', 'Odoo (calcul direct)'),
        ('kafka', 'Kafka/Spark (temps réel)'),
        ('dax', 'Mesure DAX'),
        ('manual', 'Manuel'),
    ], default='odoo', string='Source données')

    # Configuration données
    model_id = fields.Many2one('ir.model', string='Modèle')
    field_id = fields.Many2one('ir.model.fields', string='Champ')
    aggregation = fields.Selection([
        ('sum', 'Somme'),
        ('avg', 'Moyenne'),
        ('count', 'Nombre'),
        ('max', 'Maximum'),
        ('min', 'Minimum'),
    ], default='sum', string='Agrégation')

    filter_domain = fields.Char(string='Domaine filtre', default='[]')
    filter_date_range = fields.Selection([
        ('today', "Aujourd'hui"),
        ('yesterday', 'Hier'),
        ('this_week', 'Cette semaine'),
        ('last_week', 'Semaine dernière'),
        ('last_7_days', '7 derniers jours'),
        ('last_14_days', '14 derniers jours'),
        ('last_30_days', '30 derniers jours'),
        ('this_month', 'Ce mois'),
        ('last_month', 'Mois dernier'),
        ('last_3_months', '3 derniers mois'),
        ('last_6_months', '6 derniers mois'),
        ('this_quarter', 'Ce trimestre'),
        ('last_quarter', 'Trimestre dernier'),
        ('this_year', 'Cette année'),
        ('last_year', 'Année dernière'),
        ('last_365_days', '365 derniers jours'),
        ('all_time', 'Tout'),
        ('custom', 'Personnalisé'),
    ], default='all_time', string='Période')
    filter_date_from = fields.Date(string='Date début')
    filter_date_to = fields.Date(string='Date fin')
    filter_date_field = fields.Char(string='Champ date', default='create_date')

    # Affichage
    chart_type = fields.Selection([
        ('number', 'Nombre'),
        ('indicator', 'Indicateur'),
        ('counter', 'Compteur'),
        ('bar', 'Barre'),
        ('hbar', 'Barre horizontale'),
        ('line', 'Ligne'),
        ('area', 'Aire'),
        ('pie', 'Camembert'),
        ('doughnut', 'Donut'),
        ('gauge', 'Jauge'),
        ('radial', 'Radial'),
        ('radar', 'Radar'),
        ('polarArea', 'Polaire'),
        ('scatter', 'Nuage de points'),
        ('table', 'Tableau'),
        ('bullet', 'Bullet'),
        ('funnel', 'Entonnoir'),
        ('flower', 'Fleur'),
        ('mixed', 'Combiné'),
    ], default='indicator', string='Type de graphique')

    color = fields.Char(string='Couleur', default='#007bff')
    color2 = fields.Char(string='Couleur secondaire', default='#6c757d')
    unit = fields.Char(string='Unité', help='Ex: €, %, unités')
    widget_size = fields.Selection([
        ('small', 'Petit'),
        ('medium', 'Moyen'),
        ('large', 'Grand'),
        ('xlarge', 'Très grand'),
    ], default='medium', string='Taille du widget')
    sequence = fields.Integer(string='Ordre', default=10)

    icon = fields.Selection([
        ('fa-chart-line',    '📈 Ligne'),
        ('fa-chart-bar',     '📊 Barres'),
        ('fa-chart-pie',     '🥧 Camembert'),
        ('fa-dollar-sign',   '💰 Dollar'),
        ('fa-euro-sign',     '€ Euro'),
        ('fa-shopping-cart', '🛒 Panier'),
        ('fa-users',         '👥 Utilisateurs'),
        ('fa-box',           '📦 Boîte'),
        ('fa-check-circle',  '✅ Check'),
        ('fa-exclamation',   '⚠️ Alerte'),
        ('fa-arrow-up',      '⬆️ Hausse'),
        ('fa-arrow-down',    '⬇️ Baisse'),
        ('fa-star',          '⭐ Étoile'),
        ('fa-clock',         '🕐 Horloge'),
        ('fa-cog',           '⚙️ Paramètre'),
    ], default='fa-chart-line', string='Icône FA')
    icon_type = fields.Selection([
        ('fa', 'Font Awesome'),
        ('image', 'Image'),
    ], default='fa', string="Type d'icône")

    # Données (mise à jour par Kafka ou calcul direct)
    value = fields.Float(string='Valeur', readonly=True)
    value_previous = fields.Float(string='Valeur précédente', readonly=True)
    last_update = fields.Datetime(string='Dernière mise à jour', readonly=True)
    chart_data = fields.Text(string='Données graphique (JSON)')

    # Objectif
    target_value = fields.Float(string='Objectif')
    target_label = fields.Char(string='Label objectif', default='Objectif')

    # Drill-down
    drill_field_id = fields.Many2one('ir.model.fields', string='Champ drill-down')

    # Favoris
    bookmarked_user_ids = fields.Many2many(
        'res.users', 'bi_kpi_bookmark_rel', string='Favoris'
    )

    # Groupes accès
    group_ids = fields.Many2many(
        'res.groups',
        relation='bi_kpi_group_rel',
        string='Groupes autorisés'
    )

    # ─── ALERTES ───────────────────────────────────────────────────
    alert_enabled = fields.Boolean(string='Alertes actives', default=False)
    alert_threshold = fields.Float(string='Seuil alerte', default=0.0)
    alert_condition = fields.Selection([
        ('gt', '> Supérieur à'),
        ('lt', '< Inférieur à'),
        ('gte', '>= Supérieur ou égal'),
        ('lte', '<= Inférieur ou égal'),
        ('eq', '= Égal à'),
    ], default='gt', string='Condition alerte')
    alert_email = fields.Char(string='Email alerte',
                               help='Email(s) séparés par virgule. Vide = utilisateur courant')
    alert_last_sent = fields.Datetime(string='Dernière alerte envoyée', readonly=True)
    alert_cooldown_hours = fields.Integer(string='Délai entre alertes (h)', default=1)

    # ─── HISTORIQUE ──────────────────────────────────────────────
    history_ids = fields.One2many('bi.kpi.history', 'kpi_id', string='Historique valeurs')

    # ─── VARIATION ───────────────────────────────────────────────
    @api.depends('value', 'value_previous')
    def _compute_variation(self):
        for kpi in self:
            if kpi.value_previous and kpi.value_previous != 0:
                kpi.variation_pct = ((kpi.value - kpi.value_previous) / abs(kpi.value_previous)) * 100
            else:
                kpi.variation_pct = 0.0
            kpi.trend = 'up' if kpi.value >= kpi.value_previous else 'down'

    variation_pct = fields.Float(string='Variation %', compute='_compute_variation', store=True)
    trend = fields.Char(string='Tendance', compute='_compute_variation', store=True)

    # ─── MÉTHODES ────────────────────────────────────────────────

    @api.constrains('filter_domain')
    def _check_domain(self):
        for kpi in self:
            if kpi.filter_domain and kpi.filter_domain.strip():
                domain = None
                try:
                    domain = safe_eval(kpi.filter_domain)
                except Exception:
                    # Même logique que _compute_value : le frontend envoie souvent du JSON
                    # (true/false/null) via JSON.stringify, illisible par safe_eval.
                    try:
                        domain = json.loads(kpi.filter_domain)
                    except Exception as e:
                        raise ValidationError(
                            f"Domaine invalide pour '{kpi.name}': {e}"
                        ) from e
                if not isinstance(domain, list):
                    raise ValidationError(
                        f"Le domaine doit être une liste: {kpi.filter_domain}"
                    )

    def _get_date_domain(self):
        """Retourne le domaine date selon le filtre sélectionné."""
        self.ensure_one()
        today = datetime.today().date()
        date_field = self.filter_date_field or 'create_date'
        dr = self.filter_date_range

        if dr == 'today':
            d_from, d_to = today, today
        elif dr == 'yesterday':
            d_from = d_to = today - timedelta(days=1)
        elif dr == 'this_week':
            d_from = today - timedelta(days=today.weekday())
            d_to = today
        elif dr == 'last_week':
            end_last_week = today - timedelta(days=today.weekday() + 1)
            d_from = end_last_week - timedelta(days=6)
            d_to = end_last_week
        elif dr == 'last_7_days':
            d_from, d_to = today - timedelta(days=7), today
        elif dr == 'last_14_days':
            d_from, d_to = today - timedelta(days=14), today
        elif dr == 'this_month':
            d_from = today.replace(day=1)
            d_to = today
        elif dr == 'last_month':
            first_this_month = today.replace(day=1)
            d_to = first_this_month - timedelta(days=1)
            d_from = d_to.replace(day=1)
        elif dr == 'last_30_days':
            d_from, d_to = today - timedelta(days=30), today
        elif dr == 'last_3_months':
            d_from = today - timedelta(days=90)
            d_to = today
        elif dr == 'last_6_months':
            d_from = today - timedelta(days=180)
            d_to = today
        elif dr == 'this_quarter':
            q = (today.month - 1) // 3
            d_from = today.replace(month=q * 3 + 1, day=1)
            d_to = today
        elif dr == 'last_quarter':
            q = (today.month - 1) // 3
            if q == 0:
                d_from = today.replace(year=today.year - 1, month=10, day=1)
                d_to = today.replace(year=today.year - 1, month=12, day=31)
            else:
                d_from = today.replace(month=(q - 1) * 3 + 1, day=1)
                last_month_of_quarter = q * 3
                if last_month_of_quarter == 12:
                    d_to = today.replace(month=12, day=31)
                else:
                    d_to = today.replace(month=last_month_of_quarter + 1, day=1) - timedelta(days=1)
        elif dr == 'this_year':
            d_from = today.replace(month=1, day=1)
            d_to = today
        elif dr == 'last_year':
            d_from = today.replace(year=today.year - 1, month=1, day=1)
            d_to = today.replace(year=today.year - 1, month=12, day=31)
        elif dr == 'last_365_days':
            d_from, d_to = today - timedelta(days=365), today
        elif dr == 'custom' or (dr and dr.startswith('custom:')):
            if dr and dr.startswith('custom:'):
                parts = dr.split(':')
                d_from = parts[1] if len(parts) > 1 and parts[1] else str(today.replace(month=1, day=1))
                d_to = parts[2] if len(parts) > 2 and parts[2] else str(today)
            else:
                d_from = str(self.filter_date_from) if self.filter_date_from else str(today.replace(month=1, day=1))
                d_to = str(self.filter_date_to) if self.filter_date_to else str(today)
            return [(date_field, '>=', d_from), (date_field, '<=', d_to)]
        else:  # all_time
            return []

        return [(date_field, '>=', str(d_from)), (date_field, '<=', str(d_to))]

    def _compute_value(self):
        """Calcule la valeur du KPI depuis Odoo (source='odoo')."""
        self.ensure_one()
        if not self.model_id:
            return 0.0
        # Pour l'agrégation 'count', le field_id n'est pas obligatoire
        if not self.field_id and self.aggregation != 'count':
            return 0.0

        # Vérification cache
        cache_key = self.id
        if not cache_key:
            return 0.0
        if cache_key in _KPI_CACHE:
            cached_val, cached_ts = _KPI_CACHE[cache_key]
            if (datetime.now() - cached_ts).total_seconds() < _CACHE_TTL:
                return cached_val

        try:
            model_name = self.model_id.model
            field_name = self.field_id.name if self.field_id else None
            domain = []

            if self.filter_domain and self.filter_domain.strip():
                try:
                    domain = safe_eval(self.filter_domain)
                except Exception:
                    try:
                        import json as _json
                        domain = _json.loads(self.filter_domain)
                    except Exception:
                        domain = []

            date_domain = self._get_date_domain()
            domain = domain + date_domain

            model_obj = self.env[model_name].sudo()
            # Count sans field : search_count direct
            if self.aggregation == 'count' and not field_name:
                val = float(model_obj.search_count(domain))
                _KPI_CACHE[cache_key] = (val, datetime.now())
                return val

            records = model_obj.search(domain)
            values = records.mapped(field_name)
            numeric = _mapped_scalar_to_floats(values)

            if not numeric:
                result = 0.0
            elif self.aggregation == 'sum':
                result = sum(numeric)
            elif self.aggregation == 'avg':
                result = sum(numeric) / len(numeric)
            elif self.aggregation == 'count':
                result = len(records)
            elif self.aggregation == 'max':
                result = max(numeric)
            elif self.aggregation == 'min':
                result = min(numeric)
            else:
                result = len(records)

            _KPI_CACHE[cache_key] = (result, datetime.now())
            return result

        except Exception as e:
            _logger.error("Erreur calcul KPI '%s': %s", self.name, e)
            return 0.0


    def _compute_chart_data(self):
        """Calcule les données graphique (JSON) pour bar/line/pie/doughnut."""
        self.ensure_one()
        CHART_TYPES_NEED_DATA = ('bar','hbar','line','area','pie','doughnut','radar',
                                  'polarArea','funnel','flower','mixed')
        if self.chart_type not in CHART_TYPES_NEED_DATA:
            return None
        if not self.model_id:
            return None

        try:
            model_name = self.model_id.model
            model_obj  = self.env[model_name].sudo()
            domain     = []

            if self.filter_domain and self.filter_domain.strip():
                try:
                    domain = safe_eval(self.filter_domain)
                except Exception:
                    try:
                        import json as _json2
                        domain = _json2.loads(self.filter_domain)
                    except Exception:
                        domain = []
            domain += self._get_date_domain()

            # Champ de regroupement selon le modèle
            GROUP_BY_MAP = {
                'sale.order':            'date_order:month',
                'account.move':          'invoice_date:month',
                'crm.lead':              'stage_id',
                'stock.picking':         'picking_type_id',
                'stock.valuation.layer': 'product_id',
                'pos.order':             'date_order:month',
                'purchase.order':        'date_order:month',
                'hr.employee':           'department_id',
                'hr.applicant':          'stage_id',
                'product.product':       'categ_id',
                'stock.quant':           'product_id',
                'sale.order.line':       'product_id',
                'pos.order.line':        'product_id',
                'purchase.order.line':   'product_id',
                'account.move.line':     'account_id',
            }
            group_field = GROUP_BY_MAP.get(model_name)
            if not group_field:
                return None

            # Champ mesure avec agrégation
            field_name = self.field_id.name if self.field_id else None
            agg_map = {'sum': 'sum', 'avg': 'avg', 'max': 'max', 'min': 'min', 'count': None}
            agg_suffix = agg_map.get(self.aggregation, 'sum')

            if field_name and agg_suffix:
                # ex: "amount_total:sum"
                measure_spec  = f"{field_name}:{agg_suffix}"
                measure_key   = field_name  # key in result dict
            else:
                measure_spec  = None
                measure_key   = '__count'

            fields_arg = [measure_spec] if measure_spec else []

            try:
                groups = model_obj.read_group(
                    domain=domain,
                    fields=fields_arg,
                    groupby=[group_field],
                    limit=None,
                )
            except Exception as e_rg:
                _logger.warning("read_group error KPI '%s': %s", self.name, e_rg)
                return None

            if not groups:
                return None

            # Extraire label et valeur de chaque groupe
            result = {}
            group_key_base = group_field.split(':')[0]  # 'date_order' from 'date_order:month'

            for g in groups:
                # ── Label ──────────────────────────────────────────────
                # Odoo retourne la clé complète pour les groupby avec granularité
                # ex: g['date_order:month'] = 'March 2025' OU g['date_order'] = datetime
                label = None
                # Try full key first (date_order:month)
                if group_field in g and g[group_field]:
                    raw = g[group_field]
                    if isinstance(raw, (list, tuple)) and len(raw) == 2:
                        label = str(raw[1])
                    else:
                        label = str(raw)
                # Try base key (date_order)
                elif group_key_base in g and g[group_key_base]:
                    raw = g[group_key_base]
                    if isinstance(raw, (list, tuple)) and len(raw) == 2:
                        label = str(raw[1])
                    elif hasattr(raw, 'strftime'):
                        label = raw.strftime('%b %Y')
                    else:
                        label = str(raw)
                if not label or label == 'False':
                    label = 'Autre'

                # ── Valeur ─────────────────────────────────────────────
                if measure_spec and measure_key in g:
                    val = g.get(measure_key, 0) or 0
                elif measure_spec:
                    # Try the spec key
                    val = g.get(measure_spec, 0) or 0
                else:
                    val = g.get('__count', 0) or 0

                # Éviter les doublons de labels (ex: plusieurs 'Autre')
                if label in result:
                    result[label] += round(float(val), 2)
                else:
                    result[label] = round(float(val), 2)

            if not result:
                return None

            # Trier par valeur décroissante et limiter à 12
            result = dict(sorted(result.items(), key=lambda x: x[1], reverse=True)[:12])
            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            _logger.warning("Erreur chart_data KPI '%s': %s", self.name, e)
        return None


    def _compute_value_from_pipeline(self):
        """Lit la dernière agrégation Spark dans les tables kpi_* (même base PostgreSQL)."""
        self.ensure_one()
        query = _PIPELINE_KPI_SQL.get(self.name)
        if not query:
            return 0.0
        try:
            self.env.cr.execute(query)
            row = self.env.cr.fetchone()
            return float(row[0]) if row and row[0] is not None else 0.0
        except Exception as e:
            _logger.debug(
                "Pipeline SQL indisponible pour KPI '%s': %s", self.name, e
            )
            return 0.0

    def action_refresh(self):
        """Actualise la valeur du KPI depuis Odoo ou tables pipeline kpi_*."""
        for kpi in self:
            src = kpi.source or 'odoo'
            if src in ('manual', 'dax'):
                continue
            _KPI_CACHE.pop(kpi.id, None)
            old_val = kpi.value
            if src == 'kafka' and not kpi.model_id:
                new_val = kpi._compute_value_from_pipeline()
            else:
                new_val = kpi._compute_value()
            chart_data = kpi._compute_chart_data()
            write_vals = {
                'value_previous': old_val,
                'value': new_val,
                'last_update': fields.Datetime.now(),
            }
            if chart_data is not None:
                write_vals['chart_data'] = chart_data
            kpi.sudo().write(write_vals)
            kpi._save_history(new_val)
            if kpi.alert_enabled:
                kpi._check_alert(new_val)
        return True

    def _save_history(self, value):
        """Enregistre une entrée dans l'historique du KPI."""
        self.ensure_one()
        try:
            self.env['bi.kpi.history'].sudo().create({
                'kpi_id': self.id,
                'value': value,
                'recorded_at': fields.Datetime.now(),
            })
            # Nettoyage: garder seulement les 500 dernières entrées
            count = self.env['bi.kpi.history'].sudo().search_count(
                [('kpi_id', '=', self.id)]
            )
            if count > 500:
                to_del = self.env['bi.kpi.history'].sudo().search(
                    [('kpi_id', '=', self.id)],
                    order='recorded_at desc', offset=500
                )
                to_del.unlink()
        except Exception as e:
            _logger.warning("Impossible de sauvegarder l'historique KPI %s: %s", self.name, e)

    def _check_alert(self, value):
        """Vérifie si le seuil d'alerte est dépassé et envoie un email."""
        self.ensure_one()
        if not self.alert_enabled or self.alert_threshold == 0:
            return

        if self.alert_last_sent:
            elapsed_hours = (fields.Datetime.now() - self.alert_last_sent).total_seconds() / 3600
            if elapsed_hours < (self.alert_cooldown_hours or 1):
                return

        condition = self.alert_condition or 'gt'
        triggered = False
        if condition == 'gt'  and value >  self.alert_threshold: triggered = True
        elif condition == 'lt'  and value <  self.alert_threshold: triggered = True
        elif condition == 'gte' and value >= self.alert_threshold: triggered = True
        elif condition == 'lte' and value <= self.alert_threshold: triggered = True
        elif condition == 'eq'  and value == self.alert_threshold: triggered = True

        if triggered:
            self._send_alert_email(value)

    def _send_alert_email(self, value):
        """Envoie l'email d'alerte."""
        self.ensure_one()
        try:
            recipients = self.alert_email or self.env.user.email or ''
            if not recipients:
                _logger.warning("Alerte KPI '%s': aucun destinataire email.", self.name)
                return

            subject = f"🔔 Alerte KPI: {self.name}"
            condition_labels = {
                'gt': 'est supérieur à', 'lt': 'est inférieur à',
                'gte': 'est ≥', 'lte': 'est ≤', 'eq': 'est égal à'
            }
            cond_label = condition_labels.get(self.alert_condition, '')
            body = f"""
<p>Bonjour,</p>
<p>L'alerte KPI a été déclenchée :</p>
<ul>
  <li><strong>KPI :</strong> {self.name}</li>
  <li><strong>Dashboard :</strong> {self.dashboard_id.name}</li>
  <li><strong>Valeur actuelle :</strong> {value:,.2f} {self.unit or ''}</li>
  <li><strong>Condition :</strong> La valeur {cond_label} {self.alert_threshold:,.2f}</li>
  <li><strong>Heure :</strong> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</li>
</ul>
<p>Connectez-vous à Odoo pour consulter votre dashboard BI Realtime.</p>
            """

            mail_vals = {
                'subject': subject,
                'body_html': body,
                'email_to': recipients,
                'email_from': self.env.user.company_id.email or 'noreply@bi-realtime.com',
            }
            mail = self.env['mail.mail'].sudo().create(mail_vals)
            mail.sudo().send()

            self.sudo().write({'alert_last_sent': fields.Datetime.now()})
            _logger.info("Alerte email envoyée pour KPI '%s' → %s", self.name, recipients)
        except Exception as e:
            _logger.error("Erreur envoi alerte email KPI '%s': %s", self.name, e)

    def action_refresh_all(self):
        """Actualise tous les KPIs Odoo d'un coup (action de masse)."""
        odoo_kpis = self.filtered(lambda k: k.source == 'odoo')
        for kpi in odoo_kpis:
            kpi.action_refresh()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Actualisation terminée',
                'message': f'{len(odoo_kpis)} KPI(s) actualisés.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_toggle_bookmark(self):
        """Ajoute/retire le KPI des favoris de l'utilisateur."""
        for kpi in self:
            if self.env.user in kpi.bookmarked_user_ids:
                kpi.bookmarked_user_ids = [(3, self.env.user.id)]
            else:
                kpi.bookmarked_user_ids = [(4, self.env.user.id)]
        return True

    def action_export_csv(self):
        """Exporte les données du KPI en CSV."""
        self.ensure_one()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['KPI', 'Valeur', 'Valeur précédente', 'Variation %',
                         'Objectif', 'Unité', 'Dernière MAJ'])
        writer.writerow([
            self.name,
            self.value,
            self.value_previous,
            f"{self.variation_pct:.2f}",
            self.target_value,
            self.unit or '',
            str(self.last_update or ''),
        ])
        content = output.getvalue().encode('utf-8-sig')
        attachment = self.env['ir.attachment'].sudo().create({
            'name': f'kpi_{self.name.lower().replace(" ", "_")}.csv',
            'type': 'binary',
            'datas': base64.b64encode(content),
            'mimetype': 'text/csv',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def get_kpi_data_for_frontend(self):
        """Retourne les données KPI formatées pour le frontend JS."""
        self.ensure_one()
        chart_data = {}
        if self.chart_data:
            try:
                chart_data = json.loads(self.chart_data)
            except Exception:
                pass
        return {
            'id': self.id,
            'name': self.name,
            'value': self.value,
            'value_previous': self.value_previous,
            'variation_pct': self.variation_pct,
            'trend': self.trend,
            'target_value': self.target_value,
            'target_label': self.target_label,
            'unit': self.unit or '',
            'chart_type': self.chart_type,
            'color': self.color,
            'color2': self.color2,
            'icon': self.icon,
            'widget_size': self.widget_size,
            'sequence': self.sequence,
            'last_update': fields.Datetime.to_string(self.last_update) if self.last_update else None,
            'chart_data': chart_data,
            'alert_enabled': self.alert_enabled,
            'alert_threshold': self.alert_threshold,
            'source': self.source,
        }

    @api.model
    def get_dashboard_kpis(self, dashboard_id, date_filter=None):
        """Endpoint appelé par le frontend pour récupérer tous les KPIs d'un dashboard."""
        kpis = self.sudo().search([
            ('dashboard_id', '=', dashboard_id)
        ], order='sequence, name')
        return [kpi.get_kpi_data_for_frontend() for kpi in kpis]

    @api.model
    def get_kpis_with_comparison(self, dashboard_id=None, date_filter=None):
        """
        Retourne les KPIs avec valeur actuelle ET précédente pour le graphique de comparaison.
        FIX: Méthode déplacée de BiKpiHistory vers BiKpi (classe correcte).
        """
        domain = []
        if dashboard_id:
            domain.append(('dashboard_id', '=', dashboard_id))

        kpis = self.sudo().search(domain, order='sequence, name')
        result = []
        for kpi in kpis:
            if kpi.chart_type not in ('indicator', 'counter', 'bar', 'line', 'area', 'number'):
                continue
            result.append({
                'id': kpi.id,
                'name': kpi.name,
                'value': kpi.value,
                'value_previous': kpi.value_previous,
                'variation_pct': kpi.variation_pct,
                'color': kpi.color or '#6366f1',
                'unit': kpi.unit or '',
                'chart_type': kpi.chart_type,
            })
        return result

    @api.model
    def fix_ai_generated_kpis(self):
        """Corrige les KPIs générés par l'IA avec mauvais modèle/champ/domaine."""
        import json as _json

        KPI_ALIASES = {
            "CA Total": "Chiffre d'affaires total",
            "Nb Commandes": "Nombre de commandes",
            "Valeur Moyenne Commande": "Valeur moyenne commande",
            "Marge Totale": "Marge totale (ventes)",
            "Nombre factures": "Factures émises",
            "Évolution CA mensuel": "Ventes par période",
        }
        KPI_CONFIG = {
            "Chiffre d'affaires total":    {'model': 'sale.order',           'field': 'amount_total',   'agg': 'sum',   'domain': [["state","in",["sale","done"]]]},
            "Nombre de commandes":          {'model': 'sale.order',           'field': None,             'agg': 'count', 'domain': [["state","in",["sale","done"]]]},
            "Valeur moyenne commande":      {'model': 'sale.order',           'field': 'amount_total',   'agg': 'avg',   'domain': [["state","in",["sale","done"]]]},
            "Marge totale (ventes)":        {'model': 'sale.order',           'field': 'margin',         'agg': 'sum',   'domain': [["state","in",["sale","done"]]]},
            "Ventes par période":           {'model': 'sale.order',           'field': 'amount_total',   'agg': 'sum',   'domain': [["state","in",["sale","done"]]]},
            "Top produits vendus":          {'model': 'sale.order.line',      'field': 'price_subtotal', 'agg': 'sum',   'domain': [["order_id.state","in",["sale","done"]]]},
            "Opportunités actives":         {'model': 'crm.lead',             'field': None,             'agg': 'count', 'domain': [["active","=",True],["type","=","opportunity"]]},
            "Pipeline total":               {'model': 'crm.lead',             'field': 'expected_revenue','agg': 'sum',  'domain': [["active","=",True]]},
            "Taux de conversion":           {'model': 'crm.lead',             'field': None,             'agg': 'count', 'domain': [["stage_id.is_won","=",True]]},
            "Opportunités par étape":       {'model': 'crm.lead',             'field': None,             'agg': 'count', 'domain': [["active","=",True]]},
            "Leads par source":             {'model': 'crm.lead',             'field': None,             'agg': 'count', 'domain': []},
            "Transferts en cours":          {'model': 'stock.picking',        'field': None,             'agg': 'count', 'domain': [["state","=","assigned"]]},
            "Valeur du stock":              {'model': 'stock.valuation.layer','field': 'value',          'agg': 'sum',   'domain': []},
            "Produits en rupture":          {'model': 'product.product',      'field': None,             'agg': 'count', 'domain': [["qty_available","<=",0],["active","=",True]]},
            "Mouvements par type":          {'model': 'stock.picking',        'field': None,             'agg': 'count', 'domain': []},
            "Top produits stockés":         {'model': 'product.product',      'field': 'qty_available',  'agg': 'sum',   'domain': [["active","=",True],["qty_available",">",0]]},
            "Factures émises":              {'model': 'account.move',         'field': None,             'agg': 'count', 'domain': [["move_type","=","out_invoice"],["state","=","posted"]]},
            "Chiffre d'affaires facturé":   {'model': 'account.move',         'field': 'amount_total',   'agg': 'sum',   'domain': [["move_type","=","out_invoice"],["state","=","posted"]]},
            "Impayés en cours":             {'model': 'account.move',         'field': 'amount_residual','agg': 'sum',   'domain': [["move_type","=","out_invoice"],["payment_state","=","not_paid"],["state","=","posted"]]},
            "Évolution facturation":        {'model': 'account.move',         'field': 'amount_total',   'agg': 'sum',   'domain': [["move_type","=","out_invoice"],["state","=","posted"]]},
            "Répartition par statut":       {'model': 'account.move',         'field': None,             'agg': 'count', 'domain': [["move_type","=","out_invoice"]]},
            "Ventes du jour":               {'model': 'pos.order',            'field': 'amount_total',   'agg': 'sum',   'domain': [["state","in",["done","paid"]]]},
            "Nombre transactions":          {'model': 'pos.order',            'field': None,             'agg': 'count', 'domain': [["state","in",["done","paid"]]]},
            "Panier moyen":                 {'model': 'pos.order',            'field': 'amount_total',   'agg': 'avg',   'domain': [["state","in",["done","paid"]]]},
            "Ventes par heure":             {'model': 'pos.order',            'field': 'amount_total',   'agg': 'sum',   'domain': [["state","in",["done","paid"]]]},
            "Top produits caisse":          {'model': 'pos.order.line',       'field': 'price_subtotal', 'agg': 'sum',   'domain': []},
            "Commandes fournisseurs":       {'model': 'purchase.order',       'field': None,             'agg': 'count', 'domain': [["state","in",["purchase","done"]]]},
            "Montant total achats":         {'model': 'purchase.order',       'field': 'amount_total',   'agg': 'sum',   'domain': [["state","in",["purchase","done"]]]},
            "Achats par fournisseur":       {'model': 'purchase.order',       'field': 'amount_total',   'agg': 'sum',   'domain': [["state","in",["purchase","done"]]]},
            "Répartition par catégorie":    {'model': 'purchase.order',       'field': 'amount_total',   'agg': 'sum',   'domain': []},
            "Total employés":               {'model': 'hr.employee',          'field': None,             'agg': 'count', 'domain': [["active","=",True]]},
            "Nouveaux recrutements":        {'model': 'hr.applicant',         'field': None,             'agg': 'count', 'domain': [["active","=",True]]},
            "Employés par département":     {'model': 'hr.employee',          'field': None,             'agg': 'count', 'domain': [["active","=",True]]},
        }

        fixed = 0
        errors = []
        all_kpis = self.env['bi.kpi'].sudo().search([])

        for kpi in all_kpis:
            config = KPI_CONFIG.get(kpi.name) or KPI_CONFIG.get(KPI_ALIASES.get(kpi.name))
            if not config:
                continue
            try:
                vals = {
                    'aggregation':  config['agg'],
                    'filter_domain': _json.dumps(config['domain']),
                    'source':       'odoo',
                }

                # Fix model_id
                model_rec = self.env['ir.model'].sudo().search(
                    [('model', '=', config['model'])], limit=1
                )
                if model_rec:
                    vals['model_id'] = model_rec.id
                else:
                    _logger.warning("fix_kpis: model '%s' not found", config['model'])
                    continue

                # Fix field_id (marge : repli amount_untaxed si module sale_margin absent)
                if config['field']:
                    Field = self.env['ir.model.fields'].sudo()
                    field_rec = Field.search([
                        ('model_id', '=', model_rec.id),
                        ('name', '=', config['field']),
                    ], limit=1)
                    if not field_rec and config['field'] == 'margin':
                        field_rec = Field.search([
                            ('model_id', '=', model_rec.id),
                            ('name', '=', 'amount_untaxed'),
                        ], limit=1)
                    vals['field_id'] = field_rec.id if field_rec else False
                else:
                    vals['field_id'] = False

                kpi.sudo().write(vals)
                fixed += 1

            except Exception as e:
                errors.append(f"{kpi.name}: {e}")
                _logger.error("fix_kpis error on '%s': %s", kpi.name, e)

        # Refresh only successfully fixed KPIs
        if fixed:
            try:
                refreshable = self.env['bi.kpi'].sudo().search([
                    ('source', '=', 'odoo'), ('model_id', '!=', False)
                ])
                for kpi in refreshable:
                    try:
                        kpi.action_refresh()
                    except Exception as e:
                        _logger.warning("Refresh error on '%s': %s", kpi.name, e)
            except Exception as e:
                _logger.error("Batch refresh error: %s", e)

        return {'fixed': fixed, 'errors': errors}


    @api.model
    def batch_refresh_by_dashboard(self, dashboard_id):
        """
        Actualise tous les KPIs Odoo d'un dashboard en une seule opération.
        FIX: Méthode déplacée de BiKpiHistory vers BiKpi (classe correcte).
        """
        if not dashboard_id:
            return False
        kpis = self.sudo().search([('dashboard_id', '=', dashboard_id)])
        for kpi in kpis:
            try:
                kpi.action_refresh()
            except Exception as e:
                _logger.error("Erreur refresh KPI '%s': %s", kpi.name, e)
        return True

    def action_get_drill_data(self, label=None):
        """
        Retourne les données détaillées pour le drill-down d'un KPI.
        FIX: Méthode déplacée de BiKpiHistory vers BiKpi (classe correcte).
        """
        self.ensure_one()
        if not self.drill_field_id or not self.model_id:
            return {'labels': [], 'values': [], 'colors': []}

        try:
            model_name = self.model_id.model
            drill_field = self.drill_field_id.name

            domain = []
            if self.filter_domain and self.filter_domain.strip():
                try:
                    domain = safe_eval(self.filter_domain)
                except Exception:
                    try:
                        import json as _json
                        domain = _json.loads(self.filter_domain)
                    except Exception:
                        domain = []
            domain += self._get_date_domain()

            records = self.env[model_name].sudo().search(domain, limit=20)
            groups = {}
            for rec in records:
                key = str(getattr(rec, drill_field, 'N/A') or 'N/A')
                if hasattr(getattr(rec, drill_field, None), 'name'):
                    key = getattr(rec, drill_field).name or 'N/A'
                groups[key] = groups.get(key, 0) + 1

            sorted_groups = sorted(groups.items(), key=lambda x: x[1], reverse=True)[:10]
            labels = [g[0] for g in sorted_groups]
            values = [g[1] for g in sorted_groups]

            colors = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
                      '#06b6d4', '#ec4899', '#f97316', '#14b8a6', '#84cc16']

            return {
                'labels': labels,
                'values': values,
                'colors': colors[:len(labels)],
                'title': f"{self.name} — {self.drill_field_id.field_description}",
            }
        except Exception as e:
            _logger.error("Erreur drill data KPI '%s': %s", self.name, e)
            return {'labels': [], 'values': [], 'colors': [], 'error': str(e)}


class BiKpiHistory(models.Model):
    """Historique des valeurs KPI."""
    _name = 'bi.kpi.history'
    _description = 'Historique KPI'
    _order = 'recorded_at desc'
    _rec_name = 'kpi_id'

    kpi_id = fields.Many2one('bi.kpi', string='KPI', required=True, ondelete='cascade')
    value = fields.Float(string='Valeur', required=True)
    recorded_at = fields.Datetime(string='Enregistré le', required=True,
                                   default=fields.Datetime.now)
    source = fields.Char(string='Source', default='system')




