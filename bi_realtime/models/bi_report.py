# -*- coding: utf-8 -*-
"""
Rapports BI V3 — Executive Edition
Chef d'entreprise : graphiques complets + IA chat + analyse auto
"""
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging, json, csv, io, base64, math
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# HELPERS GRAPHIQUES & HTML
# ══════════════════════════════════════════════════════════════════

COLORS = ['#6366f1','#10b981','#f59e0b','#ef4444',
          '#3b82f6','#8b5cf6','#ec4899','#14b8a6']

def _chart_line(chart_id, labels, datasets, title=''):
    ds = []
    for i, d in enumerate(datasets):
        c = COLORS[i % len(COLORS)]
        ds.append({'label': d['label'], 'data': d['data'],
                   'borderColor': c, 'backgroundColor': c+'22',
                   'borderWidth': 2.5, 'tension': 0.4,
                   'fill': True, 'pointRadius': 3})
    cfg = {'type': 'line',
           'data': {'labels': labels, 'datasets': ds},
           'options': {'responsive': True, 'plugins': {
               'legend': {'position': 'top'},
               'title': {'display': bool(title), 'text': title,
                         'font': {'size': 13, 'weight': 'bold'}}},
               'scales': {'y': {'beginAtZero': False,
                                'grid': {'color': '#f0f0f0'}}}}}
    return _chart_html(chart_id, cfg)

def _chart_bar(chart_id, labels, datasets, title=''):
    ds = []
    for i, d in enumerate(datasets):
        c = COLORS[i % len(COLORS)]
        ds.append({'label': d['label'], 'data': d['data'],
                   'backgroundColor': c+'cc', 'borderColor': c,
                   'borderWidth': 1, 'borderRadius': 6})
    cfg = {'type': 'bar',
           'data': {'labels': labels, 'datasets': ds},
           'options': {'responsive': True, 'plugins': {
               'legend': {'position': 'top'},
               'title': {'display': bool(title), 'text': title,
                         'font': {'size': 13, 'weight': 'bold'}}},
               'scales': {'y': {'beginAtZero': True}}}}
    return _chart_html(chart_id, cfg)

def _chart_pie(chart_id, labels, values, title=''):
    cfg = {'type': 'pie',
           'data': {'labels': labels,
                    'datasets': [{'data': values,
                                  'backgroundColor': COLORS[:len(values)],
                                  'borderWidth': 2, 'borderColor': '#fff'}]},
           'options': {'responsive': True, 'plugins': {
               'legend': {'position': 'right'},
               'title': {'display': bool(title), 'text': title,
                         'font': {'size': 13, 'weight': 'bold'}}}}}
    return _chart_html(chart_id, cfg)

def _chart_gauge(chart_id, value, max_val, label, color='#6366f1'):
    """Jauge semi-circulaire."""
    pct = min(value / max_val, 1.0) if max_val > 0 else 0
    cfg = {'type': 'doughnut',
           'data': {'datasets': [{
               'data': [pct * 100, 100 - pct * 100],
               'backgroundColor': [color, '#f3f4f6'],
               'borderWidth': 0, 'circumference': 180,
               'rotation': 270}]},
           'options': {'responsive': True, 'cutout': '75%',
                       'plugins': {'legend': {'display': False},
                                   'title': {'display': True,
                                             'text': f'{label}: {value:,.1f}',
                                             'font': {'size': 13,
                                                      'weight': 'bold'}}}}}
    return _chart_html(chart_id, cfg, height=180)

def _chart_html(chart_id, config, height=280):
    return f'''
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;
            padding:16px;margin:12px 0">
  <canvas id="{chart_id}" style="max-height:{height}px"></canvas>
</div>
<script>
(function(){{
  function makeChart(){{
    var el = document.getElementById("{chart_id}");
    if(!el) return;
    if(typeof Chart === "undefined"){{
      setTimeout(makeChart, 400); return;
    }}
    if(el._chart) el._chart.destroy();
    el._chart = new Chart(el, {json.dumps(config)});
  }}
  if(document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", makeChart);
  else makeChart();
}})();
</script>'''

def _kpi_cards(items):
    """items = [(label, value, unit, color, prev), ...]"""
    html = '<div style="display:flex;gap:10px;flex-wrap:wrap;margin:16px 0">'
    for label, value, unit, color, prev in items:
        pct_html = ''
        if prev and prev != 0:
            pct = ((value - prev) / abs(prev)) * 100
            bg = '#dcfce7' if pct >= 0 else '#fee2e2'
            fg = '#16a34a' if pct >= 0 else '#dc2626'
            arrow = '▲' if pct >= 0 else '▼'
            pct_html = (f'<span style="background:{bg};color:{fg};'
                        f'padding:2px 7px;border-radius:10px;'
                        f'font-size:11px;font-weight:600">'
                        f'{arrow} {abs(pct):.1f}%</span>')
        val_str = f'{value:,.0f}' if unit == '' else f'{value:,.2f}'
        html += f'''
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;
            padding:14px 18px;min-width:150px;flex:1;
            border-top:3px solid {color}">
  <div style="font-size:11px;color:#6b7280;margin-bottom:4px">{label}</div>
  <div style="font-size:20px;font-weight:700;color:{color}">
    {val_str} <span style="font-size:13px;font-weight:400">{unit}</span>
  </div>
  <div style="margin-top:4px">{pct_html}</div>
</div>'''
    html += '</div>'
    return html

def _report_header(title, period, kpis_summary=''):
    now = datetime.now().strftime("%d/%m/%Y à %H:%M")
    return f'''
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"/>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<div style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);
            color:#fff;border-radius:14px;padding:24px 28px;margin-bottom:16px">
  <div style="font-size:10px;letter-spacing:2px;opacity:0.75;
              text-transform:uppercase">Rapport Exécutif BI</div>
  <div style="font-size:24px;font-weight:800;margin:6px 0">{title}</div>
  <div style="font-size:12px;opacity:0.85">
    📅 {period} &nbsp;|&nbsp; 🕐 Généré le {now}
  </div>
  {f'<div style="margin-top:8px;font-size:12px;opacity:0.9">{kpis_summary}</div>' if kpis_summary else ''}
</div>'''

def _section(title, icon='📊'):
    return (f'<div style="font-size:15px;font-weight:700;color:#4f46e5;'
            f'margin:20px 0 8px;padding-bottom:6px;'
            f'border-bottom:2px solid #e5e7eb">{icon} {title}</div>')

