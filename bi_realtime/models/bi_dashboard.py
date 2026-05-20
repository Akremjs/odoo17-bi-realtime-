



# -*- coding: utf-8 -*-
"""
bi_dashboard.py — Modèle Dashboard BI v6
CORRECTIONS:
  - Double déclaration group_ids/access_group_ids sur la même table → access_group_ids supprimé
    (conflit SQL: deux M2M pointant vers res.groups sans relation distincte causait une erreur)
  - _inherit = [] retiré (inutile)
"""
from odoo import models, fields, api
from odoo.exceptions import UserError
import json
import base64
import logging

_logger = logging.getLogger(__name__)


class BiDashboard(models.Model):
    _name = 'bi.dashboard'
    _description = 'Dashboard BI'

    name = fields.Char(string='Nom', required=True)
    description = fields.Text(string='Description')
    color_theme = fields.Selection([
        ('light',     'Clair'),
        ('dark',      'Sombre'),
        ('corporate', 'Corporate'),
        ('ocean',     'Océan'),
        ('sunset',    'Coucher de soleil'),
        ('forest',    'Forêt'),
    ], default='light', string='Thème')
    rtl_mode = fields.Boolean(string='Mode RTL', default=False)
    layout_data = fields.Text(string='Disposition (JSON)', default='{}')
    refresh_interval = fields.Integer(string='Intervalle rafraîchissement (s)', default=30)

    kpi_ids = fields.One2many('bi.kpi', 'dashboard_id', string='KPIs')
    kpi_count = fields.Integer(string='Nb KPIs', compute='_compute_kpi_count', store=True)

    # Favoris
    bookmarked_user_ids = fields.Many2many(
        'res.users', 'bi_dashboard_bookmark_rel', string='Favoris'
    )

    # FIX: Une seule relation M2M vers res.groups pour éviter conflit de table SQL
    # access_group_ids supprimé car doublon avec group_ids (même modèle cible)
    group_ids = fields.Many2many(
        'res.groups',
        relation='bi_dashboard_group_rel',
        string='Groupes autorisés'
    )

    @api.depends('kpi_ids')
    def _compute_kpi_count(self):
        for dash in self:
            dash.kpi_count = len(dash.kpi_ids)

    def action_export_json(self):
        """Exporte le dashboard en JSON (téléchargement fichier)."""
        self.ensure_one()
        export_data = {
            'name': self.name,
            'description': self.description or '',
            'color_theme': self.color_theme,
            'rtl_mode': self.rtl_mode,
            'refresh_interval': self.refresh_interval,
            'layout_data': json.loads(self.layout_data) if self.layout_data else {},
            'kpis': [
                {
                    'name': kpi.name,
                    'chart_type': kpi.chart_type,
                    'aggregation': kpi.aggregation,
                    'value': kpi.value,
                    'target_value': kpi.target_value,
                    'unit': kpi.unit or '',
                    'color': kpi.color,
                    'color2': kpi.color2,
                    'widget_size': kpi.widget_size,
                    'sequence': kpi.sequence,
                    'source': kpi.source,
                    'alert_enabled': kpi.alert_enabled,
                    'alert_threshold': kpi.alert_threshold,
                    'alert_condition': kpi.alert_condition,
                    'filter_date_range': kpi.filter_date_range,
                }
                for kpi in self.kpi_ids.sorted('sequence')
            ],
            'exported_at': fields.Datetime.to_string(fields.Datetime.now()),
            'version': '6.0.0',
        }
        content = json.dumps(export_data, ensure_ascii=False, indent=2).encode('utf-8')
        attachment = self.env['ir.attachment'].sudo().create({
            'name': f'dashboard_{self.name.lower().replace(" ", "_")}.json',
            'type': 'binary',
            'datas': base64.b64encode(content),
            'mimetype': 'application/json',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    @api.model
    def action_import_json(self, json_content):
        """Importe un dashboard depuis JSON."""
        try:
            data = json.loads(json_content)
        except json.JSONDecodeError as e:
            raise UserError(f"JSON invalide : {str(e)}")

        dashboard = self.create({
            'name': data.get('name', 'Dashboard importé'),
            'description': data.get('description', ''),
            'color_theme': data.get('color_theme', 'light'),
            'rtl_mode': data.get('rtl_mode', False),
            'refresh_interval': data.get('refresh_interval', 30),
            'layout_data': json.dumps(data.get('layout_data', {})),
        })

        for i, kpi_data in enumerate(data.get('kpis', [])):
            self.env['bi.kpi'].create({
                'dashboard_id': dashboard.id,
                'name': kpi_data.get('name', f'KPI {i+1}'),
                'chart_type': kpi_data.get('chart_type', 'indicator'),
                'unit': kpi_data.get('unit', ''),
                'color': kpi_data.get('color', '#007bff'),
                'color2': kpi_data.get('color2', '#6c757d'),
                'widget_size': kpi_data.get('widget_size', 'medium'),
                'sequence': kpi_data.get('sequence', (i + 1) * 10),
                'source': kpi_data.get('source', 'odoo'),
                'target_value': kpi_data.get('target_value', 0),
                'alert_enabled': kpi_data.get('alert_enabled', False),
                'alert_threshold': kpi_data.get('alert_threshold', 0),
                'alert_condition': kpi_data.get('alert_condition', 'gt'),
                'filter_date_range': kpi_data.get('filter_date_range', 'this_month'),
            })

        return dashboard

    def action_toggle_bookmark(self):
        """Toggle favori pour l'utilisateur courant."""
        uid = self.env.uid
        for dash in self:
            if uid in dash.bookmarked_user_ids.ids:
                dash.bookmarked_user_ids = [(3, uid)]
            else:
                dash.bookmarked_user_ids = [(4, uid)]
        return True

    def _predefined_resolve_field(self, model_rec, field_names):
        IrField = self.env['ir.model.fields'].sudo()
        for fname in field_names:
            if not fname:
                continue
            rec = IrField.search(
                [('model_id', '=', model_rec.id), ('name', '=', fname)],
                limit=1,
            )
            if rec:
                return rec
        return False

    @api.model
    def _predefined_kpi_create_vals(self, dashboard_id, spec):
        """Valeurs pour bi.kpi : calcul Odoo (plus de KPI « kafka » sans modèle = toujours 0)."""
        IrModel = self.env['ir.model'].sudo()
        model_rec = IrModel.search([('model', '=', spec['model'])], limit=1)
        if not model_rec:
            _logger.warning(
                "Dashboard prédéfini: modèle %s absent (module non installé ?) — KPI « %s » sans données",
                spec['model'],
                spec['name'],
            )
            return {
                'dashboard_id': dashboard_id,
                'name': spec['name'],
                'chart_type': spec.get('chart_type', 'indicator'),
                'color': spec.get('color', '#6366f1'),
                'unit': spec.get('unit', ''),
                'source': 'odoo',
                'sequence': spec.get('sequence', 10),
                'target_value': spec.get('target_value', 0),
                'widget_size': 'medium',
            }

        if spec.get('fields'):
            field_names = list(spec['fields'])
        elif spec.get('field'):
            field_names = [spec['field']]
        else:
            field_names = []

        field_rec = self._predefined_resolve_field(model_rec, field_names)
        agg = spec.get('aggregation', 'sum')
        if agg != 'count' and not field_rec:
            _logger.warning(
                "Dashboard prédéfini: aucun champ valide pour « %s » sur %s",
                spec['name'],
                spec['model'],
            )

        domain = spec.get('domain') or []
        return {
            'dashboard_id': dashboard_id,
            'name': spec['name'],
            'chart_type': spec.get('chart_type', 'indicator'),
            'color': spec.get('color', '#6366f1'),
            'unit': spec.get('unit', ''),
            'source': 'odoo',
            'sequence': spec.get('sequence', 10),
            'target_value': spec.get('target_value', 0),
            'widget_size': 'medium',
            'model_id': model_rec.id,
            'field_id': field_rec.id if field_rec else False,
            'aggregation': agg,
            'filter_domain': json.dumps(domain) if domain else '[]',
            'filter_date_field': spec.get('date_field', 'create_date'),
            'filter_date_range': spec.get('date_range', 'this_month'),
        }

    @api.model
    def action_create_predefined_dashboards(self):
        """Crée 5 dashboards prédéfinis dont les KPI sont calculés depuis Odoo."""
        created = []
        new_dashboard_ids = []
        sale_done_domain = [('state', 'in', ['sale', 'done'])]
        predefined = [
            {
                'name': '📊 Ventes & Revenus',
                'color_theme': 'corporate',
                'kpis': [
                    {'name': "Chiffre d'affaires total", 'chart_type': 'indicator', 'color': '#6366f1', 'unit': '€', 'sequence': 10,
                     'model': 'sale.order', 'field': 'amount_total', 'aggregation': 'sum',
                     'domain': sale_done_domain, 'date_field': 'date_order'},
                    {'name': 'Nombre de commandes', 'chart_type': 'counter', 'color': '#10b981', 'unit': '', 'sequence': 20,
                     'model': 'sale.order', 'aggregation': 'count',
                     'domain': sale_done_domain, 'date_field': 'date_order'},
                    {'name': 'Valeur moyenne commande', 'chart_type': 'gauge', 'color': '#f59e0b', 'unit': '€', 'sequence': 30,
                     'model': 'sale.order', 'field': 'amount_total', 'aggregation': 'avg',
                     'domain': sale_done_domain, 'date_field': 'date_order'},
                    {'name': 'Marge totale (ventes)', 'chart_type': 'indicator', 'color': '#ef4444', 'unit': '€', 'sequence': 40,
                     'model': 'sale.order', 'fields': ['margin', 'amount_untaxed'], 'aggregation': 'sum',
                     'domain': sale_done_domain, 'date_field': 'date_order'},
                ]
            },
            {
                'name': '💳 Facturation & Trésorerie',
                'color_theme': 'ocean',
                'kpis': [
                    {'name': "Chiffre d'affaires facturé", 'chart_type': 'indicator', 'color': '#3b82f6', 'unit': '€', 'sequence': 10,
                     'model': 'account.move', 'field': 'amount_total', 'aggregation': 'sum',
                     'domain': [('move_type', '=', 'out_invoice'), ('state', '=', 'posted')], 'date_field': 'invoice_date'},
                    {'name': 'Impayés en cours', 'chart_type': 'indicator', 'color': '#ef4444', 'unit': '€', 'sequence': 20,
                     'model': 'account.move', 'field': 'amount_residual', 'aggregation': 'sum',
                     'domain': [('move_type', '=', 'out_invoice'), ('payment_state', '=', 'not_paid'), ('state', '=', 'posted')],
                     'date_field': 'invoice_date'},
                    {'name': 'Factures émises', 'chart_type': 'counter', 'color': '#8b5cf6', 'unit': '', 'sequence': 30,
                     'model': 'account.move', 'aggregation': 'count',
                     'domain': [('move_type', '=', 'out_invoice'), ('state', '=', 'posted')], 'date_field': 'invoice_date'},
                ]
            },
            {
                'name': '🎯 CRM & Pipeline',
                'color_theme': 'forest',
                'kpis': [
                    {'name': 'Opportunités actives', 'chart_type': 'counter', 'color': '#10b981', 'unit': '', 'sequence': 10,
                     'model': 'crm.lead', 'aggregation': 'count',
                     'domain': [('active', '=', True), ('type', '=', 'opportunity')], 'date_field': 'create_date'},
                    {'name': 'Pipeline total', 'chart_type': 'indicator', 'color': '#6366f1', 'unit': '€', 'sequence': 20,
                     'model': 'crm.lead', 'field': 'expected_revenue', 'aggregation': 'sum',
                     'domain': [('active', '=', True)], 'date_field': 'create_date'},
                    {'name': 'Probabilité moyenne', 'chart_type': 'gauge', 'color': '#f59e0b', 'unit': '%', 'sequence': 30,
                     'model': 'crm.lead', 'field': 'probability', 'aggregation': 'avg',
                     'domain': [('active', '=', True), ('type', '=', 'opportunity')], 'date_field': 'create_date',
                     'target_value': 70},
                ]
            },
            {
                'name': '📦 Stock & Logistique',
                'color_theme': 'light',
                'kpis': [
                    {'name': 'Transferts en cours', 'chart_type': 'counter', 'color': '#f97316', 'unit': '', 'sequence': 10,
                     'model': 'stock.picking', 'aggregation': 'count',
                     'domain': [('state', '=', 'assigned')], 'date_field': 'create_date'},
                    {'name': 'Réceptions en attente', 'chart_type': 'counter', 'color': '#0ea5e9', 'unit': '', 'sequence': 20,
                     'model': 'stock.picking', 'aggregation': 'count',
                     'domain': [
                         ('picking_type_id.code', '=', 'incoming'),
                         ('state', 'in', ['assigned', 'waiting', 'confirmed']),
                     ], 'date_field': 'create_date'},
                    {'name': 'Valeur du stock', 'chart_type': 'indicator', 'color': '#6366f1', 'unit': '€', 'sequence': 30,
                     'model': 'stock.valuation.layer', 'field': 'value', 'aggregation': 'sum',
                     'domain': [], 'date_field': 'create_date'},
                ]
            },
            {
                'name': '🛒 Point de Vente',
                'color_theme': 'sunset',
                'kpis': [
                    {'name': 'Ventes du jour', 'chart_type': 'indicator', 'color': '#ec4899', 'unit': '€', 'sequence': 10,
                     'model': 'pos.order', 'field': 'amount_total', 'aggregation': 'sum',
                     'domain': [('state', 'in', ['done', 'paid'])], 'date_field': 'date_order', 'date_range': 'today'},
                    {'name': 'Nombre transactions', 'chart_type': 'counter', 'color': '#14b8a6', 'unit': '', 'sequence': 20,
                     'model': 'pos.order', 'aggregation': 'count',
                     'domain': [('state', 'in', ['done', 'paid'])], 'date_field': 'date_order', 'date_range': 'today'},
                    {'name': 'Panier moyen', 'chart_type': 'indicator', 'color': '#a855f7', 'unit': '€', 'sequence': 30,
                     'model': 'pos.order', 'field': 'amount_total', 'aggregation': 'avg',
                     'domain': [('state', 'in', ['done', 'paid'])], 'date_field': 'date_order', 'date_range': 'today'},
                ]
            },
        ]

        for dash_config in predefined:
            existing = self.search([('name', '=', dash_config['name'])], limit=1)
            if existing:
                created.append(existing.id)
                continue

            dashboard = self.create({
                'name': dash_config['name'],
                'color_theme': dash_config.get('color_theme', 'light'),
                'refresh_interval': 30,
            })
            created.append(dashboard.id)
            new_dashboard_ids.append(dashboard.id)

            for kpi_spec in dash_config.get('kpis', []):
                vals = self._predefined_kpi_create_vals(dashboard.id, kpi_spec)
                self.env['bi.kpi'].create(vals)

        Kpi = self.env['bi.kpi']
        for did in new_dashboard_ids:
            try:
                Kpi.batch_refresh_by_dashboard(did)
            except Exception as e:
                _logger.warning("Refresh KPI dashboard id=%s: %s", did, e)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Dashboards créés',
                'message': f'{len(created)} dashboards prédéfinis disponibles.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_deduplicate_kpis(self):
        """Supprime les KPI redondants : même calcul Odoo ou même libellé (insensible à la casse)."""
        total_removed = 0
        for dash in self:
            kpis = dash.kpi_ids.sorted(lambda k: (k.sequence, k.id))
            to_unlink = self.env['bi.kpi']
            seen_calc = {}
            for kpi in kpis:
                if not kpi.model_id:
                    continue
                sig = (
                    kpi.model_id.id,
                    kpi.field_id.id if kpi.field_id else 0,
                    kpi.aggregation or '',
                    (kpi.filter_domain or '').strip(),
                    kpi.filter_date_field or '',
                    kpi.filter_date_range or '',
                )
                if sig in seen_calc:
                    to_unlink |= kpi
                else:
                    seen_calc[sig] = kpi
            remaining = kpis - to_unlink
            seen_name = {}
            for kpi in remaining:
                nm = (kpi.name or '').strip().lower()
                if nm in seen_name:
                    to_unlink |= kpi
                else:
                    seen_name[nm] = kpi
            if to_unlink:
                total_removed += len(to_unlink)
                to_unlink.unlink()
        msg = (
            f'{total_removed} KPI en double supprimé(s).'
            if total_removed
            else 'Aucun doublon trouvé sur ce(s) dashboard(s).'
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Nettoyage KPI',
                'message': msg,
                'type': 'success' if total_removed else 'info',
                'sticky': False,
            },
        }

    @api.model
    def get_dashboard_stats(self, dashboard_id):
        """Retourne des statistiques sur un dashboard pour le frontend."""
        dash = self.sudo().browse(dashboard_id)
        if not dash.exists():
            return {}
        kpis = dash.kpi_ids
        return {
            'id': dash.id,
            'name': dash.name,
            'kpi_count': len(kpis),
            'kafka_kpis': len(kpis.filtered(lambda k: k.source == 'kafka')),
            'odoo_kpis': len(kpis.filtered(lambda k: k.source == 'odoo')),
            'alerts_active': len(kpis.filtered(lambda k: k.alert_enabled)),
            'last_update': max(
                (fields.Datetime.to_string(k.last_update) for k in kpis if k.last_update),
                default=None
            ),
        }

    @api.model
    def _collect_system_context(self):
        """Collecte automatiquement toutes les infos du système Odoo."""
        ctx = {}
        try:
            # Modules installés
            modules = self.env['ir.module.module'].sudo().search([('state','=','installed')], order='name')
            ctx['modules_installes'] = [m.name for m in modules]
            ctx['nb_modules'] = len(modules)

            # Nouveaux modules (30 derniers jours)
            from datetime import datetime, timedelta
            date_limit = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            new_mods = self.env['ir.module.module'].sudo().search([
                ('state','=','installed'), ('write_date','>=',date_limit)
            ])
            ctx['nouveaux_modules'] = [m.name for m in new_mods]

            # KPIs
            kpis = self.env['bi.kpi'].sudo().search([], order='last_update desc')
            ctx['kpis'] = [{'nom': k.name, 'valeur': k.value} for k in kpis]
            ctx['nb_kpis'] = len(kpis)

            # Dashboards
            dashboards = self.env['bi.dashboard'].sudo().search([])
            ctx['dashboards'] = [d.name for d in dashboards]
            ctx['nb_dashboards'] = len(dashboards)

            # Utilisateurs
            users = self.env['res.users'].sudo().search([('active','=',True),('share','=',False),('groups_id','!=',False)])
            ctx['utilisateurs'] = {'nb_total': len(users), 'noms': [u.name for u in users[:10]]}

            # Ventes
            try:
                orders = self.env['sale.order'].sudo().search([('state','in',['sale','done'])])
                ctx['ventes'] = {
                    'nb_commandes': len(orders),
                    'ca_total': sum(o.amount_total for o in orders),
                    'panier_moyen': sum(o.amount_total for o in orders)/len(orders) if orders else 0
                }
            except Exception:
                ctx['ventes'] = {}

            # Factures
            try:
                invoices = self.env['account.move'].sudo().search([('move_type','=','out_invoice'),('state','=','posted')])
                unpaid = invoices.filtered(lambda i: i.payment_state != 'paid')
                ctx['factures'] = {'nb_total': len(invoices), 'nb_impayes': len(unpaid), 'montant_impaye': sum(i.amount_residual for i in unpaid)}
            except Exception:
                ctx['factures'] = {}

            # CRM
            try:
                leads = self.env['crm.lead'].sudo().search([('active','=',True)])
                ctx['crm'] = {'nb_leads': len(leads), 'pipeline_total': sum(l.expected_revenue for l in leads)}
            except Exception:
                ctx['crm'] = {}

            # Stock
            try:
                products = self.env['product.product'].sudo().search([('type','=','product')])
                ctx['stock'] = {'nb_produits': len(products), 'nb_ruptures': len(products.filtered(lambda p: p.qty_available <= 0))}
            except Exception:
                ctx['stock'] = {}

            # POS
            try:
                pos = self.env['pos.order'].sudo().search([('state','=','done')])
                ctx['pos'] = {'nb_transactions': len(pos), 'ventes_total': sum(o.amount_total for o in pos)}
            except Exception:
                ctx['pos'] = {}

            # Alertes
            try:
                alerts = self.env['bi.alert.rule'].sudo().search([('active','=',True)])
                ctx['alertes'] = {'nb_actives': len(alerts), 'noms': [a.name for a in alerts[:5]]}
            except Exception:
                ctx['alertes'] = {}

            ctx['odoo_version'] = 'Odoo 17'
        except Exception as e:
            ctx['erreur'] = str(e)
        return ctx

    def action_ai_chat(self, text, system_prompt=None, history=None):
        """Chatbot IA integre au dashboard avec contexte complet."""
        if isinstance(text, list):
            text = text[0] if text else ""
        try:
            import requests as req, json as js
            ai_url = self.env['ir.config_parameter'].sudo().get_param('bi_realtime.ai_api_url', default='')
            ai_token = self.env['ir.config_parameter'].sudo().get_param('bi_realtime.ai_api_token', default='')
            if ai_url:
                ctx = self._collect_system_context()
                full_system = f"""Tu es un assistant BI expert integre dans Odoo. Tu connais TOUT le systeme.
=== SYSTEME ===
Version: {ctx.get('odoo_version','Odoo 17')}
Modules installes ({ctx.get('nb_modules',0)}): {', '.join(ctx.get('modules_installes',[])[:40])}
Nouveaux modules (30j): {', '.join(ctx.get('nouveaux_modules',[])) or 'Aucun'}
Dashboards ({ctx.get('nb_dashboards',0)}): {', '.join(ctx.get('dashboards',[]))}
Utilisateurs actifs: {ctx.get('utilisateurs',{}).get('nb_total',0)} — {', '.join(ctx.get('utilisateurs',{}).get('noms',[]))}
=== KPIs ({ctx.get('nb_kpis',0)}) ===
{js.dumps(ctx.get('kpis',[]), ensure_ascii=False)}
=== VENTES === {js.dumps(ctx.get('ventes',{}), ensure_ascii=False)}
=== FACTURES === {js.dumps(ctx.get('factures',{}), ensure_ascii=False)}
=== CRM === {js.dumps(ctx.get('crm',{}), ensure_ascii=False)}
=== STOCK === {js.dumps(ctx.get('stock',{}), ensure_ascii=False)}
=== POS === {js.dumps(ctx.get('pos',{}), ensure_ascii=False)}
=== ALERTES === {js.dumps(ctx.get('alertes',{}), ensure_ascii=False)}
Reponds en francais, precisement avec les donnees ci-dessus."""
                payload = {'message': text, 'system_prompt': full_system, 'history': history or []}
                headers = {'Authorization': f'Bearer {ai_token}'} if ai_token else {}
                resp = req.post(f"{ai_url}/chat", json=payload, headers=headers, timeout=30)
                if resp.status_code == 200:
                    return {'response': resp.json().get('response', ''), 'context': ctx}
        except Exception as e:
            return {'response': f'Erreur: {str(e)}'}
        text_lower = text.lower()
        response = self._generate_kpi_response(text_lower)
        return {'response': response}
    def _generate_kpi_response(self, text):
        """Génère une réponse contextuelle basée sur les KPIs disponibles."""
        kpis = self.env['bi.kpi'].sudo().search([], limit=20, order='last_update desc')

        if any(w in text for w in ['vente', 'ca', 'chiffre', 'revenu', 'commande']):
            sales_kpis = kpis.filtered(lambda k: any(w in k.name.lower() for w in ['ca', 'vente', 'revenu', 'commande']))
            if sales_kpis:
                kpi = sales_kpis[0]
                return (f"📊 **{kpi.name}** : **{kpi.value:,.2f} {kpi.unit or ''}**\n"
                        f"Variation : {'+' if kpi.variation_pct >= 0 else ''}{kpi.variation_pct:.1f}% "
                        f"{'↑' if kpi.trend == 'up' else '↓'} par rapport à la période précédente.")

        if any(w in text for w in ['factur', 'impayé', 'invoice', 'paiement']):
            inv_kpis = kpis.filtered(lambda k: any(w in k.name.lower() for w in ['factur', 'impayé', 'paiement']))
            if inv_kpis:
                kpi = inv_kpis[0]
                return f"💳 **{kpi.name}** : **{kpi.value:,.2f} {kpi.unit or ''}**"

        if any(w in text for w in ['stock', 'transfert', 'produit', 'inventaire']):
            stock_kpis = kpis.filtered(lambda k: any(w in k.name.lower() for w in ['stock', 'transfert', 'produit']))
            if stock_kpis:
                kpi = stock_kpis[0]
                return f"📦 **{kpi.name}** : **{kpi.value:,.0f}**"

        if any(w in text for w in ['crm', 'opportunité', 'pipeline', 'lead']):
            crm_kpis = kpis.filtered(lambda k: any(w in k.name.lower() for w in ['opportunit', 'pipeline', 'crm']))
            if crm_kpis:
                kpi = crm_kpis[0]
                return f"🎯 **{kpi.name}** : **{kpi.value:,.2f} {kpi.unit or ''}**"

        if any(w in text for w in ['bonjour', 'salut', 'hello', 'aide', 'help']):
            return ("👋 Bonjour ! Je suis votre assistant BI.\n\n"
                    "Je peux vous informer sur :\n"
                    "- 💰 Ventes & CA\n- 💳 Facturation\n- 🎯 CRM\n- 📦 Stock\n- 🛒 POS\n\n"
                    "Posez-moi une question !")

        if kpis:
            top = kpis[:3]
            lines = ["📊 **Résumé des derniers KPIs mis à jour :**\n"]
            for k in top:
                trend = "↑" if k.trend == 'up' else "↓"
                lines.append(f"• **{k.name}** : {k.value:,.2f} {k.unit or ''} {trend}")
            return "\n".join(lines)

        return "Je n'ai pas trouvé de données KPI correspondantes. Vérifiez que vos dashboards sont configurés."




