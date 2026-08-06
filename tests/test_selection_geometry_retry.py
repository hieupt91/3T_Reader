"""_get_selection_payload_sync(): PDF.js selection geometry (getClientRects()/
page viewport lookup) can briefly lag the browser selection itself settling -
text is already available via getSelection().toString() but rects come back
empty for a moment (observed live: "Chú thích" dialog showing "Đã nhận được
văn bản bôi đen nhưng chưa lấy được tọa độ trên trang PDF"). Retry the JS read
a few times with a short pumped delay before giving up, instead of
immediately failing. Deliberately does NOT fall back to page-text search
(that previously picked the wrong occurrence of duplicate text - TC42,
covered by test_tc42_strict_selection_does_not_search_duplicate_text)."""

from app.actions import annotate


class FakeLoop:
    def __init__(self, _parent):
        self._running = False

    def isRunning(self):
        return self._running

    def quit(self):
        self._running = False

    def exec(self):
        return 0


class FakeTimer:
    @staticmethod
    def singleShot(_timeout_ms, _callback):
        return None


class Window:
    current_path = "sample.pdf"

    def __init__(self, web_view):
        self._web_view = web_view

    def _get_webview(self):
        return self._web_view


def _install_fakes(monkeypatch):
    monkeypatch.setattr(annotate, "QEventLoop", FakeLoop)
    monkeypatch.setattr(annotate, "QTimer", FakeTimer)


def test_recovers_on_a_later_attempt_after_empty_rects_first(monkeypatch):
    _install_fakes(monkeypatch)
    calls = {"n": 0}

    class FlakyPage:
        def runJavaScript(self, _script, callback):
            calls["n"] += 1
            if calls["n"] == 1:
                callback({"text": "sửa", "rects": []})
            else:
                callback({"text": "sửa", "rects": [{"page_number": 1, "rect": [10, 20, 30, 40]}]})

        def selectedText(self):
            return "sửa"

    class FlakyWebView:
        def page(self):
            return FlakyPage()

    payload = annotate._get_selection_payload_sync(
        Window(FlakyWebView()),
        allow_text_search_fallback=False,
    )

    assert calls["n"] == 2
    assert payload["rects"] == [{"page_number": 1, "rect": [10, 20, 30, 40]}]


def test_gives_up_after_exhausting_retries_and_still_returns_text(monkeypatch):
    _install_fakes(monkeypatch)
    calls = {"n": 0}

    class AlwaysEmptyPage:
        def runJavaScript(self, _script, callback):
            calls["n"] += 1
            callback({"text": "sửa", "rects": []})

        def selectedText(self):
            return "sửa"

    class AlwaysEmptyWebView:
        def page(self):
            return AlwaysEmptyPage()

    payload = annotate._get_selection_payload_sync(
        Window(AlwaysEmptyWebView()),
        allow_text_search_fallback=False,
        geometry_retries=2,
    )

    # 1 initial read + 2 retries = 3 total calls, then give up with the text
    # still intact (no page-text search fallback - strict mode).
    assert calls["n"] == 3
    assert payload == {"text": "sửa", "rects": []}


def test_does_not_retry_when_first_read_already_has_rects(monkeypatch):
    """No text-but-empty-rects condition -> no retry overhead on the common,
    already-working path."""
    _install_fakes(monkeypatch)
    calls = {"n": 0}

    class GoodPage:
        def runJavaScript(self, _script, callback):
            calls["n"] += 1
            callback({"text": "sửa", "rects": [{"page_number": 1, "rect": [10, 20, 30, 40]}]})

        def selectedText(self):
            return "sửa"

    class GoodWebView:
        def page(self):
            return GoodPage()

    annotate._get_selection_payload_sync(Window(GoodWebView()), allow_text_search_fallback=False)

    assert calls["n"] == 1
