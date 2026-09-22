import re
from .groq_client import call_groq_json, GroqCallError
from .parser import Transcript, format_for_prompt, find_segment_for_quote

GROUNDING_RULES = (
    "You are analysing a real expert-call transcript for a market research project. "
    "STRICT RULES:\n"
    "1. Use ONLY information explicitly stated in the transcript provided. Never invent, infer beyond what is said, or use outside knowledge.\n"
    "2. Every answer must include an exact quote COPIED VERBATIM from the transcript, and the timestamp of that quote.\n"
    "3. If the transcript does not contain enough information to answer, set \"found\" to false and explain why in the answer field instead of guessing.\n"
    "4. Never merge or paraphrase multiple lines into a quote — the quote field must be a real, contiguous, exact excerpt."
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _clean_timestamp(ts: str) -> str:
    return ts.strip("[]").strip() if ts else ""


def verify_quote(quote: str, raw_text: str) -> bool:
    if not quote:
        return False
    return _normalize(quote) in _normalize(raw_text)


def verify_quote_and_timestamp(quote: str, claimed_timestamp: str, transcript: Transcript) -> dict:
    """Checks both that the quote exists verbatim, and that the claimed timestamp
    actually matches the segment the quote came from."""
    quote_ok = verify_quote(quote, transcript.raw_text)
    segment = find_segment_for_quote(transcript, quote)
    actual_ts = segment.timestamp if segment else None
    claimed_clean = _clean_timestamp(claimed_timestamp)
    timestamp_ok = bool(actual_ts) and actual_ts == claimed_clean
    return {
        "quote_verified": quote_ok,
        "timestamp_verified": timestamp_ok,
        "actual_timestamp": actual_ts,
    }


def answer_interview_guide(transcript: Transcript, questions: list[str]) -> list[dict]:
    numbered_qs = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    system_prompt = GROUNDING_RULES + (
        "\nReturn a JSON object: "
        '{"answers": [{"question": str, "answer": str, "quote": str, "timestamp": str, "found": bool}, ...]}'
        " with one entry per question, in order."
    )
    user_prompt = (
        f"TRANSCRIPT:\n{format_for_prompt(transcript)}\n\n"
        f"QUESTIONS:\n{numbered_qs}"
    )
    result = call_groq_json(system_prompt, user_prompt)
    answers = result.get("answers", [])

    for a in answers:
        checks = verify_quote_and_timestamp(a.get("quote", ""), a.get("timestamp", ""), transcript)
        a.update(checks)
    return answers


def cross_expert_analysis(transcripts: list[Transcript]) -> dict:
    combined = "\n\n---\n\n".join(format_for_prompt(t) for t in transcripts)
    system_prompt = GROUNDING_RULES + (
        "\nCompare the experts below. Return a JSON object:\n"
        '{"common_themes": [{"theme": str, "summary": str, '
        '"evidence": [{"expert": str, "quote": str, "timestamp": str}]}], '
        '"disagreements": [{"topic": str, "summary": str, '
        '"evidence": [{"expert": str, "quote": str, "timestamp": str}]}]}\n'
        "Only include a theme/disagreement if at least 2 experts' statements support it with a real quote each."
    )
    user_prompt = f"TRANSCRIPTS:\n{combined}"
    result = call_groq_json(system_prompt, user_prompt)

    transcripts_by_expert = {t.expert_name: t for t in transcripts}
    for bucket in ("common_themes", "disagreements"):
        for item in result.get(bucket, []):
            for ev in item.get("evidence", []):
                t = transcripts_by_expert.get(ev.get("expert"))
                if t:
                    checks = verify_quote_and_timestamp(ev.get("quote", ""), ev.get("timestamp", ""), t)
                    ev.update(checks)
                else:
                    ev["quote_verified"] = False
                    ev["timestamp_verified"] = False
    return result


def ask_across_transcripts(transcripts: list[Transcript], question: str) -> dict:
    combined = "\n\n---\n\n".join(format_for_prompt(t) for t in transcripts)
    system_prompt = GROUNDING_RULES + (
        "\nAnswer the user's question using only the transcripts below. Return a JSON object:\n"
        '{"answer": str, "found": bool, '
        '"citations": [{"expert": str, "quote": str, "timestamp": str}]}\n'
        "If the transcripts do not contain the answer, set found to false and say so plainly."
    )
    user_prompt = f"TRANSCRIPTS:\n{combined}\n\nQUESTION:\n{question}"
    result = call_groq_json(system_prompt, user_prompt)

    transcripts_by_expert = {t.expert_name: t for t in transcripts}
    for c in result.get("citations", []):
        t = transcripts_by_expert.get(c.get("expert"))
        if t:
            checks = verify_quote_and_timestamp(c.get("quote", ""), c.get("timestamp", ""), t)
            c.update(checks)
        else:
            c["quote_verified"] = False
            c["timestamp_verified"] = False
    return result