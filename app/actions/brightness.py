_STEP = 10
_MIN = 20
_MAX = 200

_JS_BRIGHTNESS = """
(function(pct) {
    var el = document.getElementById('viewerContainer');
    if (el) el.style.filter = pct === 100 ? '' : 'brightness(' + pct + '%)';
})(%d)
"""


def _apply(window, pct: int):
    pct = max(_MIN, min(_MAX, pct))
    window._brightness = pct
    window.brightness_label.setText(f"{pct}%")
    wv = window._get_webview()
    if wv:
        wv.page().runJavaScript(_JS_BRIGHTNESS % pct)


def brightness_up(window):
    _apply(window, getattr(window, '_brightness', 100) + _STEP)


def brightness_down(window):
    _apply(window, getattr(window, '_brightness', 100) - _STEP)


def apply_brightness_to_webview(window, wv):
    pct = getattr(window, '_brightness', 100)
    if wv and pct != 100:
        wv.page().runJavaScript(_JS_BRIGHTNESS % pct)
