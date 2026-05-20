
/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onMounted, onWillUnmount, useState, useRef, useEffect } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { initNativeDragDrop, restoreLayout, SIZE_TO_COLS } from "./dashboard_layout";
import { exportKpiToExcel, exportDashboardToExcel } from "./dashboard_export_excel";
import { useRealtimeRefresh } from "./dashboard_realtime";

// ─── Filtres date ───────────────────────────────────────────────────────────
const DATE_FILTERS = [
    { value: 'today',         label: "Aujourd'hui",       icon: '📅' },
    { value: 'yesterday',     label: 'Hier',              icon: '📅' },
    { value: 'this_week',     label: 'Cette semaine',     icon: '📅' },
    { value: 'last_week',     label: 'Semaine dernière',  icon: '📅' },
    { value: 'last_7_days',   label: '7 derniers jours',  icon: '📅' },
    { value: 'last_14_days',  label: '14 derniers jours', icon: '📅' },
    { value: 'last_30_days',  label: '30 derniers jours', icon: '📅' },
    { value: 'this_month',    label: 'Ce mois',           icon: '📅' },
    { value: 'last_month',    label: 'Mois dernier',      icon: '📅' },
    { value: 'last_3_months', label: '3 derniers mois',   icon: '📅' },
    { value: 'last_6_months', label: '6 derniers mois',   icon: '📅' },
    { value: 'this_quarter',  label: 'Ce trimestre',      icon: '📅' },
    { value: 'last_quarter',  label: 'Trimestre dernier', icon: '📅' },
    { value: 'this_year',     label: 'Cette année',       icon: '📅' },
    { value: 'last_year',     label: 'Année dernière',    icon: '📅' },
    { value: 'last_365_days', label: '365 derniers jours',icon: '📅' },
    { value: 'all_time',      label: 'Tout',              icon: '📅' },
    { value: 'custom',        label: 'Personnalisé',      icon: '🗓️' },
];

// ─── Thèmes ─────────────────────────────────────────────────────────────────
const THEMES = {
    light:     { bg:'#f4f6fb', card:'#fff',     nav:'#fff',     text:'#1a1f36', sub:'#8a94a6', border:'#e8ecf4' },
    dark:      { bg:'#0f1117', card:'#1a1d2e',  nav:'#1a1d2e',  text:'#e8eaf6', sub:'#6b7280', border:'#2d3148' },
    corporate: { bg:'#f0f4f8', card:'#fff',     nav:'#1e3a5f',  text:'#1e3a5f', sub:'#5a7a96', border:'#d0dde8' },
    ocean:     { bg:'#e8f4f8', card:'#fff',     nav:'#006994',  text:'#004d6e', sub:'#4a8fa8', border:'#b3d9e8' },
    sunset:    { bg:'#fff5f0', card:'#fff',     nav:'#e55a2b',  text:'#8b2500', sub:'#b85c30', border:'#fdd5c0' },
    forest:    { bg:'#f0f8f0', card:'#fff',     nav:'#2e7d32',  text:'#1b5e20', sub:'#4a7f4c', border:'#c8e6c9' },
};

// ─── Types de graphiques lisibles ───────────────────────────────────────────
const CHART_TYPES = [
    { value:'indicator', label:'Indicateur',     icon:'🔢' },
    { value:'counter',   label:'Compteur',        icon:'🧮' },
    { value:'bar',       label:'Barres',          icon:'📊' },
    { value:'hbar',      label:'Barres horiz.',   icon:'↔️' },
    { value:'line',      label:'Courbe',          icon:'📈' },
    { value:'area',      label:'Aire',            icon:'📉' },
    { value:'pie',       label:'Camembert',       icon:'🥧' },
    { value:'doughnut',  label:'Donut',           icon:'🍩' },
    { value:'radar',     label:'Radar',           icon:'🕸️' },
    { value:'polarArea', label:'Polaire',         icon:'🌀' },
    { value:'funnel',    label:'Entonnoir',       icon:'🔻' },
    { value:'scatter',   label:'Nuage de pts',    icon:'✨' },
    { value:'table',     label:'Tableau',         icon:'📋' },
    { value:'bullet',    label:'Bullet',          icon:'🎯' },
    { value:'radial',    label:'Gauge',           icon:'⭕' },
    { value:'flower',    label:'Fleur',           icon:'🌸' },
    { value:'mixed',     label:'Combiné',         icon:'📊' },
];

// ─── Modules disponibles pour dashboard IA ──────────────────────────────────
const AVAILABLE_MODULES = [
    { key:'sale',     label:'Ventes',         icon:'💰', model:'sale.order',       color:'#6366f1' },
    { key:'crm',      label:'CRM',            icon:'🤝', model:'crm.lead',         color:'#f43f5e' },
    { key:'stock',    label:'Stock',          icon:'📦', model:'stock.picking',    color:'#10b981' },
    { key:'account',  label:'Comptabilité',   icon:'📊', model:'account.move',     color:'#f59e0b' },
    { key:'pos',      label:'Point de vente', icon:'🛒', model:'pos.order',        color:'#8b5cf6' },
    { key:'purchase', label:'Achats',         icon:'🛍️', model:'purchase.order',  color:'#06b6d4' },
    { key:'hr',       label:'Ressources hum.',icon:'👥', model:'hr.employee',      color:'#ec4899' },
];

// ─── Messages IA prédéfinis par module ───────────────────────────────────────
// ─── Comptage KPIs par module (utilisé dans le template XML) ────────────────
const AI_MODULE_CONFIG_COUNTS = {
    sale: '5 KPIs', crm: '5 KPIs', stock: '5 KPIs',
    account: '5 KPIs', pos: '5 KPIs', purchase: '4 KPIs', hr: '3 KPIs',
};

const AI_MODULE_CONFIG = {
    sale: {
        kpis: [
            { name: "Chiffre d'affaires total",  chart_type:'indicator', color:'#6366f1', widget_size:'medium' },
            { name: "Nombre de commandes",        chart_type:'counter',   color:'#f43f5e', widget_size:'small'  },
            { name: "Valeur moyenne commande",    chart_type:'indicator', color:'#10b981', widget_size:'small'  },
            { name: "Ventes par période",         chart_type:'bar',       color:'#6366f1', widget_size:'large'  },
            { name: "Top produits vendus",        chart_type:'doughnut',  color:'#f59e0b', widget_size:'medium' },
        ]
    },
    crm: {
        kpis: [
            { name: "Opportunités actives",       chart_type:'counter',   color:'#f43f5e', widget_size:'small'  },
            { name: "Pipeline total",             chart_type:'indicator', color:'#6366f1', widget_size:'medium' },
            { name: "Taux de conversion",         chart_type:'radial',    color:'#10b981', widget_size:'medium' },
            { name: "Opportunités par étape",     chart_type:'funnel',    color:'#f43f5e', widget_size:'large'  },
            { name: "Leads par source",           chart_type:'pie',       color:'#8b5cf6', widget_size:'medium' },
        ]
    },
    stock: {
        kpis: [
            { name: "Transferts en cours",        chart_type:'counter',   color:'#10b981', widget_size:'small'  },
            { name: "Valeur du stock",            chart_type:'indicator', color:'#6366f1', widget_size:'medium' },
            { name: "Produits en rupture",        chart_type:'counter',   color:'#f43f5e', widget_size:'small'  },
            { name: "Mouvements par type",        chart_type:'bar',       color:'#10b981', widget_size:'large'  },
            { name: "Top produits stockés",       chart_type:'doughnut',  color:'#f59e0b', widget_size:'medium' },
        ]
    },
    account: {
        kpis: [
            { name: "Factures émises",            chart_type:'counter',   color:'#f59e0b', widget_size:'small'  },
            { name: "Chiffre d'affaires facturé", chart_type:'indicator', color:'#6366f1', widget_size:'medium' },
            { name: "Impayés en cours",           chart_type:'indicator', color:'#f43f5e', widget_size:'medium' },
            { name: "Évolution facturation",      chart_type:'line',      color:'#f59e0b', widget_size:'large'  },
            { name: "Répartition par statut",     chart_type:'doughnut',  color:'#8b5cf6', widget_size:'medium' },
        ]
    },
    pos: {
        kpis: [
            { name: "Ventes du jour",             chart_type:'indicator', color:'#8b5cf6', widget_size:'medium' },
            { name: "Nombre transactions",        chart_type:'counter',   color:'#6366f1', widget_size:'small'  },
            { name: "Panier moyen",               chart_type:'indicator', color:'#10b981', widget_size:'small'  },
            { name: "Ventes par heure",           chart_type:'bar',       color:'#8b5cf6', widget_size:'large'  },
            { name: "Top produits caisse",        chart_type:'doughnut',  color:'#f59e0b', widget_size:'medium' },
        ]
    },
    purchase: {
        kpis: [
            { name: "Commandes fournisseurs",     chart_type:'counter',   color:'#06b6d4', widget_size:'small'  },
            { name: "Montant total achats",       chart_type:'indicator', color:'#6366f1', widget_size:'medium' },
            { name: "Achats par fournisseur",     chart_type:'bar',       color:'#06b6d4', widget_size:'large'  },
            { name: "Répartition par catégorie",  chart_type:'pie',       color:'#f59e0b', widget_size:'medium' },
        ]
    },
    hr: {
        kpis: [
            { name: "Total employés",             chart_type:'counter',   color:'#ec4899', widget_size:'small'  },
            { name: "Nouveaux recrutements",      chart_type:'counter',   color:'#10b981', widget_size:'small'  },
            { name: "Employés par département",   chart_type:'doughnut',  color:'#ec4899', widget_size:'medium' },
        ]
    },
};

/** Carte unique : libellé KPI → agrégation / champ / modèle (évite doublons de logique IA vs prédéfinis). */
const KPI_FIELD_MAP = {
    "Chiffre d'affaires total":    { agg: 'sum',   field: 'amount_total',      model: 'sale.order',      domain: [['state','in',['sale','done']]] },
    "Nombre de commandes":          { agg: 'count', field: null,                model: 'sale.order',      domain: [['state','in',['sale','done']]] },
    "Valeur moyenne commande":      { agg: 'avg',   field: 'amount_total',      model: 'sale.order',      domain: [['state','in',['sale','done']]] },
    "Marge totale (ventes)":       { agg: 'sum',   field: 'margin',            model: 'sale.order',      domain: [['state','in',['sale','done']]], altField: 'amount_untaxed' },
    "Opportunités actives":         { agg: 'count', field: null,                model: 'crm.lead',        domain: [['active','=',true],['type','=','opportunity']] },
    "Pipeline total":               { agg: 'sum',   field: 'expected_revenue',  model: 'crm.lead',        domain: [['active','=',true]] },
    "Taux de conversion":           { agg: 'count', field: null,                model: 'crm.lead',        domain: [['stage_id.is_won','=',true]] },
    "Transferts en cours":          { agg: 'count', field: null,                model: 'stock.picking',   domain: [['state','=','assigned']] },
    "Valeur du stock":              { agg: 'sum',   field: 'value',             model: 'stock.valuation.layer', domain: [] },
    "Produits en rupture":          { agg: 'count', field: null,                model: 'product.product', domain: [['qty_available','<=',0],['active','=',true]] },
    "Factures émises":              { agg: 'count', field: null,                model: 'account.move',    domain: [['move_type','=','out_invoice'],['state','=','posted']] },
    "Chiffre d'affaires facturé":   { agg: 'sum',   field: 'amount_total',      model: 'account.move',    domain: [['move_type','=','out_invoice'],['state','=','posted']] },
    "Impayés en cours":             { agg: 'sum',   field: 'amount_residual',   model: 'account.move',    domain: [['move_type','=','out_invoice'],['payment_state','=','not_paid'],['state','=','posted']] },
    "Ventes du jour":               { agg: 'sum',   field: 'amount_total',      model: 'pos.order',       domain: [['state','in',['done','paid']]] },
    "Nombre transactions":          { agg: 'count', field: null,                model: 'pos.order',       domain: [['state','in',['done','paid']]] },
    "Panier moyen":                 { agg: 'avg',   field: 'amount_total',      model: 'pos.order',       domain: [['state','in',['done','paid']]] },
    "Commandes fournisseurs":       { agg: 'count', field: null,                model: 'purchase.order',  domain: [['state','in',['purchase','done']]] },
    "Montant total achats":         { agg: 'sum',   field: 'amount_total',      model: 'purchase.order',  domain: [['state','in',['purchase','done']]] },
    "Total employés":               { agg: 'count', field: null,                model: 'hr.employee',     domain: [['active','=',true]] },
    "Nouveaux recrutements":        { agg: 'count', field: null,                model: 'hr.applicant',    domain: [['active','=',true]] },
    "Ventes par période":           { agg: 'sum',   field: 'amount_total',      model: 'sale.order',      domain: [['state','in',['sale','done']]] },
    "Top produits vendus":          { agg: 'sum',   field: 'price_subtotal',    model: 'sale.order.line', domain: [['order_id.state','in',['sale','done']]] },
    "Opportunités par étape":       { agg: 'count', field: null,                model: 'crm.lead',        domain: [['active','=',true]] },
    "Leads par source":             { agg: 'count', field: null,                model: 'crm.lead',        domain: [] },
    "Mouvements par type":          { agg: 'count', field: null,                model: 'stock.picking',   domain: [] },
    "Top produits stockés":         { agg: 'sum',   field: 'qty_available',   model: 'product.product', domain: [['active','=',true],['qty_available','>',0]] },
    "Évolution facturation":        { agg: 'sum',   field: 'amount_total',      model: 'account.move',    domain: [['move_type','=','out_invoice'],['state','=','posted']] },
    "Répartition par statut":       { agg: 'count', field: null,                model: 'account.move',    domain: [['move_type','=','out_invoice']] },
    "Ventes par heure":             { agg: 'sum',   field: 'amount_total',      model: 'pos.order',       domain: [['state','in',['done','paid']]] },
    "Top produits caisse":          { agg: 'sum',   field: 'price_subtotal',    model: 'pos.order.line',  domain: [] },
    "Achats par fournisseur":       { agg: 'sum',   field: 'amount_total',      model: 'purchase.order',  domain: [['state','in',['purchase','done']]] },
    "Répartition par catégorie":    { agg: 'sum',   field: 'amount_total',      model: 'purchase.order',  domain: [] },
    "Employés par département":     { agg: 'count', field: null,                model: 'hr.employee',     domain: [['active','=',true]] },
};

