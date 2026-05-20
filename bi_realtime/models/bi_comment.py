



# -*- coding: utf-8 -*-
from odoo import models, fields

class BiComment(models.Model):
    _name = 'bi.comment'
    _description = 'Chat interne BI'
    _order = 'create_date asc'

    dashboard_id = fields.Many2one('bi.dashboard', string='Dashboard', ondelete='cascade')
    kpi_id = fields.Many2one('bi.kpi', string='KPI associé', ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Auteur',
                              default=lambda self: self.env.user, readonly=True)
    message = fields.Text(string='Message', required=True)
    is_pinned = fields.Boolean(string='Épinglé', default=False)
    create_date = fields.Datetime(string='Date', readonly=True)




