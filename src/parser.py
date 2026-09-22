import re
from dataclasses import dataclass
from typing import List

@dataclass
class Segment:
    timestamp: str
    speaker: str
    text: str

@dataclass
class Transcript:
    expert_name: str
    role: str
    market: str
    segments: List[Segment]
    raw_text: str
    filename: str

TIMESTAMP_RE = re.compile(r'^(\d{2}:\d{2})$')

def parse_transcript(filepath: str) -> Transcript:
    with open(filepath, "r", encoding="utf-8") as f:
        raw_text = f.read()

    lines = [l.rstrip() for l in raw_text.split("\n")]
    i = 0
    header_lines = []
    while i < len(lines) and lines[i].strip() != "":
        header_lines.append(lines[i].strip())
        i += 1

    expert_name, role, market = "", "", ""
    if header_lines:
        first = header_lines[0]
        for dash in ["–", "-"]:
            if dash in first:
                expert_name = first.split(dash, 1)[1].strip()
                break
        else:
            expert_name = first
    for hl in header_lines[1:]:
        if hl.lower().startswith("role:"):
            role = hl.split(":", 1)[1].strip()
        elif hl.lower().startswith("market:"):
            market = hl.split(":", 1)[1].strip()

    while i < len(lines) and lines[i].strip() == "":
        i += 1

    segments = []
    current_ts, current_speaker, current_text = None, None, []

    def flush():
        if current_ts and current_speaker:
            text = " ".join(t.strip() for t in current_text if t.strip())
            if text:
                segments.append(Segment(current_ts, current_speaker, text))

    while i < len(lines):
        line = lines[i].strip()
        if line == "":
            i += 1
            continue
        m = TIMESTAMP_RE.match(line)
        if m:
            flush()
            current_ts = m.group(1)
            current_speaker, current_text = None, []
            i += 1
            continue
        if current_speaker is None and ":" in line:
            speaker, _, rest = line.partition(":")
            current_speaker = speaker.strip()
            current_text.append(rest.strip())
        else:
            current_text.append(line)
        i += 1
    flush()

    import os
    return Transcript(expert_name, role, market, segments, raw_text, os.path.basename(filepath))


def format_for_prompt(t: Transcript) -> str:
    lines = [f"Expert: {t.expert_name}", f"Role: {t.role}", f"Market: {t.market}", ""]
    for seg in t.segments:
        lines.append(f"[{seg.timestamp}] {seg.speaker}: {seg.text}")
    return "\n".join(lines)

def find_segment_for_quote(transcript: Transcript, quote: str) -> Segment | None:
    """Find the segment whose text contains the given quote (normalized match)."""
    if not quote:
        return None
    norm_quote = re.sub(r"\s+", " ", quote).strip().lower()
    for seg in transcript.segments:
        norm_seg_text = re.sub(r"\s+", " ", seg.text).strip().lower()
        if norm_quote in norm_seg_text:
            return seg
    return None