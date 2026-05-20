



# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import base64
import json

class BiImportDashboardWizard(models.TransientModel):
    _name = 'bi.import.dashboard.wizard'
    _description = "Wizard d'import de dashboard"

    file = fields.Binary(string='Fichier JSON', required=True)
    filename = fields.Char(string='Nom du fichier')
    preview = fields.Text(string='Aperçu', readonly=True)

    def action_preview(self):
        self.ensure_one()
        try:
            content = base64.b64decode(self.file).decode('utf-8')
            data = json.loads(content)
            kpi_count = len(data.get('kpis', []))
            self.preview = (
                f"Nom: {data.get('name', 'N/A')}\n"
                f"Thème: {data.get('color_theme', 'N/A')}\n"
                f"Nombre de KPIs: {kpi_count}\n"
                f"Version: {data.get('version', 'N/A')}\n"
                f"Exporté le: {data.get('exported_at', 'N/A')}"
            )
        except Exception as e:
            self.preview = f"Erreur: {e}"
        return {'type': 'ir.actions.act_window_close'}

    def action_import(self):
        try:
            content = base64.b64decode(self.file).decode('utf-8')
            dashboard = self.env['bi.dashboard'].action_import_json(content)
            return {
                'type': 'ir.actions.act_window', 'res_model': 'bi.dashboard',
                'res_id': dashboard.id, 'view_mode': 'form', 'target': 'current',
            }
        except Exception as e:
            raise UserError(f"Erreur lors de l'import : {str(e)}")




