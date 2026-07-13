// 3T Reader — Inline text overlay for PDF editing
// Creates a draggable/resizable text overlay on a PDF page.
// Communicates with Python via QWebChannel (inlineTextBridge).
(function () {
    /* ── clear any leftover overlay from previous call ── */
    if (window.__3TTextState) {
        var _old = window.__3TTextState;
        if (_old.overlay && _old.overlay.parentNode)
            _old.overlay.parentNode.removeChild(_old.overlay);
        if (_old.dragCap && _old.dragCap.parentNode)
            _old.dragCap.parentNode.removeChild(_old.dragCap);
    }
    window.__3TTextState   = { overlay: null, textarea: null, pageNumber: null, pageView: null,
                                pageEl: null, canvas: null, dragCap: null };
    window.__3TTextBridge  = null;

    var S = window.__3TTextState;

    /* ── drag capture helpers ── */
    function makeDragCap() {
        var cap = document.createElement('div');
        cap.style.cssText =
            'position:fixed;inset:0;z-index:99998;background:transparent;cursor:move;';
        return cap;
    }

    function getBox() {
        var el = S.textarea || S.overlay;
        var canvas = S.canvas || (S.pageEl && S.pageEl.querySelector('canvas')) || S.pageEl;
        if (!canvas || !el) return { l:0, b:0, r:100, t:50 };
        var cr  = canvas.getBoundingClientRect();
        var ovr = el.getBoundingClientRect();
        var l   = ovr.left   - cr.left;
        var t   = ovr.top    - cr.top;
        var w   = ovr.width;
        var h   = ovr.height;
        var p1 = S.pageView.viewport.convertToPdfPoint(l,     t);
        var p2 = S.pageView.viewport.convertToPdfPoint(l + w, t + h);
        return { l:Math.min(p1[0],p2[0]), b:Math.min(p1[1],p2[1]),
                 r:Math.max(p1[0],p2[0]), t:Math.max(p1[1],p2[1]) };
    }

    /* called by Python panel "Chèn" button OR Ctrl+Enter in textarea */
    window.__3TTextCommit = function () {
        if (!S.textarea || !S.pageView) return;
        var text = S.textarea.value.trim();
        var br   = window.__3TTextBridge;
        if (!br) return;
        if (!text) { br.cancelEdit(); return; }
        var box = getBox();
        br.confirmText(S.pageNumber, box.l, box.b, box.r, box.t, text);
        
        if (S.overlay && S.overlay.parentNode)
            S.overlay.parentNode.removeChild(S.overlay);
        if (S.dragCap && S.dragCap.parentNode)
            S.dragCap.parentNode.removeChild(S.dragCap);
        S.overlay = null;
        S.dragCap = null;
        document.body.style.cursor = '';
        window.__3TTextState = null;
    };

    window.__3TTextCancel = function () {
        var br = window.__3TTextBridge;
        if (S.overlay && S.overlay.parentNode)
            S.overlay.parentNode.removeChild(S.overlay);
        if (S.dragCap && S.dragCap.parentNode)
            S.dragCap.parentNode.removeChild(S.dragCap);
        S.overlay = null;
        S.dragCap = null;
        document.body.style.cursor = '';
        if (br) br.cancelEdit();
    };

    /* update textarea font live when panel controls change.
       Accepts a payload object {size,color,bold,underline,italic,font_family}
       (safe for font names with spaces/quotes) or legacy positional args. */
    window.__3TTextUpdateFont = function (size, colorHex, bold, underline, italic, fontFamily) {
        if (size && typeof size === 'object') {
            var p = size;
            colorHex   = p.color;
            bold       = p.bold;
            underline  = p.underline;
            italic     = p.italic;
            fontFamily = p.font_family;
            size       = p.size;
        }
        if (S.textarea) {
            S.textarea.style.fontSize       = size + 'px';
            S.textarea.style.color          = colorHex;
            S.textarea.style.fontWeight     = bold ? 'bold' : 'normal';
            S.textarea.style.textDecoration = underline ? 'underline' : 'none';
            S.textarea.style.fontStyle      = italic ? 'italic' : 'normal';
            if (fontFamily) S.textarea.style.fontFamily = fontFamily;
        }
    };

    window.__3TTextUpdateRotation = function (angle) {
        if (S.overlay) {
            S.overlay.style.transformOrigin = 'center center';
            S.overlay.style.transform = 'rotate(' + angle + 'deg)';
        }
    };

    function startDrag(ov, ev, isResize, ta) {
        var sl = ov.getBoundingClientRect().left;
        var st = ov.getBoundingClientRect().top;
        var sw = ov.offsetWidth;
        var sh = ov.offsetHeight;
        var sx = ev.clientX, sy = ev.clientY;

        /* Create full-screen capture div */
        var cap = makeDragCap();
        if (isResize) cap.style.cursor = 'nwse-resize';
        document.body.appendChild(cap);
        S.dragCap = cap;

        function onM(e) {
            var dx = e.clientX - sx;
            var dy = e.clientY - sy;
            if (isResize) {
                var nw = Math.max(80,  sw + dx);
                var nh = Math.max(36, sh + dy);
                ov.style.width  = nw + 'px';
                ov.style.height = nh + 'px';
                if (ta) ta.style.height = (nh - 36) + 'px';
            } else {
                /* Move: compute new position relative to page div */
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

    function startListen() {
        document.body.style.cursor = 'text';

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
                var br = window.__3TTextBridge;
                if (br) br.cancelEdit();
                return;
            }
            var pgv = pv.getPageView ? pv.getPageView(pn - 1) : (pv._pages && pv._pages[pn - 1]);
            if (!pgv || !pgv.viewport) {
                var br = window.__3TTextBridge;
                if (br) br.cancelEdit();
                return;
            }
            var canvas = page.querySelector('canvas') || page;
            var pr  = canvas.getBoundingClientRect();
            var pageRect = page.getBoundingClientRect();
            var cx  = e.clientX - pageRect.left;
            var cy  = e.clientY - pageRect.top;

            S.pageNumber = pn;
            S.pageView   = pgv;
            S.pageEl     = page;
            S.canvas     = canvas;

            /* ── build overlay div ── */
            var ov = document.createElement('div');
            ov.style.cssText =
                'position:absolute;left:' + cx + 'px;top:' + cy + 'px;' +
                'width:260px;min-height:56px;' +
                'border:2px solid #1A7AFF;' +
                'background:rgba(255,255,255,0.97);' +
                'z-index:9999;box-sizing:border-box;border-radius:4px;' +
                'box-shadow:0 4px 20px rgba(26,122,255,0.4);';

            /* drag handle bar at top */
            var dragBar = document.createElement('div');
            dragBar.style.cssText =
                'width:100%;height:20px;cursor:move;background:#1A7AFF;' +
                'border-radius:2px 2px 0 0;display:flex;align-items:center;' +
                'padding:0 8px;box-sizing:border-box;';
            var badge = document.createElement('span');
            badge.textContent = '✏️ Văn bản — kéo thanh này để di chuyển';
            badge.style.cssText =
                'font-size:10px;color:#fff;white-space:nowrap;pointer-events:none;';
            dragBar.appendChild(badge);
            ov.appendChild(dragBar);

            /* textarea */
            var ta = document.createElement('textarea');
            ta.placeholder = 'Gõ văn bản…';
            ta.style.cssText =
                'display:block;width:calc(100% - 10px);min-height:36px;' +
                'margin:5px;border:none;outline:none;background:transparent;' +
                'resize:none;font-family:Arial,sans-serif;font-size:14px;' +
                'color:#000;line-height:1.6;overflow:hidden;cursor:text;';
            ta.addEventListener('input', function () {
                ta.style.height = 'auto';
                ta.style.height = ta.scrollHeight + 'px';
                ov.style.height = (ta.scrollHeight + 56) + 'px';
            });
            ov.appendChild(ta);

            var hint = document.createElement('div');
            hint.textContent = 'Ctrl+Enter để chèn · Esc để hủy';
            hint.style.cssText =
                'position:absolute;left:7px;right:22px;bottom:4px;' +
                'font-size:10px;line-height:14px;color:#475569;' +
                'pointer-events:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
            ov.appendChild(hint);

            /* resize corner */
            var rh = document.createElement('div');
            rh.style.cssText =
                'position:absolute;right:-7px;bottom:-7px;width:14px;height:14px;' +
                'background:#1A7AFF;border:2px solid #fff;border-radius:3px;' +
                'cursor:nwse-resize;z-index:10000;';
            ov.appendChild(rh);

            /* drag via drag handle bar */
            dragBar.addEventListener('mousedown', function (ev) {
                startDrag(ov, ev, false, ta);
                ev.stopPropagation();
            });

            /* resize drag */
            rh.addEventListener('mousedown', function (ev) {
                startDrag(ov, ev, true, ta);
                ev.stopPropagation();
            });

            /* keyboard shortcuts */
            ta.addEventListener('keydown', function (ev) {
                if (ev.key === 'Enter' && ev.ctrlKey) {
                    ev.preventDefault();
                    window.__3TTextCommit();
                }
                if (ev.key === 'Escape') { window.__3TTextCancel(); }
            });

            page.appendChild(ov);
            S.overlay  = ov;
            S.textarea = ta;

            /* Apply prefill when editing existing text */
            if (window.__3TTextPrefill) {
                var pf = window.__3TTextPrefill;
                if (pf.text)      ta.value = pf.text;
                if (pf.font_size) ta.style.fontSize = pf.font_size + 'px';
                if (pf.color_hex) ta.style.color = pf.color_hex;
                if (pf.font_family) ta.style.fontFamily = pf.font_family;
                ta.style.fontWeight     = pf.bold ? 'bold' : 'normal';
                ta.style.textDecoration = pf.underline ? 'underline' : 'none';
                ta.style.fontStyle      = pf.italic ? 'italic' : 'normal';
                ta.dispatchEvent(new Event('input'));
                if (typeof pf.rotation === 'number')
                    window.__3TTextUpdateRotation(pf.rotation);
                window.__3TTextPrefill = null;
            }

            ta.focus();

            var br = window.__3TTextBridge;
            if (br) br.reportReady(pn);
        }

        document.addEventListener('click', clickHandler, true);
    }

    function attach() {
        if (typeof window.__3tWithBridge !== 'function') {
            setTimeout(attach, 100);
            return;
        }
        window.__3tWithBridge('inlineTextBridge', function (bridge) {
            window.__3TTextBridge = bridge || null;
            startListen();
        });
    }
    attach();
})();
