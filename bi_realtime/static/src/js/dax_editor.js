
/** @odoo-module **/
/**
 * BI Realtime – Éditeur DAX intégré au Dashboard
 * Permet de créer/tester des formules DAX directement depuis le widget
 * avec autocomplétion, aperçu en temps réel et galerie d'exemples.
 */

// ──────────────────────────────────────────────────────────────────
//  Catalogue des fonctions DAX pour l'autocomplétion
// ──────────────────────────────────────────────────────────────────
const DAX_AUTOCOMPLETE = [
    // Agrégation
    { name: 'SUM',            snippet: 'SUM(${1:model}[${2:field}])',            desc: 'Somme des valeurs' },
    { name: 'AVERAGE',        snippet: 'AVERAGE(${1:model}[${2:field}])',        desc: 'Moyenne' },
    { name: 'COUNT',          snippet: 'COUNT(${1:model}[${2:field}])',          desc: 'Comptage' },
    { name: 'COUNTROWS',      snippet: 'COUNTROWS(${1:model})',                  desc: 'Nombre de lignes' },
    { name: 'DISTINCTCOUNT',  snippet: 'DISTINCTCOUNT(${1:model}[${2:field}])',  desc: 'Valeurs distinctes' },
    { name: 'MAX',            snippet: 'MAX(${1:model}[${2:field}])',            desc: 'Maximum' },
    { name: 'MIN',            snippet: 'MIN(${1:model}[${2:field}])',            desc: 'Minimum' },
    { name: 'MEDIAN',         snippet: 'MEDIAN(${1:model}[${2:field}])',         desc: 'Médiane' },
    // Filtres
    { name: 'CALCULATE',      snippet: 'CALCULATE(\n  ${1:expression},\n  ${2:filtre}\n)',  desc: 'Évalue avec filtre' },
    { name: 'DIVIDE',         snippet: 'DIVIDE(${1:numerateur}, ${2:denominateur})',        desc: 'Division sécurisée' },
    { name: 'IF',             snippet: 'IF(${1:condition}, ${2:si_vrai}, ${3:si_faux})',    desc: 'Condition' },
    { name: 'IFERROR',        snippet: 'IFERROR(${1:expression}, ${2:valeur_defaut})',      desc: 'Gestion erreurs' },
    // Temps
    { name: 'TOTALYTD',       snippet: 'TOTALYTD(${1:expression}, ${2:date_field})',        desc: 'Cumul année' },
    { name: 'TOTALMTD',       snippet: 'TOTALMTD(${1:expression}, ${2:date_field})',        desc: 'Cumul mois' },
    { name: 'TOTALQTD',       snippet: 'TOTALQTD(${1:expression}, ${2:date_field})',        desc: 'Cumul trimestre' },
    { name: 'DATESINPERIOD',  snippet: 'DATESINPERIOD(${1:date_field}, -${2:30}, ${3:DAY})', desc: 'Période glissante' },
    { name: 'SAMEPERIODLASTYEAR', snippet: 'SAMEPERIODLASTYEAR(${1:date_field})',           desc: 'Même période N-1' },
    // Maths
    { name: 'ROUND',          snippet: 'ROUND(${1:valeur}, ${2:decimales})',      desc: 'Arrondi' },
    { name: 'ABS',            snippet: 'ABS(${1:valeur})',                        desc: 'Valeur absolue' },
    { name: 'SQRT',           snippet: 'SQRT(${1:valeur})',                       desc: 'Racine carrée' },
    { name: 'INT',            snippet: 'INT(${1:valeur})',                        desc: 'Partie entière' },
];

