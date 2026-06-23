from types import SimpleNamespace


def test_pdf_chat_records_user_question_when_ai_fails(monkeypatch, tmp_path):
    from packages.ai import chat_pdf

    monkeypatch.setattr(chat_pdf, "get_cache_dir", lambda: str(tmp_path))
    monkeypatch.setattr(chat_pdf.PDFChatSession, "_load_text", lambda self: "[Trang 1]\nnoi dung")
    monkeypatch.setattr(chat_pdf, "ask_ai", lambda *a, **k: SimpleNamespace(success=False, text="", error="fail"))

    session = chat_pdf.PDFChatSession("dummy.pdf")
    result = session.ask("cau hoi dang hoi")

    assert result.success is False
    assert session.history[-1].role == "user"
    assert session.history[-1].content == "cau hoi dang hoi"

    reloaded = chat_pdf.PDFChatSession("dummy.pdf")
    assert reloaded.history[-1].content == "cau hoi dang hoi"


def test_pdf_chat_context_selects_relevant_tail_chunk(monkeypatch, tmp_path):
    from packages.ai import chat_pdf

    monkeypatch.setattr(chat_pdf, "get_cache_dir", lambda: str(tmp_path))
    session = chat_pdf.PDFChatSession("dummy.pdf", max_context_chars=180)
    session._pdf_text = "[Trang 1]\n" + ("mo dau " * 80) + "\n\n[Trang 9]\nma so hop dong ABC123 can tim"

    context = session._context_for_question("ABC123 o dau")

    assert "ABC123" in context
    assert "[Trang 9]" in context


def test_pdf_chat_uses_cached_ocr_text_when_pdf_text_missing(monkeypatch, tmp_path):
    from packages.ai import chat_pdf

    monkeypatch.setattr(chat_pdf, "get_cache_dir", lambda: str(tmp_path))
    chat_pdf.save_ocr_text_cache("dummy.pdf", "[Trang OCR]\nnoi dung tu ocr")

    session = chat_pdf.PDFChatSession("dummy.pdf")
    monkeypatch.setitem(__import__("sys").modules, "pdfplumber", SimpleNamespace(open=lambda _path: (_ for _ in ()).throw(RuntimeError("no text"))))
    monkeypatch.setitem(__import__("sys").modules, "pypdfium2", SimpleNamespace(PdfDocument=lambda _path: (_ for _ in ()).throw(RuntimeError("no text"))))

    assert session._load_text() == "[Trang OCR]\nnoi dung tu ocr"
