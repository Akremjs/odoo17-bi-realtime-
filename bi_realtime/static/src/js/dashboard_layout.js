
/** @odoo-module **/
/**
 * BI Realtime – Drag & Drop natif (sans GridStack, sans CDN)
 * Utilise HTML5 Drag and Drop API + CSS Grid
 * Zéro dépendance externe.
 */

export const SIZE_TO_COLS = { small: 1, medium: 2, large: 3, xlarge: 4 };

/**
 * Initialise le drag & drop natif sur le conteneur .bi-grid
 * @param {HTMLElement} container   - le div.bi-grid
 * @param {Function}    onSave      - callback(layoutJson) après chaque déplacement
 * @returns {Object}  instance { destroy, refresh }
 */
export function initNativeDragDrop(container, onSave) {
    if (!container) return null;

    let dragSrcEl = null;

    function saveLayout() {
        const layout = {};
        container.querySelectorAll('.bi-widget').forEach((el, index) => {
            const kpiId = el.dataset.kpiId;
            if (kpiId) layout[kpiId] = { order: index };
        });
        if (typeof onSave === 'function') onSave(JSON.stringify(layout));
    }

    function onDragStart(e) {
        dragSrcEl = this;
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', this.dataset.kpiId || '');
        setTimeout(() => this.classList.add('bi-drag-dragging'), 0);
    }

    function onDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        if (this !== dragSrcEl) this.classList.add('bi-drag-over');
        return false;
    }

    function onDragLeave() {
        this.classList.remove('bi-drag-over');
    }

    function onDrop(e) {
        e.stopPropagation();
        e.preventDefault();
        this.classList.remove('bi-drag-over');
        if (dragSrcEl && dragSrcEl !== this) {
            const allItems = Array.from(container.querySelectorAll('.bi-widget'));
            const srcIdx  = allItems.indexOf(dragSrcEl);
            const destIdx = allItems.indexOf(this);
            if (srcIdx < destIdx) {
                container.insertBefore(dragSrcEl, this.nextSibling);
            } else {
                container.insertBefore(dragSrcEl, this);
            }
            saveLayout();
        }
        return false;
    }

    function onDragEnd() {
        this.classList.remove('bi-drag-dragging');
        container.querySelectorAll('.bi-drag-over').forEach(el => el.classList.remove('bi-drag-over'));
        dragSrcEl = null;
    }

    function enableItem(el) {
        el.setAttribute('draggable', 'true');
        el.addEventListener('dragstart', onDragStart);
        el.addEventListener('dragover',  onDragOver);
        el.addEventListener('dragleave', onDragLeave);
        el.addEventListener('drop',      onDrop);
        el.addEventListener('dragend',   onDragEnd);
    }

    function disableItem(el) {
        el.removeAttribute('draggable');
        el.removeEventListener('dragstart', onDragStart);
        el.removeEventListener('dragover',  onDragOver);
        el.removeEventListener('dragleave', onDragLeave);
        el.removeEventListener('drop',      onDrop);
        el.removeEventListener('dragend',   onDragEnd);
    }

    container.querySelectorAll('.bi-widget').forEach(enableItem);

    return {
        destroy() { container.querySelectorAll('.bi-widget').forEach(disableItem); },
        refresh() {
            container.querySelectorAll('.bi-widget').forEach(el => { disableItem(el); enableItem(el); });
        },
    };
}

/**
 * Restaure l'ordre des cartes selon le layout sauvegardé
 */
export function restoreLayout(container, savedLayout) {
    if (!container || !savedLayout || !Object.keys(savedLayout).length) return;
    const items = Array.from(container.querySelectorAll('.bi-widget'));
    items.slice()
        .sort((a, b) => (savedLayout[a.dataset.kpiId]?.order ?? 999) - (savedLayout[b.dataset.kpiId]?.order ?? 999))
        .forEach(el => container.appendChild(el));
}







