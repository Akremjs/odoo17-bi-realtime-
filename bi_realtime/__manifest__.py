
# -*- coding: utf-8 -*-
{
    'name': 'AKREM BI Realtime',
    'version': '17.0.6.5.1',
    'category': 'Reporting',
    'summary': 'Live KPI dashboards & BI cockpit — sales, finance, CRM, stock, POS (real-time Odoo Bus)',
    'description': """
AKREM BI Realtime — Business Intelligence for Odoo 17
=======================================================

Turn your Odoo data into interactive dashboards that update in real time when
you confirm orders, post invoices or win opportunities.

Highlights
----------
* Drag & drop dashboards, 18+ Chart.js charts, 6 themes
* Departments: Sales, CRM, Accounting, Inventory, Purchase, HR, POS
* Real-time KPI refresh via Odoo Bus (LIVE badge)
* Custom KPIs, DAX-style measures, N vs N-1 comparisons, email alerts
* PDF executive reports, Excel / JSON export, optional AI assistant
* 100% native Odoo data — no external stack required for standard use

Author: AKREM.KHELIFI — https://github.com/Akremjs/BI-Realtime
    """,
    'author': 'AKREM.KHELIFI',
    'website': 'https://github.com/Akremjs/BI-Realtime',
    'maintainer': 'AKREM.KHELIFI',
    'depends': [
        'base', 'sale', 'stock', 'account',
        'web', 'bus', 'crm', 'point_of_sale',
        'purchase', 'hr', 'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/bi_config_data.xml',
        'data/bi_cron.xml',
        'views/bi_kpi_views.xml',
        'views/bi_dashboard_wizard_views.xml',
        'views/bi_dashboard_views.xml',
        'views/bi_todo_views.xml',
        'views/bi_comment_views.xml',
        'views/bi_dax_views.xml',
        'views/bi_kpi_history_views.xml',
        'views/bi_report_views.xml',
        'views/bi_alert_rule_views.xml',
        'views/bi_comparison_views.xml',
        'report/bi_report_pdf.xml',
        'views/bi_ai_proactive_views.xml',
        'views/bi_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'bi_realtime/static/src/js/report_chat.js',
            # Chart.js EN PREMIER (lib legacy, avant modules OWL)
            'bi_realtime/static/src/js/chart.umd.min.js',
            # CSS
            'bi_realtime/static/src/css/dashboard.css',
            'bi_realtime/static/src/css/dashboard_layout.css',
            'bi_realtime/static/src/css/dax_editor.css',
            # XML templates OWL
            'bi_realtime/static/src/xml/dashboard_template.xml',
            # JS modules (ordre important)
            'bi_realtime/static/src/js/dashboard_layout.js',
            'bi_realtime/static/src/js/dashboard_export_excel.js',
            'bi_realtime/static/src/js/dashboard_realtime.js',
            'bi_realtime/static/src/js/dax_editor.js',
            # EN DERNIER: enregistre l'action dans le registry
            'bi_realtime/static/src/js/dashboard_widget.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'external_dependencies': {'python': ['requests']},
}

