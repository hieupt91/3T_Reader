// 3T Reader — Inline text overlay for PDF editing
// Creates a draggable/resizable text overlay on a PDF page.
// Communicates with Python via QWebChannel (inlineTextBridge).
(function () {
    /* ── clear any leftover overlay from previous call ── */
    if (window.__3TTextState) {
        var _old = window.__3TTextState;
        if (_old.overlay && _old.overlay.parentNode)
            _old.overlay.parentNode.removeChild(_old.overlay);
    }
    window.__3TTextState   = { overlay: null, textarea: null, pageNumber: null, pageView: null };
    window.__3TTextBridge  = null;   /* set through shared 3T bridge helper */

    var S = window.__3TTextState;

    function getBox() {
        var ov = S.overlay;
        var l  = parseFloat(ov.style.left)  || 0;
        var t  = parseFloat(ov.style.top)   || 0;
        var w  = parseFloat(ov.style.width) || 200;
        var h  = parseFloat(ov.style.height)|| 44;
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
        /* Keep overlay visible — page reload will remove it naturally */
        br.confirmText(S.pageNumber, box.l, box.b, box.r, box.t, text);
    };

    window.__3TTextCancel = function () {
        var br = window.__3TTextBridge;
        if (S.overlay && S.overlay.parentNode)
            S.overlay.parentNode.removeChild(S.overlay);
        S.overlay = null;
        document.body.style.cursor = '';
        if (br) br.cancelEdit();
    };

    /* update textarea font live when panel controls change */
    window.__3TTextUpdateFont = function (size, colorHex, bold, underline) {
        if (S.textarea) {
            S.textarea.style.fontSize       = size + 'px';
            S.textarea.style.color          = colorHex;
            S.textarea.style.fontWeight     = bold ? 'bold' : 'normal';
            S.textarea.style.textDecoration = underline ? 'underline' : 'none';
        }
    };

    window.__3TTextUpdateRotation = function (angle) {
        if (S.overlay) {
            S.overlay.style.transformOrigin = 'center center';
            S.overlay.style.transform = 'rotate(' + angle + 'deg)';
        }
    };

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
            var cx  = e.clientX - pr.left;
            var cy  = e.clientY - pr.top;

            S.pageNumber = pn;
            S.pageView   = pgv;

            /* ── build overlay div ── */
            var ov = document.createElement('div');
            ov.style.cssText =
                'position:absolute;left:' + cx + 'px;top:' + cy + 'px;' +
                'width:260px;min-height:56px;' +
                'border:2px solid #1A7AFF;' +
                'background:rgba(255,255,255,0.97);' +
                'z-index:9999;box-sizing:border-box;border-radius:4px;' +
                'box-shadow:0 4px 20px rgba(26,122,255,0.4);cursor:move;';

            /* badge label */
            var badge = document.createElement('div');
            badge.textContent = '✏️ Văn bản — Ctrl+Enter để chèn';
            badge.style.cssText =
                'position:absolute;top:-26px;left:0;white-space:nowrap;' +
                'font-size:10px;color:#fff;background:#1A7AFF;' +
                'padding:3px 10px;border-radius:10px;pointer-events:none;' +
                'box-shadow:0 1px 6px rgba(0,0,0,0.3);';
            ov.appendChild(badge);

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
                ov.style.height = (ta.scrollHeight + 20) + 'px';
            });
            ov.appendChild(ta);

            /* resize corner */
            var rh = document.createElement('div');
            rh.style.cssText =
                'position:absolute;right:-7px;bottom:-7px;width:14px;height:14px;' +
                'background:#1A7AFF;border:2px solid #fff;border-radius:3px;' +
                'cursor:nwse-resize;z-index:10000;';
            ov.appendChild(rh);

            /* drag move */
            ov.addEventListener('mousedown', function (ev) {
                if (ev.target === rh || ev.target === ta) return;
                var sl = parseFloat(ov.style.left), st = parseFloat(ov.style.top);
                var sx = ev.clientX, sy = ev.clientY;
                function onM(e) {
                    ov.style.left = (sl + e.clientX - sx) + 'px';
                    ov.style.top  = (st + e.clientY - sy) + 'px';
                }
                function onU() {
                    document.removeEventListener('mousemove', onM, true);
                    document.removeEventListener('mouseup',   onU, true);
                }
                document.addEventListener('mousemove', onM, true);
                document.addEventListener('mouseup',   onU, true);
                ev.preventDefault();
            });

            /* resize drag */
            rh.addEventListener('mousedown', function (ev) {
                ev.stopPropagation();
                var sw = parseFloat(ov.style.width) || 220;
                var sh = parseFloat(ov.style.height)|| 48;
                var sx = ev.clientX, sy = ev.clientY;
                function onM(e) {
                    ov.style.width  = Math.max(80,  sw + e.clientX - sx) + 'px';
                    var nh = Math.max(36, sh + e.clientY - sy);
                    ov.style.height = nh + 'px';
                    ta.style.height = (nh - 20) + 'px';
                }
                function onU() {
                    document.removeEventListener('mousemove', onM, true);
                    document.removeEventListener('mouseup',   onU, true);
                }
                document.addEventListener('mousemove', onM, true);
                document.addEventListener('mouseup',   onU, true);
                ev.preventDefault();
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
                ta.style.fontWeight     = pf.bold ? 'bold' : 'normal';
                ta.style.textDecoration = pf.underline ? 'underline' : 'none';
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