/** Anciens libellés / prédéfinis Odoo → clé canonique dans KPI_FIELD_MAP */
const KPI_NAME_ALIASES = {
    "CA Total": "Chiffre d'affaires total",
    "Nb Commandes": "Nombre de commandes",
    "Valeur Moyenne Commande": "Valeur moyenne commande",
    "Marge Totale": "Marge totale (ventes)",
    "Nombre factures": "Factures émises",
    "Évolution CA mensuel": "Ventes par période",
};

function resolveKpiFieldMapping(displayName) {
    const key = KPI_NAME_ALIASES[displayName] || displayName;
    const spec = KPI_FIELD_MAP[key] || KPI_FIELD_MAP[displayName];
    if (spec) {
        return spec;
    }
    return { agg: 'count', field: null, model: null, domain: [] };
}

class BiDashboardWidget extends Component {
    static template = "bi_realtime.DashboardWidget";

    setup() {
        this.rpc          = useService("rpc");
        this.action       = useService("action");
        this.notification = useService("notification");
        this.charts       = {};
        this.globalChart  = null;
        this._drillChart  = null;
        this._dragDrop    = null;
        this.globalChartRef = useRef('globalChart');

        this.state = useState({
            kpis: [], dashboards: [], filteredKpis: [],
            formattedValues: {}, percentages: {}, iconUrls: {},
            evolutionPct: {}, alerts: [], tableData: {},
            todos: [], filteredTodos: [],
            todoStats: { total:0, done:0, pct:0 },
            todoFilter: 'all', showAddTodo: false,
            newTodoName: '', newTodoPriority: 'medium', newTodoDeadline: '',
            activeTab: null, loading: true, currentTime: "",

            // Filtres date
            dateFilters: DATE_FILTERS,
            globalDateFilter: 'this_month',
            showDateFilterMenu: false,
            customDateFrom: '',
            customDateTo: '',

            // Bookmarks
            bookmarkedDashboardIds: [],
            showBookmarksOnly: false,

            // Thème
            currentTheme: 'light',
            showThemeMenu: false,

            // RTL
            rtlMode: false,

            // Drill down
            drillModal: null,
            drillHistory: [],

            // Edit rapide
            editingKpi: null, showEditModal: false,

            // Export
            exportModal: null,

            // Switch layout
            switchModal: null,
            chartTypes: CHART_TYPES,

            // Chat interne KPI
            chatModal: null,
            chatPollingId: null,

            // Import CSV/Excel
            showImportModal: false,
            importPreview: null,
            importFile: null,

            // ✅ NOUVEAU: Dashboard IA prédéfini
            installedModules: [],
            showAiDashboardModal: false,
            aiSelectedModules: [],
            aiGenerating: false,
            aiProgress: '',
            aiMessages: [],
            aiChatInput: '',

            // ── Flux prévisualisation KPIs ───────────────────────────
            aiStep: 'select',        // 'select' | 'preview' | 'generating' | 'done'
            aiPreviewData: [],       // liste des modules avec leurs KPIs proposés
            aiKpiSelections: {},     // { 'sale_0': true/false, ... }
            aiKpiEdits: {},          // { 'sale_0': { chart_type, color, widget_size } }

            // Modules installés (détectés dynamiquement)
            installedModuleKeys: [],

            // ✅ NOUVEAU: Chatbot IA flottant
            showAiChatbot: false,
            aiChatbotMessages: [
                { role: 'assistant', text: "👋 Bonjour ! Je suis votre assistant BI. Posez-moi des questions sur vos données, demandez des analyses ou demandez-moi de créer des dashboards.", time: new Date().toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'}) }
            ],
            aiChatbotInput: '',
            aiChatbotLoading: false,

            // Drag & drop
            editMode: false,

            // Tri A→Z / Z→A
            sortOrder: 'default',  // 'default' | 'az' | 'za' | 'value_asc' | 'value_desc'
            showSortMenu: false,
        });

        this.timeInterval = null;

        // Exposer les constantes au template OWL
        this.AI_MODULE_CONFIG_COUNTS = AI_MODULE_CONFIG_COUNTS;

        this.realtime = useRealtimeRefresh({
            dashboardId: () => this.state.activeTab,
            intervalSec: () => 30,
            // Ne jamais laisser une promesse rejetée remonter (OwlError / UncaughtPromiseError)
            onRefresh: () =>
                this.loadData().catch((err) => {
                    console.error("[BI] refresh:", err);
                    try {
                        this.notification?.add?.("Erreur lors du rafraîchissement du dashboard.", {
                            type: "danger",
                            sticky: false,
                        });
                    } catch (_) {}
                }),
        });

        onMounted(() => {
            void this.loadData()
                .catch((err) => {
                    console.error("[BI] loadData (montage):", err);
                    try {
                        this.notification?.add?.("Impossible de charger le dashboard BI.", {
                            type: "danger",
                            sticky: true,
                        });
                    } catch (_) {}
                })
                .finally(() => {
                    this.timeInterval = setInterval(() => this.updateTime(), 1000);
                });
        });

        onWillUnmount(() => {
            clearInterval(this.timeInterval);
            if (this.state.chatPollingId) clearInterval(this.state.chatPollingId);
            if (this._dragDrop) { this._dragDrop.destroy(); this._dragDrop = null; }
            this.destroyAllCharts();
        });

        useEffect(
            () => {
                if (this.state.loading) {
                    return;
                }
                queueMicrotask(() => {
                    try {
                        this.applyTheme(this.state.currentTheme);
                        this.renderAllCharts();
                        this.renderGlobalChart();
                        if (this.state.editMode && this._dragDrop) {
                            setTimeout(() => {
                                try {
                                    this._dragDrop.refresh();
                                } catch (e) {
                                    console.warn("[BI] dragDrop.refresh:", e);
                                }
                            }, 50);
                        }
                    } catch (err) {
                        console.error("[BI] rendu graphiques:", err);
                        try {
                            this.notification?.add?.(
                                "Erreur d’affichage des graphiques (voir la console).",
                                { type: "warning", sticky: false }
                            );
                        } catch (_) {}
                    }
                });
            },
            () => [this.state.filteredKpis, this.state.loading, this.state.currentTheme]
        );
    }

    destroyAllCharts() {
        Object.values(this.charts).forEach(c => c && c.destroy());
        this.charts = {};
        if (this.globalChart) { this.globalChart.destroy(); this.globalChart = null; }
        if (this._drillChart) { this._drillChart.destroy(); this._drillChart = null; }
    }

    updateTime() { this.state.currentTime = new Date().toLocaleTimeString("fr-FR"); }

    // ═══════════════════════════════════════════════════════════ CHARGEMENT
    async loadData() {
        try {
            // ── Fetch chaque modèle séparément (meilleure isolation des erreurs) ──
            let kpis = [], dashboards = [], todos = [];

            try {
                kpis = await this.rpc("/web/dataset/call_kw", {
                    model: "bi.kpi", method: "search_read", args: [],
                    kwargs: {
                        fields: ["id","name","value","value_previous","chart_type","chart_data",
                                 "color","color2","icon","icon_type","aggregation","dashboard_id",
                                 "target_value","unit","widget_size","alert_enabled","alert_threshold",
                                 "sequence","drill_field_id","bookmarked_user_ids","source"],
                        limit: 200, order: "sequence asc",
                    },
                });
            } catch(e) { console.error("❌ bi.kpi search_read:", e); kpis = []; }

            try {
                dashboards = await this.rpc("/web/dataset/call_kw", {
                    model: "bi.dashboard", method: "search_read", args: [],
                    kwargs: {
                        fields: ["name","id","bookmarked_user_ids","color_theme","rtl_mode",
                                 "group_ids","layout_data","refresh_interval"],
                        limit: 30,
                    },
                });
            } catch(e) { console.error("❌ bi.dashboard search_read:", e); dashboards = []; }

            try {
                todos = await this.rpc("/web/dataset/call_kw", {
                    model: "bi.todo", method: "search_read", args: [],
                    kwargs: {
                        fields: ["name","is_done","priority","deadline","user_id","sequence","color"],
                        limit: 50, order: "sequence asc",
                    },
                });
            } catch(e) { console.error("❌ bi.todo search_read:", e); todos = []; }

            const today = new Date().toISOString().slice(0,10);
            todos.forEach(t => { t.is_overdue = !!(t.deadline && t.deadline < today && !t.is_done); });

            const uid = (window.odoo && odoo.session_info && odoo.session_info.uid) || 1;
            this.state.bookmarkedDashboardIds = dashboards
                .filter(d => d.bookmarked_user_ids?.includes(uid)).map(d => d.id);
            kpis.forEach(k => { k.is_bookmarked = !!k.bookmarked_user_ids?.includes(uid); });

            const iconUrls = {};
            kpis.forEach(k => {
                iconUrls[k.id] = k.icon_type === 'image'
                    ? `/web/image/bi.kpi/${k.id}/icon_image?t=${Date.now()}` : null;
            });

            this.state.iconUrls   = iconUrls;
            this.state.kpis       = kpis;
            this.state.dashboards = dashboards;
            this.state.todos      = todos;

            if (!this.state.activeTab && dashboards.length > 0) {
                this.state.activeTab = dashboards[0].id;
            }
            const activeDash = dashboards.find(d => d.id === this.state.activeTab);
            if (activeDash) {
                this.state.currentTheme = activeDash.color_theme || 'light';
                this.state.rtlMode      = activeDash.rtl_mode || false;
            }

            // Détecter les modules Odoo installés
            try {
                const installedModels = await this.rpc("/web/dataset/call_kw", {
                    model: "ir.module.module", method: "search_read",
                    args: [[ ["state", "=", "installed"], ["name", "in",
                        ["sale_management","crm","stock","account","point_of_sale","purchase","hr"]] ]],
                    kwargs: { fields: ["name"], limit: 20 },
                });
                const moduleMap = {
                    "sale_management":"sale", "crm":"crm", "stock":"stock",
                    "account":"account", "point_of_sale":"pos",
                    "purchase":"purchase", "hr":"hr"
                };
                this.state.installedModuleKeys = installedModels.map(m => moduleMap[m.name]).filter(Boolean);
                if (this.state.installedModuleKeys.length === 0) {
                    this.state.installedModuleKeys = AVAILABLE_MODULES.map(m => m.key);
                }
            } catch {
                this.state.installedModuleKeys = AVAILABLE_MODULES.map(m => m.key);
            }

            this.filterAndCompute();
            if (this.state.sortOrder !== 'default') this.applySortOrder();
            this.computeTodos();
            await this.detectInstalledModules();
            this.state.loading = false;
            this.updateTime();
        } catch (e) {
            console.error("❌ BI loadData critical:", e);
            this.state.loading = false;
        }
    }


    async detectInstalledModules() {
        try {
            // Récupérer les modules installés depuis ir.module.module
            const installedApps = await this.rpc("/web/dataset/call_kw", {
                model: "ir.module.module",
                method: "search_read",
                args: [[[  "state", "=", "installed" ]]],
                kwargs: { fields: ["name","shortdesc"], limit: 200 },
            });
            const installedNames = new Set(installedApps.map(a => a.name));

            // Mapping module Odoo technique → nos clés
            const MODULE_MAP = {
                sale:     ['sale', 'sale_management', 'sale_crm'],
                crm:      ['crm'],
                stock:    ['stock', 'stock_account'],
                account:  ['account', 'account_accountant'],
                pos:      ['point_of_sale', 'pos_restaurant'],
                purchase: ['purchase', 'purchase_stock'],
                hr:       ['hr', 'hr_payroll', 'hr_attendance', 'hr_leave'],
            };

            // Filtrer les modules disponibles selon installation
            const detected = AVAILABLE_MODULES.filter(mod => {
                const techNames = MODULE_MAP[mod.key] || [mod.key];
                return techNames.some(n => installedNames.has(n));
            });

            // Si aucun détecté (env de test), tout afficher
            const finalModules = detected.length > 0 ? detected : AVAILABLE_MODULES;
            this.state.installedModules = finalModules;
            this.state.installedModuleKeys = finalModules.map(m => m.key);
            console.log(`🔍 Modules BI détectés: ${finalModules.map(m=>m.label).join(', ')}`);
        } catch(e) {
            console.warn('⚠️ detectInstalledModules error:', e);
            // En cas d'erreur, afficher tous les modules
            this.state.installedModules = AVAILABLE_MODULES;
            this.state.installedModuleKeys = AVAILABLE_MODULES.map(m => m.key);
        }
    }

    filterAndCompute() {
        const kpis = this.state.kpis || [];
        let filtered = this.state.activeTab
            ? kpis.filter(k => {
                if (!k.dashboard_id) return false;
                const did = Array.isArray(k.dashboard_id) ? k.dashboard_id[0] : k.dashboard_id;
                return did === this.state.activeTab;
            })
            : kpis;
        if (this.state.showBookmarksOnly) filtered = filtered.filter(k => k.is_bookmarked);

        this.state.filteredKpis = filtered;
        const maxVal = Math.max(...filtered.map(k => k.value || 0), 1);
        this.state.alerts = filtered
            .filter(k => k.alert_enabled && k.alert_threshold && k.value < k.alert_threshold)
            .map(k => ({ id:k.id, name:k.name, value:k.value, threshold:k.alert_threshold }));

        const fv = {}, pct = {}, evo = {}, td = {};
        filtered.forEach(k => {
            const v = k.value || 0, prev = k.value_previous || 0;
            fv[k.id] = v>=1e6 ? (v/1e6).toFixed(1)+"M"
                : v>=1000 ? (v/1000).toFixed(1)+"K" : v.toFixed(v%1===0?0:2);
            pct[k.id]  = Math.round((v/maxVal)*100);
            evo[k.id] = prev>0 ? Math.abs(((v-prev)/prev)*100).toFixed(1) : null;
            if (k.chart_type==='table' && k.chart_data) {
                try {
                    const d = JSON.parse(k.chart_data), total = Object.values(d).reduce((a,b)=>a+b,0)||1;
                    td[k.id] = Object.entries(d).sort((a,b)=>b[1]-a[1]).slice(0,8)
                        .map(([label,value])=>({ label, value, pct:Math.round((value/total)*100) }));
                } catch { td[k.id]=[]; }
            }
        });
        this.state.formattedValues = fv;
        this.state.percentages = pct;
        this.state.evolutionPct = evo;
        this.state.tableData = td;
    }

    // ═══════════════════════════════════════════════════════════ TABS
    setTab(id) {
        if (this.state.editMode) {
            if (this._dragDrop) { this._dragDrop.destroy(); this._dragDrop = null; }
            this.state.editMode = false;
            const cont = document.querySelector('.bi-grid');
            if (cont) cont.classList.remove('bi-edit-active');
        }
        this.state.activeTab = id;
        const dash = this.state.dashboards.find(d => d.id === id);
        if (dash) {
            this.state.currentTheme = dash.color_theme || 'light';
            this.state.rtlMode      = dash.rtl_mode || false;
        }
        this.filterAndCompute();
        this.realtime.onDashboardChange();
    }

    isDashboardBookmarked(id) { return this.state.bookmarkedDashboardIds.includes(id); }

    async toggleDashboardBookmark(id) {
        await this.rpc("/web/dataset/call_kw", { model:"bi.dashboard", method:"action_toggle_bookmark", args:[[id]], kwargs:{} });
        this.state.bookmarkedDashboardIds = this.isDashboardBookmarked(id)
            ? this.state.bookmarkedDashboardIds.filter(x=>x!==id)
            : [...this.state.bookmarkedDashboardIds, id];
    }

    async toggleKpiBookmark(kpiId) {
        await this.rpc("/web/dataset/call_kw", { model:"bi.kpi", method:"action_toggle_bookmark", args:[[kpiId]], kwargs:{} });
        const k = this.state.kpis.find(k=>k.id===kpiId);
        if (k) k.is_bookmarked = !k.is_bookmarked;
        this.filterAndCompute();
    }

    toggleShowBookmarks() { this.state.showBookmarksOnly = !this.state.showBookmarksOnly; this.filterAndCompute(); }

    // ═══════════════════════════════════════════════════════════ THEMES
    toggleThemeMenu() { this.state.showThemeMenu = !this.state.showThemeMenu; }

    applyTheme(themeName) {
        const t = THEMES[themeName] || THEMES.light;
        const root = document.documentElement;
        root.style.setProperty('--bi-bg',     t.bg);
        root.style.setProperty('--bi-card',   t.card);
        root.style.setProperty('--bi-text',   t.text);
        root.style.setProperty('--bi-sub',    t.sub);
        root.style.setProperty('--bi-border', t.border);
        const dash = document.querySelector('.bi-dashboard');
        if (dash) {
            dash.setAttribute('data-theme', themeName);
            dash.style.direction = this.state.rtlMode ? 'rtl' : 'ltr';
        }
    }

    async setTheme(themeName) {
        this.state.currentTheme = themeName;
        this.state.showThemeMenu = false;
        this.applyTheme(themeName);
        if (this.state.activeTab) {
            await this.rpc("/web/dataset/call_kw", {
                model:"bi.dashboard", method:"write",
                args:[[this.state.activeTab],{color_theme:themeName}], kwargs:{},
            });
        }
    }

    async toggleRTL() {
        this.state.rtlMode = !this.state.rtlMode;
        const dash = document.querySelector('.bi-dashboard');
        if (dash) dash.style.direction = this.state.rtlMode ? 'rtl' : 'ltr';
        if (this.state.activeTab) {
            await this.rpc("/web/dataset/call_kw", {
                model:"bi.dashboard", method:"write",
                args:[[this.state.activeTab],{rtl_mode:this.state.rtlMode}], kwargs:{},
            });
        }
    }

    getThemeLabel() {
        const labels = { light:'☀️ Light', dark:'🌙 Dark', corporate:'🏢 Corporate',
                         ocean:'🌊 Ocean', sunset:'🌅 Sunset', forest:'🌲 Forest' };
        return labels[this.state.currentTheme] || '🎨 Thème';
    }

    // ═══════════════════════════════════════════════════════════ DATE FILTER
    toggleDateFilterMenu() { this.state.showDateFilterMenu = !this.state.showDateFilterMenu; }

    formatDateDisplay(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr + 'T00:00:00');
        return d.toLocaleDateString('fr-FR', { day:'2-digit', month:'short', year:'numeric' });
    }

