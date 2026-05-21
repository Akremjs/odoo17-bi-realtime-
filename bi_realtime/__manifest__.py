
# -*- coding: utf-8 -*-
{
    'name': 'BI Realtime',
    'version': '17.0.7.0.0',
    'category': 'Reporting',
    'summary': 'Live KPI dashboards & BI cockpit — sales, finance, CRM, stock, POS (Odoo Bus)',
    'description': """
BI Realtime — Business Intelligence for Odoo 17
================================================

Interactive dashboards with real-time KPI refresh when you post invoices,
confirm sales orders or win CRM opportunities.

* Drag & drop dashboards, 18+ Chart.js charts, 6 themes
* Sales, CRM, Accounting, Inventory, Purchase, HR, POS
* Odoo Bus live sync, email alerts, PDF reports, optional AI
* Custom KPIs, DAX-style measures, N vs N-1 comparisons

Author: AKREM.KHELIFI
https://github.com/Akremjs/BI-Realtime-Dashboard
    """,
    'author': 'AKREM.KHELIFI',
    'website': 'https://github.com/Akremjs/BI-Realtime-Dashboard',
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
            'bi_realtime/static/src/js/chart.umd.min.js',
            'bi_realtime/static/src/css/dashboard.css',
            'bi_realtime/static/src/css/dashboard_layout.css',
            'bi_realtime/static/src/css/dax_editor.css',
            'bi_realtime/static/src/xml/dashboard_template.xml',
            'bi_realtime/static/src/js/dashboard_layout.js',
            'bi_realtime/static/src/js/dashboard_export_excel.js',
            'bi_realtime/static/src/js/dashboard_realtime.js',
            'bi_realtime/static/src/js/dax_editor.js',
            'bi_realtime/static/src/js/dashboard_widget.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'external_dependencies': {'python': ['requests']},
}
