// 3T Reader - inline image placement overlay for PDF editing
// Ghost preview follows the pointer until the user clicks a page.
(function () {
    function clearNode(node) {
        if (node && node.parentNode) node.parentNode.removeChild(node);
    }

    if (window.__3TImgState) {
        clearNode(window.__3TImgState.overlay);
        clearNode(window.__3TImgState.dragCap);
        clearNode(window.__3TImgState.ghost);
    }

    window.__3TImgState = {
        overlay: null,
        pageNumber: null,
        pageView: null,
        pageEl: null,
        canvas: null,
        dragCap: null,
        ghost: null,
    };
    window.__3TImgBridge = null;

    var S = window.__3TImgState;

    function imageInfo() {
        return window.__3TInlineImageInfo || {};
    }

    function isTransparentImage() {
        var info = imageInfo();
        return !!info.has_alpha || String(info.mime || '').toLowerCase() === 'png';
    }

    function makeDragCap(cursor) {
        var cap = document.createElement('div');
        cap.style.cssText =
            'position:fixed;inset:0;z-index:99998;background:transparent;cursor:' +
            (cursor || 'move') + ';';
        return cap;
    }

    function getInitialSize() {
        var info = imageInfo();
        var nw = parseFloat(info.width || 0);
        var nh = parseFloat(info.height || 0);
        if (!(nw > 0 && nh > 0)) return { width: 200, height: 150 };
        var maxW = 240, maxH = 180;
        var width = nw, height = nh, ratio = nw / nh;
        if (width > maxW) { width = maxW; height = width / ratio; }
        if (height > maxH) { height = maxH; width = height * ratio; }
        return { width: Math.max(80, Math.round(width)), height: Math.max(60, Math.round(height)) };
    }

    function makeGhostPreview(imgUrl) {
        var transparentImage = isTransparentImage();
        var initial = getInitialSize();

        var ghost = document.createElement('div');
        ghost.setAttribute('data-3t-img-ghost', '1');
        ghost.style.cssText =
            'position:fixed;left:24px;top:24px;z-index:99997;pointer-events:none;' +
            'padding:6px;border-radius:8px;background:rgba(15,23,42,0.20);' +
            'box-shadow:0 12px 30px rgba(15,23,42,0.22);backdrop-filter:blur(2px);';

        var wrap = document.createElement('div');
        wrap.style.cssText =
            'position:relative;overflow:hidden;border-radius:6px;' +
            'width:' + Math.min(240, Math.max(120, initial.width)) + 'px;' +
            'height:' + Math.min(180, Math.max(80, initial.height)) + 'px;' +
            'border:2px solid rgba(26,122,255,0.95);' +
            'background:' + (transparentImage ? 'transparent' : 'rgba(255,255,255,0.92)') + ';';

        var hud = document.createElement('div');
        hud.style.cssText =
            'position:absolute;left:8px;top:8px;z-index:2;background:rgba(26,122,255,0.92);' +
            'color:#fff;border-radius:999px;padding:3px 8px;font:700 10px/1.2 sans-serif;';
        hud.textContent = transparentImage ? 'PNG trong suot' : 'Anh se duoc chen';
        wrap.appendChild(hud);

        var checker = document.createElement('div');
        checker.style.cssText =
            'position:absolute;inset:0;opacity:' + (transparentImage ? '0.75' : '0.55') + ';' +
            'background-image:linear-gradient(45deg, rgba(148,163,184,0.18) 25%, transparent 25%),' +
            'linear-gradient(-45deg, rgba(148,163,184,0.18) 25%, transparent 25%),' +
            'linear-gradient(45deg, transparent 75%, rgba(148,163,184,0.18) 75%),' +
            'linear-gradient(-45deg, transparent 75%, rgba(148,163,184,0.18) 75%);' +
            'background-size:18px 18px;background-position:0 0, 0 9px, 9px -9px, -9px 0px;';
        wrap.appendChild(checker);

        var img = document.createElement('img');
        img.src = imgUrl;
        img.style.cssText =
            'position:absolute;inset:0;width:100%;height:100%;object-fit:contain;' +
            'pointer-events:none;display:block;opacity:0.95;mix-blend-mode:normal;';
        wrap.appendChild(img);

        var frame = document.createElement('div');
        frame.style.cssText =
            'position:absolute;inset:0;border:1px dashed rgba(26,122,255,0.45);box-sizing:border-box;pointer-events:none;';
        wrap.appendChild(frame);

        ghost.appendChild(wrap);
        document.body.appendChild(ghost);
        return ghost;
    }

    function updateLiveHint() {
        if (!S.overlay) return;
        var body = S.overlay.querySelector('[data-3t-img-body]');
        var hud = S.overlay.querySelector('[data-3t-img-hud]');
        if (!body || !hud) return;
        var w = Math.max(40, Math.round(S.overlay.offsetWidth));
        var h = Math.max(30, Math.round(S.overlay.offsetHeight));
        hud.textContent = (isTransparentImage() ? 'PNG trong suot' : 'Anh preview') + '  •  ' + w + ' x ' + h + ' px';
        body.style.boxShadow = S.draggingResize
            ? 'inset 0 0 0 2px rgba(26,122,255,0.35)'
            : 'inset 0 0 0 2px rgba(26,122,255,0.18)';
    }

    function startDrag(ov, ev, isResize) {
        var rect = ov.getBoundingClientRect();
        var sl = rect.left, st = rect.top;
        var sw = ov.offsetWidth, sh = ov.offsetHeight;
        var sx = ev.clientX, sy = ev.clientY;

        var cap = makeDragCap(isResize ? 'nwse-resize' : 'move');
        document.body.appendChild(cap);
        S.dragCap = cap;
        S.draggingResize = !!isResize;

        function onMove(e) {
            var dx = e.clientX - sx;
            var dy = e.clientY - sy;
            if (isResize) {
                ov.style.width = Math.max(40, sw + dx) + 'px';
                ov.style.height = Math.max(30, sh + dy) + 'px';
            } else {
                var pageRect = S.pageEl.getBoundingClientRect();
                ov.style.left = (sl + dx - pageRect.left) + 'px';
                ov.style.top = (st + dy - pageRect.top) + 'px';
            }
            updateLiveHint();
        }

        function onUp() {
            cap.removeEventListener('mousemove', onMove);
            cap.removeEventListener('mouseup', onUp);
            clearNode(cap);
            S.dragCap = null;
            S.draggingResize = false;
        }

        cap.addEventListener('mousemove', onMove);
        cap.addEventListener('mouseup', onUp);
        ev.preventDefault();
    }

    window.__3TImgConfirm = function () {
        if (!S.overlay || !S.pageView) return;
        var ov = S.overlay;
        var canvas = S.canvas || (S.pageEl && S.pageEl.querySelector('canvas')) || S.pageEl;
        var cr = canvas ? canvas.getBoundingClientRect() : { left: 0, top: 0 };
        var ovr = ov.getBoundingClientRect();
        var l = ovr.left - cr.left;
        var t = ovr.top - cr.top;
        var w = ovr.width;
        var h = ovr.height;
        var p1 = S.pageView.viewport.convertToPdfPoint(l, t);
        var p2 = S.pageView.viewport.convertToPdfPoint(l + w, t + h);
        var br = window.__3TImgBridge;
        if (br) {
            br.confirmImage(
                S.pageNumber,
                Math.min(p1[0], p2[0]), Math.min(p1[1], p2[1]),
                Math.max(p1[0], p2[0]), Math.max(p1[1], p2[1])
            );
        }
        clearNode(S.overlay);
        clearNode(S.dragCap);
        clearNode(S.ghost);
        S.overlay = null;
        S.dragCap = null;
        S.ghost = null;
        document.body.style.cursor = '';
        window.__3TImgState = null;
    };

    window.__3TImgCancel = function () {
        clearNode(S.overlay);
        clearNode(S.dragCap);
        clearNode(S.ghost);
        S.overlay = null;
        S.dragCap = null;
        S.ghost = null;
        document.body.style.cursor = '';
        var br = window.__3TImgBridge;
        if (br) br.cancelEdit();
    };

    function startListen(imgUrl) {
        document.body.style.cursor = 'crosshair';

        function clickHandler(e) {
            var page = e.target.closest('.page');
            if (!page) return;
            e.preventDefault();
            e.stopPropagation();
            document.removeEventListener('click', clickHandler, true);
            document.body.style.cursor = '';
            clearNode(S.ghost);
            S.ghost = null;

            var pn = parseInt(page.dataset.pageNumber, 10);
            var app = window.PDFViewerApplication;
            var pv = app && app.pdfViewer;
            if (!pv) {
                var br0 = window.__3TImgBridge;
                if (br0) br0.cancelEdit();
                return;
            }

            var pgv = pv.getPageView ? pv.getPageView(pn - 1) : (pv._pages && pv._pages[pn - 1]);
            if (!pgv || !pgv.viewport) {
                var br1 = window.__3TImgBridge;
                if (br1) br1.cancelEdit();
                return;
            }

            var pageRect = page.getBoundingClientRect();
            var cx = e.clientX - pageRect.left;
            var cy = e.clientY - pageRect.top;

            S.pageNumber = pn;
            S.pageView = pgv;
            S.pageEl = page;
            S.canvas = page.querySelector('canvas') || page;

            var initial = getInitialSize();
            var transparentImage = isTransparentImage();
            var left = Math.max(0, Math.round(cx - initial.width / 2));
            var top = Math.max(0, Math.round(cy - initial.height / 2));

            var ov = document.createElement('div');
            ov.style.cssText =
                'position:absolute;left:' + left + 'px;top:' + top + 'px;' +
                'width:' + initial.width + 'px;height:' + initial.height + 'px;' +
                'border:3px solid #1A7AFF;z-index:9999;box-sizing:border-box;' +
                'border-radius:4px;box-shadow:0 10px 28px rgba(26,122,255,0.45),' +
                '0 0 0 1px rgba(255,255,255,0.8) inset;overflow:hidden;';

            var dragBar = document.createElement('div');
            dragBar.style.cssText =
                'position:absolute;top:0;left:0;right:0;height:20px;cursor:move;' +
                'background:linear-gradient(90deg, rgba(26,122,255,0.98), rgba(57,145,255,0.85));' +
                'display:flex;align-items:center;padding:0 8px;z-index:10001;';

            var badge = document.createElement('span');
            badge.textContent = transparentImage
                ? 'PNG trong suot - keo de di chuyen - keo goc de doi kich thuoc - Enter de chen'
                : 'Keo de di chuyen - keo goc de doi kich thuoc - Enter de chen';
            badge.style.cssText =
                'font-size:11px;font-weight:600;color:#fff;white-space:nowrap;pointer-events:none;' +
                'text-shadow:0 1px 2px rgba(0,0,0,0.25);';
            dragBar.appendChild(badge);
            ov.appendChild(dragBar);

            var hud = document.createElement('div');
            hud.setAttribute('data-3t-img-hud', '1');
            hud.style.cssText =
                'position:absolute;left:8px;top:24px;z-index:10002;background:rgba(15,23,42,0.88);' +
                'color:#fff;border-radius:5px;padding:3px 8px;font:600 10px/1.2 sans-serif;' +
                'letter-spacing:0.2px;pointer-events:none;';
            hud.textContent = (transparentImage ? 'PNG trong suot' : 'Image preview') +
                '  •  ' + initial.width + ' x ' + initial.height + ' px';
            ov.appendChild(hud);

            var body = document.createElement('div');
            body.setAttribute('data-3t-img-body', '1');
            body.style.cssText =
                'position:absolute;top:20px;left:0;right:0;bottom:0;' +
                'background:' + (transparentImage ? 'transparent' : 'rgba(255,255,255,0.92)') + ';';

            var checker = document.createElement('div');
            checker.style.cssText =
                'position:absolute;inset:0;opacity:' + (transparentImage ? '0.75' : '0.55') + ';' +
                'background-image:linear-gradient(45deg, rgba(148,163,184,0.18) 25%, transparent 25%),' +
                'linear-gradient(-45deg, rgba(148,163,184,0.18) 25%, transparent 25%),' +
                'linear-gradient(45deg, transparent 75%, rgba(148,163,184,0.18) 75%),' +
                'linear-gradient(-45deg, transparent 75%, rgba(148,163,184,0.18) 75%);' +
                'background-size:18px 18px;background-position:0 0, 0 9px, 9px -9px, -9px 0px;';
            body.appendChild(checker);

            var img = document.createElement('img');
            img.src = imgUrl;
            img.style.cssText =
                'position:absolute;inset:0;width:100%;height:100%;object-fit:contain;' +
                'pointer-events:none;display:block;opacity:0.95;mix-blend-mode:normal;';
            body.appendChild(img);

            var frame = document.createElement('div');
            frame.style.cssText =
                'position:absolute;inset:0;border:1px dashed rgba(26,122,255,0.45);' +
                'box-sizing:border-box;pointer-events:none;';
            body.appendChild(frame);

            ov.appendChild(body);

            window.__3TImgUpdateRotation = function (angle) {
                if (S.overlay) {
                    S.overlay.style.transformOrigin = 'center center';
                    S.overlay.style.transform = 'rotate(' + angle + 'deg)';
                }
            };

            var rh = document.createElement('div');
            rh.style.cssText =
                'position:absolute;right:-7px;bottom:-7px;width:14px;height:14px;' +
                'background:#1A7AFF;border:2px solid #fff;border-radius:3px;' +
                'cursor:nwse-resize;z-index:10000;';
            ov.appendChild(rh);

            ov.addEventListener('mousedown', function (ev) {
                if (ev.target === rh) return;
                startDrag(ov, ev, false);
                ev.stopPropagation();
            }, true);

            rh.addEventListener('mousedown', function (ev) {
                startDrag(ov, ev, true);
                ev.stopPropagation();
            }, true);

            function kh(ev) {
                if (ev.key === 'Enter') {
                    window.__3TImgConfirm();
                    document.removeEventListener('keydown', kh, true);
                }
                if (ev.key === 'Escape') {
                    window.__3TImgCancel();
                    document.removeEventListener('keydown', kh, true);
                }
            }
            document.addEventListener('keydown', kh, true);

            page.appendChild(ov);
            S.overlay = ov;

            var br = window.__3TImgBridge;
            if (br && typeof br.reportReady === 'function') br.reportReady(pn);
        }

        function trackMouse(e) {
            if (!S.ghost) return;
            var x = e.clientX + 18;
            var y = e.clientY + 18;
            var maxX = Math.max(0, window.innerWidth - 24);
            var maxY = Math.max(0, window.innerHeight - 24);
            S.ghost.style.left = Math.min(x, maxX) + 'px';
            S.ghost.style.top = Math.min(y, maxY) + 'px';
            S.ghost.style.display = e.target && e.target.closest && e.target.closest('.page') ? 'block' : 'none';
        }

        document.addEventListener('click', clickHandler, true);
        document.addEventListener('mousemove', trackMouse, true);

        S.ghost = makeGhostPreview(imgUrl);
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
