
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════╗
║  bi.alert.rule — Sprint 2                                        ║
║  Règles d'alertes configurables sur les KPIs temps réel          ║
║  Deux modes : rule-based (seuil) + analyse IA optionnelle        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import logging
import requests
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

KPI_NAMES = [
    ('ca_total',         'CA Total'),
    ('nb_commandes',     'Nb Commandes'),
    ('impayes',          'Impayés'),
    ('pipeline_total',   'Pipeline Total'),
    ('panier_moyen',     'Panier Moyen'),
    ('marge_totale',     'Marge Totale'),
    ('opportunites',     'Opportunités actives'),
    ('transferts',       'Transferts en cours'),
    ('ca_facture',       'CA Facturé'),
    ('nb_transactions',  'Nb Transactions POS'),
]

OPERATORS = [
    ('>',  'Supérieur à'),
    ('<',  'Inférieur à'),
    ('>=', 'Supérieur ou égal à'),
    ('<=', 'Inférieur ou égal à'),
    ('=',  'Égal à'),
]

CHANNELS = [
    ('bus',   'Notification Odoo (ir.bus)'),
    ('email', 'Email'),
    ('both',  'Notification + Email'),
]


class BiAlertRule(models.Model):
    _name = 'bi.alert.rule'
    _inherit = ['mail.thread']
    _description = 'Règle d\'alerte BI temps réel'
    _order = 'sequence, id'

    # ── Identification ────────────────────────────────────────────
    name = fields.Char(
        string='Nom de la règle',
        required=True,
        help='Ex. : Alerte CA journalier bas',
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, string='Actif')
    color = fields.Integer(string='Couleur')

    # ── Condition ─────────────────────────────────────────────────
    kpi_name = fields.Selection(
        selection=KPI_NAMES,
        string='KPI surveillé',
        required=True,
    )
    operator = fields.Selection(
        selection=OPERATORS,
        string='Opérateur',
        required=True,
        default='>',
    )
    threshold = fields.Float(
        string='Seuil',
        required=True,
        digits=(16, 2),
        help='Valeur numérique déclenchant l\'alerte',
    )

    # ── Notification ──────────────────────────────────────────────
    channel = fields.Selection(
        selection=CHANNELS,
        string='Canal de notification',
        required=True,
        default='bus',
    )
    email_to = fields.Char(
        string='Destinataires email',
        help='Adresses séparées par des virgules. Obligatoire si canal = Email.',
    )
    message_template = fields.Text(
        string='Template du message',
        default='🚨 Alerte {kpi} : valeur {value} {operator} seuil {threshold}',
        help='Variables disponibles : {kpi}, {value}, {operator}, {threshold}, {ai_analysis}',
    )

    # ── Analyse IA (optionnelle) ───────────────────────────────────
    ai_enabled = fields.Boolean(
        string='Analyse IA activée',
        default=False,
        help='Interroge l\'API IA pour enrichir la notification d\'une analyse contextuelle',
    )
    ai_prompt_template = fields.Text(
        string='Prompt IA',
        default=(
            'Le KPI "{kpi}" vaut {value}. Le seuil d\'alerte est {threshold}. '
            'En 2-3 phrases, explique les causes probables et recommande une action.'
        ),
    )

    # ── Statistiques ──────────────────────────────────────────────
    trigger_count = fields.Integer(
        string='Déclenchements',
        readonly=True,
        default=0,
    )
    last_triggered = fields.Datetime(
        string='Dernier déclenchement',
        readonly=True,
    )
    last_value = fields.Float(
        string='Dernière valeur observée',
        readonly=True,
        digits=(16, 2),
    )
    last_ai_analysis = fields.Text(
        string='Dernière analyse IA',
        readonly=True,
    )

    # ── Cooldown (anti-flood) ──────────────────────────────────────
    cooldown_minutes = fields.Integer(
        string='Cooldown (minutes)',
        default=15,
        help='Délai minimum entre deux déclenchements de la même règle',
    )

    # ── Contraintes ───────────────────────────────────────────────
    @api.constrains('channel', 'email_to')
    def _check_email(self):
        for rule in self:
            if rule.channel in ('email', 'both') and not rule.email_to:
                raise ValidationError(
                    'Le champ "Destinataires email" est obligatoire '
                    'quand le canal inclut l\'email.'
                )

    @api.constrains('cooldown_minutes')
    def _check_cooldown(self):
        for rule in self:
            if rule.cooldown_minutes < 0:
                raise ValidationError('Le cooldown ne peut pas être négatif.')

    # ── Évaluation d'une valeur entrante ──────────────────────────
    def evaluate(self, kpi_name: str, value: float) -> bool:
        """
        Évalue si la règle doit se déclencher pour la valeur donnée.
        Retourne True si l'alerte est envoyée.
        """
        self.ensure_one()
        if not self.active or self.kpi_name != kpi_name:
            return False

        # Test de la condition
        ops = {'>': lambda a, b: a > b, '<': lambda a, b: a < b,
               '>=': lambda a, b: a >= b, '<=': lambda a, b: a <= b,
               '=': lambda a, b: a == b}
        triggered = ops[self.operator](value, self.threshold)
        if not triggered:
            return False

        # Cooldown : vérifier si assez de temps s'est écoulé
        if self.last_triggered:
            from datetime import datetime, timedelta
            elapsed = datetime.utcnow() - fields.Datetime.from_string(self.last_triggered)
            if elapsed < timedelta(minutes=self.cooldown_minutes):
                _logger.debug(
                    'Règle %s en cooldown (%s restant)',
                    self.name, timedelta(minutes=self.cooldown_minutes) - elapsed
                )
                return False

        # Analyse IA optionnelle
        ai_analysis = ''
        if self.ai_enabled:
            ai_analysis = self._call_ai_analysis(kpi_name, value) or ''

        # Construire le message
        message = (self.message_template or '{kpi} = {value}').format(
            kpi=dict(KPI_NAMES).get(kpi_name, kpi_name),
            value=f'{value:,.2f}',
            operator=dict(OPERATORS).get(self.operator, self.operator),
            threshold=f'{self.threshold:,.2f}',
            ai_analysis=ai_analysis,
        )

        # Envoyer sur le/les canal/canaux
        if self.channel in ('bus', 'both'):
            self._send_bus_notification(message)
        if self.channel in ('email', 'both'):
            self._send_email(message)

        # Mettre à jour les stats
        self.sudo().write({
            'trigger_count': self.trigger_count + 1,
            'last_triggered': fields.Datetime.now(),
            'last_value': value,
            'last_ai_analysis': ai_analysis,
        })
        _logger.info('Alerte "%s" déclenchée — %s %s %s', self.name, kpi_name, self.operator, self.threshold)
        return True

    # ── Notification ir.bus ───────────────────────────────────────
    def _send_bus_notification(self, message: str):
        self.ensure_one()
        try:
            self.env['bus.bus']._sendone(
                (self._cr.dbname, 'bi.alert', self.env.user.partner_id.id),
                'bi_alert',
                {
                    'type': 'bi_alert',
                    'rule_id': self.id,
                    'rule_name': self.name,
                    'message': message,
                    'kpi': self.kpi_name,
                    'threshold': self.threshold,
                }
            )
        except Exception as exc:
            _logger.error('Erreur bus notification [%s]: %s', self.name, exc)

    # ── Notification email ────────────────────────────────────────
    def _send_email(self, message: str):
        self.ensure_one()
        if not self.email_to:
            return
        try:
            mail = self.env['mail.mail'].sudo().create({
                'subject': f'🚨 Alerte BI : {self.name}',
                'body_html': f'<p>{message}</p>',
                'email_to': self.email_to,
                'auto_delete': True,
            })
            mail.send()
        except Exception as exc:
            _logger.error('Erreur email [%s]: %s', self.name, exc)

    # ── Analyse IA ────────────────────────────────────────────────
    def _call_ai_analysis(self, kpi_name: str, value: float) -> str:
        self.ensure_one()
        from odoo.addons.bi_realtime.models.bi_utils import get_ai_api_url
        ai_url = get_ai_api_url(self.env)
        prompt = (self.ai_prompt_template or '').format(
            kpi=dict(KPI_NAMES).get(kpi_name, kpi_name),
            value=f'{value:,.2f}',
            threshold=f'{self.threshold:,.2f}',
        )
        try:
            resp = requests.post(
                f'{ai_url}/chat',
                json={'message': prompt, 'system_prompt': 'Tu es un analyste BI expert. Réponds en français, de façon concise.'},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get('response', data.get('message', ''))
        except Exception as exc:
            _logger.warning('IA indisponible pour alerte "%s": %s', self.name, exc)
            return ''

    # ── Action manuelle de test ───────────────────────────────────
    def action_test_alert(self):
        """Déclenche manuellement l'alerte avec la valeur seuil + 1."""
        for rule in self:
            test_value = rule.threshold + 1 if rule.operator in ('>', '>=') else rule.threshold - 1
            # Forcer le cooldown à 0 pour le test
            old_cooldown = rule.cooldown_minutes
            rule.sudo().write({'cooldown_minutes': 0, 'last_triggered': False})
            rule.evaluate(rule.kpi_name, test_value)
            rule.sudo().write({'cooldown_minutes': old_cooldown})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test envoyé',
                'message': f'Alerte test déclenchée pour {len(self)} règle(s)',
                'type': 'success',
            }
        }

