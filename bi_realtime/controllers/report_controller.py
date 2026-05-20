# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json

class BiReportController(http.Controller):

    @http.route('/bi/report/chat', type='json', auth='user', methods=['POST'])
    def report_chat(self, report_id, message, **kwargs):
        report = request.env['bi.report'].browse(int(report_id))
        if not report.exists():
            return {'error': 'Rapport introuvable'}
        try:
            report.check_access_rights('read')
            report.check_access_rule('read')
        except Exception:
            return {'error': 'Accès refusé'}
        response = report.action_chat_ai(message)
        return {'response': response,
                'messages': json.loads(report.chat_messages or '[]')}
