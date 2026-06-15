// 3T Reader — Inline image overlay for PDF editing
// Creates a draggable/resizable image overlay on a PDF page.
// Communicates with Python via QWebChannel (inlineImageBridge).
(function () {
    /* clear old overlay */
    if (window.__3TImgState) {
        var _ov = window.__3TImgState.overlay;
        if (_ov && _ov.parentNode) _ov.parentNode.removeChild(_ov);
        var _cap = window.__3TImgState.dragCap;
        if (_cap && _cap.parentNode) _cap.parentNode.removeChild(_cap);
    }
    window.__3TImgState  = { overlay: null, pageNumber: null, pageView: null,
                              pageEl: null, canvas: null, dragCap: null };
    window.__3TImgBridge = null;

    var S = window.__3TImgState;

    /* ── drag capture helpers ── */
    function makeDragCap(cursor) {
        var cap = document.createElement('div');
        cap.style.cssText =
            'position:fixed;inset:0;z-index:99998;background:transparent;cursor:' + (cursor || 'move') + ';';
        return cap;
    }

    function startDrag(ov, ev, isResize) {
        var rect = ov.getBoundingClientRect();
        var sl = rect.left, st = rect.top;
        var sw = ov.offsetWidth, sh = ov.offsetHeight;
        var sx = ev.clientX, sy = ev.clientY;

        var cap = makeDragCap(isResize ? 'nwse-resize' : 'move');
        document.body.appendChild(cap);
        S.dragCap = cap;

        function onM(e) {
            var dx = e.clientX - sx;
            var dy = e.clientY - sy;
            if (isResize) {
                ov.style.width  = Math.max(40, sw + dx) + 'px';
                ov.style.height = Math.max(30, sh + dy) + 'px';
            } else {
                var pageRect = S.pageEl.getBoundingClientRect();
                ov.style.left = (sl + dx - pageRect.left) + 'px';
                ov.style.top  = (st + dy - pageRect.top)  + 'px';
            }
        }
        function onU() {
            cap.removeEventListener('mousemove', onM);
            cap.removeEventListener('mouseup',   onU);
            if (cap.parentNode) cap.parentNode.removeChild(cap);
            S.dragCap = null;
        }
        cap.addEventListener('mousemove', onM);
        cap.addEventListener('mouseup',   onU);
        ev.preventDefault();
    }

    window.__3TImgConfirm = function () {
        if (!S.overlay || !S.pageView) return;
        var ov = S.overlay;
        var canvas = S.canvas || (S.pageEl && S.pageEl.querySelector('canvas')) || S.pageEl;
        var cr  = canvas ? canvas.getBoundingClientRect() : { left: 0, top: 0 };
        var ovr = ov.getBoundingClientRect();
        var l   = ovr.left   - cr.left;
        var t   = ovr.top    - cr.top;
        var w   = ovr.width;
        var h   = ovr.height;
        var p1 = S.pageView.viewport.convertToPdfPoint(l,     t);
        var p2 = S.pageView.viewport.convertToPdfPoint(l + w, t + h);
        var br = window.__3TImgBridge;
        if (br) br.confirmImage(
            S.pageNumber,
            Math.min(p1[0],p2[0]), Math.min(p1[1],p2[1]),
            Math.max(p1[0],p2[0]), Math.max(p1[1],p2[1])
        );
        
        if (S.overlay && S.overlay.parentNode)
            S.overlay.parentNode.removeChild(S.overlay);
        if (S.dragCap && S.dragCap.parentNode)
            S.dragCap.parentNode.removeChild(S.dragCap);
        S.overlay = null;
        S.dragCap = null;
        document.body.style.cursor = '';
        window.__3TImgState = null;
    };

    window.__3TImgCancel = function () {
        if (S.overlay && S.overlay.parentNode)
            S.overlay.parentNode.removeChild(S.overlay);
        if (S.dragCap && S.dragCap.parentNode)
            S.dragCap.parentNode.removeChild(S.dragCap);
        S.overlay = null;
        S.dragCap = null;
        document.body.style.cursor = '';
        var br = window.__3TImgBridge;
        if (br) br.cancelEdit();
    };

    function startListen(imgUrl) {
        document.body.style.cursor = 'crosshair';

        function getInitialSize() {
            var info = window.__3TInlineImageInfo || {};
            var nw = parseFloat(info.width || 0);
            var nh = parseFloat(info.height || 0);
            if (!(nw > 0 && nh > 0)) return { width: 200, height: 150 };
            var maxW = 240, maxH = 180;
            var width = nw, height = nh, ratio = nw / nh;
            if (width > maxW) { width = maxW; height = width / ratio; }
            if (height > maxH) { height = maxH; width = height * ratio; }
            return { width: Math.max(80, Math.round(width)), height: Math.max(60, Math.round(height)) };
        }

        function clickHandler(e) {
            var page = e.target.closest('.page');
            if (!page) return;
            e.preventDefault(); e.stopPropagation();
            document.removeEventListener('click', clickHandler, true);
            document.body.style.cursor = '';

            var pn  = parseInt(page.dataset.pageNumber, 10);
            var app = window.PDFViewerApplication;
            var pv  = app && app.pdfViewer;
            if (!pv) { var br = window.__3TImgBridge; if (br) br.cancelEdit(); return; }
            var pgv = pv.getPageView ? pv.getPageView(pn - 1) : (pv._pages && pv._pages[pn - 1]);
            if (!pgv || !pgv.viewport) { var br = window.__3TImgBridge; if (br) br.cancelEdit(); return; }

            var canvas  = page.querySelector('canvas') || page;
            var pageRect = page.getBoundingClientRect();
            var cx = e.clientX - pageRect.left;
            var cy = e.clientY - pageRect.top;

            S.pageNumber = pn;
            S.pageView   = pgv;
            S.pageEl     = page;
            S.canvas     = canvas;

            var initial = getInitialSize();
            var left = Math.max(0, Math.round(cx - initial.width / 2));
            var top  = Math.max(0, Math.round(cy - initial.height / 2));

            var ov = document.createElement('div');
            ov.style.cssText =
                'position:absolute;left:' + left + 'px;top:' + top + 'px;' +
                'width:' + initial.width + 'px;height:' + initial.height + 'px;' +
                'border:2px solid #1A7AFF;z-index:9999;' +
                'box-sizing:border-box;border-radius:4px;' +
                'box-shadow:0 4px 20px rgba(26,122,255,0.4);' +
                'overflow:hidden;';

            /* drag handle bar */
            var dragBar = document.createElement('div');
            dragBar.style.cssText =
                'position:absolute;top:0;left:0;right:0;height:20px;' +
                'cursor:move;background:rgba(26,122,255,0.85);' +
                'display:flex;align-items:center;padding:0 8px;z-index:10001;';
            var badge = document.createElement('span');
            badge.textContent = '🖼️ Ảnh — kéo thanh này · kéo góc resize · Enter xác nhận';
            badge.style.cssText = 'font-size:10px;color:#fff;white-space:nowrap;pointer-events:none;';
            dragBar.appendChild(badge);
            ov.appendChild(dragBar);

            var img = document.createElement('img');
            img.src = imgUrl;
            img.style.cssText =
                'position:absolute;top:20px;left:0;right:0;bottom:0;' +
                'width:100%;height:calc(100% - 20px);object-fit:contain;pointer-events:none;display:block;';
            ov.appendChild(img);

            window.__3TImgUpdateRotation = function (angle) {
                if (S.overlay) {
                    S.overlay.style.transformOrigin = 'center center';
                    S.overlay.style.transform = 'rotate(' + angle + 'deg)';
                }
            };

            /* resize corner */
            var rh = document.createElement('div');
            rh.style.cssText =
                'position:absolute;right:-7px;bottom:-7px;width:14px;height:14px;' +
                'background:#1A7AFF;border:2px solid #fff;border-radius:3px;' +
                'cursor:nwse-resize;z-index:10000;';
            ov.appendChild(rh);

            /* drag via handle bar */
            dragBar.addEventListener('mousedown', function (ev) {
                startDrag(ov, ev, false);
                ev.stopPropagation();
            });

            /* resize */
            rh.addEventListener('mousedown', function (ev) {
                startDrag(ov, ev, true);
                ev.stopPropagation();
            });

            /* keyboard */
            function kh(ev) {
                if (ev.key === 'Enter')  { window.__3TImgConfirm(); document.removeEventListener('keydown', kh, true); }
                if (ev.key === 'Escape') { window.__3TImgCancel();  document.removeEventListener('keydown', kh, true); }
            }
            document.addEventListener('keydown', kh, true);

            page.appendChild(ov);
            S.overlay = ov;

            var br = window.__3TImgBridge;
            if (br) br.reportReady(pn);
        }

        document.addEventListener('click', clickHandler, true);
    }

    function attach() {
        if (typeof window.__3tWithBridge !== 'function') {
            setTimeout(attach, 100);
            return;
        }
        window.__3tWithBridge('inlineImageBridge', function (bridge) {
            window.__3TImgBridge = bridge || null;
            startListen(window.__3TInlineImageUrl || '');
        });
    }
    attach();
})();
