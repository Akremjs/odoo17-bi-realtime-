# -*- coding: utf-8 -*-
"""API HTTP pour le pipeline Spark / Kafka → mise à jour des KPIs Odoo."""
import json
import logging

from odoo import http, SUPERUSER_ID
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class BiKpiApiController(http.Controller):

    @http.route(
        '/bi_realtime/api/kpi/update',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def kpi_update(self, **kwargs):
        """
        Mise à jour d'un KPI par nom (appelé par Spark Streaming).
        Auth : Basic (ODOO_USER / ODOO_PASSWORD) ou en-tête X-BI-Token.
        Corps JSON : {"name": "CA Total", "value": 1234.5, "db": "pfe_bi"}
        """
        try:
            body = request.httprequest.get_data(as_text=True) or '{}'
            data = json.loads(body)
        except json.JSONDecodeError:
            return self._json_response({'error': 'JSON invalide'}, 400)

        name = data.get('name')
        if not name:
            return self._json_response({'error': 'Champ name requis'}, 400)

        try:
            value = float(data.get('value', 0))
        except (TypeError, ValueError):
            return self._json_response({'error': 'Valeur numérique invalide'}, 400)

        db_name = data.get('db') or request.db
        if not db_name:
            return self._json_response({'error': 'Base de données non spécifiée'}, 400)

        try:
            result = self._run_with_pipeline_env(db_name, name, value)
            status = 200 if result.get('updated') else 404
            return self._json_response(result, status)
        except PermissionError:
            return self._json_response({'error': 'Non autorisé'}, 401)
        except Exception as e:
            _logger.exception("Erreur API KPI update: %s", e)
            return self._json_response({'error': str(e)}, 500)

    def _run_with_pipeline_env(self, db_name, name, value):
        import odoo
        from odoo.api import Environment

        token = (request.httprequest.headers.get('X-BI-Token') or '').strip()
        auth = request.httprequest.authorization

        if token:
            registry = odoo.registry(db_name)
            with registry.cursor() as cr:
                env = Environment(cr, SUPERUSER_ID, {})
                expected = (
                    env['ir.config_parameter']
                    .sudo()
                    .get_param('bi_realtime.pipeline_token', '')
                    .strip()
                )
                if not expected or token != expected:
                    raise PermissionError()
                result = env['bi.kpi'].update_from_pipeline(name, value)
                cr.commit()
                return result

        if not auth or auth.type != 'basic':
            raise PermissionError()

        request.session.db = db_name
        uid = request.session.authenticate(db_name, auth.username, auth.password)
        if not uid:
            raise PermissionError()

        return request.env(user=uid)['bi.kpi'].update_from_pipeline(name, value)

    @staticmethod
    def _json_response(payload, status=200):
        return Response(
            json.dumps(payload, ensure_ascii=False),
            status=status,
            mimetype='application/json',
        )
