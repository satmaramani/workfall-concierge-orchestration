"""Session memory summarization helpers."""

from __future__ import annotations

from collections.abc import Iterable


MAX_MEMORY_TEXT_LENGTH = 4000
SUMMARY_SENTENCE_COUNT = 2


def _stringify_lines(lines: Iterable[str | None]) -> str:
    filtered = [line.strip() for line in lines if line and line.strip()]
    return "\n".join(filtered)


def build_session_memory_text(
    *,
    prior_summary: str | None,
    last_input: str,
    last_intent: str,
    last_response: dict,
) -> str:
    # The summary source text is intentionally plain so both Sumy and the fallback truncation stay predictable.
    ai_parse = last_response.get("ai_parse") or {}
    result_data = last_response.get("data") or {}
    lines = [
        f"Previous summary: {prior_summary}" if prior_summary else None,
        f"Latest user request: {last_input}",
        f"Latest resolved intent: {last_intent}",
        (
            "Latest parsed entities: "
            f"product_id={ai_parse.get('product_id')}, "
            f"product_name={ai_parse.get('product_name')}, "
            f"quantity={ai_parse.get('quantity')}"
        ),
        f"Latest workflow status: {last_response.get('status')}",
        f"Latest response message: {last_response.get('message')}",
        f"Latest result data: {result_data}",
    ]
    memory_text = _stringify_lines(lines)
    return memory_text[:MAX_MEMORY_TEXT_LENGTH]


def summarize_session_memory(memory_text: str) -> str:
    if not memory_text.strip():
        return ""

    try:
        # Sumy gives us a cheap local summary, which is enough for session carry-over in this MVP.
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.summarizers.lsa import LsaSummarizer

        parser = PlaintextParser.from_string(memory_text, Tokenizer("english"))
        summarizer = LsaSummarizer()
        summary_sentences = [str(sentence).strip() for sentence in summarizer(parser.document, SUMMARY_SENTENCE_COUNT)]
        summary = " ".join(sentence for sentence in summary_sentences if sentence)
        if summary:
            return summary[:1000]
    except Exception:
        pass

    flattened = " ".join(memory_text.split())
    return flattened[:1000]