    getDateRangeLabel() {
        if (this.state.customDateFrom && this.state.customDateTo) {
            return `${this.formatDateDisplay(this.state.customDateFrom)} → ${this.formatDateDisplay(this.state.customDateTo)}`;
        }
        const labels = {
            "today": "Aujourd'hui",
            "yesterday": "Hier",
            "this_week": "Cette semaine",
            "last_week": "Sem. dernière",
            "last_7_days": "7 derniers jours",
            "last_14_days": "14 derniers jours",
            "last_30_days": "30 derniers jours",
            "this_month": "Ce mois",
            "last_month": "Mois dernier",
            "last_3_months": "3 derniers mois",
            "last_6_months": "6 derniers mois",
            "this_quarter": "Ce trimestre",
            "last_quarter": "Trim. dernier",
            "this_year": "Cette année",
            "last_year": "Année dernière",
            "last_365_days": "365 derniers jours",
            "all_time": "Tout le temps",
        };
        return labels[this.state.globalDateFilter] || 'Sélectionner...';
    }

    async resetDateFilter() {
        this.state.globalDateFilter = 'this_month';
        const today = new Date();
        const fmt = d => d.toISOString().slice(0,10);
        this.state.customDateFrom = fmt(new Date(today.getFullYear(), today.getMonth(), 1));
        this.state.customDateTo   = fmt(today);
        this.state.showDateFilterMenu = false;
        await this._applyDateFilter();
    }

    onDateFromChange(ev) {
        this.state.customDateFrom = ev.target.value;
        this.state.globalDateFilter = 'custom';
    }

    onDateToChange(ev) {
        this.state.customDateTo = ev.target.value;
        this.state.globalDateFilter = 'custom';
    }

    async setGlobalDateFilter(val) {
        this.state.globalDateFilter = val;
        this.state.showDateFilterMenu = false;
        // Auto-fill De/À fields based on quick filter
        const today = new Date();
        const fmt = d => d.toISOString().slice(0,10);
        const d = new Date();
        switch(val) {
            case 'today':        this.state.customDateFrom=fmt(today); this.state.customDateTo=fmt(today); break;
            case 'yesterday':    d.setDate(d.getDate()-1); this.state.customDateFrom=fmt(d); this.state.customDateTo=fmt(d); break;
            case 'this_week':    { const mon=new Date(today); mon.setDate(today.getDate()-today.getDay()+1); this.state.customDateFrom=fmt(mon); this.state.customDateTo=fmt(today); break; }
            case 'last_week':    { const lm=new Date(today); lm.setDate(today.getDate()-today.getDay()-6); const ls=new Date(lm); ls.setDate(lm.getDate()+6); this.state.customDateFrom=fmt(lm); this.state.customDateTo=fmt(ls); break; }
            case 'last_7_days':  { const s=new Date(today); s.setDate(s.getDate()-7); this.state.customDateFrom=fmt(s); this.state.customDateTo=fmt(today); break; }
            case 'last_14_days': { const s=new Date(today); s.setDate(s.getDate()-14); this.state.customDateFrom=fmt(s); this.state.customDateTo=fmt(today); break; }
            case 'last_30_days': { const s=new Date(today); s.setDate(s.getDate()-30); this.state.customDateFrom=fmt(s); this.state.customDateTo=fmt(today); break; }
            case 'last_365_days':{ const s=new Date(today); s.setDate(s.getDate()-365); this.state.customDateFrom=fmt(s); this.state.customDateTo=fmt(today); break; }
            case 'this_month':   { this.state.customDateFrom=fmt(new Date(today.getFullYear(),today.getMonth(),1)); this.state.customDateTo=fmt(today); break; }
            case 'last_month':   { const f=new Date(today.getFullYear(),today.getMonth()-1,1); const t=new Date(today.getFullYear(),today.getMonth(),0); this.state.customDateFrom=fmt(f); this.state.customDateTo=fmt(t); break; }
            case 'last_3_months':{ const s=new Date(today); s.setMonth(s.getMonth()-3); this.state.customDateFrom=fmt(s); this.state.customDateTo=fmt(today); break; }
            case 'last_6_months':{ const s=new Date(today); s.setMonth(s.getMonth()-6); this.state.customDateFrom=fmt(s); this.state.customDateTo=fmt(today); break; }
            case 'this_quarter': { const q=Math.floor(today.getMonth()/3); const f=new Date(today.getFullYear(),q*3,1); this.state.customDateFrom=fmt(f); this.state.customDateTo=fmt(today); break; }
            case 'last_quarter': { const q=Math.floor(today.getMonth()/3)-1; const f=new Date(today.getFullYear(),q*3,1); const t=new Date(today.getFullYear(),(q+1)*3,0); this.state.customDateFrom=fmt(f); this.state.customDateTo=fmt(t); break; }
            case 'this_year':    this.state.customDateFrom=`${today.getFullYear()}-01-01`; this.state.customDateTo=fmt(today); break;
            case 'last_year':    this.state.customDateFrom=`${today.getFullYear()-1}-01-01`; this.state.customDateTo=`${today.getFullYear()-1}-12-31`; break;
            case 'all_time':     this.state.customDateFrom='2000-01-01'; this.state.customDateTo=fmt(today); break;
        }
        if (val !== 'custom') await this._applyDateFilter();
    }