// Modèles Odoo courants
const DAX_MODELS = [
    { name: 'sale.order',           label: 'Commandes ventes',   fields: ['amount_total','amount_untaxed','margin','id','partner_id','state','date_order'] },
    { name: 'account.move',         label: 'Factures',           fields: ['amount_total','amount_residual','invoice_date','state','payment_state','id'] },
    { name: 'crm.lead',             label: 'Opportunités CRM',   fields: ['expected_revenue','probability','id','stage_id','user_id','create_date'] },
    { name: 'stock.picking',        label: 'Transferts stock',   fields: ['id','state','scheduled_date','partner_id'] },
    { name: 'purchase.order',       label: 'Commandes achats',   fields: ['amount_total','id','state','date_order','partner_id'] },
    { name: 'hr.employee',          label: 'Employés',           fields: ['id','department_id','job_id','active'] },
    { name: 'pos.order',            label: 'Ventes POS',         fields: ['amount_total','id','state','date_order','partner_id'] },
    { name: 'product.product',      label: 'Produits',           fields: ['id','standard_price','list_price','qty_available'] },
    { name: 'account.move.line',    label: 'Lignes comptables',  fields: ['balance','debit','credit','id'] },
    { name: 'stock.quant',          label: 'Stocks',             fields: ['quantity','reserved_quantity','id','product_id'] },
];

// Exemples prêts à l'emploi
const DAX_QUICK_EXAMPLES = [
    { label: '💰 CA confirmé',         formula: 'CALCULATE(\n  SUM(sale.order[amount_total]),\n  sale.order[state] = "sale"\n)' },
    { label: '📈 Croissance MoM %',    formula: 'VAR ce_mois = TOTALMTD(SUM(sale.order[amount_total]), date_order)\nVAR mois_precedent = CALCULATE(SUM(sale.order[amount_total]), DATESINPERIOD(date_order, -60, DAY))\nRETURN DIVIDE(ce_mois - mois_precedent, mois_precedent) * 100' },
    { label: '🎯 Taux conversion %',   formula: 'DIVIDE(\n  CALCULATE(COUNT(sale.order[id]), sale.order[state] = "sale"),\n  COUNT(sale.order[id])\n) * 100' },
    { label: '📊 Marge brute %',       formula: 'DIVIDE(\n  SUM(sale.order[margin]),\n  SUM(sale.order[amount_total])\n) * 100' },
    { label: '📅 CA YTD',              formula: 'TOTALYTD(SUM(sale.order[amount_total]), date_order)' },
    { label: '👥 Clients actifs',      formula: 'CALCULATE(DISTINCTCOUNT(sale.order[partner_id]), sale.order[state] = "sale")' },
    { label: '💳 Factures impayées',   formula: 'CALCULATE(\n  SUM(account.move[amount_residual]),\n  account.move[payment_state] = "not_paid"\n)' },
    { label: '📦 Valeur stock',        formula: 'SUM(stock.quant[quantity]) * AVERAGE(product.product[standard_price])' },
    { label: '🔄 Same Period Last Year', formula: 'CALCULATE(\n  SUM(sale.order[amount_total]),\n  SAMEPERIODLASTYEAR(date_order)\n)' },
    { label: '💹 Ticket moyen',        formula: 'DIVIDE(\n  SUM(sale.order[amount_total]),\n  COUNT(sale.order[id])\n)' },
];

// ──────────────────────────────────────────────────────────────────
//  Classe principale : DaxEditorModal
// ──────────────────────────────────────────────────────────────────

export class DaxEditorModal {
    constructor(rpc, notification, onSave) {
        this.rpc = rpc;
        this.notification = notification;
        this.onSave = onSave;
        this._el = null;
        this._textarea = null;
        this._previewEl = null;
        this._debounceTimer = null;
        this._autocompleteList = null;
        this._currentMeasureId = null;
    }

    // ── Rendu HTML ────────────────────────────────────────────────