def _ai_block(insight, suggestions=None):
    if not insight:
        return ""
    import re as _re
    h = insight
    h = _re.sub(r'## (.+)', lambda m: '<h3 style="color:#4f46e5;margin:20px 0 10px;font-size:15px;font-weight:800;border-bottom:2px solid #e0e7ff;padding-bottom:8px">' + m.group(1) + '</h3>', h)
    h = _re.sub(r'\*\*(.+?)\*\*', lambda m: '<strong style="color:#1f2937">' + m.group(1) + '</strong>', h)
    h = _re.sub(r'• (.+)', lambda m: '<li style="margin:6px 0;color:#374151;line-height:1.6">' + m.group(1) + '</li>', h)
    h = _re.sub(r'^- (.+)$', lambda m: '<li style="margin:4px 0;color:#374151">' + m.group(1) + '</li>', h, flags=_re.MULTILINE)
    h = _re.sub(r'(\d+)\. (.+)', lambda m: '<li style="margin:6px 0;color:#374151;font-weight:500"><span style="color:#4f46e5;font-weight:700">' + m.group(1) + '.</span> ' + m.group(2) + '</li>', h)
    h = h.replace('\n\n', '</p><p style="margin:8px 0">')
    h = h.replace('\n', '<br/>')
    return (
        '<div style="background:linear-gradient(135deg,#f5f3ff 0%,#ede9fe 100%);'
        'border:1px solid #c4b5fd;border-radius:16px;padding:24px 28px;margin:20px 0;'
        'box-shadow:0 4px 16px rgba(99,102,241,0.12)">'
        '<div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;'
        'border-bottom:2px solid #c4b5fd;padding-bottom:14px">'
        '<span style="font-size:28px">🤖</span>'
        '<div><div style="font-size:16px;font-weight:800;color:#4f46e5">'
        'Rapport d\'Analyse IA — Décision Management</div>'
        '<div style="font-size:11px;color:#7c3aed;margin-top:2px">'
        'Généré par LLaMA 3.1 via Groq • Analyse temps réel</div></div></div>'
        '<div style="font-size:13.5px;line-height:1.8;color:#374151">' + h + '</div>'
        '<div style="margin-top:16px;padding-top:12px;border-top:1px solid #c4b5fd;'
        'font-size:11px;color:#7c3aed;text-align:right">'
        'BI Realtime • Analyse confidentielle • Usage interne</div></div>'
    )


def _anomaly_block(anomalies):
    if not anomalies:
        return ''
    items = ''.join(f'<li style="margin:3px 0">{a}</li>' for a in anomalies)
    return f'''
<div style="background:#fff7ed;border-left:4px solid #f59e0b;
            border-radius:0 12px 12px 0;padding:14px 18px;margin:12px 0">
  <div style="font-size:13px;font-weight:700;color:#d97706;margin-bottom:6px">
    ⚠️ Anomalies détectées ({len(anomalies)})
  </div>
  <ul style="margin:0;padding-left:20px;font-size:12px;color:#374151">{items}</ul>
</div>'''

def _html_table(headers, rows, title=''):
    html = ''
    if title:
        html += f'<div style="font-size:13px;font-weight:600;color:#374151;margin:12px 0 6px">{title}</div>'
    html += '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:12px">'
    html += '<thead><tr>' + ''.join(
        f'<th style="background:#4f46e5;color:#fff;padding:8px 12px;text-align:left;white-space:nowrap">{h}</th>'
        for h in headers) + '</tr></thead><tbody>'
    for i, row in enumerate(rows):
        bg = '#faf5ff' if i % 2 == 0 else '#fff'
        html += f'<tr style="background:{bg}">' + ''.join(
            f'<td style="padding:6px 12px;border-bottom:1px solid #f0f0f0">{v}</td>'
            for v in row) + '</tr>'
    html += '</tbody></table></div>'
    return html

def _detect_anomalies(data_list, key, label):
    vals = [r[key] for r in data_list if r.get(key)]
    if len(vals) < 4:
        return []
    mean = sum(vals) / len(vals)
    std = math.sqrt(sum((v - mean)**2 for v in vals) / len(vals))
    out = []
    for r in data_list:
        v = r.get(key, 0)
        if std > 0 and abs(v - mean) > 2.2 * std:
            d = 'élevé' if v > mean else 'bas'
            out.append(f"{label} anormalement {d} le {r.get('jour','?')} "
                       f": {v:,.2f} (moy={mean:,.2f})")
    return out


# ══════════════════════════════════════════════════════════════════
# MODÈLE
# ══════════════════════════════════════════════════════════════════

