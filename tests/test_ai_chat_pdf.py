from __future__ import annotations


def test_chat_session_keeps_more_than_three_turns_in_prompt(monkeypatch):
    import packages.ai.chat_pdf as chat_pdf
    from packages.ai.provider import AIResponse

    captured = {}

    def fake_ask_ai(prompt, system="", max_tokens=1024):
        captured["prompt"] = prompt
        return AIResponse(text="answer", model="test", success=True)

    monkeypatch.setattr(chat_pdf.PDFChatSession, "_load_text", lambda self: "Nội dung tài liệu.")
    monkeypatch.setattr(chat_pdf, "ask_ai", fake_ask_ai)

    session = chat_pdf.PDFChatSession("dummy.pdf")
    for idx in range(5):
        result = session.ask(f"Câu hỏi {idx + 1}")
        assert result.success

    assert len(session.history) == 10
    assert "Câu hỏi 1" in captured["prompt"]
    assert "Câu hỏi 4" in captured["prompt"]
