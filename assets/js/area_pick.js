// 3T Reader — Area pick script for PDF.js
// Allows user to drag-select a rectangular area on a PDF page.
// Communicates with Python via QWebChannel (areaPickBridge).
(function () {
    if (window.__readerPdfAreaPickInstalled) {
        return;
    }
    window.__readerPdfAreaPickInstalled = true;

    function startPick(bridge) {
        let dragState = null;
        let overlay = null;

        function cleanup() {
            document.removeEventListener('mousedown', onMouseDown, true);
            document.removeEventListener('mousemove', onMouseMove, true);
            document.removeEventListener('mouseup', onMouseUp, true);
            window.removeEventListener('keydown', onKeyDown, true);
            document.body.style.cursor = '';
            clearOverlay();
            dragState = null;
        }

        function clearOverlay() {
            if (overlay && overlay.parentNode) {
                overlay.parentNode.removeChild(overlay);
            }
            overlay = null;
        }

        function resolvePageFromEvent(event) {
            const candidates = [];
            const directTarget = event.target && event.target.nodeType === 1
                ? event.target
                : (event.target && event.target.parentElement);
            if (directTarget) {
                candidates.push(directTarget);
            }
            if (document.elementsFromPoint) {
                try {
                    const hits = document.elementsFromPoint(event.clientX, event.clientY) || [];
                    for (const el of hits) {
                        candidates.push(el);
                    }
                } catch (_err) {}
            } else if (document.elementFromPoint) {
                try {
                    const hit = document.elementFromPoint(event.clientX, event.clientY);
                    if (hit) {
                        candidates.push(hit);
                    }
                } catch (_err) {}
            }

            for (const candidate of candidates) {
                if (candidate && candidate.closest) {
                    const page = candidate.closest('.page');
                    if (page && page.dataset && page.dataset.pageNumber) {
                        return page;
                    }
                }
            }
            return null;
        }

        function cancel() {
            cleanup();
            try { bridge.cancelPick(); } catch (_err) {}
        }

        function onMouseDown(event) {
            const page = resolvePageFromEvent(event);
            if (!page) {
                return;
            }
            const pdfViewer = window.PDFViewerApplication && PDFViewerApplication.pdfViewer;
            if (!pdfViewer) {
                return;
            }
            const pageNumber = parseInt(page.dataset.pageNumber, 10);
            const pageView = pdfViewer.getPageView
                ? pdfViewer.getPageView(pageNumber - 1)
                : (pdfViewer._pages && pdfViewer._pages[pageNumber - 1]);
            if (!pageView || !pageView.viewport || !pageView.pdfPage) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            document.body.style.cursor = 'crosshair';
            const rect = page.getBoundingClientRect();
            const startX = Math.max(0, Math.min(event.clientX - rect.left, page.clientWidth));
            const startY = Math.max(0, Math.min(event.clientY - rect.top, page.clientHeight));

            dragState = {
                page,
                pageView,
                pageNumber,
                rect,
                startX,
                startY,
                curX: startX,
                curY: startY,
            };

            if (!overlay) {
                overlay = document.createElement('div');
                overlay.style.position = 'absolute';
                overlay.style.border = '2px dashed #0B84F3';
                overlay.style.background = 'rgba(11, 132, 243, 0.15)';
                overlay.style.pointerEvents = 'none';
                overlay.style.zIndex = '10000';
                overlay.style.boxSizing = 'border-box';
                page.appendChild(overlay);
            } else if (overlay.parentNode !== page) {
                if (overlay.parentNode) {
                    overlay.parentNode.removeChild(overlay);
                }
                page.appendChild(overlay);
            }
            overlay.style.left = `${startX}px`;
            overlay.style.top = `${startY}px`;
            overlay.style.width = '1px';
            overlay.style.height = '1px';
        }

        function onMouseMove(event) {
            if (!dragState || !overlay) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
            const x = Math.max(0, Math.min(event.clientX - dragState.rect.left, dragState.page.clientWidth));
            const y = Math.max(0, Math.min(event.clientY - dragState.rect.top, dragState.page.clientHeight));
            dragState.curX = x;
            dragState.curY = y;

            const left = Math.min(dragState.startX, x);
            const top = Math.min(dragState.startY, y);
            const width = Math.max(1, Math.abs(x - dragState.startX));
            const height = Math.max(1, Math.abs(y - dragState.startY));

            overlay.style.left = `${left}px`;
            overlay.style.top = `${top}px`;
            overlay.style.width = `${width}px`;
            overlay.style.height = `${height}px`;
        }

        function onMouseUp(event) {
            if (!dragState) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            const x2 = Math.max(0, Math.min(event.clientX - dragState.rect.left, dragState.page.clientWidth));
            const y2 = Math.max(0, Math.min(event.clientY - dragState.rect.top, dragState.page.clientHeight));
            const x1 = dragState.startX;
            const y1 = dragState.startY;

            const minX = Math.min(x1, x2);
            const minY = Math.min(y1, y2);
            const maxX = Math.max(x1, x2);
            const maxY = Math.max(y1, y2);

            const p1 = dragState.pageView.viewport.convertToPdfPoint(minX, minY);
            const p2 = dragState.pageView.viewport.convertToPdfPoint(maxX, maxY);

            const left = Math.min(p1[0], p2[0]);
            const right = Math.max(p1[0], p2[0]);
            const bottom = Math.min(p1[1], p2[1]);
            const top = Math.max(p1[1], p2[1]);

            const pickedPageNumber = dragState.pageNumber;
            cleanup();

            try {
                bridge.reportArea(pickedPageNumber, left, bottom, right, top);
            } catch (_err) {}
        }

        function onKeyDown(event) {
            if (event.key === 'Escape') {
                cancel();
            }
        }

        document.addEventListener('mousedown', onMouseDown, true);
        document.addEventListener('mousemove', onMouseMove, true);
        document.addEventListener('mouseup', onMouseUp, true);
        window.addEventListener('keydown', onKeyDown, true);
    }

    function attachBridge() {
        if (typeof window.__3tWithBridge !== 'function') {
            setTimeout(attachBridge, 50);
            return;
        }

        // Reuse cached bridge from previous pick in the same channel session.
        // This avoids a second async QWebChannel handshake for Move's second pick.
        if (window.__3tAreaPickBridgeCache) {
            startPick(window.__3tAreaPickBridgeCache);
            return;
        }

        window.__3tWithBridge('areaPickBridge', function (b) {
            if (!b) {
                return;
            }
            window.__3tAreaPickBridgeCache = b;
            startPick(b);
        });
    }

    attachBridge();
})();