    render(containerId, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const formula = options.formula || '';
        const name    = options.name    || '';
        const unit    = options.unit    || '';
        const format  = options.format  || 'number';
        this._currentMeasureId = options.measureId || null;

        container.innerHTML = this._buildHTML(name, formula, unit, format);
        this._el = container;
        this._textarea = container.querySelector('.dax-editor-textarea');
        this._previewEl = container.querySelector('.dax-preview-result');
        this._autocompleteList = container.querySelector('.dax-autocomplete-list');

        this._attachEvents();
        if (formula) this._triggerPreview();
    }

    _buildHTML(name, formula, unit, format) {
        const examples = DAX_QUICK_EXAMPLES.map(ex =>
            `<button class="dax-example-btn" data-formula="${this._escAttr(ex.formula)}">${ex.label}</button>`
        ).join('');

        const modelOptions = DAX_MODELS.map(m =>
            `<option value="${m.name}">${m.label} (${m.name})</option>`
        ).join('');

        const formatOptions = [
            ['number','Nombre'],['decimal','Décimal'],['percent','Pourcentage %'],
            ['currency','Monnaie €'],['integer','Entier'],
        ].map(([v,l]) => `<option value="${v}" ${format===v?'selected':''}>${l}</option>`).join('');

        return `
<div class="dax-editor-wrap">

  <!-- En-tête -->
  <div class="dax-editor-header">
    <span class="dax-editor-icon">⚡</span>
    <span class="dax-editor-title">Éditeur DAX</span>
    <span class="dax-editor-badge">Power BI-like</span>
  </div>

  <!-- Infos mesure -->
  <div class="dax-meta-row">
    <div class="dax-field-group">
      <label class="dax-label">Nom de la mesure</label>
      <input class="dax-input" type="text" id="daxMeasureName"
             value="${this._escAttr(name)}" placeholder="Ex: CA Confirmé"/>
    </div>
    <div class="dax-field-group">
      <label class="dax-label">Format</label>
      <select class="dax-select" id="daxMeasureFormat">${formatOptions}</select>
    </div>
    <div class="dax-field-group">
      <label class="dax-label">Unité</label>
      <input class="dax-input" type="text" id="daxMeasureUnit"
             value="${this._escAttr(unit)}" placeholder="€, %, jours…"/>
    </div>
  </div>

  <!-- Corps : éditeur + aide -->
  <div class="dax-editor-body">

    <!-- Colonne gauche : éditeur -->
    <div class="dax-editor-col">
      <div class="dax-toolbar">
        <span class="dax-toolbar-label">📐 Formule</span>
        <div class="dax-toolbar-btns">
          <button class="dax-tb-btn" id="daxBtnValidate">✓ Valider</button>
          <button class="dax-tb-btn dax-tb-btn-primary" id="daxBtnCompute">▶ Calculer</button>
        </div>
      </div>

      <div class="dax-editor-area-wrap" style="position:relative">
        <div class="dax-line-numbers" id="daxLineNumbers">1</div>
        <textarea class="dax-editor-textarea" id="daxFormulaTextarea"
                  spellcheck="false"
                  placeholder="Saisir une formule DAX…&#10;Ex: CALCULATE(SUM(sale.order[amount_total]), sale.order[state]=&quot;sale&quot;)"
>${this._escHtml(formula)}</textarea>
        <div class="dax-autocomplete-list" id="daxAutocomplete" style="display:none"></div>
      </div>

      <!-- Aperçu résultat -->
      <div class="dax-preview-bar">
        <span class="dax-preview-label">Résultat :</span>
        <span class="dax-preview-result" id="daxPreviewResult">—</span>
        <span class="dax-preview-status" id="daxPreviewStatus"></span>
      </div>

      <!-- Modèle helper -->
      <div class="dax-model-helper">
        <label class="dax-label">📋 Référence rapide :</label>
        <select class="dax-select" id="daxModelHelper">
          <option value="">— Sélectionner un modèle —</option>
          ${modelOptions}
        </select>
        <div class="dax-fields-chips" id="daxFieldsChips"></div>
      </div>
    </div>

    <!-- Colonne droite : aide & exemples -->
    <div class="dax-help-col">
      <div class="dax-help-tabs">
        <button class="dax-help-tab active" data-tab="examples">💡 Exemples</button>
        <button class="dax-help-tab" data-tab="functions">📚 Fonctions</button>
      </div>

      <!-- Onglet exemples -->
      <div class="dax-help-panel active" id="daxTabExamples">
        <div class="dax-examples-grid">${examples}</div>
      </div>

      <!-- Onglet fonctions -->
      <div class="dax-help-panel" id="daxTabFunctions">
        <div class="dax-fn-list">
          ${this._buildFunctionsList()}
        </div>
      </div>
    </div>

  </div><!-- /dax-editor-body -->

  <!-- Boutons de sauvegarde -->
  <div class="dax-editor-footer">
    <button class="dax-btn-save" id="daxBtnSave">💾 Sauvegarder la mesure</button>
    <button class="dax-btn-cancel" id="daxBtnCancel">Annuler</button>
  </div>

</div><!-- /dax-editor-wrap -->
`;
    }

