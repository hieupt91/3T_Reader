// 3T Reader — PDF.js UI overrides and event hooks
//
// Hides the built-in PDF.js toolbar/sidebar (the app provides its own),
// installs event listeners for find state, page tracking, selection
// caching, and QWebChannel bridge helpers.
(function () {
    // --- Hide built-in chrome ---
    var css = [
        '#toolbarContainer { display: none !important; }',
        '#loadingBar { display: none !important; }',
        '#viewsManager { display: none !important; }',
        '#mainContainer { top: 0 !important; }',
        '#viewerContainer { top: 0 !important; left: 0 !important; }',
        'body { background-color: #0f0f13 !important; }',
        '#viewer .page {',
        '  border: none !important;',
        '  box-shadow: 0 4px 24px rgba(0,0,0,.5) !important;',
        '  margin: 16px auto !important;',
        '  border-radius: 4px !important;',
        '}',
        // Signature widget annotations are rendered as static appearance
        // streams (annotationMode=ENABLE) so they stay visible without
        // needing to hide interactive form inputs.
        '.annotationLayer .signatureWidgetAnnotation { cursor: pointer !important; }',
    ].join('\n');
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);

    // --- Install PDF.js event hooks (retried until eventBus is ready) ---
    window.__3tFindState = -1;   // -1=unknown, 0=notFound, 1=found, 2=wrapped
    window.__3tCurrentPage = 0;

    function readVisiblePage(app) {
        try {
            var viewer = app && app.pdfViewer;
            if (!viewer) return 0;

            var visible = null;
            if (typeof viewer._getVisiblePages === 'function') {
                visible = viewer._getVisiblePages();
            } else if (viewer._visiblePages) {
                visible = viewer._visiblePages;
            } else if (viewer.visiblePages) {
                visible = viewer.visiblePages;
            }

            var views = visible && (visible.views || visible);
            if (views && views.length) {
                var best = views[0];
                var bestPercent = -1;
                for (var i = 0; i < views.length; i++) {
                    var item = views[i];
                    var percent = Number(item.percent || 0);
                    if (percent > bestPercent) {
                        best = item;
                        bestPercent = percent;
                    }
                }
                return parseInt(best.id || (best.view && best.view.id) || 0, 10) || 0;
            }

            if (viewer._location && viewer._location.pageNumber) {
                return parseInt(viewer._location.pageNumber, 10) || 0;
            }
            return parseInt(viewer.currentPageNumber || 0, 10) || 0;
        } catch (_) {
            return 0;
        }
    }

    window.__3tReadVisiblePage = function () {
        return readVisiblePage(window.PDFViewerApplication);
    };

    function ensureQWebChannelScript(callback) {
        if (typeof QWebChannel !== 'undefined') {
            callback();
            return;
        }
        var existing = document.getElementById('__3t_qwebchannel_script');
        if (existing) {
            existing.addEventListener('load', callback, { once: true });
            return;
        }
        var script = document.createElement('script');
        script.id = '__3t_qwebchannel_script';
        script.src = 'qrc:///qtwebchannel/qwebchannel.js';
        script.onload = callback;
        document.head.appendChild(script);
    }

    window.__3tWithBridge = function (name, callback) {
        if (!name || typeof callback !== 'function') return;

        function deliver(channel) {
            try {
                callback((channel && channel.objects && channel.objects[name]) || null);
            } catch (_) {}
        }

        if (window.__3tSharedWebChannel) {
            deliver(window.__3tSharedWebChannel);
            return;
        }

        if (!window.__3tSharedWebChannelCallbacks) {
            window.__3tSharedWebChannelCallbacks = [];
        }
        window.__3tSharedWebChannelCallbacks.push(function(channel) {
            deliver(channel);
        });
        if (window.__3tSharedWebChannelConnecting) return;
        window.__3tSharedWebChannelConnecting = true;

        ensureQWebChannelScript(function () {
            function connectWhenReady() {
                if (!(window.qt && qt.webChannelTransport) || typeof QWebChannel === 'undefined') {
                    setTimeout(connectWhenReady, 50);
                    return;
                }
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    window.__3tSharedWebChannel = channel;
                    window.__3tSharedWebChannelConnecting = false;
                    var callbacks = window.__3tSharedWebChannelCallbacks || [];
                    window.__3tSharedWebChannelCallbacks = [];
                    callbacks.forEach(function(fn) {
                        try { fn(channel); } catch (_) {}
                    });
                });
            }
            connectWhenReady();
        });
    };

    function signatureFieldName(sigEl) {
        if (!sigEl) return '';
        var attrs = ['data-annotation-id', 'data-id', 'id', 'name', 'title', 'aria-label'];
        for (var i = 0; i < attrs.length; i++) {
            var value = sigEl.getAttribute && sigEl.getAttribute(attrs[i]);
            if (value) return String(value);
        }
        var input = sigEl.querySelector && sigEl.querySelector('input, textarea, button, select');
        if (input) {
            return input.getAttribute('name') || input.getAttribute('id') || input.getAttribute('title') || '';
        }
        return '';
    }

    function installSignatureInfoClickHandler() {
        if (window.__3tSignatureInfoClickInstalled) return;
        window.__3tSignatureInfoClickInstalled = true;
        var loadTargetsPromise = null;

        function signatureTargets() {
            if (window.__3tSignatureTargets) {
                return Promise.resolve(window.__3tSignatureTargets);
            }
            if (loadTargetsPromise) {
                return loadTargetsPromise;
            }
            loadTargetsPromise = new Promise(function (resolve) {
                try {
                    var params = new URLSearchParams(window.location.search || '');
                    var sigmeta = params.get('sigmeta');
                    if (!sigmeta) {
                        window.__3tSignatureTargets = [];
                        resolve([]);
                        return;
                    }
                    fetch(sigmeta, { cache: 'no-store' })
                        .then(function (resp) { return resp.ok ? resp.json() : { targets: [] }; })
                        .then(function (payload) {
                            window.__3tSignatureTargets = Array.isArray(payload && payload.targets) ? payload.targets : [];
                            resolve(window.__3tSignatureTargets);
                        })
                        .catch(function () {
                            window.__3tSignatureTargets = [];
                            resolve([]);
                        });
                } catch (_) {
                    window.__3tSignatureTargets = [];
                    resolve([]);
                }
            });
            return loadTargetsPromise;
        }

        function findSignatureTargetFromPoint(event) {
            try {
                var pageEl = event.target && event.target.closest ? event.target.closest('.page[data-page-number]') : null;
                if (!pageEl) return Promise.resolve(null);
                var pageNumber = parseInt(pageEl.getAttribute('data-page-number') || '0', 10) || 0;
                if (!pageNumber) return Promise.resolve(null);
                var app = window.PDFViewerApplication;
                var viewer = app && app.pdfViewer;
                if (!viewer) return Promise.resolve(null);
                var pageView = viewer.getPageView ? viewer.getPageView(pageNumber - 1) : (viewer._pages && viewer._pages[pageNumber - 1]);
                if (!pageView || !pageView.viewport) return Promise.resolve(null);
                var rect = pageEl.getBoundingClientRect();
                var pdfPoint = pageView.viewport.convertToPdfPoint(event.clientX - rect.left, event.clientY - rect.top);
                var px = Number(pdfPoint[0] || 0);
                var py = Number(pdfPoint[1] || 0);
                return signatureTargets().then(function (targets) {
                    var best = null;
                    for (var i = 0; i < targets.length; i++) {
                        var item = targets[i];
                        if ((parseInt(item.page || '0', 10) || 0) !== pageNumber) continue;
                        var box = item.rect || [];
                        if (box.length !== 4) continue;
                        var left = Math.min(box[0], box[2]);
                        var right = Math.max(box[0], box[2]);
                        var bottom = Math.min(box[1], box[3]);
                        var top = Math.max(box[1], box[3]);
                        if (px < left || px > right || py < bottom || py > top) continue;
                        var area = Math.max(1, (right - left) * (top - bottom));
                        if (!best || area < best.area) {
                            best = {
                                pageNumber: pageNumber,
                                fieldName: String(item.field_name || ''),
                                area: area
                            };
                        }
                    }
                    return best;
                });
            } catch (_) {
                return Promise.resolve(null);
            }
        }

        document.addEventListener('click', function (event) {
            if (window.__readerPdfSignaturePickInstalled || window.__readerPdfSignaturePickCleanup) return;
            var target = event.target;
            var sigEl = target && target.closest ? target.closest('.signatureWidgetAnnotation') : null;

            function dispatchSignatureInfo(pageNumber, fieldName) {
                event.preventDefault();
                event.stopPropagation();
                if (event.stopImmediatePropagation) event.stopImmediatePropagation();
                window.__3tWithBridge('signatureInfoBridge', function (bridge) {
                    if (bridge && typeof bridge.showSignatureInfo === 'function') {
                        bridge.showSignatureInfo(pageNumber, fieldName);
                    }
                });
            }

            if (sigEl) {
                var pageEl = sigEl.closest ? sigEl.closest('.page[data-page-number]') : null;
                var pageNumber = pageEl ? (parseInt(pageEl.getAttribute('data-page-number') || '0', 10) || 0) : 0;
                var fieldName = signatureFieldName(sigEl);
                dispatchSignatureInfo(pageNumber, fieldName);
                return;
            }

            findSignatureTargetFromPoint(event).then(function (hit) {
                if (!hit) return;
                dispatchSignatureInfo(hit.pageNumber, hit.fieldName);
            });
        }, true);
    }

    function collectSelectionPayload() {
        var sel = window.getSelection ? window.getSelection() : null;
        var text = sel ? String(sel.toString() || '') : '';
        var app = window.PDFViewerApplication;
        var viewer = app && app.pdfViewer;
        if (!sel || sel.rangeCount <= 0 || !viewer) return { text: text, rects: [] };

        function pageViewFor(pageNumber) {
            return viewer.getPageView ? viewer.getPageView(pageNumber - 1) : (viewer._pages && viewer._pages[pageNumber - 1]);
        }
        function pageForNode(node) {
            try {
                var el = node && (node.nodeType === 1 ? node : node.parentElement);
                return el && el.closest ? el.closest('.page') : null;
            } catch (_) {
                return null;
            }
        }
        function pageForRect(rect) {
            var cx = (rect.left + rect.right) / 2;
            var cy = (rect.top + rect.bottom) / 2;
            var el = document.elementFromPoint(cx, cy);
            var pageEl = el && el.closest ? el.closest('.page') : null;
            if (pageEl) return pageEl;
            var pages = document.querySelectorAll('.page[data-page-number]');
            var best = null;
            var bestArea = 0;
            for (var i = 0; i < pages.length; i++) {
                var pr = pages[i].getBoundingClientRect();
                if (cx >= pr.left && cx <= pr.right && cy >= pr.top && cy <= pr.bottom) return pages[i];
                var ix = Math.max(0, Math.min(rect.right, pr.right) - Math.max(rect.left, pr.left));
                var iy = Math.max(0, Math.min(rect.bottom, pr.bottom) - Math.max(rect.top, pr.top));
                var area = ix * iy;
                if (area > bestArea) {
                    bestArea = area;
                    best = pages[i];
                }
            }
            return bestArea > 0 ? best : null;
        }

        var out = [];
        for (var r = 0; r < sel.rangeCount; r++) {
            var range = sel.getRangeAt(r);
            var fallbackPage = pageForNode(range.commonAncestorContainer) || pageForNode(range.startContainer);
            var rects = range.getClientRects();
            for (var i = 0; i < rects.length; i++) {
                var cr = rects[i];
                if (!cr || cr.width < 2 || cr.height < 2) continue;
                var pageEl = pageForRect(cr) || fallbackPage;
                if (!pageEl) continue;
                var pageNumber = parseInt(pageEl.getAttribute('data-page-number') || '0', 10);
                var pageView = pageNumber ? pageViewFor(pageNumber) : null;
                if (!pageView || !pageView.viewport) continue;
                var pr = pageEl.getBoundingClientRect();
                var p0 = pageView.viewport.convertToPdfPoint(cr.left - pr.left, cr.top - pr.top);
                var p1 = pageView.viewport.convertToPdfPoint(cr.right - pr.left, cr.bottom - pr.top);
                out.push({
                    page_number: pageNumber,
                    rect: [
                        Math.min(p0[0], p1[0]), Math.min(p0[1], p1[1]),
                        Math.max(p0[0], p1[0]), Math.max(p0[1], p1[1])
                    ]
                });
            }
        }
        return { text: text, rects: out };
    }

    function updateSelectionCache() {
        try {
            var payload = collectSelectionPayload();
            if (payload && payload.rects && payload.rects.length > 0) {
                payload.timestamp = Date.now();
                window.__3tLastSelectionPayload = payload;
            }
        } catch (_) {}
    }

    window.__3tReadSelectionPayload = function () {
        var payload = collectSelectionPayload();
        if (payload && payload.rects && payload.rects.length > 0) {
            payload.timestamp = Date.now();
            window.__3tLastSelectionPayload = payload;
            return payload;
        }
        var cached = window.__3tLastSelectionPayload;
        if (cached && cached.rects && cached.rects.length > 0 && Date.now() - (cached.timestamp || 0) < 60000) {
            return cached;
        }
        return payload || { text: '', rects: [] };
    };

    function currentZoomPercent(app) {
        try {
            var viewer = app && app.pdfViewer;
            return Math.round((viewer && viewer.currentScale || 0) * 100);
        } catch (_) {
            return 0;
        }
    }

    function reportPageState(app, reason) {
        // Suppress page state reports during zoom to reduce QWebChannel overhead
        if (window.__3tZoomInProgress) return;

        var page = readVisiblePage(app) || window.__3tCurrentPage || 0;
        if (!page) return;
        window.__3tCurrentPage = page;
        var zoom = currentZoomPercent(app);

        function send(bridge) {
            try {
                if (bridge && typeof bridge.reportState === 'function') {
                    bridge.reportState(page, zoom || 0);
                }
            } catch (_) {}
        }

        // Cache bridge to avoid repeated QWebChannel lookups
        if (window.__3tPageStateBridge) {
            send(window.__3tPageStateBridge);
        } else {
            window.__3tWithBridge('pageStateBridge', function(bridge) {
                window.__3tPageStateBridge = bridge || null;
                send(window.__3tPageStateBridge);
            });
        }
    }

    function reportPageStateSoon(app, reason) {
        reportPageState(app, reason);
        setTimeout(function () { reportPageState(app, reason + ':settled'); }, 80);
    }

    function installHooks() {
        var app = window.PDFViewerApplication;
        if (!app || !app.eventBus) {
            setTimeout(installHooks, 200);
            return;
        }
        installSignatureInfoClickHandler();
        if (window.__3tHooksInstalled) return;
        window.__3tHooksInstalled = true;

        var selectionTimer = null;
        var scheduleSelectionCache = function () {
            if (selectionTimer) clearTimeout(selectionTimer);
            [0, 60, 160, 320, 640].forEach(function(delay) {
                setTimeout(updateSelectionCache, delay);
            });
            selectionTimer = setTimeout(function () { selectionTimer = null; }, 700);
        };
        document.addEventListener('selectionchange', scheduleSelectionCache, true);
        document.addEventListener('mouseup', scheduleSelectionCache, true);
        document.addEventListener('pointerup', scheduleSelectionCache, true);
        document.addEventListener('keyup', scheduleSelectionCache, true);

        // Track find state
        app.eventBus.on('updatefindcontrolstate', function (data) {
            window.__3tFindState = data.state;
        });
        // Track page changes from scroll/keyboard inside PDF.js
        app.eventBus.on('pagechanging', function (data) {
            window.__3tCurrentPage = data.pageNumber;
            reportPageState(app, 'pagechanging');
        });
        app.eventBus.on('updateviewarea', function (data) {
            if (window.__3tZoomInProgress) return;
            var page = 0;
            if (data && data.location && data.location.pageNumber) {
                page = parseInt(data.location.pageNumber, 10) || 0;
            }
            window.__3tCurrentPage = page || readVisiblePage(app) || window.__3tCurrentPage || 1;
            reportPageState(app, 'updateviewarea');
        });
        app.eventBus.on('scalechanging', function () {
            if (!window.__3tZoomInProgress) reportPageStateSoon(app, 'scalechanging');
        });
        app.eventBus.on('scalechanged', function () {
            if (!window.__3tZoomInProgress) reportPageStateSoon(app, 'scalechanged');
        });
        var container = document.getElementById('viewerContainer');
        if (container) {
            var scrollTimer = null;
            container.addEventListener('pointermove', function (event) {
                window.__3tLastPointer = {
                    x: event.clientX,
                    y: event.clientY,
                    timestamp: Date.now()
                };
            }, { passive: true });
            container.addEventListener('scroll', function () {
                if (scrollTimer) clearTimeout(scrollTimer);
                // Longer debounce during zoom to reduce QWebChannel overhead
                var delay = window.__3tZoomInProgress ? 500 : 80;
                scrollTimer = setTimeout(function () {
                    scrollTimer = null;
                    window.__3tCurrentPage = readVisiblePage(app) || window.__3tCurrentPage || 1;
                    reportPageState(app, 'scroll');
                }, delay);
            }, { passive: true });
        }
        function clear3TOverlays() {
            window.__3tLastSelectionPayload = null;
            document.querySelectorAll('.reader-pdf-sigfield-marker').forEach(function(el) { el.remove(); });
            var state = window.__readerPdfSignaturePreviewState;
            if (state && state.overlay && state.overlay.parentNode) {
                state.overlay.parentNode.removeChild(state.overlay);
            }
            if (state) {
                state.overlay = null;
                state.handle = null;
                state.pageView = null;
                state.pageNumber = null;
                state.dragging = false;
                state.dragMode = null;
            }
        }
        app.eventBus.on('documentinit', clear3TOverlays);
        app.eventBus.on('pagesinit', clear3TOverlays);
    }
    installHooks();
})();