class BiReport(models.Model):
    _name = 'bi.report'
    _description = 'Rapport BI Executive'
    _order = 'create_date desc'
    _rec_name = 'name'

    name = fields.Char(string='Nom du rapport', required=True)
    report_type = fields.Selection([
        ('executive', '🏢 Vue Exécutive (Tout)'),
        ('kpi',       '📊 KPI Périodique'),
        ('sales',     '💰 Ventes'),
        ('invoice',   '🧾 Facturation'),
        ('crm',       '🎯 CRM + Prévisions IA'),
        ('stock',     '📦 Stocks'),
        ('alert',     '🔔 Alertes Historique'),
    ], string='Type', required=True, default='executive')

    period = fields.Selection([
        ('today',   "Aujourd'hui"),
        ('week',    'Cette semaine'),
        ('month',   'Ce mois'),
        ('quarter', 'Ce trimestre'),
        ('custom',  'Personnalisé'),
    ], string='Période', default='month', required=True)

    date_from = fields.Date(string='Du',
        default=lambda self: fields.Date.today() - timedelta(days=30))
    date_to   = fields.Date(string='Au', default=fields.Date.today)

    # Chat IA avant génération
    ai_question   = fields.Text(string='💬 Question à l\'IA',
        help='Posez une question à l\'IA avant de générer le rapport')
    ai_chat_response = fields.Html(string='Réponse IA', readonly=True, sanitize=False)

    state = fields.Selection([
        ('draft', 'Brouillon'), ('generated', 'Généré'),
    ], default='draft')

    result_html   = fields.Html(string='Résultat', readonly=True, sanitize=False)
    export_file   = fields.Binary(string='Export CSV')
    export_fname  = fields.Char(string='Nom fichier')
    ai_insight    = fields.Text(string='Analyse IA', readonly=True)
    record_count  = fields.Float(string='Nb enregistrements', readonly=True, digits=(16, 0))
    anomaly_count = fields.Float(string='Anomalies', readonly=True, digits=(16, 0))
    score_global  = fields.Float(string='Score Performance (%)', readonly=True)
    # Comparaison N vs N-1
    compare_previous = fields.Boolean(string='Comparer N vs N-1', default=True)
    comparison_html  = fields.Html(string='Comparaison', readonly=True, sanitize=False)

    # Envoi email
    email_to     = fields.Char(string='Envoyer par email à')
    email_sent   = fields.Boolean(string='Email envoyé', readonly=True, default=False)
    auto_send    = fields.Boolean(string='Envoi automatique', default=False)

    # Chat IA style dashboard
    chat_messages = fields.Text(string='Historique chat', default='[]')


    def _get_dates(self):
        today = fields.Date.today()
        if self.period == 'today':   return today, today
        elif self.period == 'week':  return today - timedelta(days=today.weekday()), today
        elif self.period == 'month': return today.replace(day=1), today
        elif self.period == 'quarter':
            q = ((today.month - 1) // 3) * 3 + 1
            return today.replace(month=q, day=1), today
        return self.date_from, self.date_to

    def _ask_ai(self, prompt, structured=False):
        try:
            import urllib.request
            system = """Tu es un analyste BI senior expert pour dirigeants d entreprise.
Tu fournis des analyses STRUCTURÉES, PRÉCISES et ACTIONNABLES.
Ton format de réponse DOIT toujours être :

## 📊 ANALYSE
[Analyse factuelle des données en 3-4 phrases]

## 🔍 POINTS CLÉS
- [Point 1 — avec chiffre précis]
- [Point 2 — avec chiffre précis]
- [Point 3 — avec chiffre précis]
- [Point 4 — avec chiffre précis]

## ⚠️ ALERTES & RISQUES
- [Risque 1 si applicable, sinon RAS]
- [Risque 2 si applicable]

## 🚀 RECOMMANDATIONS PRIORITAIRES
1. [Action immédiate — Court terme]
2. [Action stratégique — Moyen terme]
3. [Action préventive — Long terme]

## 🎯 DÉCISION SUGGÉRÉE
[Une décision claire et directe que le dirigeant doit prendre]

Utilise des chiffres précis, des pourcentages et des comparaisons concrètes."""

            data = json.dumps({
                'message': prompt,
                'system_prompt': system,
                'context': {}
            }).encode()
            from odoo.addons.bi_realtime.models.bi_utils import get_ai_api_url
            req = urllib.request.Request(
                f'{get_ai_api_url(self.env)}/chat', data=data,
                headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=120) as r:
                res = json.loads(r.read().decode())
                return res.get('response', res.get('message', ''))
        except Exception as e:
            _logger.warning("AI: %s", e)
            return None

    # ── Chat IA avant génération ──────────────────────────────────
    def action_ask_ai(self):
        self.ensure_one()
        if not self.ai_question:
            raise UserError("Posez d'abord une question à l'IA.")
        df, dt = self._get_dates()
        context_prompt = (
            f"Tu es un assistant BI expert pour un chef d'entreprise. "
            f"Le rapport concerne : {dict(self._fields['report_type'].selection).get(self.report_type)}, "
            f"période {df} → {dt}. "
            f"Question du dirigeant : {self.ai_question} "
            f"Réponds de manière concise et actionnable."
        )
        response = self._ask_ai(context_prompt)
        if response:
            self.ai_chat_response = f'''
<div style="background:#f5f3ff;border-left:4px solid #6366f1;
            border-radius:0 10px 10px 0;padding:14px 18px">
  <div style="font-size:12px;font-weight:700;color:#4f46e5;margin-bottom:8px">
    🤖 Réponse IA
  </div>
  <div style="font-size:13px;color:#374151;line-height:1.7;
              white-space:pre-wrap">{response}</div>
  <div style="font-size:11px;color:#9ca3af;margin-top:8px">
    Question : {self.ai_question}
  </div>
</div>'''
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': '🤖 IA a répondu', 'type': 'success',
                           'message': 'Consultez la réponse ci-dessous.'}}


    def _gen_comparison(self, df, dt):
        """Génère la comparaison N vs N-1 pour tous les domaines."""
        from datetime import timedelta
        delta = dt - df
        prev_dt = df - timedelta(days=1)
        prev_df = prev_dt - delta

        cr = self.env.cr

        def get_sales(d1, d2):
            cr.execute("""
                SELECT COALESCE(SUM(total_revenue),0),
                       COALESCE(SUM(order_count),0),
                       COALESCE(SUM(total_margin),0)
                FROM kpi_sales
                WHERE window_start::date BETWEEN %s AND %s
            """, [d1, d2])
            return cr.fetchone()

        def get_inv(d1, d2):
            cr.execute("""
                SELECT COALESCE(SUM(total_amount),0),
                       COALESCE(SUM(total_residual),0)
                FROM kpi_invoices
                WHERE window_start::date BETWEEN %s AND %s
            """, [d1, d2])
            return cr.fetchone()

        def get_crm(d1, d2):
            cr.execute("""
                SELECT COALESCE(SUM(pipeline_total),0),
                       COALESCE(SUM(lead_count),0)
                FROM kpi_crm
                WHERE window_start::date BETWEEN %s AND %s
            """, [d1, d2])
            return cr.fetchone()

        cur_s = get_sales(df, dt)
        prv_s = get_sales(prev_df, prev_dt)
        cur_i = get_inv(df, dt)
        prv_i = get_inv(prev_df, prev_dt)
        cur_c = get_crm(df, dt)
        prv_c = get_crm(prev_df, prev_dt)

        def pct(cur, prv):
            if not prv or prv == 0:
                return 0
            return ((cur - prv) / abs(prv)) * 100

        def arrow(p):
            if p > 5:
                return f'<span style="color:#16a34a;font-weight:700">▲ {p:.1f}%</span>'
            elif p < -5:
                return f'<span style="color:#dc2626;font-weight:700">▼ {abs(p):.1f}%</span>'
            return f'<span style="color:#6b7280">→ {p:.1f}%</span>'

        html = f"""
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;
            padding:20px;margin:12px 0">
  <div style="font-size:15px;font-weight:700;color:#4f46e5;margin-bottom:16px">
    📈 Comparaison N vs N-1
  </div>
  <div style="font-size:12px;color:#6b7280;margin-bottom:12px">
    Période actuelle : <b>{df} → {dt}</b> &nbsp;|&nbsp;
    Période précédente : <b>{prev_df} → {prev_dt}</b>
  </div>
  <table style="width:100%;border-collapse:collapse;font-size:13px">
    <thead>
      <tr style="background:#4f46e5;color:#fff">
        <th style="padding:10px 14px;text-align:left">Indicateur</th>
        <th style="padding:10px 14px;text-align:right">Période N</th>
        <th style="padding:10px 14px;text-align:right">Période N-1</th>
        <th style="padding:10px 14px;text-align:center">Évolution</th>
      </tr>
    </thead>
    <tbody>
      <tr style="background:#f9fafb">
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;font-weight:600">
          💰 CA Total
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:right">
          {cur_s[0]:,.2f} €
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:right;
                   color:#6b7280">
          {prv_s[0]:,.2f} €
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:center">
          {arrow(pct(cur_s[0], prv_s[0]))}
        </td>
      </tr>
      <tr>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;font-weight:600">
          📦 Nb Commandes
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:right">
          {int(cur_s[1])}
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:right;
                   color:#6b7280">
          {int(prv_s[1])}
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:center">
          {arrow(pct(cur_s[1], prv_s[1]))}
        </td>
      </tr>
      <tr style="background:#f9fafb">
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;font-weight:600">
          📊 Marge
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:right">
          {cur_s[2]:,.2f} €
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:right;
                   color:#6b7280">
          {prv_s[2]:,.2f} €
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:center">
          {arrow(pct(cur_s[2], prv_s[2]))}
        </td>
      </tr>
      <tr>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;font-weight:600">
          🧾 Factures
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:right">
          {cur_i[0]:,.2f} €
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:right;
                   color:#6b7280">
          {prv_i[0]:,.2f} €
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:center">
          {arrow(pct(cur_i[0], prv_i[0]))}
        </td>
      </tr>
      <tr style="background:#f9fafb">
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;font-weight:600">
          🎯 Pipeline CRM
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:right">
          {cur_c[0]:,.2f} €
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:right;
                   color:#6b7280">
          {prv_c[0]:,.2f} €
        </td>
        <td style="padding:9px 14px;border-bottom:1px solid #f0f0f0;text-align:center">
          {arrow(pct(cur_c[0], prv_c[0]))}
        </td>
      </tr>
      <tr>
        <td style="padding:9px 14px;font-weight:600">
          👥 Leads CRM
        </td>
        <td style="padding:9px 14px;text-align:right">
          {int(cur_c[1])}
        </td>
        <td style="padding:9px 14px;text-align:right;color:#6b7280">
          {int(prv_c[1])}
        </td>
        <td style="padding:9px 14px;text-align:center">
          {arrow(pct(cur_c[1], prv_c[1]))}
        </td>
      </tr>
    </tbody>
  </table>
</div>"""
        self.comparison_html = html

    def action_generate(self):
        self.ensure_one()
        df, dt = self._get_dates()
        method = f'_gen_{self.report_type}'
        if hasattr(self, method):
            getattr(self, method)(df, dt)
        else:
            self._gen_executive(df, dt)
        if self.compare_previous:
            try:
                self._gen_comparison(df, dt)
            except Exception as e:
                _logger.warning("Comparaison N/N-1 erreur: %s", e)
        self.state = 'generated'
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': '✅ Rapport généré', 'type': 'success',
                           'message': f'"{self.name}" prêt avec analyse IA complète.'}}


    def action_send_email(self):
        self.ensure_one()
        if not self.email_to:
            raise UserError("Veuillez saisir une adresse email.")
        if not self.result_html:
            raise UserError("Générez d'abord le rapport.")
        mail_values = {
            'subject': f'Rapport BI — {self.name}',
            'email_to': self.email_to,
            'body_html': f"""
<div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto">
  <div style="background:#4f46e5;color:#fff;padding:20px;border-radius:8px;margin-bottom:20px">
    <div style="font-size:18px;font-weight:800">{self.name}</div>
    <div style="font-size:12px;opacity:0.85">
      Période : {self.date_from} → {self.date_to}
    </div>
  </div>
  <div style="background:#f5f3ff;border-left:4px solid #6366f1;padding:14px;
              border-radius:0 8px 8px 0;margin-bottom:16px">
    <b>Score Global :</b> {self.score_global:.1f}% &nbsp;|&nbsp;
    <b>Enregistrements :</b> {self.record_count} &nbsp;|&nbsp;
    <b>Anomalies :</b> {self.anomaly_count}
  </div>
  {self.result_html or ''}
  <div style="background:#f5f3ff;border-left:4px solid #6366f1;
              padding:14px;border-radius:0 8px 8px 0;margin-top:16px">
    <b>🤖 Analyse IA :</b><br/>
    <pre style="font-size:12px;white-space:pre-wrap">{self.ai_insight or 'Non disponible'}</pre>
  </div>
  <div style="text-align:center;font-size:10px;color:#9ca3af;margin-top:20px">
    BI Realtime — Rapport confidentiel — {self.name}
  </div>
</div>""",
            'auto_delete': True,
        }
        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()
        self.email_sent = True
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': '📧 Email envoyé',
                           'message': f'Rapport envoyé à {self.email_to}',
                           'type': 'success'}}

    def action_chat_ai(self, message):
        """Chat IA style dashboard — réponse contextuelle."""
        self.ensure_one()
        try:
            messages = json.loads(self.chat_messages or '[]')
        except Exception:
            messages = []

        df, dt = self._get_dates()
        context = (
            f"Tu es assistant BI pour un chef d\'entreprise. "
            f"Rapport: {self.name}, type: {self.report_type}, "
            f"période: {df}→{dt}, score: {self.score_global:.1f}%, "
            f"anomalies: {self.anomaly_count}. "
            f"Analyse IA disponible: {(self.ai_insight or 'aucune')[:200]}. "
            f"Question: {message}"
        )
        response = self._ask_ai(context) or "Je n\'ai pas pu analyser votre question."

        messages.append({'role': 'user', 'text': message,
                         'time': datetime.now().strftime('%H:%M')})
        messages.append({'role': 'assistant', 'text': response,
                         'time': datetime.now().strftime('%H:%M')})
        self.chat_messages = json.dumps(messages[-20:])
        return response

    def action_reset(self):
        self.write({'state': 'draft', 'result_html': False,
                    'export_file': False, 'ai_insight': False,
                    'anomaly_count': 0, 'score_global': 0,
                    'ai_chat_response': False})

    # ── Vue Exécutive (Tout) ──────────────────────────────────────
    def _gen_executive(self, df, dt):
        cr = self.env.cr
        period_str = f"{df} → {dt}"

        # Données multi-domaines
        cr.execute("""
            SELECT COALESCE(SUM(total_revenue),0),
                   COALESCE(SUM(order_count),0),
                   COALESCE(AVG(avg_order_value),0),
                   COALESCE(SUM(total_margin),0)
            FROM kpi_sales WHERE window_start::date BETWEEN %s AND %s
        """, [df, dt])
        s = cr.fetchone()
        ca, nb_cmd, panier, marge = s[0], s[1], s[2], s[3]

        cr.execute("""
            SELECT COALESCE(SUM(total_amount),0),
                   COALESCE(SUM(total_residual),0)
            FROM kpi_invoices WHERE window_start::date BETWEEN %s AND %s
        """, [df, dt])
        inv = cr.fetchone()
        total_inv, impaye = inv[0], inv[1]
        taux_recouv = (1 - impaye/total_inv)*100 if total_inv > 0 else 0

        cr.execute("""
            SELECT COALESCE(SUM(pipeline_total),0),
                   COALESCE(SUM(lead_count),0),
                   COALESCE(AVG(avg_probability),0)
            FROM kpi_crm WHERE window_start::date BETWEEN %s AND %s
        """, [df, dt])
        crm = cr.fetchone()
        pipeline, leads, proba = crm[0], crm[1], crm[2]

        cr.execute("""
            SELECT COALESCE(SUM(total_sales),0),
                   COALESCE(SUM(transaction_count),0)
            FROM kpi_pos WHERE window_start::date BETWEEN %s AND %s
        """, [df, dt])
        pos = cr.fetchone()
        pos_sales, pos_tx = pos[0], pos[1]

        # Score global (moyenne pondérée)
        score = min(100, (
            min(ca / 10000, 1) * 30 +
            min(taux_recouv / 100, 1) * 25 +
            min(proba / 100, 1) * 25 +
            min(pipeline / 50000, 1) * 20
        ) * 100 / 100)
        self.score_global = score

        taux_marge = (marge / ca * 100) if ca > 0 else 0
        summary = f"CA={ca:,.0f}€ | Pipeline={pipeline:,.0f}€ | Score={score:.0f}%"
        html = _report_header('🏢 Vue Exécutive — Tableau de Bord', period_str, summary)

        # Score jauge
        html += _section('Performance Globale', '🎯')
        html += '<div style="display:flex;gap:10px;flex-wrap:wrap">'
        html += _chart_gauge('g_score', score, 100, 'Score Global %', '#6366f1')
        html += _chart_gauge('g_recouv', taux_recouv, 100, 'Recouvrement %', '#10b981')
        html += _chart_gauge('g_proba', proba, 100, 'Proba CRM %', '#f59e0b')
        html += '</div>'

        # KPI Cards
        html += _section('Indicateurs Clés', '📊')
        html += _kpi_cards([
            ('CA Total', ca, '€', '#6366f1', None),
            ('Marge', marge, '€', '#10b981', None),
            ('Taux Marge', taux_marge, '%', '#f59e0b', None),
            ('Pipeline CRM', pipeline, '€', '#8b5cf6', None),
            ('Impayés', impaye, '€', '#ef4444', None),
            ('Recouvrement', taux_recouv, '%', '#14b8a6', None),
        ])

        # Graphique comparatif
        html += _section('Vue Comparative des Domaines', '📈')
        html += _chart_bar('bar_exec',
            ['Ventes', 'Facturation', 'CRM Pipeline', 'Point de Vente'],
            [{'label': 'Total (€)',
              'data': [float(ca), float(total_inv),
                       float(pipeline), float(pos_sales)]}],
            'Performance par domaine')

        # Camembert répartition
        total_global = ca + total_inv + pipeline + pos_sales
        if total_global > 0:
            html += _section('Répartition du Chiffre d\'Affaires', '🥧')
            html += _chart_pie('pie_exec',
                ['Ventes', 'Factures', 'CRM', 'POS'],
                [float(ca), float(total_inv),
                 float(pipeline), float(pos_sales)],
                'Répartition par domaine')

        # Données historiques pour courbe
        cr.execute("""
            SELECT window_start::date as j,
                   COALESCE(SUM(total_revenue),0)
            FROM kpi_sales WHERE window_start::date BETWEEN %s AND %s
            GROUP BY 1 ORDER BY 1
        """, [df, dt])
        hist = cr.fetchall()
        if hist:
            labels_h = [str(r[0]) for r in hist][-30:]
            vals_h = [float(r[1]) for r in hist][-30:]
            html += _section('Évolution du CA dans le Temps', '📉')
            html += _chart_line('line_exec', labels_h,
                [{'label': 'CA (€)', 'data': vals_h}],
                'Tendance CA')

        # IA analyse executive — prompt enrichi et structuré
        taux_marge_str = f"{taux_marge:.1f}%"
        prompt = f"""Tu es un conseiller stratégique senior pour un dirigeant d entreprise.
Voici les données financières et commerciales complètes pour la période {df} au {dt} :

=== PERFORMANCE FINANCIÈRE ===
- Chiffre d Affaires Total : {ca:,.0f} DT
- Marge Brute : {marge:,.0f} DT ({taux_marge_str} du CA)
- Nombre de Commandes : {int(nb_cmd)}
- Panier Moyen par Commande : {panier:,.0f} DT

=== FACTURATION & RECOUVREMENT ===
- Total Facturé : {total_inv:,.0f} DT
- Montant Impayé : {impaye:,.0f} DT
- Taux de Recouvrement : {taux_recouv:.1f}%

=== CRM & PIPELINE COMMERCIAL ===
- Pipeline Commercial Total : {pipeline:,.0f} DT
- Nombre de Leads Actifs : {int(leads)}
- Probabilité Moyenne de Conversion : {proba:.1f}%

=== POINT DE VENTE ===
- Ventes POS : {pos_sales:,.0f} DT
- Nombre de Transactions : {int(pos_tx)}

=== SCORE GLOBAL : {score:.0f}/100 ===

Génère un rapport d analyse COMPLET et STRUCTURÉ avec exactement ce format :

## 🎯 RÉSUMÉ EXÉCUTIF
[3 phrases synthétisant la situation globale de l entreprise avec les chiffres clés]

## 💚 POINTS FORTS
- [Point fort 1 avec chiffre précis et interprétation]
- [Point fort 2 avec chiffre précis et interprétation]
- [Point fort 3 avec chiffre précis et interprétation]

## 🔴 POINTS À AMÉLIORER EN URGENCE
- [Problème 1 — impact chiffré — cause probable]
- [Problème 2 — impact chiffré — cause probable]
- [Problème 3 — impact chiffré — cause probable]

## 📊 INTERPRÉTATION DES KPIs
- CA {ca:,.0f} DT : [signification et évaluation]
- Marge {taux_marge_str} : [signification — bon/moyen/faible et pourquoi]
- Recouvrement {taux_recouv:.1f}% : [signification et risque]
- Pipeline {pipeline:,.0f} DT : [signification pour la croissance future]
- Leads {int(leads)} : [signification pour l acquisition client]

## ⚠️ ALERTES & RISQUES DÉTECTÉS
- [Alerte 1 si applicable — sinon écrire RAS]
- [Alerte 2 si applicable]
- [Alerte 3 si applicable]

## 🚀 PLAN D ACTION RECOMMANDÉ
**Court terme (1-2 semaines) :**
1. [Action immédiate prioritaire avec impact attendu]
2. [Action immédiate 2]

**Moyen terme (1-3 mois) :**
1. [Action stratégique avec objectif chiffré]
2. [Action stratégique 2]

## 🎯 DÉCISION CLÉE DU DIRIGEANT
[Une décision claire, directe et actionnable que le dirigeant DOIT prendre cette semaine]

## 📈 OBJECTIFS RECOMMANDÉS POUR LE PROCHAIN MOIS
- CA cible : [valeur recommandée basée sur les données]
- Taux recouvrement cible : [valeur recommandée]
- Leads cible : [valeur recommandée]
- Score global cible : [valeur recommandée]/100"""

        insight = self._ask_ai(prompt)
        if insight:
            self.ai_insight = insight
            html += _section('Analyse & Recommandations IA', '🤖')
            html += _ai_block(insight)

        self.result_html = html
        self.record_count = int(nb_cmd + leads + pos_tx)

        # CSV synthèse
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['Indicateur', 'Valeur', 'Unité'])
        w.writerows([
            ['CA Total', f'{ca:.2f}', '€'],
            ['Marge', f'{marge:.2f}', '€'],
            ['Taux Marge', f'{taux_marge:.1f}', '%'],
            ['Total Facturé', f'{total_inv:.2f}', '€'],
            ['Impayés', f'{impaye:.2f}', '€'],
            ['Taux Recouvrement', f'{taux_recouv:.1f}', '%'],
            ['Pipeline CRM', f'{pipeline:.2f}', '€'],
            ['Nb Leads', int(leads), ''],
            ['Score Global', f'{score:.1f}', '/100'],
        ])
        self.export_file = base64.b64encode(buf.getvalue().encode('utf-8-sig'))
        self.export_fname = f'executive_{df}_{dt}.csv'

    # ── KPI Périodique ────────────────────────────────────────────
    def _gen_kpi(self, df, dt):
        cr = self.env.cr
        cr.execute("""
            SELECT 'Ventes' as d, COALESCE(SUM(total_revenue),0) as t,
                   COALESCE(AVG(total_revenue),0) as a, COUNT(*) as n
            FROM kpi_sales WHERE window_start::date BETWEEN %s AND %s
            UNION ALL
            SELECT 'Factures', COALESCE(SUM(total_amount),0),
                   COALESCE(AVG(total_amount),0), COUNT(*)
            FROM kpi_invoices WHERE window_start::date BETWEEN %s AND %s
            UNION ALL
            SELECT 'CRM', COALESCE(SUM(pipeline_total),0),
                   COALESCE(AVG(pipeline_total),0), COUNT(*)
            FROM kpi_crm WHERE window_start::date BETWEEN %s AND %s
            UNION ALL
            SELECT 'POS', COALESCE(SUM(total_sales),0),
                   COALESCE(AVG(total_sales),0), COUNT(*)
            FROM kpi_pos WHERE window_start::date BETWEEN %s AND %s
        """, [df, dt] * 4)
        rows = cr.fetchall()
        html = _report_header('📊 Rapport KPI Périodique', f'{df} → {dt}')
        html += _kpi_cards([
            (r[0], r[1], '€', COLORS[i], None)
            for i, r in enumerate(rows)
        ])
        labels = [r[0] for r in rows]
        html += _chart_bar('bar_kpi', labels,
            [{'label': 'Total (€)', 'data': [float(r[1]) for r in rows]}],
            'KPI par domaine')
        html += _chart_pie('pie_kpi', labels,
            [float(r[1]) for r in rows], 'Répartition')
        thead = ['Domaine', 'Total (€)', 'Moyenne', 'Fenêtres']
        trows = [(r[0], f'{r[1]:,.2f}', f'{r[2]:,.2f}', r[3]) for r in rows]
        html += _html_table(thead, trows, 'Détail')
        prompt = (f"KPI {df}→{dt}: "
                  + ', '.join(f"{r[0]}={r[1]:,.0f}€" for r in rows)
                  + ". Résumé exécutif et 3 recommandations.")
        insight = self._ask_ai(prompt)
        if insight:
            self.ai_insight = insight
            html += _ai_block(insight)
        self.result_html = html
        self.record_count = sum(r[3] for r in rows)
        buf = io.StringIO()
        csv.writer(buf).writerows([thead] + list(trows))
        self.export_file = base64.b64encode(buf.getvalue().encode('utf-8-sig'))
        self.export_fname = f'kpi_{df}_{dt}.csv'

    # ── Ventes ────────────────────────────────────────────────────
    def _gen_sales(self, df, dt):
        cr = self.env.cr
        cr.execute("""
            SELECT window_start::date as jour,
                   COALESCE(SUM(total_revenue),0) as ca,
                   COALESCE(SUM(order_count),0) as cmd,
                   COALESCE(AVG(avg_order_value),0) as panier,
                   COALESCE(SUM(total_margin),0) as marge
            FROM kpi_sales WHERE window_start::date BETWEEN %s AND %s
            GROUP BY 1 ORDER BY 1 DESC LIMIT 60
        """, [df, dt])
        data = [{'jour': str(r[0]), 'ca': r[1], 'cmd': r[2],
                 'panier': r[3], 'marge': r[4]}
                for r in cr.fetchall()]
        total_ca = sum(r['ca'] for r in data)
        total_cmd = sum(r['cmd'] for r in data)
        total_marge = sum(r['marge'] for r in data)
        taux_m = (total_marge/total_ca*100) if total_ca > 0 else 0

        html = _report_header('💰 Rapport Ventes', f'{df} → {dt}',
                              f'CA={total_ca:,.0f}€ | Marge={taux_m:.1f}%')
        html += _kpi_cards([
            ('CA Total', total_ca, '€', '#6366f1', None),
            ('Nb Commandes', total_cmd, '', '#10b981', None),
            ('Marge Totale', total_marge, '€', '#f59e0b', None),
            ('Taux de Marge', taux_m, '%', '#3b82f6', None),
        ])
        labels = [r['jour'] for r in reversed(data)][-30:]
        html += _chart_line('line_sales', labels, [
            {'label': 'CA (€)', 'data': [float(r['ca']) for r in reversed(data)][-30:]},
            {'label': 'Marge (€)', 'data': [float(r['marge']) for r in reversed(data)][-30:]},
        ], 'Évolution CA et Marge')
        html += _chart_bar('bar_sales', labels, [
            {'label': 'Commandes', 'data': [float(r['cmd']) for r in reversed(data)][-30:]},
        ], 'Évolution Commandes')
        anomalies = _detect_anomalies(data, 'ca', 'CA')
        self.anomaly_count = len(anomalies)
        if anomalies: html += _anomaly_block(anomalies)
        thead = ['Date', 'CA (€)', 'Commandes', 'Panier (€)', 'Marge (€)']
        trows = [(r['jour'], f"{r['ca']:,.2f}", int(r['cmd']),
                  f"{r['panier']:,.2f}", f"{r['marge']:,.2f}") for r in data]
        html += _html_table(thead, trows, 'Détail journalier')
        prompt = (f"Ventes {df}→{dt}: CA={total_ca:,.0f}€, "
                  f"commandes={int(total_cmd)}, marge={taux_m:.1f}%, "
                  f"anomalies={len(anomalies)}. "
                  f"Résumé + 3 actions commerciales prioritaires.")
        insight = self._ask_ai(prompt)
        if insight:
            self.ai_insight = insight
            html += _ai_block(insight)
        self.result_html = html
        self.record_count = len(data)
        buf = io.StringIO()
        csv.writer(buf).writerows([thead] + list(trows))
        self.export_file = base64.b64encode(buf.getvalue().encode('utf-8-sig'))
        self.export_fname = f'ventes_{df}_{dt}.csv'

    # ── Facturation ───────────────────────────────────────────────
    def _gen_invoice(self, df, dt):
        cr = self.env.cr
        cr.execute("""
            SELECT window_start::date as jour, payment_state,
                   COALESCE(SUM(total_amount),0),
                   COALESCE(SUM(total_residual),0),
                   COALESCE(SUM(invoice_count),0)
            FROM kpi_invoices WHERE window_start::date BETWEEN %s AND %s
            GROUP BY 1,2 ORDER BY 1 DESC LIMIT 100
        """, [df, dt])
        rows = cr.fetchall()
        total_m = sum(r[2] for r in rows)
        total_r = sum(r[3] for r in rows)
        paid = total_m - total_r
        taux = (paid/total_m*100) if total_m > 0 else 0

        html = _report_header('🧾 Rapport Facturation', f'{df} → {dt}',
                              f'Recouvrement={taux:.1f}%')
        html += _kpi_cards([
            ('Total Facturé', total_m, '€', '#6366f1', None),
            ('Payé', paid, '€', '#10b981', None),
            ('Impayés', total_r, '€', '#ef4444', None),
            ('Taux Recouvrement', taux, '%', '#14b8a6', None),
        ])
        html += _chart_pie('pie_inv', ['Payé', 'Impayé'],
                           [float(paid), float(total_r)],
                           'Répartition Payé / Impayé')
        html += _chart_gauge('g_inv', taux, 100,
                             'Taux recouvrement %', '#10b981')
        anomalies = []
        if taux < 70:
            anomalies.append(f"Taux critique : {taux:.1f}% (cible ≥ 80%)")
        if anomalies:
            html += _anomaly_block(anomalies)
            self.anomaly_count = len(anomalies)
        thead = ['Date', 'État', 'Montant (€)', 'Impayés (€)', 'Nb']
        trows = [(str(r[0]), r[1] or '-', f'{r[2]:,.2f}',
                  f'{r[3]:,.2f}', int(r[4])) for r in rows]
        html += _html_table(thead, trows, 'Détail')
        prompt = (f"Facturation {df}→{dt}: total={total_m:,.0f}€, "
                  f"impayés={total_r:,.0f}€, recouvrement={taux:.1f}%. "
                  f"Analyse et 3 recommandations.")
        insight = self._ask_ai(prompt)
        if insight:
            self.ai_insight = insight
            html += _ai_block(insight)
        self.result_html = html
        self.record_count = len(rows)
        buf = io.StringIO()
        csv.writer(buf).writerows([thead] + list(trows))
        self.export_file = base64.b64encode(buf.getvalue().encode('utf-8-sig'))
        self.export_fname = f'facturation_{df}_{dt}.csv'

    # ── CRM ───────────────────────────────────────────────────────
    def _gen_crm(self, df, dt):
        cr = self.env.cr
        cr.execute("""
            SELECT window_start::date as jour,
                   COALESCE(SUM(pipeline_total),0),
                   COALESCE(SUM(lead_count),0),
                   COALESCE(AVG(avg_probability),0)
            FROM kpi_crm WHERE window_start::date BETWEEN %s AND %s
            GROUP BY 1 ORDER BY 1 DESC LIMIT 60
        """, [df, dt])
        data = [{'jour': str(r[0]), 'pipeline': r[1],
                 'leads': r[2], 'proba': r[3]}
                for r in cr.fetchall()]
        total_p = sum(r['pipeline'] for r in data)
        total_l = sum(r['leads'] for r in data)
        avg_pr = sum(r['proba'] for r in data)/len(data) if data else 0
        valeur_prevue = total_p * avg_pr / 100

        html = _report_header('🎯 Rapport CRM + Prévisions', f'{df} → {dt}',
                              f'Pipeline={total_p:,.0f}€ | Prévision={valeur_prevue:,.0f}€')
        html += _kpi_cards([
            ('Pipeline Total', total_p, '€', '#6366f1', None),
            ('Nb Leads', total_l, '', '#10b981', None),
            ('Probabilité Moy.', avg_pr, '%', '#f59e0b', None),
            ('Valeur Prévue', valeur_prevue, '€', '#8b5cf6', None),
        ])
        labels = [r['jour'] for r in reversed(data)][-30:]
        html += _chart_line('line_crm', labels, [
            {'label': 'Pipeline (€)',
             'data': [float(r['pipeline']) for r in reversed(data)][-30:]},
        ], 'Évolution Pipeline')
        html += _chart_bar('bar_crm_leads', labels, [
            {'label': 'Nb Leads',
             'data': [float(r['leads']) for r in reversed(data)][-30:]},
        ], 'Évolution Leads')
        html += _chart_gauge('g_crm', avg_pr, 100,
                             'Probabilité moyenne %', '#8b5cf6')
        anomalies = _detect_anomalies(data, 'pipeline', 'Pipeline')
        self.anomaly_count = len(anomalies)
        if anomalies: html += _anomaly_block(anomalies)
        thead = ['Date', 'Pipeline (€)', 'Leads', 'Proba (%)']
        trows = [(r['jour'], f"{r['pipeline']:,.2f}",
                  int(r['leads']), f"{r['proba']:.1f}%") for r in data]
        html += _html_table(thead, trows, 'Détail CRM')
        prompt = (f"CRM {df}→{dt}: pipeline={total_p:,.0f}€, "
                  f"leads={int(total_l)}, probabilité={avg_pr:.1f}%, "
                  f"valeur prévue={valeur_prevue:,.0f}€. "
                  f"Prévision 30j et stratégie conversion.")
        insight = self._ask_ai(prompt)
        if insight:
            self.ai_insight = insight
            html += _ai_block(insight)
        self.result_html = html
        self.record_count = len(data)
        buf = io.StringIO()
        csv.writer(buf).writerows([thead] + list(trows))
        self.export_file = base64.b64encode(buf.getvalue().encode('utf-8-sig'))
        self.export_fname = f'crm_{df}_{dt}.csv'

    # ── Stocks ────────────────────────────────────────────────────
    def _gen_stock(self, df, dt):
        cr = self.env.cr
        cr.execute("""
            SELECT product_name,
                   COALESCE(SUM(total_qty),0) as qty,
                   COALESCE(SUM(move_count),0) as nb
            FROM kpi_stock_moves
            WHERE window_start::date BETWEEN %s AND %s
            GROUP BY product_name ORDER BY qty DESC LIMIT 20
        """, [df, dt])
        rows = cr.fetchall()
        html = _report_header('📦 Rapport Stocks', f'{df} → {dt}')
        if rows:
            labels = [r[0][:20] if r[0] else 'N/A' for r in rows[:10]]
            vals = [float(r[1]) for r in rows[:10]]
            html += _chart_bar('bar_stock', labels,
                [{'label': 'Quantité', 'data': vals}],
                'Top 10 produits par quantité')
            html += _chart_pie('pie_stock', labels[:6], vals[:6],
                               'Répartition top 6 produits')
        thead = ['Produit', 'Quantité totale', 'Nb mouvements']
        trows = [(r[0] or 'N/A', f'{r[1]:,.2f}', int(r[2])) for r in rows]
        html += _html_table(thead, trows, 'Top produits')
        total_qty = sum(r[1] for r in rows)
        prompt = (f"Stocks {df}→{dt}: {len(rows)} produits, "
                  f"quantité totale={total_qty:,.0f}. "
                  f"Top 5: {[(r[0],f'{r[1]:.0f}') for r in rows[:5]]}. "
                  f"Analyse et recommandations supply chain.")
        insight = self._ask_ai(prompt)
        if insight:
            self.ai_insight = insight
            html += _ai_block(insight)
        self.result_html = html
        self.record_count = len(rows)
        buf = io.StringIO()
        csv.writer(buf).writerows([thead] + list(trows))
        self.export_file = base64.b64encode(buf.getvalue().encode('utf-8-sig'))
        self.export_fname = f'stocks_{df}_{dt}.csv'

    # ── Alertes ───────────────────────────────────────────────────
    def _gen_alert(self, df, dt):
        alerts = self.env['bi.alert.rule'].sudo().search_read(
            [], ['name', 'kpi_name', 'operator', 'threshold',
                 'last_triggered', 'active'], limit=200)
        actives = sum(1 for a in alerts if a['active'])
        triggered = sum(1 for a in alerts if a['last_triggered'])
        kpi_counts = {}
        for a in alerts:
            k = a['kpi_name'] or 'Autre'
            kpi_counts[k] = kpi_counts.get(k, 0) + 1

        html = _report_header('🔔 Rapport Alertes', f'{df} → {dt}')
        html += _kpi_cards([
            ('Total Règles', len(alerts), '', '#6366f1', None),
            ('Actives', actives, '', '#10b981', None),
            ('Déclenchées', triggered, '', '#f59e0b', None),
            ('Inactives', len(alerts)-actives, '', '#6b7280', None),
        ])
        if kpi_counts:
            html += _chart_bar('bar_alerts',
                list(kpi_counts.keys()),
                [{'label': 'Nb règles', 'data': list(kpi_counts.values())}],
                'Règles par KPI')
            html += _chart_pie('pie_alerts',
                list(kpi_counts.keys()),
                list(kpi_counts.values()),
                'Répartition par KPI')
        thead = ['Règle', 'KPI', 'Condition', 'Seuil', 'Dernière alerte', 'Active']
        trows = [(a['name'], a['kpi_name'] or '-', a['operator'] or '-',
                  a['threshold'],
                  str(a['last_triggered'])[:16] if a['last_triggered'] else 'Jamais',
                  '✅' if a['active'] else '❌') for a in alerts]
        html += _html_table(thead, trows, 'Règles d\'alerte')
        prompt = (f"Monitoring {len(alerts)} alertes, {actives} actives, "
                  f"{triggered} déclenchées. KPIs: {list(kpi_counts.keys())}. "
                  f"Évalue la couverture et recommande des améliorations.")
        insight = self._ask_ai(prompt)
        if insight:
            self.ai_insight = insight
            html += _ai_block(insight)
        self.result_html = html
        self.record_count = len(alerts)
        buf = io.StringIO()
        csv.writer(buf).writerows([thead] + list(trows))
        self.export_file = base64.b64encode(buf.getvalue().encode('utf-8-sig'))
        self.export_fname = f'alertes_{df}_{dt}.csv'
