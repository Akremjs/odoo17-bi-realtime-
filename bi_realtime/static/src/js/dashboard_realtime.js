
/** @odoo-module **/
/**
 * BI Realtime — Refresh temps réel
 *
 * Stratégie en 3 couches :
 *   1. Odoo Bus (WebSocket/longpoll) — notifications push instantanées
 *      déclenché par bi_bus_notify.py lui-même alimenté par Kafka consumer
 *   2. setInterval configurable — fallback si Bus indisponible
 *   3. visibilitychange — refresh au retour sur l'onglet
 */

import { useService } from "@web/core/utils/hooks";
import { onMounted, onWillUnmount } from "@odoo/owl";

/**
 * Hook OWL principal
 * @param {Object}   options
 * @param {Function} options.dashboardId   () => number|null
 * @param {Function} options.intervalSec   () => number  (défaut 30)
 * @param {Function} options.onRefresh     async () => void
 * @param {Function} [options.onKpiPush]   async (payload) => void  callback live
 */
export function useRealtimeRefresh({ dashboardId, intervalSec, onRefresh, onKpiPush }) {

    let busService    = null;
    let fallbackTimer = null;
    let busChannel    = null;
    let subscribed    = false;
    let _paused       = false;

    try { busService = useService('bus_service'); } catch { busService = null; }

    // ── Fallback interval ────────────────────────────────────────
    const startFallback = () => {
        stopFallback();
        const ms = (intervalSec?.() || 30) * 1000;
        fallbackTimer = setInterval(async () => {
            if (!_paused) { try { await onRefresh(); } catch {} }
        }, ms);
    };
    const stopFallback = () => {
        if (fallbackTimer) { clearInterval(fallbackTimer); fallbackTimer = null; }
    };

    // ── Handler messages Bus (provenant du kafka-consumer → Odoo Bus) ──
    const handleBusMessage = async (message) => {
        if (!message || _paused) return;
        const { type, payload } = message;

        switch (type) {

            // KPI mis à jour (par kafka-consumer via bi_bus_notify)
            case 'bi_kpi_updated': {
                const targetDash = payload?.dashboard_id;
                const myDash     = dashboardId?.();
                if (!targetDash || !myDash || targetDash === myDash) {
                    // Callback live optionnel (mise à jour partielle sans reload complet)
                    if (onKpiPush && payload) {
                        try { await onKpiPush(payload); } catch {}
                    } else {
                        try { await onRefresh(); } catch {}
                    }
                }
                break;
            }

            // Dashboard modifié (layout, thème…)
            case 'bi_dashboard_updated': {
                const targetDash = payload?.dashboard_id;
                const myDash     = dashboardId?.();
                if (!targetDash || !myDash || targetDash === myDash) {
                    try { await onRefresh(); } catch {}
                }
                break;
            }

            // Snapshot Kafka complet (tous les KPIs)
            case 'bi_kafka_snapshot': {
                try { await onRefresh(); } catch {}
                break;
            }

            default:
                break;
        }
    };

    // ── Abonnement / désabonnement Bus ────────────────────────────
    const subscribeBus = () => {
        if (!busService) return;
        const did = dashboardId?.();
        if (!did) return;
        const channel = `bi_dashboard_${did}`;
        if (channel === busChannel && subscribed) return;
        unsubscribeBus();
        try {
            busChannel = channel;
            busService.subscribe(channel, handleBusMessage);
            subscribed = true;
        } catch (e) {
            console.warn('[BI Realtime] Bus subscribe error:', e);
        }
    };

    const unsubscribeBus = () => {
        if (busService && busChannel && subscribed) {
            try { busService.unsubscribe(busChannel, handleBusMessage); } catch {}
            subscribed = false;
            busChannel = null;
        }
    };

    // ── Visibilité onglet ────────────────────────────────────────
    const handleVisibility = async () => {
        if (document.visibilityState === 'visible' && !_paused) {
            try { await onRefresh(); } catch {}
            // Réabonner si la session a été perdue
            if (!subscribed) subscribeBus();
        }
    };

    // ── Lifecycle OWL ────────────────────────────────────────────
    onMounted(() => {
        subscribeBus();
        startFallback();
        document.addEventListener('visibilitychange', handleVisibility);
    });

    onWillUnmount(() => {
        unsubscribeBus();
        stopFallback();
        document.removeEventListener('visibilitychange', handleVisibility);
    });

    // ── API publique ─────────────────────────────────────────────
    return {
        /** Appeler quand l'utilisateur change d'onglet dashboard */
        onDashboardChange: () => {
            unsubscribeBus();
            subscribeBus();
            startFallback();
        },
        forceRefresh: async () => { try { await onRefresh(); } catch {} },
        pause:  () => { _paused = true;  stopFallback();  unsubscribeBus(); },
        resume: () => { _paused = false; startFallback(); subscribeBus();   },
        isSubscribed: () => subscribed,
    };
}







