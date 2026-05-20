



# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
import re

_logger = logging.getLogger(__name__)


class BiDaxMeasure(models.Model):
    _name = 'bi.dax.measure'
    _description = 'Mesure DAX personnalisée'
    _order = 'sequence, name'

    name = fields.Char(string='Nom de la mesure', required=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(default=10)
    formula = fields.Text(string='Formule DAX', required=True,
        help='Syntaxe DAX. Ex: CALCULATE(SUM(sale.order[amount_total]), sale.order[state]="sale")')
    result_value = fields.Float(string='Valeur calculée', readonly=True)
    result_preview = fields.Char(string='Aperçu résultat', readonly=True)
    last_computed = fields.Datetime(string='Dernier calcul', readonly=True)
    formula_error = fields.Char(string='Erreur formule', readonly=True)
    formula_valid = fields.Boolean(string='Formule valide', readonly=True, default=False)
    format_type = fields.Selection([
        ('number', '123 (Nombre)'), ('decimal', '123.45 (Décimal)'),
        ('percent', '12.3% (Pourcentage)'), ('currency', '1 234 € (Monnaie)'),
        ('integer', '123 (Entier)'),
    ], default='number', string='Format')
    decimal_places = fields.Integer(string='Décimales', default=2)
    unit = fields.Char(string='Unité')
    currency_symbol = fields.Char(string='Symbole', default='€')
    # FIX: default_date_filter field referenced in view - added here
    default_date_filter = fields.Selection([
        ('this_month', 'Ce mois'), ('this_year', 'Cette année'),
        ('last_30_days', '30 derniers jours'), ('all_time', 'Tout'),
    ], default='this_month', string='Filtre date par défaut')
    # FIX: variables field referenced in view - added here
    variables = fields.Text(string='Variables JSON', help='Ex: {"objectif": 50000}')
    dashboard_id = fields.Many2one('bi.dashboard', string='Dashboard cible', required=True)
    chart_type = fields.Selection([
        ('indicator', '🔢 Indicateur'), ('counter', '🧮 Compteur'),
        ('radial', '⭕ Gauge'), ('bar', '📊 Barres'), ('line', '📈 Courbe'),
        ('bullet', '🎯 Bullet'), ('pie', '🥧 Camembert'), ('doughnut', '🍩 Donut'),
    ], default='indicator', string='Type de graphique')
    color = fields.Char(string='Couleur', default='#6366f1')
    widget_size = fields.Selection([
        ('small', 'Petit'), ('medium', 'Moyen'), ('large', 'Grand'),
    ], default='medium')
    target_value = fields.Float(string='Objectif')
    kpi_id = fields.Many2one('bi.kpi', string='KPI lié',
        domain="[('dashboard_id','=',dashboard_id)]",
        help='KPI mis à jour automatiquement après calcul')

    def action_compute(self):
        for measure in self:
            try:
                result = measure._eval_dax_formula(measure.formula)
                measure.write({
                    'result_value': float(result),
                    'result_preview': measure._format_result(result),
                    'last_computed': fields.Datetime.now(),
                    'formula_error': False, 'formula_valid': True,
                })
                if measure.kpi_id:
                    old_val = measure.kpi_id.value
                    measure.kpi_id.sudo().write({
                        'value_previous': old_val, 'value': float(result),
                        'last_update': fields.Datetime.now(), 'source': 'dax',
                    })
            except Exception as e:
                measure.write({'formula_error': str(e)[:255], 'formula_valid': False})
        return True

    def _eval_dax_formula(self, formula: str) -> float:
        formula = formula.strip()
        m = re.match(r'CALCULATE\(\s*(\w+)\s*\(\s*([\w.]+)\[([\w]+)\]\s*\)(.*)\)',
                     formula, re.IGNORECASE)
        if m:
            return self._calculate_with_filters(m.group(1), m.group(2), m.group(3), m.group(4))
        m = re.match(r'(\w+)\s*\(\s*([\w.]+)\[([\w]+)\]\s*\)', formula, re.IGNORECASE)
        if m:
            return self._simple_aggregate(m.group(1), m.group(2), m.group(3))
        raise UserError(f"Syntaxe DAX non reconnue: {formula}")

    def _calculate_with_filters(self, func, model_name, field_name, filters_str):
        domain = self._parse_dax_filters(filters_str.strip().lstrip(',').strip())
        return self._simple_aggregate(func, model_name, field_name, domain)

    def _parse_dax_filters(self, filters_str):
        domain = []
        if not filters_str:
            return domain
        for m in re.finditer(r'([\w.]+)\[(\w+)\]\s*=\s*"([^"]+)"', filters_str):
            domain.append((m.group(2), '=', m.group(3)))
        return domain

    def _simple_aggregate(self, func, model_name, field_name, domain=None):
        try:
            records = self.env[model_name].sudo().search(domain or [])
            values = [v for v in records.mapped(field_name) if isinstance(v, (int, float))]
            func = func.upper()
            if func == 'SUM':   return sum(values)
            if func == 'AVG':   return sum(values) / len(values) if values else 0
            if func == 'COUNT': return len(records)
            if func == 'MAX':   return max(values) if values else 0
            if func == 'MIN':   return min(values) if values else 0
            raise UserError(f"Fonction DAX inconnue: {func}")
        except KeyError:
            raise UserError(f"Modèle non trouvé: {model_name}")

    def _format_result(self, value: float) -> str:
        fmt, dp = self.format_type, self.decimal_places or 2
        if fmt == 'percent':  return f"{value:.{dp}f}%"
        if fmt == 'currency': return f"{value:,.{dp}f} {self.currency_symbol or '€'}"
        if fmt == 'integer':  return f"{int(value):,}"
        if fmt == 'decimal':  return f"{value:.{dp}f}"
        return f"{value:,.{dp}f}"

    def action_validate_formula(self):
        for measure in self:
            try:
                measure._eval_dax_formula(measure.formula)
                measure.write({'formula_valid': True, 'formula_error': False})
                return {'type': 'ir.actions.client', 'tag': 'display_notification',
                        'params': {'title': '✅ Formule valide', 'type': 'success', 'sticky': False}}
            except Exception as e:
                measure.write({'formula_valid': False, 'formula_error': str(e)[:255]})
                raise UserError(f"Formule invalide : {e}")




