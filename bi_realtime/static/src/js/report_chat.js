/**
 * Chat IA flottant pour les Rapports BI
 * Même style que le dashboard — position fixe en bas à droite
 */
(function() {
    'use strict';

    function pad(n) { return n < 10 ? '0' + n : n; }
    function getTime() {
        var d = new Date();
        return pad(d.getHours()) + ':' + pad(d.getMinutes());
    }

    function createChatWidget() {
        // Chercher si on est sur une page bi.report
        var bodyClass = document.body.className || '';
        var isReportPage = document.querySelector('.o_form_view') &&
            (window.location.hash.includes('bi.report') ||
             document.querySelector('[data-model="bi.report"]') ||
             document.querySelector('.o_bi_report_chat'));

        if (!isReportPage) return;

        // Éviter double initialisation
        if (document.getElementById('bi-report-chat-fab-wrap')) return;

        var reportId = null;
        var urlMatch = window.location.hash.match(/id=(\d+)/);
        if (urlMatch) reportId = urlMatch[1];

        var messages = [
            {
                role: 'assistant',
                text: '👋 Bonjour ! Je suis votre assistant BI. Posez-moi des questions sur ce rapport, demandez des analyses ou des recommandations.',
                time: getTime()
            }
        ];
        var isOpen = false;
        var isLoading = false;

        // Créer le widget
        var wrap = document.createElement('div');
        wrap.id = 'bi-report-chat-fab-wrap';
        wrap.className = 'bi-report-chat-fab-wrap';
        document.body.appendChild(wrap);

        function render() {
            wrap.innerHTML = '';

            if (isOpen) {
                var win = document.createElement('div');
                win.className = 'bi-report-chat-window';

                // Header
                var header = document.createElement('div');
                header.className = 'bi-report-chat-header';
                header.innerHTML = '' +
                    '<div class="bi-report-chat-hd-left">' +
                        '<div class="bi-report-chat-avatar">🤖</div>' +
                        '<div>' +
                            '<div class="bi-report-chat-name">Assistant BI</div>' +
                            '<div class="bi-report-chat-status">● En ligne — llama3.2</div>' +
                        '</div>' +
                    '</div>' +
                    '<button class="bi-report-chat-close" id="bi-report-chat-close">✕</button>';
                win.appendChild(header);

                // Messages
                var msgZone = document.createElement('div');
                msgZone.className = 'bi-report-chat-messages';
                msgZone.id = 'bi-report-chat-messages';

                messages.forEach(function(msg) {
                    var row = document.createElement('div');
                    row.className = 'bi-report-chat-msg ' +
                        (msg.role === 'user' ? 'bi-report-chat-msg-user' : 'bi-report-chat-msg-bot');

                    var html = '';
                    if (msg.role !== 'user') {
                        html += '<div class="bi-report-chat-bubble-avatar">🤖</div>';
                    }
                    html += '<div class="bi-report-chat-bubble-wrap">' +
                        '<div class="bi-report-chat-bubble">' + msg.text + '</div>' +
                        '<span class="bi-report-chat-bubble-time">' + msg.time + '</span>' +
                    '</div>';
                    row.innerHTML = html;
                    msgZone.appendChild(row);
                });

                if (isLoading) {
                    var typing = document.createElement('div');
                    typing.className = 'bi-report-chat-msg bi-report-chat-msg-bot';
                    typing.innerHTML = '<div class="bi-report-chat-typing"><span></span><span></span><span></span></div>';
                    msgZone.appendChild(typing);
                }
                win.appendChild(msgZone);

                // Input
                var inputWrap = document.createElement('div');
                inputWrap.className = 'bi-report-chat-input-wrap';
                inputWrap.innerHTML = '' +
                    '<input class="bi-report-chat-input" id="bi-report-chat-input" ' +
                        'type="text" placeholder="Posez votre question sur ce rapport..."/>' +
                    '<button class="bi-report-chat-send" id="bi-report-chat-send">➤</button>';
                win.appendChild(inputWrap);
                wrap.appendChild(win);

                // Scroll bas
                setTimeout(function() {
                    var mz = document.getElementById('bi-report-chat-messages');
                    if (mz) mz.scrollTop = mz.scrollHeight;
                }, 50);

                // Events
                document.getElementById('bi-report-chat-close').addEventListener('click', function() {
                    isOpen = false; render();
                });

                var input = document.getElementById('bi-report-chat-input');
                var sendBtn = document.getElementById('bi-report-chat-send');

                function sendMessage() {
                    var text = input.value.trim();
                    if (!text || isLoading) return;
                    messages.push({ role: 'user', text: text, time: getTime() });
                    input.value = '';
                    isLoading = true;
                    render();
                    askAI(text);
                }

                sendBtn.addEventListener('click', sendMessage);
                input.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') sendMessage();
                });
                input.focus();
            }

            // FAB button
            var fab = document.createElement('button');
            fab.className = 'bi-report-chat-fab' + (isOpen ? ' bi-report-chat-fab-open' : '');
            fab.innerHTML = isOpen ? '✕' : '🤖';
            fab.addEventListener('click', function() {
                isOpen = !isOpen; render();
            });
            wrap.appendChild(fab);
        }

        function askAI(text) {
            // Récupérer le report_id depuis l'URL ou le DOM
            var id = reportId;
            if (!id) {
                var match = window.location.hash.match(/[?&]id=(\d+)/);
                if (match) id = match[1];
            }

            if (id) {
                // Appel via RPC Odoo
                fetch('/web/dataset/call_kw', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        method: 'call',
                        params: {
                            model: 'bi.report',
                            method: 'action_chat_ai',
                            args: [[parseInt(id)], text],
                            kwargs: {}
                        }
                    })
                })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var response = (data.result) || "Je n'ai pas pu analyser votre question.";
                    messages.push({ role: 'assistant', text: response, time: getTime() });
                    isLoading = false;
                    render();
                })
                .catch(function() {
                    messages.push({
                        role: 'assistant',
                        text: "Erreur de connexion à l'IA. Vérifiez que le rapport est généré.",
                        time: getTime()
                    });
                    isLoading = false;
                    render();
                });
            } else {
                // Pas d'ID — message générique
                setTimeout(function() {
                    messages.push({
                        role: 'assistant',
                        text: "Pour une analyse personnalisée, veuillez d'abord générer le rapport (bouton 🚀 Générer).",
                        time: getTime()
                    });
                    isLoading = false;
                    render();
                }, 800);
            }
        }

        render();
    }

    // Observer les changements de page (Odoo SPA)
    var lastHash = '';
    function checkPage() {
        if (window.location.hash !== lastHash) {
            lastHash = window.location.hash;
            setTimeout(function() {
                // Supprimer l'ancien widget
                var old = document.getElementById('bi-report-chat-fab-wrap');
                if (old) old.remove();
                // Recréer si nécessaire
                createChatWidget();
            }, 600);
        }
    }

    // Init au chargement
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(createChatWidget, 1000);
            setInterval(checkPage, 500);
        });
    } else {
        setTimeout(createChatWidget, 1000);
        setInterval(checkPage, 500);
    }

})();
