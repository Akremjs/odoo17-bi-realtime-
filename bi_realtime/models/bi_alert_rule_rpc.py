
# -*- coding: utf-8 -*-
"""
Méthode evaluate_by_id exposée en XML-RPC pour le consumer Kafka.
À ajouter dans bi_alert_rule.py (ou dans un fichier séparé chargé via __init__.py).
"""
from odoo import models, api


class BiAlertRuleRpc(models.Model):
    _inherit = 'bi.alert.rule'

    @api.model
    def evaluate_by_id(self, rule_id: int, value: float) -> bool:
        """
        Point d'entrée XML-RPC appelé par le consumer Kafka.
        Charge la règle et délègue à evaluate().
        """
        rule = self.sudo().browse(rule_id)
        if not rule.exists():
            return False
        return rule.evaluate(rule.kpi_name, value)

    @api.model
    def bulk_evaluate(self, kpi_name: str, value: float) -> int:
        """
        Évalue toutes les règles actives pour un KPI donné.
        Retourne le nombre d'alertes déclenchées.
        """
        rules = self.sudo().search([
            ('active', '=', True),
            ('kpi_name', '=', kpi_name),
        ])
        triggered = sum(1 for r in rules if r.evaluate(kpi_name, value))
        return triggered