    async applyCustomDateFilter() {
        if (!this.state.customDateFrom || !this.state.customDateTo) {
            this.notification.add("Veuillez sélectionner une date de début et de fin", { type:'warning' });
            return;
        }
        this.state.showDateFilterMenu = false;
        await this._applyDateFilter();
    }

    async _applyDateFilter() {
        this.state.loading = true;
        try {
            const ids = this.state.filteredKpis.map(k=>k.id);
            if (ids.length) {
                const filterVal = this.state.globalDateFilter === 'custom'
                    ? `custom:${this.state.customDateFrom}:${this.state.customDateTo}`
                    : this.state.globalDateFilter;
                const writeVals = {filter_date_range: filterVal};
                if (this.state.customDateFrom) writeVals.filter_date_from = this.state.customDateFrom;
                if (this.state.customDateTo) writeVals.filter_date_to = this.state.customDateTo;
                await this.rpc("/web/dataset/call_kw", { model:"bi.kpi", method:"write", args:[ids, writeVals], kwargs:{} });
                await this.rpc("/web/dataset/call_kw", { model:"bi.kpi", method:"action_refresh", args:[ids], kwargs:{} });
            }
            await this.loadData();
        } catch(e) {
            console.error("Erreur application filtre date:", e);
            this.notification.add("Erreur lors du changement de filtre", { type:'danger' });
            this.state.loading = false;
        }
    }

    getDateFilterLabel() {
        if (this.state.globalDateFilter === 'custom' && this.state.customDateFrom) {
            return `📅 ${this.state.customDateFrom} → ${this.state.customDateTo}`;
        }
        const f = DATE_FILTERS.find(d=>d.value===this.state.globalDateFilter);
        return f ? `${f.icon} ${f.label}` : '📅 Période';
    }

    // ═══════════════════════════════════════════════════════════ DRAG & DROP
    toggleEditMode() {
        this.state.editMode = !this.state.editMode;
        const container = document.querySelector('.bi-grid');
        if (this.state.editMode) {
            if (container) container.classList.add('bi-edit-active');
            setTimeout(() => this._initDragDrop(), 50);
        } else {
            if (container) container.classList.remove('bi-edit-active');
            if (this._dragDrop) { this._dragDrop.destroy(); this._dragDrop = null; }
        }
    }

    _initDragDrop() {
        if (this._dragDrop) { this._dragDrop.destroy(); this._dragDrop = null; }
        const container = document.querySelector('.bi-grid');
        if (!container) return;
        const activeDash = this.state.dashboards.find(d => d.id === this.state.activeTab);
        let savedLayout = {};
        try {
            if (activeDash?.layout_data && activeDash.layout_data !== '{}') {
                savedLayout = JSON.parse(activeDash.layout_data);
            }
        } catch {}
        restoreLayout(container, savedLayout);
        this._dragDrop = initNativeDragDrop(container, async (layoutJson) => {
            if (this.state.activeTab) {
                try {
                    await this.rpc("/web/dataset/call_kw", {
                        model:"bi.dashboard", method:"write",
                        args:[[this.state.activeTab],{layout_data:layoutJson}], kwargs:{},
                    });
                } catch (e) { console.error("Erreur sauvegarde layout", e); }
            }
        });
        this.notification.add("✅ Mode édition activé — glissez les cartes", { type:'info' });
    }

    async resetLayout() {
        if (this.state.activeTab) {
            await this.rpc("/web/dataset/call_kw", {
                model:"bi.dashboard", method:"write",
                args:[[this.state.activeTab],{layout_data:'{}'}], kwargs:{},
            });
            this.notification.add("Disposition réinitialisée ↺", { type:"info" });
            if (this._dragDrop) { this._dragDrop.destroy(); this._dragDrop = null; }
            this.state.editMode = false;
            const container = document.querySelector('.bi-grid');
            if (container) container.classList.remove('bi-edit-active');
            await this.loadData();
        }
    }

    async onResizeSelect(kpiId, newSize) {
        await this.rpc("/web/dataset/call_kw", {
            model:"bi.kpi", method:"write",
            args:[[kpiId],{widget_size:newSize}], kwargs:{},
        });
        const k = this.state.kpis.find(k=>k.id===kpiId);
        if (k) k.widget_size = newSize;
        const el = document.querySelector(`[data-kpi-id="${kpiId}"]`);
        if (el) { el.className = el.className.replace(/bi-w-\w+/, `bi-w-${newSize}`); }
        this.notification.add(`Taille : ${newSize}`, { type:'info' });
    }

    // ═══════════════════════════════════════════════════════════ SWITCH LAYOUT
    openSwitchModal(kpiId) { this.state.switchModal = { kpiId }; }
    closeSwitchModal() { this.state.switchModal = null; }

    async switchChartType(kpiId, newType) {
        await this.rpc("/web/dataset/call_kw", {
            model:"bi.kpi", method:"write",
            args:[[kpiId],{chart_type:newType}], kwargs:{},
        });
        const k = this.state.kpis.find(k=>k.id===kpiId);
        if (k) k.chart_type = newType;
        this.filterAndCompute();
        this.closeSwitchModal();
        this.notification.add("Layout mis à jour ✅", { type:"success" });
    }

    // ═══════════════════════════════════════════════════════════ CHAT KPI
    async openChat(kpiId, kpiName) {
        const messages = await this._loadChatMessages(kpiId);
        this.state.chatModal = { kpiId, kpiName, messages, newMsg: '' };
        if (this.state.chatPollingId) clearInterval(this.state.chatPollingId);
        this.state.chatPollingId = setInterval(async () => {
            if (!this.state.chatModal) { clearInterval(this.state.chatPollingId); return; }
            const msgs = await this._loadChatMessages(kpiId);
            if (this.state.chatModal) this.state.chatModal.messages = msgs;
            this._scrollChatToBottom();
        }, 8000);
        setTimeout(() => this._scrollChatToBottom(), 100);
    }

    async _loadChatMessages(kpiId) {
        try {
            const comments = await this.rpc("/web/dataset/call_kw", {
                model:"bi.comment", method:"search_read", args:[],
                kwargs: {
                    domain: [["kpi_id","=",kpiId]],
                    fields: ["id","message","user_id","create_date","is_pinned"],
                    limit:50, order:"create_date asc",
                },
            });
            return comments.map(c => ({
                id:c.id, user:c.user_id?.[1]||'Utilisateur', text:c.message,
                time:c.create_date?new Date(c.create_date.replace(' ','T')).toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'}):'',
                date:c.create_date?new Date(c.create_date.replace(' ','T')).toLocaleDateString('fr-FR'):'',
                pinned:c.is_pinned, mine:false,
            }));
        } catch { return []; }
    }

    closeChat() {
        if (this.state.chatPollingId) clearInterval(this.state.chatPollingId);
        this.state.chatModal = null;
    }

    async sendChatMsg() {
        if (!this.state.chatModal || !this.state.chatModal.newMsg.trim()) return;
        const text = this.state.chatModal.newMsg.trim();
        try {
            await this.rpc("/web/dataset/call_kw", {
                model:"bi.comment", method:"create",
                args:[{kpi_id:this.state.chatModal.kpiId, message:text, dashboard_id:this.state.activeTab||false}],
                kwargs:{},
            });
            this.state.chatModal.newMsg = '';
            this.state.chatModal.messages = await this._loadChatMessages(this.state.chatModal.kpiId);
            setTimeout(() => this._scrollChatToBottom(), 50);
        } catch(e) { this.notification.add("Erreur envoi message", {type:"danger"}); }
    }

    _scrollChatToBottom() {
        const el = document.getElementById('bi-chat-messages');
        if (el) el.scrollTop = el.scrollHeight;
    }

    onChatKeydown(ev) { if (ev.key==='Enter'&&!ev.shiftKey){ev.preventDefault();this.sendChatMsg();} }

    // ═══════════════════════════════════════════════════════════ AI CHATBOT FLOTTANT
    toggleAiChatbot() { this.state.showAiChatbot = !this.state.showAiChatbot; }

