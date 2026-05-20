



# -*- coding: utf-8 -*-
from odoo import models, fields
import logging
_logger = logging.getLogger(__name__)

class BiKpiBusNotify(models.Model):
    _inherit = 'bi.kpi'

    def _notify_dashboard(self, event_type='bi_kpi_updated'):
        self.ensure_one()
        if not self.dashboard_id:
            return
        channel = f'bi_dashboard_{self.dashboard_id.id}'
        payload = {
            'type': event_type, 'kpi_id': self.id, 'kpi_name': self.name,
            'dashboard_id': self.dashboard_id.id, 'value': self.value,
            'value_previous': self.value_previous, 'variation_pct': self.variation_pct,
            'trend': self.trend, 'target_value': self.target_value,
            'unit': self.unit or '', 'chart_type': self.chart_type,
            'color': self.color, 'source': self.source,
            'last_update': fields.Datetime.to_string(self.last_update) if self.last_update else None,
        }
        try:
            self.env['bus.bus']._sendone(channel, event_type, payload)
        except Exception as e:
            _logger.debug("Bus non disponible pour KPI '%s': %s", self.name, e)

    def action_refresh(self):
        result = super().action_refresh()
        for kpi in self:
            try:
                kpi._notify_dashboard('bi_kpi_updated')
            except Exception:
                pass
        return result

    def write(self, vals):
        result = super().write(vals)
        watched = {'value', 'chart_data', 'chart_type', 'color', 'color2',
                   'widget_size', 'name', 'alert_enabled', 'alert_threshold',
                   'target_value', 'source'}
        if watched & set(vals.keys()):
            for kpi in self:
                try:
                    kpi._notify_dashboard('bi_kpi_updated')
                except Exception:
                    pass
        return result


class BiDashboardBusNotify(models.Model):
    _inherit = 'bi.dashboard'

    def write(self, vals):
        result = super().write(vals)
        watched = {'layout_data', 'color_theme', 'rtl_mode', 'name', 'refresh_interval'}
        if watched & set(vals.keys()):
            for dash in self:
                channel = f'bi_dashboard_{dash.id}'
                payload = {
                    'type': 'bi_dashboard_updated', 'dashboard_id': dash.id,
                    'changed_fields': list(watched & set(vals.keys())),
                    'refresh_interval': dash.refresh_interval,
                }
                try:
                    self.env['bus.bus']._sendone(channel, 'bi_dashboard_updated', payload)
                except Exception as e:
                    _logger.debug("Bus non disponible pour dashboard %d: %s", dash.id, e)
        return result




