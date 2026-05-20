
# -*- coding: utf-8 -*-
{
    'name': 'AKREM BI Realtime',
    'version': '17.0.6.4.0',
    'category': 'Reporting',
    'summary': 'Live KPI dashboards synced with Odoo (sales, invoices, CRM, stock, POS)',
    'description': """
        BI Realtime for Odoo 17
        =======================
        * Interactive drag & drop dashboards (Chart.js, 6 themes)
        * KPIs from native Odoo models (sales, accounting, CRM, stock, purchase, POS)
        * Real-time refresh via Odoo Bus when documents are created or posted
        * DAX-style measures, email alerts, N vs N-1 comparisons
        * PDF reports and Excel / JSON export
        * Optional AI assistant (configurable API URL)
        * Role-based security

        Works standalone inside Odoo — no external infrastructure required.
    """,
    'author': 'AKREM.KHELIFI',
    'website': 'https://github.com/Akremjs/bi-realtime-odoo17',
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