    async sendAiMessage() {
        const text = this.state.aiChatbotInput.trim();
        if (!text || this.state.aiChatbotLoading) return;
        const time = new Date().toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'});
        this.state.aiChatbotMessages = [...this.state.aiChatbotMessages, { role:'user', text, time }];
        this.state.aiChatbotInput = '';
        this.state.aiChatbotLoading = true;
        setTimeout(() => this._scrollAiChat(), 50);

        try {
            // Construire le contexte des données disponibles
            const dashNames = this.state.dashboards.map(d=>d.name).join(', ');
            const kpiCount  = this.state.kpis.length;
            const kpiNames  = this.state.filteredKpis.slice(0,5).map(k=>k.name).join(', ');
            const activeDash = this.state.dashboards.find(d=>d.id===this.state.activeTab);
            const systemPrompt = `Tu es un assistant BI expert intégré dans un dashboard Odoo 17.
Données disponibles :
- Dashboards : ${dashNames || 'aucun'}
- Dashboard actif : ${activeDash?.name || 'aucun'}
- Nombre total de KPIs : ${kpiCount}
- KPIs visibles : ${kpiNames || 'aucun'}
- Filtre date actuel : ${this.getDateFilterLabel()}

Réponds en français, de façon concise et professionnelle.
Tu peux analyser les données, suggérer des améliorations, expliquer des tendances ou aider à créer des dashboards.`;

            const response = await fetch("/web/dataset/call_kw", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    jsonrpc: "2.0", method: "call", id: 1,
                    params: {
                        model: "bi.dashboard", method: "action_ai_chat",
                        args: [[], text], kwargs: { system_prompt: systemPrompt, history: this.state.aiChatbotMessages.slice(-6).map(m=>({role:m.role,content:m.text})) }
                    }
                })
            });
            const data = await response.json();
            console.log("=== AI RESPONSE ===", JSON.stringify(data)); const aiReply = data?.result?.response || this._getFallbackResponse(text);
            this.state.aiChatbotMessages = [...this.state.aiChatbotMessages, {
                role:'assistant', text: aiReply,
                time: new Date().toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'})
            }];
        } catch {
            const aiReply = this._getFallbackResponse(text);
            this.state.aiChatbotMessages = [...this.state.aiChatbotMessages, {
                role:'assistant', text: aiReply,
                time: new Date().toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'})
            }];
        }
        this.state.aiChatbotLoading = false;
        setTimeout(() => this._scrollAiChat(), 50);
    }

    _getFallbackResponse(text) {
        const t = text.toLowerCase();
        const activeDash = this.state.dashboards.find(d=>d.id===this.state.activeTab);
        const kpis = this.state.filteredKpis;
        if (t.includes('kpi') || t.includes('indicateur')) {
            return `📊 Vous avez ${kpis.length} KPI(s) dans "${activeDash?.name||'ce dashboard'}". Les valeurs vont de ${Math.min(...kpis.map(k=>k.value||0)).toLocaleString('fr-FR')} à ${Math.max(...kpis.map(k=>k.value||0)).toLocaleString('fr-FR')}.`;
        }
        if (t.includes('dashboard') || t.includes('tableau')) {
            return `📋 Vous avez ${this.state.dashboards.length} dashboard(s) configuré(s) : ${this.state.dashboards.map(d=>d.name).join(', ')}.`;
        }
        if (t.includes('alerte') || t.includes('alert')) {
            return this.state.alerts.length > 0
                ? `⚠️ ${this.state.alerts.length} alerte(s) active(s) : ${this.state.alerts.map(a=>a.name).join(', ')}.`
                : `✅ Aucune alerte active pour le moment.`;
        }
        if (t.includes('export') || t.includes('excel')) {
            return `📊 Pour exporter : cliquez sur "Excel" dans la barre de navigation pour exporter tout le dashboard, ou sur l'icône 📥 d'un KPI pour l'exporter individuellement.`;
        }
        return `🤖 Je comprends votre question sur "${text}". Pour une analyse approfondie, consultez les KPIs disponibles dans ce dashboard (${kpis.length} indicateurs actifs). Puis-je vous aider avec quelque chose de plus spécifique ?`;
    }

    _scrollAiChat() {
        const el = document.getElementById('bi-ai-chatbot-messages');
        if (el) el.scrollTop = el.scrollHeight;
    }

    onAiChatKeydown(ev) { if (ev.key==='Enter'&&!ev.shiftKey){ev.preventDefault();this.sendAiMessage();} }

    // ═══════════════════════════════════════════════════════════ AI DASHBOARD — NOUVEAU FLUX
    openAiDashboardModal() {
        this.state.showAiDashboardModal = true;
        this.state.aiSelectedModules = [];
        this.state.aiStep = 'select';
        this.state.aiPreviewData = [];
        this.state.aiKpiSelections = {};
        this.state.aiKpiEdits = {};
        this.state.aiGenerating = false;
        this.state.aiProgress = '';
    }

    closeAiDashboardModal() {
        this.state.showAiDashboardModal = false;
        this.state.aiStep = 'select';
    }

    toggleAiModule(moduleKey) {
        if (this.state.aiSelectedModules.includes(moduleKey)) {
            this.state.aiSelectedModules = this.state.aiSelectedModules.filter(m => m !== moduleKey);
        } else {
            this.state.aiSelectedModules = [...this.state.aiSelectedModules, moduleKey];
        }
    }

    isAiModuleSelected(moduleKey) { return this.state.aiSelectedModules.includes(moduleKey); }

    getAvailableModules() {
        if (this.state.installedModuleKeys && this.state.installedModuleKeys.length > 0) {
            return AVAILABLE_MODULES.filter(m => this.state.installedModuleKeys.includes(m.key));
        }
        return AVAILABLE_MODULES;
    }

    // ── ÉTAPE 1 → 2 : Générer la prévisualisation des KPIs ───────────────────
    aiPreviewKpis() {
        if (this.state.aiSelectedModules.length === 0) {
            this.notification.add("Sélectionnez au moins un module", { type: 'warning' });
            return;
        }

        // Construire la liste de preview avec tous les KPIs cochés par défaut
        const preview = [];
        const selections = {};
        const edits = {};

        for (const moduleKey of this.state.aiSelectedModules) {
            const mod = AVAILABLE_MODULES.find(m => m.key === moduleKey);
            const config = AI_MODULE_CONFIG[moduleKey];
            if (!mod || !config) continue;

            const kpisWithId = config.kpis.map((kpi, idx) => {
                const key = `${moduleKey}_${idx}`;
                // Tout sélectionné par défaut
                selections[key] = true;
                edits[key] = {
                    chart_type: kpi.chart_type,
                    color: kpi.color,
                    widget_size: kpi.widget_size,
                };
                return { ...kpi, _key: key, _idx: idx };
            });

            preview.push({
                moduleKey,
                label: mod.label,
                icon: mod.icon,
                color: mod.color,
                model: mod.model,
                kpis: kpisWithId,
            });
        }

        this.state.aiPreviewData = preview;
        this.state.aiKpiSelections = selections;
        this.state.aiKpiEdits = edits;
        this.state.aiStep = 'preview';
    }

    // ── Sélection / désélection d'un KPI dans la préview ─────────────────────
    aiToggleKpi(key) {
        this.state.aiKpiSelections = {
            ...this.state.aiKpiSelections,
            [key]: !this.state.aiKpiSelections[key],
        };
    }

    aiIsKpiSelected(key) { return !!this.state.aiKpiSelections[key]; }

    // ── Modifier le type de graphique d'un KPI depuis la preview ──────────────
    aiChangeChartType(key, chartType) {
        this.state.aiKpiEdits = {
            ...this.state.aiKpiEdits,
            [key]: { ...this.state.aiKpiEdits[key], chart_type: chartType },
        };
    }

    aiChangeColor(key, color) {
        this.state.aiKpiEdits = {
            ...this.state.aiKpiEdits,
            [key]: { ...this.state.aiKpiEdits[key], color },
        };
    }

    aiChangeSize(key, size) {
        this.state.aiKpiEdits = {
            ...this.state.aiKpiEdits,
            [key]: { ...this.state.aiKpiEdits[key], widget_size: size },
        };
    }


    goBackToSelectStep() {
        this.state.aiStep = 'select';
    }

    // Sélectionner / désélectionner tous les KPIs d'un module
    aiToggleAllKpisOfModule(moduleKey, kpis, selectAll) {
        const updated = { ...this.state.aiKpiSelections };
        kpis.forEach(kpi => { updated[kpi._key] = selectAll; });
        this.state.aiKpiSelections = updated;
    }

    aiCountSelectedKpis() {
        return Object.values(this.state.aiKpiSelections).filter(Boolean).length;
    }

    // ── ÉTAPE 2 → 3 : Créer effectivement les dashboards et KPIs ─────────────
    async generateAiDashboards() {
        const totalSelected = this.aiCountSelectedKpis();
        if (totalSelected === 0) {
            this.notification.add("Sélectionnez au moins un KPI", { type: 'warning' });
            return;
        }

        this.state.aiStep = 'generating';
        this.state.aiGenerating = true;
        this.state.aiProgress = '⏳ Analyse de vos données...';
        let createdDashboards = 0;
        let createdKpis = 0;
        /** IDs dashboard touchés (nouveaux ou existants) pour batch_refresh après création KPI */
        const dashIdsForRefresh = new Set();

        try {
            for (const moduleData of this.state.aiPreviewData) {
                const selectedKpis = moduleData.kpis.filter(k => this.state.aiKpiSelections[k._key]);
                if (selectedKpis.length === 0) continue;

                this.state.aiProgress = `🤖 Création du dashboard "${moduleData.label}"...`;

                // Créer ou récupérer le dashboard
                const existing = this.state.dashboards.find(d => d.name === moduleData.label);
                let dashId;
                if (existing) {
                    dashId = existing.id;
                } else {
                    dashId = await this.rpc("/web/dataset/call_kw", {
                        model: "bi.dashboard", method: "create",
                        args: [{ name: moduleData.label, color_theme: 'light', layout_data: '{}' }],
                        kwargs: {},
                    });
                    createdDashboards++;
                }
                dashIdsForRefresh.add(dashId);

                // Trouver le model_id Odoo (utiliser le modèle du module par défaut)
                const defaultModelRec = await this.rpc("/web/dataset/call_kw", {
                    model: "ir.model", method: "search_read",
                    args: [[["model", "=", moduleData.model]]],
                    kwargs: { fields: ["id"], limit: 1 },
                });
                const defaultModelId = defaultModelRec[0]?.id || null;

                // Créer chaque KPI sélectionné avec les options éditées
                this.state.aiProgress = `📊 Création de ${selectedKpis.length} KPIs pour "${moduleData.label}"...`;
                for (let i = 0; i < selectedKpis.length; i++) {
                    const kpi = selectedKpis[i];
                    const edits = this.state.aiKpiEdits[kpi._key] || {};
                    const kpiMapping = resolveKpiFieldMapping(kpi.name);

                    // Utiliser le modèle spécifique du KPI si défini
                    let kpiModelId = defaultModelId;
                    if (kpiMapping.model && kpiMapping.model !== moduleData.model) {
                        try {
                            const kpiModelRec = await this.rpc("/web/dataset/call_kw", {
                                model: "ir.model", method: "search_read",
                                args: [[["model", "=", kpiMapping.model]]],
                                kwargs: { fields: ["id"], limit: 1 },
                            });
                            kpiModelId = kpiModelRec[0]?.id || defaultModelId;
                        } catch {}
                    }

                    // Chercher le field_id (champ principal puis altField ex. margin → amount_untaxed)
                    let fieldId = false;
                    if (kpiModelId) {
                        const fieldNames = [];
                        if (kpiMapping.field) {
                            fieldNames.push(kpiMapping.field);
                        }
                        if (kpiMapping.altField) {
                            fieldNames.push(kpiMapping.altField);
                        }
                        for (const fname of fieldNames) {
                            if (!fname) {
                                continue;
                            }
                            try {
                                const fieldRec = await this.rpc("/web/dataset/call_kw", {
                                    model: "ir.model.fields", method: "search_read",
                                    args: [[["model_id", "=", kpiModelId], ["name", "=", fname]]],
                                    kwargs: { fields: ["id"], limit: 1 },
                                });
                                if (fieldRec[0]?.id) {
                                    fieldId = fieldRec[0].id;
                                    break;
                                }
                            } catch {}
                        }
                    }

                    // Construire le domaine de filtre du KPI
                    const kpiDomain = kpiMapping.domain ? JSON.stringify(kpiMapping.domain) : '[]';

                    await this.rpc("/web/dataset/call_kw", {
                        model: "bi.kpi", method: "create",
                        args: [{
                            name:          kpi.name,
                            dashboard_id:  dashId,
                            model_id:      kpiModelId,
                            field_id:      fieldId,
                            filter_domain: kpiDomain,
                            aggregation:   kpiMapping.agg || 'count',
                            chart_type:   edits.chart_type || kpi.chart_type,
                            color:        edits.color      || kpi.color,
                            color2:       '#764ba2',
                            widget_size:  edits.widget_size || kpi.widget_size,
                            sequence:     (i + 1) * 10,
                            source:       'odoo',
                        }],
                        kwargs: {},
                    });
                    createdKpis++;
                }
            }

            this.state.aiProgress = `⚙️ Calcul des valeurs initiales...`;
            // Auto-refresh: déclencher le calcul des valeurs KPI depuis Odoo
            try {
                for (const did of dashIdsForRefresh) {
                    await this.rpc("/web/dataset/call_kw", {
                        model: "bi.kpi",
                        method: "batch_refresh_by_dashboard",
                        args: [did],
                        kwargs: {},
                    });
                }
            } catch(e) { console.warn("Auto-refresh KPIs:", e); }

            this.state.aiProgress = `✅ ${createdKpis} KPI(s) créés dans ${createdDashboards || this.state.aiPreviewData.length} dashboard(s) !`;
            this.state.aiStep = 'done';

            setTimeout(async () => {
                this.closeAiDashboardModal();
                await this.loadData();
                this.notification.add(
                    `✅ ${createdKpis} KPI(s) créés dans vos dashboards !`,
                    { type: 'success' }
                );
            }, 2000);

        } catch (e) {
            console.error("Erreur génération IA", e);
            this.state.aiProgress = '❌ Erreur lors de la génération';
            this.state.aiGenerating = false;
            this.state.aiStep = 'preview';
            const odooMsg =
                e?.data?.message ||
                (typeof e?.message === "string" && e.message) ||
                (e?.data?.arguments && String(e.data.arguments)) ||
                "";
            this.notification.add(
                odooMsg
                    ? `Erreur lors de la création des dashboards : ${odooMsg}`
                    : "Erreur lors de la création des dashboards (voir la console).",
                { type: "danger", sticky: !!odooMsg }
            );
        }
    }

    // ═══════════════════════════════════════════════════════════ IMPORT
    openImportModal() { this.state.showImportModal = true; this.state.importPreview = null; }
    closeImportModal() { this.state.showImportModal = false; this.state.importPreview = null; }

    onImportFileChange(ev) {
        const file = ev.target.files[0];
        if (!file) return;
        const ext = file.name.split('.').pop().toLowerCase();
        if (ext==='csv') { this._readCSV(file); }
        else if (['xlsx','xls'].includes(ext)) { this._readExcel(file); }
        else { this.notification.add("Format non supporté. Utilisez CSV ou Excel.", {type:"warning"}); }
    }

    _readCSV(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const lines = e.target.result.split('\n').filter(l=>l.trim());
            if (lines.length<2) return;
            const headers = lines[0].split(/[,;]/).map(h=>h.trim().replace(/"/g,''));
            const rows    = lines.slice(1).map(l=>l.split(/[,;]/).map(c=>c.trim().replace(/"/g,'')));
            this.state.importPreview = { headers, rows:rows.slice(0,5), allRows:rows, chartType:'bar', name:file.name.replace(/\.[^.]+$/,''), labelCol:0, valueCol:1 };
        };
        reader.readAsText(file,'UTF-8');
    }

    _readExcel(file) {
        if (typeof XLSX==='undefined') { this.notification.add("SheetJS non chargé.", {type:"warning"}); return; }
        const reader = new FileReader();
        reader.onload = (e) => {
            const wb=XLSX.read(e.target.result,{type:'binary'}), ws=wb.Sheets[wb.SheetNames[0]];
            const arr=XLSX.utils.sheet_to_json(ws,{header:1});
            if (arr.length<2) return;
            const headers=arr[0].map(String), rows=arr.slice(1);
            this.state.importPreview = { headers, rows:rows.slice(0,5), allRows:rows, chartType:'bar', name:wb.SheetNames[0], labelCol:0, valueCol:1 };
        };
        reader.readAsBinaryString(file);
    }

    async createChartFromImport() {
        const p = this.state.importPreview;
        if (!p) return;
        const grouped = {};
        p.allRows.forEach(row => {
            const lbl=String(row[p.labelCol]||'').trim();
            const val=parseFloat(String(row[p.valueCol]||'0').replace(/[^\d.-]/g,''))||0;
            if (lbl) grouped[lbl]=(grouped[lbl]||0)+val;
        });
        const model = await this.rpc("/web/dataset/call_kw", {
            model:"ir.model", method:"search_read", args:[[["model","=","bi.kpi"]]],
            kwargs:{fields:["id"],limit:1},
        });
        await this.rpc("/web/dataset/call_kw", {
            model:"bi.kpi", method:"create",
            args:[{ name:p.name, model_id:model[0]?.id||1, aggregation:'count', chart_type:p.chartType,
                    chart_data:JSON.stringify(grouped), color:'#6366f1', color2:'#764ba2',
                    widget_size:'large', dashboard_id:this.state.activeTab||false, sequence:999 }],
            kwargs:{},
        });
        this.notification.add(`✅ Graphique "${p.name}" créé`, {type:'success'});
        this.closeImportModal();
        await this.loadData();
    }

    // ═══════════════════════════════════════════════════════════ DRILL DOWN
    async onChartClick(kpiId, label) {
        const kpi = this.state.kpis.find(k=>k.id===kpiId);
        if (!kpi?.drill_field_id) return;
        try {
            const drillData = await this.rpc("/web/dataset/call_kw", {
                model:"bi.kpi", method:"action_get_drill_data", args:[[kpiId],label], kwargs:{},
            });
            this.state.drillHistory.push({label:'Vue principale',data:null});
            this.state.drillModal = {kpiId, label, data:drillData, color:kpi.color};
            setTimeout(() => this._renderDrillChart(drillData, label, kpi.color), 80);
        } catch(e) { console.error("Drill", e); }
    }

    drillUp() { if (!this.state.drillHistory.length){this.state.drillModal=null;return;} this.state.drillHistory.pop(); this.state.drillModal=null; }
    closeDrillModal() { this.state.drillHistory=[]; this.state.drillModal=null; }

    _renderDrillChart(data, label, color) {
        const canvas = document.getElementById('bi-drill-canvas');
        if (!canvas||typeof Chart==='undefined') return;
        if (this._drillChart) this._drillChart.destroy();
        const labels=Object.keys(data).slice(0,12), vals=Object.values(data).slice(0,12);
        this._drillChart = new Chart(canvas.getContext('2d'), {
            type:'bar', data:{labels, datasets:[{data:vals, backgroundColor:color+'99', borderColor:color, borderWidth:2, borderRadius:6}]},
            options:{responsive:true,animation:{duration:600},plugins:{legend:{display:false},title:{display:true,text:`🔍 ${label}`,font:{size:13}}},scales:{y:{beginAtZero:true},x:{ticks:{font:{size:10}}}}},
        });
    }

    // ═══════════════════════════════════════════════════════════ EDIT MODAL
    openEditModal(kpiId) {
        const k=this.state.kpis.find(k=>k.id===kpiId);
        if (!k) return;
        this.state.editingKpi={id:k.id,name:k.name,color:k.color,color2:k.color2||'#6366f1',
            unit:k.unit||'',target_value:k.target_value||0,widget_size:k.widget_size||'small',
            chart_type:k.chart_type||'indicator',alert_enabled:k.alert_enabled||false,alert_threshold:k.alert_threshold||0};
        this.state.showEditModal=true;
    }
    closeEditModal() { this.state.showEditModal=false; this.state.editingKpi=null; }

    async saveEditModal() {
        if (!this.state.editingKpi) return;
        const {id,name,color,color2,unit,target_value,widget_size,chart_type,alert_enabled,alert_threshold}=this.state.editingKpi;
        try {
            await this.rpc("/web/dataset/call_kw",{model:"bi.kpi",method:"write",args:[[id],{name,color,color2,unit,target_value,widget_size,chart_type,alert_enabled,alert_threshold}],kwargs:{}});
            this.notification.add("✅ KPI mis à jour",{type:"success"});
            this.closeEditModal();
            await this.loadData();
        } catch { this.notification.add("Erreur sauvegarde",{type:"danger"}); }
    }

    // ═══════════════════════════════════════════════════════════ EXPORT
    openExportModal(kpiId) { this.state.exportModal={kpiId}; }
    closeExportModal() { this.state.exportModal=null; }

    async exportKpiCsv(kpiId) {
        try {
            const r=await this.rpc("/web/dataset/call_kw",{model:"bi.kpi",method:"action_export_csv",args:[[kpiId]],kwargs:{}});
            if (r?.url) window.open(r.url,'_blank');
        } catch { this.notification.add("Erreur export CSV",{type:"danger"}); }
        this.closeExportModal();
    }

    exportKpiPng(kpiId) {
        const canvas=document.getElementById('chart_'+kpiId);
        if (!canvas){this.notification.add("Pas de graphique",{type:"warning"});return;}
        const a=document.createElement('a');a.download=`kpi_${kpiId}.png`;a.href=canvas.toDataURL('image/png');a.click();
        this.closeExportModal();
    }

    exportKpiJson(kpiId) {
        const k=this.state.kpis.find(k=>k.id===kpiId);
        if (!k) return;
        const blob=new Blob([JSON.stringify({name:k.name,value:k.value,chart_data:k.chart_data},null,2)],{type:'application/json'});
        const a=document.createElement('a');a.download=`kpi_${kpiId}.json`;a.href=URL.createObjectURL(blob);a.click();
        this.closeExportModal();
    }

    exportKpiXlsx(kpiId) {
        const kpi=this.state.kpis.find(k=>k.id===kpiId);
        if (!kpi) return;
        try { exportKpiToExcel(kpi); this.notification.add(`✅ Export Excel : ${kpi.name}`,{type:'success'}); }
        catch { this.notification.add("SheetJS non chargé.",{type:'warning'}); }
        this.closeExportModal();
    }

    exportDashboardXlsx() {
        const dash=this.state.dashboards.find(d=>d.id===this.state.activeTab);
        try { exportDashboardToExcel(this.state.filteredKpis,dash?.name||'Dashboard'); this.notification.add("✅ Dashboard exporté en Excel",{type:'success'}); }
        catch { this.notification.add("SheetJS non chargé.",{type:'warning'}); }
    }

    exportPDF() {
        const s=document.createElement('style');
        s.innerHTML='@media print{.bi-navbar,.bi-w-actions,.bi-todo-section,.bi-date-filter-wrap,.bi-layout-toolbar,.bi-ai-fab{display:none!important}.bi-content{height:auto!important;overflow:visible!important}}';
        document.head.appendChild(s);window.print();setTimeout(()=>document.head.removeChild(s),1000);
    }

    // ═══════════════════════════════════════════════════════════ TODOS
    computeTodos() {
        const done=this.state.todos.filter(t=>t.is_done).length;
        this.state.todoStats={total:this.state.todos.length,done,pct:this.state.todos.length>0?Math.round((done/this.state.todos.length)*100):0};
        this.applyTodoFilter();
    }
    applyTodoFilter() {
        const f=this.state.todoFilter;
        this.state.filteredTodos=this.state.todos.filter(t=>f==='done'?t.is_done:f==='pending'?!t.is_done:true);
    }
    setTodoFilter(f){this.state.todoFilter=f;this.applyTodoFilter();}
    addTodo(){this.state.showAddTodo=true;this.state.newTodoName='';}

    async saveTodo() {
        if (!this.state.newTodoName.trim()) return;
        await this.rpc("/web/dataset/call_kw",{model:"bi.todo",method:"create",args:[{name:this.state.newTodoName.trim(),priority:this.state.newTodoPriority,deadline:this.state.newTodoDeadline||false,is_done:false}],kwargs:{}});
        this.state.showAddTodo=false;
        await this.loadData();
    }

    async toggleTodo(id) {
        await this.rpc("/web/dataset/call_kw",{model:"bi.todo",method:"toggle_done",args:[[id]],kwargs:{}});
        const t=this.state.todos.find(t=>t.id===id);
        if(t){t.is_done=!t.is_done;const today=new Date().toISOString().slice(0,10);t.is_overdue=!!(t.deadline&&t.deadline<today&&!t.is_done);}
        this.computeTodos();
    }

    async deleteTodo(id) {
        await this.rpc("/web/dataset/call_kw",{model:"bi.todo",method:"unlink",args:[[id]],kwargs:{}});
        this.state.todos=this.state.todos.filter(t=>t.id!==id);
        this.computeTodos();
    }

    async refreshKpi(id) {
        await this.rpc("/web/dataset/call_kw",{model:"bi.kpi",method:"action_refresh",args:[[id]],kwargs:{}});
        await this.loadData();
    }

    async editKpiFull(id) {
        await this.action.doAction({type:'ir.actions.act_window',res_model:'bi.kpi',res_id:id,view_mode:'form',views:[[false,'form']],target:'new'});
        await this.loadData();
    }

    // ═══════════════════════════════════════════════════════════ CHARTS
    renderGlobalChart() {
        if (typeof Chart === 'undefined') return;
        const ref = this.globalChartRef && this.globalChartRef.el;
        if (!ref) return;
        if (this.globalChart) { try { this.globalChart.destroy(); } catch {} this.globalChart = null; }
        const kpis = this.state.filteredKpis.filter(k => k.value !== null && k.value !== undefined).slice(0, 10);
        if (!kpis.length) {
            const ctx = ref.getContext('2d');
            ctx.clearRect(0, 0, ref.width, ref.height);
            ctx.fillStyle = '#94a3b8';
            ctx.font = '13px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Aucun KPI avec données. Cliquez sur 🔄 Sync Odoo', ref.width/2, ref.height/2);
            return;
        }
        const labels = kpis.map(k => k.name.length > 14 ? k.name.slice(0,14)+'…' : k.name);
        const vals = kpis.map(k => k.value || 0);
        const prevVals = kpis.map(k => k.value_previous || 0);
        const colors = kpis.map(k => k.color || '#6366f1');
        const isDark = this.state.currentTheme === 'dark';
        const tickColor = isDark ? '#6b7280' : '#94a3b8';
        try {
            this.globalChart = new Chart(ref.getContext('2d'), {
                type: 'bar',
                data: {
                    labels,
                    datasets: [
                        { label: 'Actuel',    data: vals,     backgroundColor: colors.map(c => c+'cc'), borderRadius: 4, borderSkipped: false },
                        { label: 'Précédent', data: prevVals, backgroundColor: colors.map(c => c+'44'), borderRadius: 4, borderSkipped: false },
                    ],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    animation: { duration: 600 },
                    plugins: { legend: { display: true, position: 'top', labels: { color: tickColor, usePointStyle: true, font: { size: 11 } } } },
                    scales: {
                        y: { beginAtZero: true, grid: { color: isDark ? '#2d3148' : '#f0f4ff' }, ticks: { color: tickColor } },
                        x: { grid: { display: false }, ticks: { color: tickColor, font: { size: 10 } } },
                    },
                },
            });
        } catch(e) { console.error('globalChart error:', e); }
    }

    renderAllCharts() {
        if (typeof Chart === 'undefined') {
            console.warn('⚠️ Chart.js non disponible - graphiques désactivés');
            return;
        }
        Object.values(this.charts).forEach(c=>c&&c.destroy());
        this.charts={};
        this.state.filteredKpis.forEach(kpi=>{
            if (['indicator','counter','table'].includes(kpi.chart_type)) return;
            const canvas=document.getElementById('chart_'+kpi.id);
            if (!canvas) return;
            let labels=[], dataVals=[];
            if (kpi.chart_data) {
                try { const cd=JSON.parse(kpi.chart_data);if(Object.keys(cd).length){labels=Object.keys(cd).slice(0,12);dataVals=Object.values(cd).slice(0,12);} } catch{}
            }
            // Si pas de données réelles, afficher message vide plutôt que données aléatoires
            if (!labels.length) {
                // Afficher canvas vide avec message
                // No data - show message using requestAnimationFrame to ensure dimensions
                requestAnimationFrame(() => {
                    const ctx2 = canvas.getContext('2d');
                    const w = canvas.offsetWidth || 300;
                    const h = canvas.offsetHeight || 200;
                    canvas.width = w;
                    canvas.height = h;
                    ctx2.clearRect(0, 0, w, h);
                    ctx2.fillStyle = '#94a3b8';
                    ctx2.font = '12px sans-serif';
                    ctx2.textAlign = 'center';
                    ctx2.fillText('🔄 Cliquez Sync Odoo pour charger', w/2, h/2 - 10);
                    ctx2.fillText('les données du graphique', w/2, h/2 + 10);
                });
                return;
            }
            const cfg=this._getChartConfig(kpi,labels,dataVals);
            if (cfg) {
                try {
                    const chart=new Chart(canvas.getContext('2d'),cfg);
                    if (kpi.drill_field_id) {
                        canvas.onclick=(evt)=>{
                            const pts=chart.getElementsAtEventForMode(evt,'nearest',{intersect:true},true);
                            if(pts.length) this.onChartClick(kpi.id,labels[pts[0].index]);
                        };
                        canvas.style.cursor='pointer';
                    }
                    this.charts[kpi.id]=chart;
                } catch(e){console.error("chart",kpi.id,e);}
            }
        });
    }

    _getChartConfig(kpi,labels,dataVals) {
        const c=kpi.color||'#6366f1', c2=kpi.color2||'#10b981';
        const isDark=this.state.currentTheme==='dark';
        const gridColor=isDark?'#2d3148':'#f0f4ff';
        const tickColor=isDark?'#6b7280':'#94a3b8';
        const commonOpts={responsive:true,maintainAspectRatio:false,animation:{duration:700,easing:'easeInOutQuart'},plugins:{legend:{display:false}}};
        const scales={y:{beginAtZero:true,grid:{color:gridColor},ticks:{color:tickColor,font:{size:10}}},x:{grid:{display:false},ticks:{color:tickColor,font:{size:10}}}};
        const colors=labels.map((_,i)=>`hsl(${(i*47+220)%360},65%,60%)`);

        switch(kpi.chart_type) {
            case 'bar':       return {type:'bar',data:{labels,datasets:[{data:dataVals,backgroundColor:c+'cc',borderColor:c,borderWidth:0,borderRadius:6,borderSkipped:false}]},options:{...commonOpts,scales}};
            case 'hbar':      return {type:'bar',data:{labels,datasets:[{data:dataVals,backgroundColor:c+'cc',borderColor:c,borderWidth:0,borderRadius:4}]},options:{...commonOpts,indexAxis:'y',scales:{x:{beginAtZero:true,grid:{color:gridColor},ticks:{color:tickColor}},y:{ticks:{color:tickColor,font:{size:10}}}}}};
            case 'line':      return {type:'line',data:{labels,datasets:[{data:dataVals,borderColor:c,borderWidth:2.5,backgroundColor:c+'18',fill:true,tension:0.4,pointRadius:3,pointBackgroundColor:c,pointBorderColor:'#fff',pointBorderWidth:2}]},options:{...commonOpts,scales}};
            case 'area':      return {type:'line',data:{labels,datasets:[{data:dataVals,borderColor:c,borderWidth:2,backgroundColor:c+'40',fill:true,tension:0.4,pointRadius:2}]},options:{...commonOpts,scales}};
            case 'pie':       return {type:'pie',data:{labels,datasets:[{data:dataVals,backgroundColor:colors,borderWidth:3,borderColor:isDark?'#1a1d2e':'#fff'}]},options:{...commonOpts,plugins:{legend:{display:true,position:'bottom',labels:{color:tickColor,font:{size:10},padding:8,usePointStyle:true}}}}};
            case 'doughnut':  return {type:'doughnut',data:{labels,datasets:[{data:dataVals,backgroundColor:colors,borderWidth:3,borderColor:isDark?'#1a1d2e':'#fff'}]},options:{...commonOpts,cutout:'68%',plugins:{legend:{display:true,position:'bottom',labels:{color:tickColor,font:{size:10},padding:6,usePointStyle:true}}}}};
            case 'radar':     return {type:'radar',data:{labels,datasets:[{data:dataVals,backgroundColor:c+'33',borderColor:c,borderWidth:2,pointBackgroundColor:c,pointRadius:3}]},options:{...commonOpts,scales:{r:{beginAtZero:true,grid:{color:gridColor},ticks:{color:tickColor,backdropColor:'transparent'}}}}};
            case 'polarArea': return {type:'polarArea',data:{labels,datasets:[{data:dataVals,backgroundColor:colors,borderWidth:2,borderColor:isDark?'#1a1d2e':'#fff'}]},options:{...commonOpts,plugins:{legend:{display:true,position:'bottom',labels:{color:tickColor}}}}};
            case 'scatter':   return {type:'scatter',data:{datasets:[{data:dataVals.map((v,i)=>({x:i,y:v})),backgroundColor:c+'cc',pointRadius:6,pointHoverRadius:8}]},options:{...commonOpts,scales}};
            case 'funnel':    return {type:'bar',data:{labels,datasets:[{data:dataVals,backgroundColor:labels.map((_,i)=>`hsla(${240+i*15},65%,55%,0.85)`),borderRadius:4}]},options:{...commonOpts,indexAxis:'y',scales:{x:{beginAtZero:true,grid:{color:gridColor}},y:{ticks:{color:tickColor}}}}};
            case 'mixed': {
                const prev=labels.map(()=>Math.round((kpi.value_previous||10)*(0.5+Math.random()*0.8)));
                return {data:{labels,datasets:[{type:'bar',label:'Actuel',data:dataVals,backgroundColor:c+'88',borderRadius:4},{type:'line',label:'Précédent',data:prev,borderColor:'#94a3b8',borderWidth:2,borderDash:[4,4],tension:0.4,pointRadius:2,fill:false}]},options:{...commonOpts,plugins:{legend:{display:true,position:'top',labels:{color:tickColor,usePointStyle:true}}},scales}};
            }
            case 'bullet': {
                const target=kpi.target_value||Math.max(...dataVals)*1.2||100;
                return {type:'bar',data:{labels:[kpi.name],datasets:[{label:'Valeur',data:[kpi.value||dataVals[0]||0],backgroundColor:c+'cc',borderRadius:4},{label:'Objectif',data:[target],backgroundColor:c+'22',borderRadius:4}]},options:{...commonOpts,indexAxis:'y',plugins:{legend:{display:true,labels:{color:tickColor,usePointStyle:true}}},scales:{x:{beginAtZero:true,max:target*1.1},y:{ticks:{color:tickColor}}}}};
            }
            case 'radial': {
                const val=kpi.value||0, target=kpi.target_value||100, pct=Math.min((val/target)*100,100);
                return {type:'doughnut',data:{datasets:[{data:[pct,100-pct],backgroundColor:[c,isDark?'#2d3148':'#f0f4ff'],borderWidth:0,circumference:180,rotation:270}]},options:{...commonOpts,cutout:'75%',plugins:{legend:{display:false},tooltip:{enabled:false}}}};
            }
            case 'flower': {
                const n=Math.min(labels.length,8),ls=labels.slice(0,n),vs=dataVals.slice(0,n);
                return {type:'polarArea',data:{labels:ls,datasets:[{data:vs,backgroundColor:ls.map((_,i)=>`hsl(${(i*360/n)%360},65%,65%)`),borderWidth:2,borderColor:isDark?'#1a1d2e':'#fff'}]},options:{...commonOpts,plugins:{legend:{display:true,position:'bottom',labels:{color:tickColor,font:{size:9},padding:6}}},scales:{r:{ticks:{display:false},grid:{color:gridColor}}}}};
            }
            default: return null;
        }
    }

    // ═══════════════════════════════════════════════════════════ VUE GLOBALE
    /**
     * ✅ FIX: renderGlobalChart amélioré
     *  - Appelle la méthode serveur get_kpis_with_comparison pour avoir de vraies
     *    valeurs Actuel vs Précédent calculées selon le filtre de date actif
     *  - Affiche un message clair si aucune donnée de comparaison n'est disponible
     *  - Gère le cas où value_previous est 0 partout (premier chargement)
     */
    async renderGlobalChart() {
        if (typeof Chart === 'undefined') return;
        const canvas = this.globalChartRef.el;
        if (!canvas) return;
        if (this.globalChart) { this.globalChart.destroy(); this.globalChart = null; }

        const isDark = this.state.currentTheme === 'dark';
        const tickColor = isDark ? '#94a3b8' : '#64748b';
        const gridColor = isDark ? '#2d3148' : '#f0f4ff';

        // 1. Récupérer les données avec comparaison depuis le serveur
        let kpisData = [];
        try {
            const dashId = this.state.activeTab || null;
            const dateFilter = this.state.globalDateFilter || 'this_month';
            kpisData = await this.rpc('/web/dataset/call_kw', {
                model: 'bi.kpi',
                method: 'get_kpis_with_comparison',
                args: [],
                kwargs: { dashboard_id: dashId, date_filter: dateFilter },
            });
        } catch (e) {
            // Fallback: utiliser les données déjà chargées en mémoire
            kpisData = this.state.filteredKpis
                .filter(k => ['indicator', 'counter', 'bar', 'line', 'area', 'number'].includes(k.chart_type))
                .map(k => ({
                    id: k.id,
                    name: k.name,
                    value: k.value || 0,
                    value_previous: k.value_previous || 0,
                    color: k.color || '#6366f1',
                    unit: k.unit || '',
                    evolution_pct: k.value_previous
                        ? Math.round(((k.value - k.value_previous) / Math.abs(k.value_previous)) * 1000) / 10
                        : 0,
                }));
        }

        // 2. Filtrer les KPIs pertinents pour ce graphique
        const kpis = kpisData.filter(k =>
            ['indicator', 'counter', 'bar', 'line', 'area', 'number'].includes(k.chart_type) ||
            !k.chart_type
        );
        if (!kpis.length) return;

        // 3. Vérifier si on a des données de comparaison réelles
        const hasPreviousData = kpis.some(k => k.value_previous && k.value_previous !== 0);

        const labels = kpis.map(k => k.name.length > 16 ? k.name.slice(0, 16) + '…' : k.name);
        const currentData = kpis.map(k => k.value || 0);
        const previousData = kpis.map(k => k.value_previous || 0);
        const bgColors = kpis.map(k => (k.color || '#6366f1') + 'bb');
        const borderColors = kpis.map(k => k.color || '#6366f1');

        // 4. Construire les datasets
        const datasets = [
            {
                type: 'bar',
                label: 'Actuel',
                data: currentData,
                backgroundColor: bgColors,
                borderColor: borderColors,
                borderWidth: 1,
                borderRadius: 6,
                order: 2,
            },
        ];

        if (hasPreviousData) {
            datasets.push({
                type: 'line',
                label: 'Précédent',
                data: previousData,
                borderColor: isDark ? '#94a3b8' : '#64748b',
                backgroundColor: 'transparent',
                borderWidth: 2,
                borderDash: [6, 4],
                tension: 0.4,
                pointRadius: 5,
                pointBackgroundColor: isDark ? '#94a3b8' : '#64748b',
                pointBorderColor: isDark ? '#1a1d2e' : '#fff',
                pointBorderWidth: 2,
                fill: false,
                order: 1,
            });
        }

        try {
            this.globalChart = new Chart(canvas.getContext('2d'), {
                type: 'bar',
                data: { labels, datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: { duration: 800, easing: 'easeInOutQuart' },
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top',
                            labels: {
                                usePointStyle: true,
                                color: tickColor,
                                padding: 20,
                                font: { size: 12 },
                            },
                        },
                        tooltip: {
                            callbacks: {
                                afterBody: (items) => {
                                    if (!hasPreviousData) return [];
                                    const idx = items[0]?.dataIndex;
                                    if (idx === undefined) return [];
                                    const kpi = kpis[idx];
                                    if (!kpi) return [];
                                    const pct = kpi.evolution_pct || 0;
                                    const arrow = pct >= 0 ? '↑' : '↓';
                                    const sign = pct >= 0 ? '+' : '';
                                    return [`${arrow} Évolution: ${sign}${pct}%`];
                                },
                            },
                        },
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: gridColor },
                            ticks: { color: tickColor, font: { size: 11 } },
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: tickColor, font: { size: 11 } },
                        },
                    },
                },
            });

            // Afficher un message si pas de données précédentes
            if (!hasPreviousData) {
                const ctx = canvas.getContext('2d');
                ctx.save();
                ctx.font = '12px sans-serif';
                ctx.fillStyle = isDark ? '#6b7280' : '#94a3b8';
                ctx.textAlign = 'right';
                ctx.fillText('ℹ️ Actualisez les KPIs pour voir la comparaison Précédent', canvas.width - 10, canvas.height - 8);
                ctx.restore();
            }
        } catch (e) {
            console.error('BI global chart error:', e);
        }
    }


        toggleSortMenu() { this.state.showSortMenu = !this.state.showSortMenu; }

    setSortOrder(order) {
        this.state.sortOrder = order;
        this.state.showSortMenu = false;
        this.applySortOrder();
    }

    applySortOrder() {
        let kpis = [...this.state.filteredKpis];
        switch(this.state.sortOrder) {
            case 'az':
                kpis.sort((a,b) => a.name.localeCompare(b.name, 'fr'));
                break;
            case 'za':
                kpis.sort((a,b) => b.name.localeCompare(a.name, 'fr'));
                break;
            case 'value_desc':
                kpis.sort((a,b) => (b.value||0) - (a.value||0));
                break;
            case 'value_asc':
                kpis.sort((a,b) => (a.value||0) - (b.value||0));
                break;
            default:
                kpis.sort((a,b) => (a.sequence||0) - (b.sequence||0));
        }
        this.state.filteredKpis = kpis;
    }

    getSortLabel() {
        const labels = {
            'default': '↕️ Ordre',
            'az':      '🔤 A → Z',
            'za':      '🔤 Z → A',
            'value_desc': '📊 Valeur ↓',
            'value_asc':  '📊 Valeur ↑',
        };
        return labels[this.state.sortOrder] || '↕️ Ordre';
    }

    getChartTypeLabel(chartType) {
        const ct = CHART_TYPES.find(c => c.value === chartType);
        return ct ? `${ct.icon} ${ct.label}` : chartType;
    }

    // ═══════════════════════════════════════════════════════════
    // WRAPPERS OWL2 — event handlers lisant data-* au lieu d'arrow functions
    // OWL2 perd le contexte `this` dans les arrow functions inline du template.
    // Solution : méthodes nommées qui lisent l'attribut data-* de l'événement.
    // ═══════════════════════════════════════════════════════════

    // Tabs
    onTabClick(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        this.setTab(id);
    }
    onDashBookmarkClick(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        this.toggleDashboardBookmark(id);
    }

    // KPI actions (boutons survol)
    onKpiRefresh(ev)  { this.refreshKpi(parseInt(ev.currentTarget.dataset.id, 10)); }
    onKpiEdit(ev)     { this.openEditModal(parseInt(ev.currentTarget.dataset.id, 10)); }
    onKpiSwitch(ev)   { this.openSwitchModal(parseInt(ev.currentTarget.dataset.id, 10)); }
    onKpiChat(ev)     { const el = ev.currentTarget; this.openChat(parseInt(el.dataset.id, 10), el.dataset.name); }
    onKpiExport(ev)   { this.openExportModal(parseInt(ev.currentTarget.dataset.id, 10)); }
    onKpiEditFull(ev) { this.editKpiFull(parseInt(ev.currentTarget.dataset.id, 10)); }
    onKpiBookmark(ev) { this.toggleKpiBookmark(parseInt(ev.currentTarget.dataset.id, 10)); }

    // Resize widget (select en mode édition)
    onResizeChange(ev) {
        const id = parseInt(ev.currentTarget.dataset.id, 10);
        this.onResizeSelect(id, ev.target.value);
    }

    // Tri
    onSortClick(ev) { this.setSortOrder(ev.currentTarget.dataset.order); }

    // Filtre date rapide
    onQuickDateFilter(ev) { this.setGlobalDateFilter(ev.currentTarget.dataset.filter); }

    // Thème
    onThemeClick(ev) { this.setTheme(ev.currentTarget.dataset.theme); }

    // Todos
    onTodoFilter(ev)  { this.setTodoFilter(ev.currentTarget.dataset.filter); }
    onTodoToggle(ev)  { this.toggleTodo(parseInt(ev.currentTarget.dataset.id, 10)); }
    onTodoDelete(ev)  { this.deleteTodo(parseInt(ev.currentTarget.dataset.id, 10)); }
    onNewTodoInput(ev)    { this.state.newTodoName = ev.target.value; }
    onNewTodoPriority(ev) { this.state.newTodoPriority = ev.target.value; }
    onNewTodoDeadline(ev) { this.state.newTodoDeadline = ev.target.value; }
    cancelAddTodo()       { this.state.showAddTodo = false; }

    // Switch type graphique
    onSwitchTypeClick(ev) {
        const type = ev.currentTarget.dataset.type;
        if (this.state.switchModal) {
            this.switchChartType(this.state.switchModal.kpiId, type);
        }
    }

    // Edition KPI rapide
    onEditKpiName(ev)      { if (this.state.editingKpi) this.state.editingKpi.name = ev.target.value; }
    onEditKpiColor(ev)     { if (this.state.editingKpi) this.state.editingKpi.color = ev.target.value; }
    onEditKpiColor2(ev)    { if (this.state.editingKpi) this.state.editingKpi.color2 = ev.target.value; }
    onEditKpiUnit(ev)      { if (this.state.editingKpi) this.state.editingKpi.unit = ev.target.value; }
    onEditKpiTarget(ev)    { if (this.state.editingKpi) this.state.editingKpi.target_value = parseFloat(ev.target.value) || 0; }
    onEditKpiSize(ev)      { if (this.state.editingKpi) this.state.editingKpi.widget_size = ev.target.value; }
    onEditKpiAlert(ev)     { if (this.state.editingKpi) this.state.editingKpi.alert_enabled = ev.target.checked; }
    onEditKpiThreshold(ev) { if (this.state.editingKpi) this.state.editingKpi.alert_threshold = parseFloat(ev.target.value) || 0; }

    // Export KPI
    onExportCsv()  { if (this.state.exportModal) this.exportKpiCsv(this.state.exportModal.kpiId); }
    onExportXlsx() { if (this.state.exportModal) this.exportKpiXlsx(this.state.exportModal.kpiId); }
    onExportPng()  { if (this.state.exportModal) this.exportKpiPng(this.state.exportModal.kpiId); }
    onExportJson() { if (this.state.exportModal) this.exportKpiJson(this.state.exportModal.kpiId); }

    // Chat KPI
    onChatInput(ev) { if (this.state.chatModal) this.state.chatModal.newMsg = ev.target.value; }

    // Chatbot IA
    onAiChatInput(ev) { this.state.aiChatbotInput = ev.target.value; }

    // Import
    onImportChartType(ev) { if (this.state.importPreview) this.state.importPreview.chartType = ev.target.value; }

    // IA modules

    // ── Synchronisation KPIs avec Odoo (rafraîchit les valeurs depuis les modèles) ──

    // ── Vider le cache des assets Odoo et recharger ─────────────────────────

    // ── Corriger les KPIs existants avec mauvais modèle/champ ──────────────
    async fixExistingKpis() {
        try {
            this.state.loading = true;
            const result = await this.rpc("/web/dataset/call_kw", {
                model: "bi.kpi",
                method: "fix_ai_generated_kpis",
                args: [],
                kwargs: {},
            });
            await this.loadData();
            if (result && result.fixed !== undefined) {
                const errMsg = result.errors && result.errors.length
                    ? ` (${result.errors.length} erreur(s))` : '';
                this.notification.add(
                    `✅ ${result.fixed} KPI(s) corrigés !${errMsg}`,
                    { type: result.errors && result.errors.length ? 'warning' : 'success' }
                );
            } else {
                this.notification.add("✅ KPIs corrigés !", { type: 'success' });
            }
        } catch (e) {
            console.error("Erreur fix KPIs:", e);
            const msg = e.message || (e.data && e.data.message) || "Erreur serveur";
            this.notification.add(`❌ Fix KPIs: ${msg}`, { type: 'danger' });
            this.state.loading = false;
        }
    }

    async clearAssetsCache() {
        try {
            const result = await this.rpc("/bi/clear_assets_cache", {});
            if (result && result.success) {
                this.notification.add(
                    "✅ Cache vidé ! Rechargement dans 2 secondes...",
                    { type: 'success' }
                );
                setTimeout(() => window.location.reload(true), 2000);
            } else {
                this.notification.add(
                    result?.error || "Erreur lors du vidage du cache",
                    { type: 'warning' }
                );
            }
        } catch (e) {
            // Fallback: hard reload
            this.notification.add("Rechargement forcé...", { type: 'info' });
            setTimeout(() => window.location.reload(true), 1000);
        }
    }

    async syncKpisWithOdoo() {
        if (!this.state.activeTab) {
            this.notification.add("Sélectionnez un dashboard d'abord", { type: 'warning' });
            return;
        }
        try {
            this.state.loading = true;
            await this.rpc("/web/dataset/call_kw", {
                model: "bi.kpi",
                method: "batch_refresh_by_dashboard",
                args: [this.state.activeTab],
                kwargs: {},
            });
            await this.loadData();
            this.notification.add("✅ KPIs synchronisés avec Odoo", { type: 'success' });
        } catch (e) {
            console.error("Erreur sync KPIs", e);
            this.notification.add("Erreur lors de la synchronisation", { type: 'danger' });
        } finally {
            this.state.loading = false;
        }
    }

    onAiModuleClick(ev) { this.toggleAiModule(ev.currentTarget.dataset.key); }
}

registry.category("actions").add("bi_realtime.dashboard_action", BiDashboardWidget);







