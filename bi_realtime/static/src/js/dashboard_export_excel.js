
/** @odoo-module **/
/**
 * BI Realtime – Export Excel (XLSX) via SheetJS
 * Fonctions : exportKpiToExcel, exportDashboardToExcel
 */

function requireXLSX() {
    if (typeof XLSX === 'undefined') throw new Error('SheetJS non chargé');
    return XLSX;
}

function kpiToRows(kpi) {
    const rows = [];
    if (kpi.chart_data) {
        try {
            const data = JSON.parse(kpi.chart_data);
            if (typeof data === 'object' && !Array.isArray(data)) {
                rows.push(['Catégorie', 'Valeur', '% du total']);
                const total = Object.values(data).reduce((a, b) => a + b, 0) || 1;
                Object.entries(data)
                    .sort((a, b) => b[1] - a[1])
                    .forEach(([label, value]) => {
                        rows.push([label, value, ((value / total) * 100).toFixed(1) + '%']);
                    });
            }
        } catch {}
    }
    if (rows.length === 0) {
        rows.push(['KPI', 'Valeur actuelle', 'Valeur précédente', 'Objectif', 'Unité']);
        rows.push([kpi.name, kpi.value ?? 0, kpi.value_previous ?? 0, kpi.target_value ?? 0, kpi.unit ?? '']);
    }
    return rows;
}

/**
 * Exporte un KPI en fichier .xlsx
 * @param {Object} kpi
 */
export function exportKpiToExcel(kpi) {
    const X = requireXLSX();
    const rows = kpiToRows(kpi);
    const ws = X.utils.aoa_to_sheet(rows);
    ws['!cols'] = rows[0].map(() => ({ wch: 22 }));
    const lastRow = rows.length + 2;
    X.utils.sheet_add_aoa(ws, [[], [`Exporté le : ${new Date().toLocaleString('fr-FR')}`, '', `KPI : ${kpi.name}`]], { origin: lastRow });
    const wb = X.utils.book_new();
    X.utils.book_append_sheet(wb, ws, kpi.name.slice(0, 31));
    X.writeFile(wb, `kpi_${kpi.name.replace(/[^a-zA-Z0-9_]/g, '_')}.xlsx`);
}

/**
 * Exporte tout le dashboard en fichier .xlsx multi-onglets
 * @param {Array}  kpis
 * @param {string} dashName
 */
export function exportDashboardToExcel(kpis, dashName = 'Dashboard') {
    const X = requireXLSX();
    const wb = X.utils.book_new();

    // Onglet récapitulatif
    const summaryRows = [['Nom KPI', 'Type', 'Valeur actuelle', 'Valeur précédente', 'Objectif', 'Unité']];
    kpis.forEach(k => summaryRows.push([k.name, k.chart_type, k.value ?? 0, k.value_previous ?? 0, k.target_value ?? 0, k.unit ?? '']));
    const wsSummary = X.utils.aoa_to_sheet(summaryRows);
    wsSummary['!cols'] = summaryRows[0].map(() => ({ wch: 20 }));
    X.utils.book_append_sheet(wb, wsSummary, 'Récapitulatif');

    // Un onglet par KPI
    kpis.forEach(kpi => {
        const rows = kpiToRows(kpi);
        const ws = X.utils.aoa_to_sheet(rows);
        ws['!cols'] = rows[0].map(() => ({ wch: 22 }));
        const sheetName = kpi.name.replace(/[\/\\?\*\[\]]/g, '').slice(0, 31) || `KPI_${kpi.id}`;
        X.utils.book_append_sheet(wb, ws, sheetName);
    });

    // Onglet méta
    const metaWs = X.utils.aoa_to_sheet([
        ['Dashboard', dashName],
        ['Exporté le', new Date().toLocaleString('fr-FR')],
        ['Nombre de KPIs', kpis.length],
    ]);
    X.utils.book_append_sheet(wb, metaWs, 'Infos');

    X.writeFile(wb, `${dashName.replace(/[^a-zA-Z0-9_]/g, '_')}_export.xlsx`);
}







