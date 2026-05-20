# -*- coding: utf-8 -*-
"""
IA Proactive — Surveillance automatique des KPIs sans intervention utilisateur
Se déclenche via un cron job toutes les X minutes
"""
import logging
import json
import urllib.request
from odoo import models, fields, api
from odoo.addons.bi_realtime.models.bi_utils import get_ai_api_url

_logger = logging.getLogger(__name__)

_SEVERITY_ORDER = {'info': 0, 'warning': 1, 'danger': 2}

class BiAiProactive(models.Model):
    _name = 'bi.ai.proactive'
    _description = 'IA Proactive — Surveillance automatique KPIs'
    _order = 'create_date desc'

    name        = fields.Char('Titre alerte', readonly=True)
    kpi_data    = fields.Text('Données KPIs', readonly=True)
    analysis    = fields.Text('Analyse IA', readonly=True)
    severity    = fields.Selection([
        ('info',    '📘 Information'),
        ('warning', '⚠️ Avertissement'),
        ('danger',  '🔴 Critique'),
    ], string='Sévérité', readonly=True, default='info')
    is_read     = fields.Boolean('Lu', default=False)
    notified    = fields.Boolean('Notifié', default=False)

    @api.model
    def _run_proactive_analysis(self):
        """Cron — Analyse automatique des KPIs et génère des alertes IA"""
        _logger.info("🤖 IA Proactive — Démarrage analyse automatique")
        try:
            cr = self.env.cr

            # ── Collecter tous les KPIs récents ──────────────────
            cr.execute("""
                SELECT COALESCE(SUM(total_revenue),0),
                       COALESCE(SUM(order_count),0),
                       COALESCE(AVG(avg_order_value),0),
                       COALESCE(SUM(total_margin),0)
                FROM kpi_sales
                WHERE window_start >= NOW() - INTERVAL '24 hours'
            """)
            s = cr.fetchone()
            ca, nb_cmd, panier, marge = s[0], s[1], s[2], s[3]

            cr.execute("""
                SELECT COALESCE(SUM(total_residual),0),
                       COALESCE(SUM(total_amount),0)
                FROM kpi_invoices
                WHERE window_start >= NOW() - INTERVAL '24 hours'
            """)
            inv = cr.fetchone()
            impaye, total_inv = inv[0], inv[1]
            taux_recouv = (1 - impaye/total_inv)*100 if total_inv > 0 else 100

            cr.execute("""
                SELECT COALESCE(SUM(pipeline_total),0),
                       COALESCE(SUM(lead_count),0),
                       COALESCE(AVG(avg_probability),0)
                FROM kpi_crm
                WHERE window_start >= NOW() - INTERVAL '24 hours'
            """)
            crm = cr.fetchone()
            pipeline, leads, proba = crm[0], crm[1], crm[2]

            cr.execute("""
                SELECT COALESCE(SUM(total_sales),0),
                       COALESCE(SUM(transaction_count),0)
                FROM kpi_pos
                WHERE window_start >= NOW() - INTERVAL '24 hours'
            """)
            pos = cr.fetchone()
            pos_sales, pos_tx = pos[0], pos[1]

            # ── Détecter sévérité automatiquement ────────────────
            severity = 'info'
            alerts = []

            if taux_recouv < 80:
                severity = 'danger'
                alerts.append(f"🔴 CRITIQUE: Taux de recouvrement très bas ({taux_recouv:.1f}%)")
            elif taux_recouv < 90:
                severity = 'warning'
                alerts.append(f"⚠️ Taux de recouvrement faible ({taux_recouv:.1f}%)")

            if ca > 0 and impaye > ca * 0.2:
                severity = 'danger'
                alerts.append(f"🔴 CRITIQUE: Impayés élevés ({impaye:,.0f} DT = {impaye/ca*100:.1f}% du CA)")

            if leads == 0:
                if _SEVERITY_ORDER.get(severity, 0) < _SEVERITY_ORDER['warning']:
                    severity = 'warning'
                alerts.append("⚠️ Aucun lead actif dans le CRM")

            if proba < 30 and pipeline > 0:
                alerts.append(f"⚠️ Probabilité CRM faible ({proba:.1f}%)")

            taux_marge = (marge/ca*100) if ca > 0 else 0
            if taux_marge < 10 and ca > 0:
                if _SEVERITY_ORDER.get(severity, 0) < _SEVERITY_ORDER['warning']:
                    severity = 'warning'
                alerts.append(f"⚠️ Marge faible ({taux_marge:.1f}%)")

            # ── Prompt IA enrichi ─────────────────────────────────
            kpi_context = f"""
Analyse automatique des KPIs des dernières 24 heures :
- CA : {ca:,.0f} DT | Commandes : {int(nb_cmd)} | Panier : {panier:,.0f} DT
- Marge : {marge:,.0f} DT ({taux_marge:.1f}%)
- Impayés : {impaye:,.0f} DT | Recouvrement : {taux_recouv:.1f}%
- Pipeline CRM : {pipeline:,.0f} DT | Leads : {int(leads)} | Proba : {proba:.1f}%
- Ventes POS : {pos_sales:,.0f} DT | Transactions : {int(pos_tx)}

Alertes détectées : {', '.join(alerts) if alerts else 'Aucune anomalie majeure'}

En tant qu analyste BI proactif, génère une analyse courte (5-6 lignes max) avec :
1. État général de l entreprise
2. Points d attention immédiats
3. Une action prioritaire recommandée"""

            # ── Appel IA ──────────────────────────────────────────
            ai_url = get_ai_api_url(self.env)
            analysis = ''
            try:
                data = json.dumps({
                    'message': kpi_context,
                    'system_prompt': 'Tu es un analyste BI proactif. Sois concis et direct.'
                }).encode()
                req = urllib.request.Request(
                    f'{ai_url}/chat', data=data,
                    headers={'Content-Type': 'application/json'}, method='POST'
                )
                with urllib.request.urlopen(req, timeout=30) as r:
                    res = json.loads(r.read().decode())
                    analysis = res.get('response', '')
            except Exception as e:
                _logger.warning("IA Proactive — API error: %s", e)
                analysis = "Analyse IA indisponible — vérifiez les KPIs manuellement."

            # ── Créer l'alerte proactive ──────────────────────────
            title = f"🤖 Analyse automatique — {fields.Date.today()}"
            if alerts:
                title = f"🚨 {alerts[0][:50]}"

            record = self.sudo().create({
                'name': title,
                'kpi_data': json.dumps({
                    'ca': float(ca), 'nb_cmd': float(nb_cmd),
                    'marge': float(marge), 'taux_marge': float(taux_marge),
                    'impaye': float(impaye), 'taux_recouv': float(taux_recouv),
                    'pipeline': float(pipeline), 'leads': float(leads),
                    'proba': float(proba), 'pos_sales': float(pos_sales),
                }, ensure_ascii=False),
                'analysis': analysis,
                'severity': severity,
                'notified': False,
            })

            # ── Notification Odoo Bus ─────────────────────────────
            try:
                self.env['bus.bus']._sendone(
                    self.env.user.partner_id,
                    'bi_proactive_alert',
                    {
                        'type': 'bi_proactive_alert',
                        'severity': severity,
                        'title': title,
                        'message': analysis[:200] + '...' if len(analysis) > 200 else analysis,
                        'record_id': record.id,
                    }
                )
                record.sudo().write({'notified': True})
            except Exception as e:
                _logger.warning("Bus notification error: %s", e)

            _logger.info("✅ IA Proactive — Alerte créée: %s (sévérité: %s)", title, severity)

        except Exception as e:
            _logger.error("❌ IA Proactive — Erreur: %s", e)

    def action_mark_read(self):
        self.write({'is_read': True})

    def action_mark_all_read(self):
        self.search([('is_read', '=', False)]).write({'is_read': True})
