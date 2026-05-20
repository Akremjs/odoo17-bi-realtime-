# -*- coding: utf-8 -*-
"""
bi_auto_sync.py — Synchronisation automatique Odoo ↔ Dashboard BI
Intercepte les create/write/unlink sur les modèles métier clés
et déclenche un rafraîchissement ciblé des KPIs liés.
"""
import logging
from odoo import models, api
from odoo.addons.bi_realtime.models.bi_kpi import _KPI_CACHE

_logger = logging.getLogger(__name__)


def _invalidate_kpi_cache(kpis):
    """Invalide le cache en mémoire pour les KPIs donnés."""
    for kpi in kpis:
        _KPI_CACHE.pop(kpi.id, None)

# Mapping modèle Odoo → refresh dashboard
_WATCHED_MODELS = {
    'sale.order': 'sale.order',
    'account.move': 'account.move',
    'crm.lead': 'crm.lead',
    'stock.picking': 'stock.picking',
    'purchase.order': 'purchase.order',
    'pos.order': 'pos.order',
    'hr.employee': 'hr.employee',
}


class BiAutoSyncSaleOrder(models.Model):
    _inherit = 'sale.order'

    def _bi_refresh_kpis(self):
        try:
            kpis = self.env['bi.kpi'].sudo().search([
                ('source', '=', 'odoo'),
                ('model_id.model', '=', 'sale.order'),
            ])
            if kpis:
                _invalidate_kpi_cache(kpis)
                kpis.action_refresh()
        except Exception as e:
            _logger.debug("BI auto-sync sale.order: %s", e)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._bi_refresh_kpis()
        return records

    def write(self, vals):
        result = super().write(vals)
        if vals.get('state') or vals.get('amount_total') or vals.get('order_line'):
            self._bi_refresh_kpis()
        return result

    def action_confirm(self):
        result = super().action_confirm()
        self._bi_refresh_kpis()
        return result


class BiAutoSyncAccountMove(models.Model):
    _inherit = 'account.move'

    def _bi_refresh_kpis(self):
        try:
            kpis = self.env['bi.kpi'].sudo().search([
                ('source', '=', 'odoo'),
                ('model_id.model', '=', 'account.move'),
            ])
            if kpis:
                _invalidate_kpi_cache(kpis)
                kpis.action_refresh()
        except Exception as e:
            _logger.debug("BI auto-sync account.move: %s", e)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._bi_refresh_kpis()
        return records

    def write(self, vals):
        result = super().write(vals)
        if vals.get('state') or vals.get('payment_state') or vals.get('amount_total'):
            self._bi_refresh_kpis()
        return result

    def action_post(self):
        result = super().action_post()
        self._bi_refresh_kpis()
        return result


class BiAutoSyncCrmLead(models.Model):
    _inherit = 'crm.lead'

    def _bi_refresh_kpis(self):
        try:
            kpis = self.env['bi.kpi'].sudo().search([
                ('source', '=', 'odoo'),
                ('model_id.model', '=', 'crm.lead'),
            ])
            if kpis:
                _invalidate_kpi_cache(kpis)
                kpis.action_refresh()
        except Exception as e:
            _logger.debug("BI auto-sync crm.lead: %s", e)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._bi_refresh_kpis()
        return records

    def write(self, vals):
        result = super().write(vals)
        if vals.get('stage_id') or vals.get('active') or vals.get('expected_revenue'):
            self._bi_refresh_kpis()
        return result


class BiAutoSyncStockPicking(models.Model):
    _inherit = 'stock.picking'

    def _bi_refresh_kpis(self):
        try:
            kpis = self.env['bi.kpi'].sudo().search([
                ('source', '=', 'odoo'),
                ('model_id.model', 'in', ['stock.picking', 'stock.move', 'product.product']),
            ])
            if kpis:
                _invalidate_kpi_cache(kpis)
                kpis.action_refresh()
        except Exception as e:
            _logger.debug("BI auto-sync stock.picking: %s", e)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._bi_refresh_kpis()
        return records

    def write(self, vals):
        result = super().write(vals)
        if vals.get('state'):
            self._bi_refresh_kpis()
        return result

    def button_validate(self):
        result = super().button_validate()
        self._bi_refresh_kpis()
        return result


class BiAutoSyncPurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _bi_refresh_kpis(self):
        try:
            kpis = self.env['bi.kpi'].sudo().search([
                ('source', '=', 'odoo'),
                ('model_id.model', '=', 'purchase.order'),
            ])
            if kpis:
                _invalidate_kpi_cache(kpis)
                kpis.action_refresh()
        except Exception as e:
            _logger.debug("BI auto-sync purchase.order: %s", e)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._bi_refresh_kpis()
        return records

    def write(self, vals):
        result = super().write(vals)
        if vals.get('state') or vals.get('amount_total'):
            self._bi_refresh_kpis()
        return result

    def button_confirm(self):
        result = super().button_confirm()
        self._bi_refresh_kpis()
        return result


class BiKpiCron(models.Model):
    """Ajoute la méthode cron de rafraîchissement global."""
    _inherit = 'bi.kpi'

    @api.model
    def _cron_refresh_all_odoo_kpis(self):
        """Cron : rafraîchit tous les KPIs source='odoo' avec un model_id."""
        kpis = self.search([
            ('source', '=', 'odoo'),
            ('model_id', '!=', False),
        ])
        _logger.info("BI Cron: rafraîchissement de %d KPIs Odoo", len(kpis))
        _invalidate_kpi_cache(kpis)
        for kpi in kpis:
            try:
                kpi.action_refresh()
            except Exception as e:
                _logger.warning("BI Cron: erreur KPI '%s': %s", kpi.name, e)
        self.env.cr.commit()
