
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║  bi.comparison — Sprint 4                                        ║
║  Comparaison KPIs semaine/mois courant vs N-1                    ║
║  Calcule les deltas et pourcentages d'évolution                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

PERIODS = [
    ('week',  'Semaine courante vs N-1'),
    ('month', 'Mois courant vs N-1'),
]

KPI_SOURCES = {
    'total_revenue':   ('kpi_sales',        'total_revenue',    'SUM'),
    'order_count':     ('kpi_sales',        'order_count',      'SUM'),
    'avg_order_value': ('kpi_sales',        'avg_order_value',  'AVG'),
    'total_margin':    ('kpi_sales',        'total_margin',     'SUM'),
    'ca_facture':      ('kpi_invoices',     'total_amount',     'SUM'),
    'total_impayes':   ('kpi_invoices',     'total_residual',   'SUM'),
    'pipeline_total':  ('kpi_crm',          'pipeline_total',   'SUM'),
    'lead_count':      ('kpi_crm',          'lead_count',       'SUM'),
    'total_qty':       ('kpi_stock_moves',  'total_qty',        'SUM'),
    'total_sales_pos': ('kpi_pos',          'total_sales',      'SUM'),
    'transaction_count':('kpi_pos',         'transaction_count','SUM'),
    'avg_basket':      ('kpi_pos',          'avg_basket',       'AVG'),
}


class BiComparison(models.TransientModel):
    """
    Modèle transient : calculé à la volée sur demande.
    Chaque record = un KPI comparé sur une période.
    """
    _name        = 'bi.comparison'
    _description = 'Comparaison KPIs N vs N-1'

    period       = fields.Selection(PERIODS, string='Période', required=True, default='week')
    kpi_label    = fields.Char(string='KPI',         readonly=True)
    kpi_key      = fields.Char(string='Clé interne', readonly=True)
    current_val  = fields.Float(string='Période courante',  readonly=True, digits=(16, 2))
    previous_val = fields.Float(string='Période N-1',       readonly=True, digits=(16, 2))
    delta        = fields.Float(string='Variation absolue', readonly=True, digits=(16, 2))
    pct_change   = fields.Float(string='Variation (%)',     readonly=True, digits=(6, 2))
    trend        = fields.Selection(
        [('up', 'Hausse'), ('down', 'Baisse'), ('flat', 'Stable')],
        string='Tendance', readonly=True,
    )
    color_class  = fields.Char(
        string='Classe CSS',
        compute='_compute_color_class',
        help='text-success, text-danger ou text-muted',
    )

    @api.depends('trend')
    def _compute_color_class(self):
        mapping = {'up': 'text-success', 'down': 'text-danger', 'flat': 'text-muted'}
        for rec in self:
            rec.color_class = mapping.get(rec.trend, 'text-muted')

    # ── Calcul SQL optimisé ───────────────────────────────────────
    @api.model
    def compute_comparison(self, period: str = 'week') -> list:
        """
        Exécute les requêtes SQL et retourne une liste de dicts
        avec current_val, previous_val, delta, pct_change, trend.
        """
        cr = self.env.cr

        if period == 'week':
            current_filter  = "window_start >= DATE_TRUNC('week', NOW())"
            previous_filter = ("window_start >= DATE_TRUNC('week', NOW()) - INTERVAL '7 days' "
                               "AND window_start < DATE_TRUNC('week', NOW())")
        else:  # month
            current_filter  = "window_start >= DATE_TRUNC('month', NOW())"
            previous_filter = ("window_start >= DATE_TRUNC('month', NOW()) - INTERVAL '1 month' "
                               "AND window_start < DATE_TRUNC('month', NOW())")

        LABELS = {
            'total_revenue':    'CA Total',
            'order_count':      'Nb Commandes',
            'avg_order_value':  'Panier moyen ventes',
            'total_margin':     'Marge totale',
            'ca_facture':       'CA Facturé',
            'total_impayes':    'Impayés',
            'pipeline_total':   'Pipeline CRM',
            'lead_count':       'Opportunités',
            'total_qty':        'Qté mouvements stock',
            'total_sales_pos':  'Ventes POS',
            'transaction_count':'Transactions POS',
            'avg_basket':       'Panier moyen POS',
        }

        results = []
        for kpi_key, (table, col, agg) in KPI_SOURCES.items():
            try:
                query = f"""
                    SELECT
                        {agg}(CASE WHEN {current_filter}  THEN {col} END) AS current_val,
                        {agg}(CASE WHEN {previous_filter} THEN {col} END) AS previous_val
                    FROM {table}
                """
                cr.execute(query)
                row = cr.fetchone()
                if not row:
                    continue
                current  = float(row[0] or 0)
                previous = float(row[1] or 0)
                delta    = current - previous
                if previous != 0:
                    pct = round((delta / abs(previous)) * 100, 2)
                elif current > 0:
                    pct = 100.0
                else:
                    pct = 0.0

                trend = 'flat'
                if abs(pct) >= 1:
                    trend = 'up' if delta >= 0 else 'down'

                results.append({
                    'kpi_key':      kpi_key,
                    'kpi_label':    LABELS.get(kpi_key, kpi_key),
                    'period':       period,
                    'current_val':  round(current,  2),
                    'previous_val': round(previous, 2),
                    'delta':        round(delta,    2),
                    'pct_change':   pct,
                    'trend':        trend,
                })
            except Exception as exc:
                _logger.warning('Erreur comparaison %s.%s: %s', table, col, exc)

        return results

    # ── Action depuis un bouton Odoo ──────────────────────────────
    @api.model
    def action_open_comparison(self, period: str = 'week'):
        rows = self.compute_comparison(period)
        records = self.create(rows)
        return {
            'type':      'ir.actions.act_window',
            'name':      f'Comparaison KPIs — {dict(PERIODS).get(period, period)}',
            'res_model': 'bi.comparison',
            'view_mode': 'tree',
            'domain':    [('id', 'in', records.ids)],
            'target':    'current',
        }