    _buildFunctionsList() {
        return DAX_AUTOCOMPLETE.map(fn => `
          <div class="dax-fn-item" data-snippet="${this._escAttr(fn.snippet)}">
            <span class="dax-fn-name">${fn.name}</span>
            <span class="dax-fn-desc">${fn.desc}</span>
          </div>
        `).join('');
    }

    // ── Événements ────────────────────────────────────────────────

    _attachEvents() {
        const ta = this._textarea;

        // Numéros de ligne
        ta.addEventListener('input', () => {
            this._updateLineNumbers();
            this._triggerAutoComplete();
            this._debouncedPreview();
        });
        ta.addEventListener('scroll', () => {
            const ln = document.getElementById('daxLineNumbers');
            if (ln) ln.scrollTop = ta.scrollTop;
        });
        ta.addEventListener('keydown', (e) => this._handleKeyDown(e));

        // Boutons
        document.getElementById('daxBtnValidate')?.addEventListener('click', () => this._validate());
        document.getElementById('daxBtnCompute')?.addEventListener('click', () => this._compute());
        document.getElementById('daxBtnSave')?.addEventListener('click', () => this._save());
        document.getElementById('daxBtnCancel')?.addEventListener('click', () => this._cancel());

        // Exemples
        this._el.querySelectorAll('.dax-example-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                ta.value = btn.dataset.formula;
                this._updateLineNumbers();
                this._debouncedPreview();
            });
        });

        // Onglets aide
        this._el.querySelectorAll('.dax-help-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this._el.querySelectorAll('.dax-help-tab').forEach(t => t.classList.remove('active'));
                this._el.querySelectorAll('.dax-help-panel').forEach(p => p.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(`daxTab${tab.dataset.tab.charAt(0).toUpperCase() + tab.dataset.tab.slice(1)}`)
                    ?.classList.add('active');
            });
        });

        // Clic sur une fonction dans la liste
        this._el.querySelectorAll('.dax-fn-item').forEach(item => {
            item.addEventListener('click', () => {
                const snippet = item.dataset.snippet.replace(/\$\{[0-9]+:([^}]+)\}/g, '$1');
                ta.value = snippet;
                ta.focus();
                this._updateLineNumbers();
                this._debouncedPreview();
            });
        });

        // Modèle helper
        document.getElementById('daxModelHelper')?.addEventListener('change', (e) => {
            const modelName = e.target.value;
            const model = DAX_MODELS.find(m => m.name === modelName);
            const chips = document.getElementById('daxFieldsChips');
            if (!chips) return;
            chips.innerHTML = '';
            if (!model) return;
            model.fields.forEach(f => {
                const chip = document.createElement('span');
                chip.className = 'dax-field-chip';
                chip.textContent = `[${f}]`;
                chip.title = `Cliquer pour insérer ${modelName}[${f}]`;
                chip.addEventListener('click', () => {
                    const ref = `${modelName}[${f}]`;
                    this._insertAtCursor(ref);
                });
                chips.appendChild(chip);
            });
        });
    }

    _handleKeyDown(e) {
        // Tab → 2 espaces
        if (e.key === 'Tab') {
            e.preventDefault();
            this._insertAtCursor('  ');
        }
        // Escape → fermer autocomplétion
        if (e.key === 'Escape') {
            this._hideAutocomplete();
        }
        // Enter sur autocomplétion → sélectionner
        if (e.key === 'Enter' && this._autocompleteList?.style.display !== 'none') {
            const active = this._autocompleteList?.querySelector('.dax-ac-item.active');
            if (active) {
                e.preventDefault();
                active.click();
            }
        }
        // Flèches sur autocomplétion
        if (['ArrowUp', 'ArrowDown'].includes(e.key) && this._autocompleteList?.style.display !== 'none') {
            e.preventDefault();
            const items = [...(this._autocompleteList?.querySelectorAll('.dax-ac-item') || [])];
            const activeIdx = items.findIndex(i => i.classList.contains('active'));
            items.forEach(i => i.classList.remove('active'));
            let next = e.key === 'ArrowDown' ? activeIdx + 1 : activeIdx - 1;
            if (next < 0) next = items.length - 1;
            if (next >= items.length) next = 0;
            items[next]?.classList.add('active');
        }
    }

    // ── Autocomplétion ────────────────────────────────────────────

    _triggerAutoComplete() {
        const ta = this._textarea;
        const pos = ta.selectionStart;
        const text = ta.value.substring(0, pos);
        const word = text.match(/([A-Z_]{2,})$/i)?.[1] || '';

        if (word.length < 2) { this._hideAutocomplete(); return; }

        const matches = DAX_AUTOCOMPLETE.filter(f =>
            f.name.toUpperCase().startsWith(word.toUpperCase())
        ).slice(0, 8);

        if (!matches.length) { this._hideAutocomplete(); return; }

        const list = this._autocompleteList;
        if (!list) return;
        list.innerHTML = matches.map((m, i) => `
          <div class="dax-ac-item ${i===0?'active':''}" data-name="${m.name}" data-snippet="${this._escAttr(m.snippet)}">
            <span class="dax-ac-name">${m.name}</span>
            <span class="dax-ac-desc">${m.desc}</span>
          </div>
        `).join('');

        list.querySelectorAll('.dax-ac-item').forEach(item => {
            item.addEventListener('click', () => {
                const snippet = item.dataset.snippet.replace(/\$\{[0-9]+:([^}]+)\}/g, '$1');
                // Remplacer le mot en cours par le snippet
                const before = ta.value.substring(0, pos - word.length);
                const after  = ta.value.substring(pos);
                ta.value = before + snippet + after;
                this._hideAutocomplete();
                ta.focus();
                this._updateLineNumbers();
                this._debouncedPreview();
            });
        });

        list.style.display = 'block';
    }

    _hideAutocomplete() {
        if (this._autocompleteList) this._autocompleteList.style.display = 'none';
    }

    // ── Prévisualisation live ─────────────────────────────────────

    _debouncedPreview() {
        clearTimeout(this._debounceTimer);
        this._debounceTimer = setTimeout(() => this._triggerPreview(), 900);
    }

    async _triggerPreview() {
        const formula = this._textarea?.value?.trim();
        if (!formula) return;
        const statusEl = document.getElementById('daxPreviewStatus');
        const resultEl = document.getElementById('daxPreviewResult');
        if (statusEl) statusEl.textContent = '⟳ Calcul…';
        if (resultEl) resultEl.textContent = '…';
        try {
            const res = await this.rpc('/web/dataset/call_kw', {
                model: 'bi.dax.measure',
                method: 'compute_formula_inline',
                args: [],
                kwargs: { formula, date_filter: 'this_month' },
            });
            if (res.error) {
                if (resultEl) { resultEl.textContent = '❌ Erreur'; resultEl.style.color = '#e74c3c'; }
                if (statusEl) statusEl.textContent = res.error.slice(0, 120);
            } else {
                const fmt = this._formatPreviewValue(res.value, document.getElementById('daxMeasureFormat')?.value);
                if (resultEl) { resultEl.textContent = fmt; resultEl.style.color = '#2ecc71'; }
                if (statusEl) statusEl.textContent = '✓ OK';
            }
        } catch (e) {
            if (resultEl) { resultEl.textContent = '—'; resultEl.style.color = '#aaa'; }
            if (statusEl) statusEl.textContent = '';
        }
    }

    _formatPreviewValue(val, format) {
        if (val === null || val === undefined) return '—';
        const v = parseFloat(val);
        if (isNaN(v)) return String(val);
        if (format === 'percent')  return `${v.toFixed(2)}%`;
        if (format === 'currency') return `${v.toLocaleString('fr-FR', {minimumFractionDigits:2})} €`;
        if (format === 'integer')  return Math.round(v).toLocaleString('fr-FR');
        return v.toLocaleString('fr-FR', {minimumFractionDigits:2, maximumFractionDigits:4});
    }

    // ── Actions ───────────────────────────────────────────────────

    async _validate() {
        const formula = this._textarea?.value?.trim();
        if (!formula) return;
        try {
            const res = await this.rpc('/web/dataset/call_kw', {
                model: 'bi.dax.measure', method: 'compute_formula_inline',
                args: [], kwargs: { formula },
            });
            const statusEl = document.getElementById('daxPreviewStatus');
            if (res.error) {
                if (statusEl) statusEl.textContent = `❌ ${res.error}`;
                this.notification.add(`❌ Erreur DAX : ${res.error}`, { type: 'danger' });
            } else {
                if (statusEl) statusEl.textContent = '✓ Formule valide';
                this.notification.add('✅ Formule DAX valide !', { type: 'success' });
            }
        } catch (e) {
            this.notification.add('Erreur de validation', { type: 'warning' });
        }
    }

    async _compute() {
        await this._triggerPreview();
    }

    async _save() {
        const formula = this._textarea?.value?.trim();
        const name    = document.getElementById('daxMeasureName')?.value?.trim();
        const unit    = document.getElementById('daxMeasureUnit')?.value?.trim();
        const format  = document.getElementById('daxMeasureFormat')?.value;
        if (!formula) {
            this.notification.add('La formule est vide.', { type: 'warning' });
            return;
        }
        if (this.onSave) {
            await this.onSave({ formula, name, unit, format, measureId: this._currentMeasureId });
        }
    }

    _cancel() {
        if (this.onSave) this.onSave(null);
    }

    // ── Helpers ───────────────────────────────────────────────────

    _insertAtCursor(text) {
        const ta = this._textarea;
        if (!ta) return;
        const start = ta.selectionStart;
        const end   = ta.selectionEnd;
        ta.value = ta.value.substring(0, start) + text + ta.value.substring(end);
        ta.selectionStart = ta.selectionEnd = start + text.length;
        ta.focus();
        this._updateLineNumbers();
        this._debouncedPreview();
    }

    _updateLineNumbers() {
        const ta = this._textarea;
        const ln = document.getElementById('daxLineNumbers');
        if (!ta || !ln) return;
        const lines = ta.value.split('\n').length;
        ln.innerHTML = Array.from({length: lines}, (_, i) => i + 1).join('<br>');
    }

    _escHtml(str) {
        return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }
    _escAttr(str) {
        return String(str).replace(/"/g,'&quot;').replace(/'/g,'&#39;').replace(/\n/g,'&#10;');
    }
}

export { DAX_QUICK_EXAMPLES, DAX_AUTOCOMPLETE, DAX_MODELS };







