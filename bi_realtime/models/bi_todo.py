



# -*- coding: utf-8 -*-
from odoo import models, fields, api

class BiTodo(models.Model):
    _name = 'bi.todo'
    _description = 'Tâche BI'
    _order = 'sequence, deadline'

    name = fields.Char(string='Tâche', required=True)
    description = fields.Text(string='Description')
    dashboard_id = fields.Many2one('bi.dashboard', string='Dashboard lié')
    user_id = fields.Many2one('res.users', string='Assigné à',
                             default=lambda self: self.env.user)
    priority = fields.Selection([
        ('low', 'Basse'), ('medium', 'Normale'), ('high', 'Haute'), ('urgent', 'Urgente'),
    ], default='medium', string='Priorité')
    is_done = fields.Boolean(string='Complétée', default=False)
    deadline = fields.Date(string='Date limite')
    is_overdue = fields.Boolean(string='En retard', compute='_compute_overdue', store=True)
    tag = fields.Char(string='Tag', help='Ex: Marketing, Dev, Urgent...')
    color = fields.Char(string='Couleur', default='#007bff')
    sequence = fields.Integer(string='Ordre', default=10)

    @api.depends('deadline', 'is_done')
    def _compute_overdue(self):
        today = fields.Date.today()
        for todo in self:
            todo.is_overdue = (todo.deadline and todo.deadline < today and not todo.is_done)

    def toggle_done(self):
        for todo in self:
            todo.is_done = not todo.is_done
        return True




