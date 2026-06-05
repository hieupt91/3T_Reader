// 3T Reader — Inline image overlay for PDF editing
// Creates a draggable/resizable image overlay on a PDF page.
// Communicates with Python via QWebChannel (inlineImageBridge).
(function () {
    /* clear old overlay */
    if (window.__3TImgState && window.__3TImgState.overlay) {
        var _ov = window.__3TImgState.overlay;
        if (_ov.parentNode) _ov.parentNode.removeChild(_ov);
    }
    window.__3TImgState  = { overlay: null, pageNumber: null, pageView: null };
    window.__3TImgBridge = null;

    var S = window.__3TImgState;

    window.__3TImgConfirm = function () {
        if (!S.overlay || !S.pageView) return;
        var ov = S.overlay;
        var l  = parseFloat(ov.style.left)  || 0;
        var t  = parseFloat(ov.style.top)   || 0;
        var w  = parseFloat(ov.style.width) || 200;
        var h  = parseFloat(ov.style.height)|| 150;
        var p1 = S.pageView.viewport.convertToPdfPoint(l,     t);
        var p2 = S.pageView.viewport.convertToPdfPoint(l + w, t + h);
        var br = window.__3TImgBridge;
        /* keep overlay — page reload clears it */
        if (br) br.confirmImage(
            S.pageNumber,
            Math.min(p1[0],p2[0]), Math.min(p1[1],p2[1]),
            Math.max(p1[0],p2[0]), Math.max(p1[1],p2[1])
        );
    };

    window.__3TImgCancel = function () {
        if (S.overlay && S.overlay.parentNode)
            S.overlay.parentNode.removeChild(S.overlay);
        S.overlay = null;
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
            if (!(nw > 0 && nh > 0)) {
                return { width: 200, height: 150 };
            }

            var maxW = 240;
            var maxH = 180;
            var width = nw;
            var height = nh;
            var ratio = nw / nh;
            if (width > maxW) {
                width = maxW;
                height = width / ratio;
            }
            if (height > maxH) {
                height = maxH;
                width = height * ratio;
            }
            width = Math.max(80, Math.round(width));
            height = Math.max(60, Math.round(height));
            return { width: width, height: height };
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
            if (!pv) {
                var br = window.__3TImgBridge;
                if (br) br.cancelEdit();
                return;
            }
            var pgv = pv.getPageView ? pv.getPageView(pn - 1) : (pv._pages && pv._pages[pn - 1]);
            if (!pgv || !pgv.viewport) {
                var br = window.__3TImgBridge;
                if (br) br.cancelEdit();
                return;
            }
            var canvas = page.querySelector('canvas') || page;
            var pr  = canvas.getBoundingClientRect();
            var cx  = e.clientX - pr.left;
            var cy  = e.clientY - pr.top;

            S.pageNumber = pn;
            S.pageView   = pgv;

            var initial = getInitialSize();
            var left = Math.max(0, Math.round(cx - (initial.width / 2)));
            var top = Math.max(0, Math.round(cy - (initial.height / 2)));

            var ov = document.createElement('div');
            ov.style.cssText =
                'position:absolute;left:' + left + 'px;top:' + top + 'px;' +
                'width:' + initial.width + 'px;height:' + initial.height + 'px;' +
                'border:2px solid #1A7AFF;z-index:9999;' +
                'box-sizing:border-box;border-radius:4px;' +
                'box-shadow:0 4px 20px rgba(26,122,255,0.4);' +
                'cursor:move;overflow:hidden;';

            var img = document.createElement('img');
            img.src = imgUrl;
            img.style.cssText = 'width:100%;height:100%;object-fit:contain;pointer-events:none;display:block;';
            ov.appendChild(img);

            window.__3TImgUpdateRotation = function (angle) {
                if (S.overlay) {
                    S.overlay.style.transformOrigin = 'center center';
                    S.overlay.style.transform = 'rotate(' + angle + 'deg)';
                }
            };

            var badge = document.createElement('div');
            badge.textContent = '🖼️ Ảnh — kéo di chuyển · kéo góc resize · Enter xác nhận';
            badge.style.cssText =
                'position:absolute;top:-26px;left:0;white-space:nowrap;' +
                'font-size:10px;color:#fff;background:#1A7AFF;' +
                'padding:3px 10px;border-radius:10px;pointer-events:none;' +
                'box-shadow:0 1px 6px rgba(0,0,0,0.3);';
            ov.appendChild(badge);

            var rh = document.createElement('div');
            rh.style.cssText =
                'position:absolute;right:-7px;bottom:-7px;width:14px;height:14px;' +
                'background:#1A7AFF;border:2px solid #fff;border-radius:3px;' +
                'cursor:nwse-resize;z-index:10000;';
            ov.appendChild(rh);

            /* drag */
            ov.addEventListener('mousedown', function (ev) {
                if (ev.target === rh) return;
                var sl=parseFloat(ov.style.left), st=parseFloat(ov.style.top);
                var sx=ev.clientX, sy=ev.clientY;
                function onM(e){ ov.style.left=(sl+e.clientX-sx)+'px'; ov.style.top=(st+e.clientY-sy)+'px'; }
                function onU(){ document.removeEventListener('mousemove',onM,true); document.removeEventListener('mouseup',onU,true); }
                document.addEventListener('mousemove',onM,true);
                document.addEventListener('mouseup',onU,true);
                ev.preventDefault();
            });

            /* resize */
            rh.addEventListener('mousedown', function (ev) {
                ev.stopPropagation();
                var sw=parseFloat(ov.style.width)||200, sh=parseFloat(ov.style.height)||150;
                var sx=ev.clientX, sy=ev.clientY;
                function onM(e){ ov.style.width=Math.max(40,sw+e.clientX-sx)+'px'; ov.style.height=Math.max(30,sh+e.clientY-sy)+'px'; }
                function onU(){ document.removeEventListener('mousemove',onM,true); document.removeEventListener('mouseup',onU,true); }
                document.addEventListener('mousemove',onM,true);
                document.addEventListener('mouseup',onU,true);
                ev.preventDefault();
            });

            /* keyboard */
            function kh(ev) {
                if (ev.key === 'Enter')  { window.__3TImgConfirm(); document.removeEventListener('keydown',kh,true); }
                if (ev.key === 'Escape') { window.__3TImgCancel();  document.removeEventListener('keydown',kh,true); }
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
