# -*- coding: utf-8 -*-
"""
bi_kpi_batch.py — Méthode batch pour les mises à jour KPI
Réduit les appels RPC individuels en regroupant les mises à jour
"""
from odoo import models, fields, api
import logging
import time
from collections import defaultdict

_logger = logging.getLogger(__name__)

# Cache debounce en mémoire
_PENDING_UPDATES = defaultdict(dict)   # {kpi_id: {values}}
_LAST_FLUSH = 0
_DEBOUNCE_SEC = 2.0  # flush toutes les 2 secondes max


class BiKpiBatch(models.Model):
    _inherit = 'bi.kpi'

    @api.model
    def write_batch(self, updates):
        """
        Mise à jour batch de plusieurs KPIs en un seul appel RPC.

        :param updates: liste de dicts [
            {'id': 1, 'value': 1500.0, 'trend': 'up'},
            {'id': 2, 'value': 890.0,  'trend': 'stable'},
            ...
        ]
        :return: {'updated': N, 'errors': [...]}

        Usage depuis kafka-consumer :
            client.call('bi.kpi', 'write_batch', [updates_list])
        """
        if not updates or not isinstance(updates, list):
            return {'updated': 0, 'errors': ['Aucune mise à jour fournie']}

        updated = 0
        errors = []
        start = time.time()

        # Regrouper par ID pour éviter les doublons
        updates_by_id = {}
        for u in updates:
            kpi_id = u.get('id')
            if kpi_id:
                updates_by_id[int(kpi_id)] = u

        # Charger tous les KPIs en une seule requête SQL
        kpi_ids = list(updates_by_id.keys())
        kpis = self.sudo().browse(kpi_ids).exists()
        kpi_map = {k.id: k for k in kpis}

        for kpi_id, vals in updates_by_id.items():
            try:
                kpi = kpi_map.get(kpi_id)
                if not kpi:
                    errors.append(f"KPI {kpi_id} introuvable")
                    continue

                write_vals = {}
                if 'value' in vals:
                    write_vals['value'] = float(vals['value'])
                if 'value_previous' in vals:
                    write_vals['value_previous'] = float(vals['value_previous'])
                if 'trend' in vals:
                    write_vals['trend'] = vals['trend']
                if 'last_update' in vals:
                    write_vals['last_update'] = vals['last_update']

                if write_vals:
                    kpi.write(write_vals)
                    updated += 1

            except Exception as e:
                errors.append(f"KPI {kpi_id}: {e}")
                _logger.error("write_batch erreur KPI %s: %s", kpi_id, e)

        elapsed = (time.time() - start) * 1000
        _logger.info(
            "write_batch: %d/%d mis à jour en %.1fms (%d erreurs)",
            updated, len(updates_by_id), elapsed, len(errors)
        )

        return {
            'updated': updated,
            'errors': errors,
            'elapsed_ms': round(elapsed, 1)
        }

    @api.model
    def write_batch_debounced(self, updates, flush=False):
        """
        Variante avec debounce — accumule les mises à jour
        et flush toutes les DEBOUNCE_SEC secondes.
        Utile pour les bursts de messages Kafka.
        """
        global _PENDING_UPDATES, _LAST_FLUSH

        # Accumuler
        for u in updates:
            kpi_id = u.get('id')
            if kpi_id:
                _PENDING_UPDATES[int(kpi_id)].update(u)

        now = time.time()
        if flush or (now - _LAST_FLUSH) >= _DEBOUNCE_SEC:
            if _PENDING_UPDATES:
                pending = list(_PENDING_UPDATES.values())
                _PENDING_UPDATES.clear()
                _LAST_FLUSH = now
                return self.write_batch(pending)

        return {'updated': 0, 'pending': len(_PENDING_UPDATES)}

    @api.model
    def update_from_pipeline(self, name, value):
        """
        Met à jour un KPI par son libellé (appel Spark / Kafka consumer).
        Déclenche la notification Bus pour rafraîchir le dashboard ouvert.
        """
        kpi = self.sudo().search([('name', '=', name)], limit=1)
        if not kpi:
            _logger.debug("Pipeline: KPI '%s' introuvable dans Odoo", name)
            return {'updated': False, 'name': name, 'reason': 'kpi_not_found'}

        old_val = kpi.value
        kpi.write({
            'value_previous': old_val,
            'value': round(float(value), 4),
            'last_update': fields.Datetime.now(),
            'source': kpi.source or 'kafka',
        })
        kpi._save_history(float(value))
        if kpi.alert_enabled:
            kpi._check_alert(float(value))
        try:
            kpi._notify_dashboard('bi_kpi_updated')
        except Exception:
            pass

        return {
            'updated': True,
            'kpi_id': kpi.id,
            'name': name,
            'value': float(value),
            'dashboard_id': kpi.dashboard_id.id if kpi.dashboard_id else None,
        }
