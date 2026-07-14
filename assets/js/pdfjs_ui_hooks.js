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
        '#viewerContainer.__3t-ctrl-panning, #viewerContainer.__3t-ctrl-panning * { cursor: grabbing !important; user-select: none !important; }',
        // Signature widget annotations are rendered as static appearance
        // streams (annotationMode=ENABLE) so they stay visible without
        // needing to hide interactive form inputs.
        '.annotationLayer .signatureWidgetAnnotation { cursor: pointer !important; }',
    ].join('\n');
    var style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);

    // --- Install PDF.js event hooks (retried until eventBus is ready) ---
    window.__3tFindState = -1;   // PDF.js FindState: 0=FOUND, 1=NOT_FOUND, 2=WRAPPED, 3=PENDING
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
        if (!window.__3tSignatureTargetsPromise) {
            window.__3tSignatureTargetsPromise = null;
        }

        function dispatchSignatureInfoToBridge(pageNumber, fieldName) {
            var tries = 0;
            function attempt() {
                tries += 1;
                window.__3tWithBridge('signatureInfoBridge', function (bridge) {
                    if (bridge && typeof bridge.showSignatureInfo === 'function') {
                        bridge.showSignatureInfo(pageNumber, fieldName);
                    } else if (tries < 6) {
                        setTimeout(attempt, 80);
                    }
                });
            }
            attempt();
        }

        function signatureTargets() {
            if (window.__3tSignatureTargets) {
                return Promise.resolve(window.__3tSignatureTargets);
            }
            if (window.__3tSignatureTargetsPromise) {
                return window.__3tSignatureTargetsPromise;
            }
            window.__3tSignatureTargetsPromise = new Promise(function (resolve) {
                try {
                    var params = new URLSearchParams(window.location.search || '');
                    var sigmeta = params.get('sigmeta');
                    if (!sigmeta) {
                        window.__3tSignatureTargets = [];
                        window.__3tSignatureTargetsPromise = null;
                        resolve([]);
                        return;
                    }
                    fetch(sigmeta, { cache: 'no-store' })
                        .then(function (resp) { return resp.ok ? resp.json() : { targets: [] }; })
                        .then(function (payload) {
                            window.__3tSignatureTargets = Array.isArray(payload && payload.targets) ? payload.targets : [];
                            window.__3tSignatureTargetsPromise = null;
                            resolve(window.__3tSignatureTargets);
                        })
                        .catch(function () {
                            window.__3tSignatureTargets = [];
                            window.__3tSignatureTargetsPromise = null;
                            resolve([]);
                        });
                } catch (_) {
                    window.__3tSignatureTargets = [];
                    window.__3tSignatureTargetsPromise = null;
                    resolve([]);
                }
            });
            return window.__3tSignatureTargetsPromise;
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

        function renderSignatureHitboxes() {
            var app = window.PDFViewerApplication;
            var viewer = app && app.pdfViewer;
            if (!viewer) return;
            document.querySelectorAll('.__3t-signature-hitbox').forEach(function (el) { el.remove(); });
            signatureTargets().then(function (targets) {
                if (!Array.isArray(targets) || !targets.length) return;
                targets.forEach(function (item) {
                    try {
                        var pageNumber = parseInt(item.page || '0', 10) || 0;
                        if (!pageNumber) return;
                        var box = item.rect || [];
                        if (box.length !== 4) return;
                        var pageEl = document.querySelector('.page[data-page-number="' + pageNumber + '"]');
                        if (!pageEl) return;
                        var pageView = viewer.getPageView ? viewer.getPageView(pageNumber - 1) : (viewer._pages && viewer._pages[pageNumber - 1]);
                        if (!pageView || !pageView.viewport) return;
                        var coords = pageView.viewport.convertToViewportRectangle(box);
                        var left = Math.min(coords[0], coords[2]);
                        var top = Math.min(coords[1], coords[3]);
                        var width = Math.abs(coords[2] - coords[0]);
                        var height = Math.abs(coords[3] - coords[1]);
                        if (width < 1 || height < 1) return;
                        // The rectangle is computed in page viewport coordinates.
                        // Mount the invisible hitbox on the page root to keep the
                        // same coordinate space as the rendered signature overlay.
                        var host = pageEl;
                        var hit = document.createElement('div');
                        hit.className = '__3t-signature-hitbox';
                        hit.setAttribute('data-page-number', String(pageNumber));
                        hit.setAttribute('data-field-name', String(item.field_name || ''));
                        hit.style.cssText =
                            'position:absolute;left:' + left + 'px;top:' + top + 'px;width:' + width + 'px;height:' + height + 'px;' +
                            'background:rgba(0,0,0,0.001);cursor:pointer;z-index:999;pointer-events:auto;';
                        hit.addEventListener('click', function (event) {
                            event.preventDefault();
                            event.stopPropagation();
                            if (event.stopImmediatePropagation) event.stopImmediatePropagation();
                            dispatchSignatureInfoToBridge(pageNumber, String(item.field_name || ''));
                        }, true);
                        host.appendChild(hit);
                    } catch (_) {}
                });
            });
        }

        document.addEventListener('click', function (event) {
            if (window.__readerPdfSignaturePickInstalled) return;
            var target = event.target;
            var hitboxEl = target && target.closest ? target.closest('.__3t-signature-hitbox') : null;
            var sigEl = target && target.closest ? target.closest('.signatureWidgetAnnotation') : null;

            function dispatchSignatureInfo(pageNumber, fieldName) {
                event.preventDefault();
                event.stopPropagation();
                if (event.stopImmediatePropagation) event.stopImmediatePropagation();
                dispatchSignatureInfoToBridge(pageNumber, fieldName);
            }

            if (hitboxEl) {
                var hitPageNumber = parseInt(hitboxEl.getAttribute('data-page-number') || '0', 10) || 0;
                var hitFieldName = String(hitboxEl.getAttribute('data-field-name') || '');
                dispatchSignatureInfo(hitPageNumber, hitFieldName);
                return;
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

        var app = window.PDFViewerApplication;
        if (app && app.eventBus && !window.__3tSignatureHitboxesInstalled) {
            window.__3tSignatureHitboxesInstalled = true;
            app.eventBus.on('pagesinit', function () { setTimeout(renderSignatureHitboxes, 80); });
            app.eventBus.on('pagerendered', function () { setTimeout(renderSignatureHitboxes, 30); });
            app.eventBus.on('scalechanged', function () { setTimeout(renderSignatureHitboxes, 60); });
            app.eventBus.on('updateviewarea', function () { setTimeout(renderSignatureHitboxes, 30); });
            setTimeout(renderSignatureHitboxes, 120);
        }
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
        function intersectionArea(a, b) {
            var left = Math.max(a.left, b.left);
            var top = Math.max(a.top, b.top);
            var right = Math.min(a.right, b.right);
            var bottom = Math.min(a.bottom, b.bottom);
            return Math.max(0, right - left) * Math.max(0, bottom - top);
        }
        function bestTextSpanForRect(rect, pageEl) {
            if (!pageEl || !pageEl.querySelectorAll) return null;
            var spans = pageEl.querySelectorAll('.textLayer span');
            var best = null;
            var bestArea = 0;
            for (var i = 0; i < spans.length; i++) {
                var spanRect = spans[i].getBoundingClientRect();
                if (!spanRect || spanRect.width < 1 || spanRect.height < 1) continue;
                var area = intersectionArea(rect, spanRect);
                if (area > bestArea) {
                    bestArea = area;
                    best = spanRect;
                }
            }
            return bestArea > 0 ? best : null;
        }
        function clampSelectionRectToText(rect, pageEl) {
            var pageRect = pageEl.getBoundingClientRect();
            var spanRect = bestTextSpanForRect(rect, pageEl);
            var clamped = {
                left: Math.max(pageRect.left, rect.left),
                top: Math.max(pageRect.top, rect.top),
                right: Math.min(pageRect.right, rect.right),
                bottom: Math.min(pageRect.bottom, rect.bottom)
            };
            if (spanRect) {
                var spanHeight = Math.max(1, spanRect.bottom - spanRect.top);
                var overlapTop = Math.max(clamped.top, spanRect.top);
                var overlapBottom = Math.min(clamped.bottom, spanRect.bottom);
                if (overlapBottom - overlapTop >= Math.min(2, spanHeight * 0.25)) {
                    clamped.top = overlapTop;
                    clamped.bottom = overlapBottom;
                } else {
                    clamped.top = spanRect.top;
                    clamped.bottom = spanRect.bottom;
                }
            }
            if (clamped.right - clamped.left <= 0 || clamped.bottom - clamped.top <= 0) {
                return rect; // Fallback to raw rect instead of dropping
            }
            return clamped;
        }
        function pushPdfRect(out, pageNumber, pageView, pageEl, rect) {
            var pr = pageEl.getBoundingClientRect();
            var p0 = pageView.viewport.convertToPdfPoint(rect.left - pr.left, rect.top - pr.top);
            var p1 = pageView.viewport.convertToPdfPoint(rect.right - pr.left, rect.bottom - pr.top);
            var pdfRect = [
                Math.min(p0[0], p1[0]), Math.min(p0[1], p1[1]),
                Math.max(p0[0], p1[0]), Math.max(p0[1], p1[1])
            ];
            for (var i = 0; i < out.length; i++) {
                var old = out[i];
                if (old.page_number !== pageNumber) continue;
                var r = old.rect || [];
                if (Math.abs(r[0] - pdfRect[0]) < 0.2 && Math.abs(r[1] - pdfRect[1]) < 0.2 &&
                    Math.abs(r[2] - pdfRect[2]) < 0.2 && Math.abs(r[3] - pdfRect[3]) < 0.2) {
                    return;
                }
            }
            out.push({ page_number: pageNumber, rect: pdfRect });
        }

        // Style của span neo (span text đầu tiên chạm selection) — để chế độ bôi
        // đen lấy đúng font/cỡ/màu/đậm/nghiêng/gạch chân như chế độ click, thay
        // vì truyền styles rỗng rồi rơi về mặc định sai.
        function anchorSpanStyle() {
            try {
                var a = sel.anchorNode;
                var el = a && (a.nodeType === 1 ? a : a.parentElement);
                var span = el && el.closest ? el.closest('.textLayer span') : null;
                if (!span) {
                    var fn = sel.focusNode;
                    var fel = fn && (fn.nodeType === 1 ? fn : fn.parentElement);
                    span = fel && fel.closest ? fel.closest('.textLayer span') : null;
                }
                if (!span) return null;
                var st = window.getComputedStyle(span);
                var pv = null, pnEl = span.closest('.page');
                if (pnEl) {
                    var pn = parseInt(pnEl.getAttribute('data-page-number') || '0', 10);
                    pv = pn ? pageViewFor(pn) : null;
                }
                var fsPx = parseFloat(st.fontSize) || 16;
                var vpScale = pv && pv.viewport ? Number(pv.viewport.scale || 1) : 1;
                return {
                    fontSizePt: fsPx / Math.max(0.01, vpScale),
                    fontFamily: st.fontFamily,
                    color: st.color,
                    fontWeight: st.fontWeight,
                    fontStyle: st.fontStyle,
                    textDecoration: st.textDecorationLine || st.textDecoration,
                    fontSize: st.fontSize
                };
            } catch (_e) { return null; }
        }

        var out = [];
        for (var r = 0; r < sel.rangeCount; r++) {
            var range = sel.getRangeAt(r);
            var fallbackPage = pageForNode(range.commonAncestorContainer) || pageForNode(range.startContainer);
            var rects = range.getClientRects();
            for (var i = 0; i < rects.length; i++) {
                var cr = rects[i];
                if (!cr || cr.width < 0.5 || cr.height < 0.5) continue;
                var pageEl = pageForRect(cr) || fallbackPage;
                if (!pageEl) continue;
                var pageNumber = parseInt(pageEl.getAttribute('data-page-number') || '0', 10);
                var pageView = pageNumber ? pageViewFor(pageNumber) : null;
                if (!pageView || !pageView.viewport) continue;
                var refined = clampSelectionRectToText(cr, pageEl);
                if (!refined) continue;
                pushPdfRect(out, pageNumber, pageView, pageEl, refined);
            }
        }
        return { text: text, rects: out, styles: anchorSpanStyle(), source: 'pdfjs_textlayer_selection' };
    }

    function updateSelectionCache() {
        try {
            var payload = collectSelectionPayload();
            if (payload && (payload.text || (payload.rects && payload.rects.length > 0))) {
                payload.timestamp = Date.now();
                window.__3tLastSelectionPayload = payload;
            }
        } catch (_) {}
    }

    window.__3tReadSelectionPayload = function (freshOnly) {
        var payload = collectSelectionPayload();
        if (payload && (payload.text || (payload.rects && payload.rects.length > 0))) {
            payload.timestamp = Date.now();
            window.__3tLastSelectionPayload = payload;
            return payload;
        }
        if (freshOnly) {
            return payload || { text: '', rects: [] };
        }
        var cached = window.__3tLastSelectionPayload;
        if (cached && (cached.text || (cached.rects && cached.rects.length > 0)) && Date.now() - (cached.timestamp || 0) < 60000) {
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

    function installExistingTextClickHandler() {
        if (window.__3tExistingTextClickInstalled) return;
        window.__3tExistingTextClickInstalled = true;

        function textOffsetWithinSpan(span, node, offset) {
            var walker = document.createTreeWalker(span, NodeFilter.SHOW_TEXT);
            var total = 0;
            var current;
            while ((current = walker.nextNode())) {
                if (current === node) return total + Math.max(0, offset || 0);
                total += String(current.nodeValue || '').length;
            }
            return -1;
        }

        function textNodeAtOffset(span, offset) {
            var walker = document.createTreeWalker(span, NodeFilter.SHOW_TEXT);
            var total = 0;
            var current;
            while ((current = walker.nextNode())) {
                var len = String(current.nodeValue || '').length;
                if (offset <= total + len) {
                    return { node: current, offset: Math.max(0, Math.min(len, offset - total)) };
                }
                total += len;
            }
            return null;
        }

        function clickedTextFragment(span, event) {
            var fullText = String(span.textContent || '');
            var spanRect = span.getBoundingClientRect();
            var fallback = { text: fullText, rect: spanRect };
            if (!fullText) return fallback;

            var caret = null;
            try {
                if (document.caretRangeFromPoint) {
                    caret = document.caretRangeFromPoint(event.clientX, event.clientY);
                } else if (document.caretPositionFromPoint) {
                    var pos = document.caretPositionFromPoint(event.clientX, event.clientY);
                    if (pos) {
                        caret = document.createRange();
                        caret.setStart(pos.offsetNode, pos.offset);
                        caret.collapse(true);
                    }
                }
            } catch (_) {}
            if (!caret || !span.contains(caret.startContainer)) return fallback;

            var offset = textOffsetWithinSpan(span, caret.startContainer, caret.startOffset);
            if (offset < 0) return fallback;
            offset = Math.max(0, Math.min(fullText.length, offset));
            if (offset >= fullText.length && fullText.length > 0) offset = fullText.length - 1;
            if (/\s/.test(fullText.charAt(offset)) && offset > 0) offset -= 1;

            var start = offset;
            var end = offset + 1;
            while (start > 0 && !/\s/.test(fullText.charAt(start - 1))) start -= 1;
            while (end < fullText.length && !/\s/.test(fullText.charAt(end))) end += 1;
            if (start >= end) return fallback;

            var startPos = textNodeAtOffset(span, start);
            var endPos = textNodeAtOffset(span, end);
            if (!startPos || !endPos) return fallback;

            try {
                var range = document.createRange();
                range.setStart(startPos.node, startPos.offset);
                range.setEnd(endPos.node, endPos.offset);
                var rect = range.getBoundingClientRect();
                var text = fullText.slice(start, end);
                if (rect && rect.width > 0 && rect.height > 0 && text) {
                    return { text: text, rect: rect };
                }
            } catch (_) {}
            return fallback;
        }

        document.addEventListener('keydown', function(event) {
            if (!window.__3tExistingTextMode || event.key !== 'Escape') return;
            window.__3tExistingTextMode = false;
            event.preventDefault();
            event.stopPropagation();
            window.__3tWithBridge('editExistingTextBridge', function(bridge) {
                if (bridge && typeof bridge.cancelExistingTextEdit === 'function') {
                    bridge.cancelExistingTextEdit();
                }
            });
        }, true);

        // Ghi nhận điểm bấm — KHÔNG chặn để người dùng vẫn kéo BÔI ĐEN được.
        // Quyết định click-sửa-1-từ hay bôi-đen-chọn-cụm dời sang pointerup.
        var _etDown = null;
        document.addEventListener('pointerdown', function(event) {
            if (!window.__3tExistingTextMode) { _etDown = null; return; }
            if (event.button !== 0) { _etDown = null; return; }
            var target = event.target && event.target.nodeType === 1 ? event.target : event.target.parentElement;
            var textSpan = target && target.closest ? target.closest('.textLayer span') : null;
            if (!textSpan) { _etDown = null; return; }
            _etDown = {x: event.clientX, y: event.clientY, span: textSpan, cx: event.clientX, cy: event.clientY};
        }, true);

        document.addEventListener('pointerup', function(event) {
            if (!window.__3tExistingTextMode) return;
            var d = _etDown; _etDown = null;
            if (!d) return;
            // Đã bôi đen (có vùng chọn) → KHÔNG tự mở sửa; để dùng nút "Sửa text gốc".
            var selTxt = window.getSelection ? String(window.getSelection().toString() || '').trim() : '';
            if (selTxt) return;
            // Kéo (di chuyển > 4px) → coi là chọn/pan, không phải click 1 từ.
            if (Math.abs(event.clientX - d.x) + Math.abs(event.clientY - d.y) > 4) return;

            var textSpan = d.span;
            var pageEl = textSpan.closest('.page[data-page-number]');
            if (!pageEl) return;
            var pageNum = parseInt(pageEl.getAttribute('data-page-number') || '0', 10);
            if (!pageNum) return;
            var app = window.PDFViewerApplication;
            var viewer = app && app.pdfViewer;
            var pageView = viewer && viewer.getPageView
                ? viewer.getPageView(pageNum - 1)
                : (viewer && viewer._pages && viewer._pages[pageNum - 1]);
            if (!pageView || !pageView.viewport) return;

            var evForFrag = {clientX: d.cx, clientY: d.cy};
            var fragment = clickedTextFragment(textSpan, evForFrag);
            var spanRect = fragment.rect || textSpan.getBoundingClientRect();
            var pageRect = pageEl.getBoundingClientRect();
            var p0 = pageView.viewport.convertToPdfPoint(spanRect.left - pageRect.left, spanRect.top - pageRect.top);
            var p1 = pageView.viewport.convertToPdfPoint(spanRect.right - pageRect.left, spanRect.bottom - pageRect.top);
            var left = Math.min(p0[0], p1[0]);
            var right = Math.max(p0[0], p1[0]);
            var bottom = Math.min(p0[1], p1[1]);
            var top = Math.max(p0[1], p1[1]);

            var style = window.getComputedStyle(textSpan);
            var fsPx = parseFloat(style.fontSize) || 16;
            var vpScale = Number(pageView.viewport.scale || 1);
            var styleJson = JSON.stringify({
                fontSizePt: fsPx / Math.max(0.01, vpScale),
                fontFamily: style.fontFamily,
                color: style.color,
                fontWeight: style.fontWeight,
                fontStyle: style.fontStyle,
                textDecoration: style.textDecorationLine || style.textDecoration,
                fontSize: style.fontSize
            });

            window.__3tWithBridge('editExistingTextBridge', function(bridge) {
                if (bridge && typeof bridge.reportExistingTextClick === 'function') {
                    bridge.reportExistingTextClick(
                        pageNum, left, bottom, right, top,
                        String(fragment.text || textSpan.textContent || ''),
                        styleJson
                    );
                }
            });
        }, true);
    }

    function installHooks() {
        var app = window.PDFViewerApplication;
        if (!app || !app.eventBus) {
            setTimeout(installHooks, 200);
            return;
        }
        installSignatureInfoClickHandler();
        installExistingTextClickHandler();
        if (window.__3tHooksInstalled) return;
        window.__3tHooksInstalled = true;

        var selectionTimer = null;
        var scheduleSelectionCache = function () {
            if (selectionTimer) clearTimeout(selectionTimer);
            updateSelectionCache();
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
            var ctrlPan = null;
            function stopCtrlPan() {
                if (!ctrlPan) return;
                ctrlPan = null;
                container.classList.remove('__3t-ctrl-panning');
                document.body.style.cursor = '';
            }
            container.addEventListener('mousedown', function (event) {
                // Ctrl (Win/Linux) hoặc Ctrl/⌘ (macOS) + chuột trái để kéo di chuyển.
                // LƯU Ý macOS: Ctrl+chuột trái bị hệ điều hành đổi thành chuột phải
                // (button === 2) → phải chấp nhận cả button 0 và 2 khi giữ Ctrl/⌘.
                if (!(event.ctrlKey || event.metaKey)) return;
                if (event.button !== 0 && event.button !== 2) return;
                var target = event.target && event.target.nodeType === 1 ? event.target : event.target.parentElement;
                if (target && target.closest && target.closest('input, textarea, select, button, [contenteditable="true"]')) return;
                ctrlPan = {
                    x: event.clientX,
                    y: event.clientY,
                    scrollLeft: container.scrollLeft,
                    scrollTop: container.scrollTop
                };
                container.classList.add('__3t-ctrl-panning');
                document.body.style.cursor = 'grabbing';
                event.preventDefault();
                event.stopPropagation();
            }, true);
            // macOS: Ctrl + chuột trái bị hệ điều hành coi là chuột phải → bật context
            // menu cắt ngang thao tác kéo. Chặn context menu khi đang giữ Ctrl/⌘ hoặc
            // khi đang pan, để Ctrl+kéo di chuyển mượt trên Mac.
            container.addEventListener('contextmenu', function (event) {
                if (ctrlPan || event.ctrlKey || event.metaKey) {
                    event.preventDefault();
                    event.stopPropagation();
                }
            }, true);
            document.addEventListener('mousemove', function (event) {
                if (!ctrlPan) return;
                container.scrollLeft = ctrlPan.scrollLeft - (event.clientX - ctrlPan.x);
                container.scrollTop = ctrlPan.scrollTop - (event.clientY - ctrlPan.y);
                event.preventDefault();
                event.stopPropagation();
            }, true);
            document.addEventListener('mouseup', function () {
                stopCtrlPan();
            }, true);
            window.addEventListener('blur', stopCtrlPan, true);
            window.addEventListener('keyup', function (event) {
                if (event.key === 'Control' || event.key === 'Meta') stopCtrlPan();
            }, true);
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
            window.__3tSignatureTargets = null;
            window.__3tSignatureTargetsPromise = null;
            document.querySelectorAll('.reader-pdf-sigfield-marker').forEach(function(el) { el.remove(); });
            document.querySelectorAll('.__3t-signature-hitbox').forEach(function(el) { el.remove(); });
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
