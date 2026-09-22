# Robotic Surgery Expert-Call Analyzer

A simple app that analyses 3 expert-call transcripts (France, Germany, UK) on
robotic surgery adoption in Europe, built for the Hasamex AI Engineer technical case.

## What it does
1. Reads the 3 provided transcripts (timestamped, per-expert).
2. Answers the fixed interview-guide questions for each expert individually,
   with an exact quote and timestamp for every answer.
3. Extracts exact, verbatim quotes as evidence for every answer.
4. Shows the source timestamp alongside every quote.
5. Identifies common themes and disagreements across all 3 experts, each
   backed by a quote per expert.
6. Lets the user ask free-form questions across all 3 transcripts, with
   citations.

## Architecture
- **No vector DB / retrieval** — at 3 transcripts, the full text of each
  transcript (or all 3, for cross-expert analysis) is passed directly as
  context to the LLM. This is simpler and more accurate than approximate
  retrieval at this scale.
- **Model**: Groq API, `openai/gpt-oss-120b`, temperature 0 for determinism.
- **Hallucination control**:
  - The system prompt strictly instructs the model to use only the
    transcript text provided, never invent information, and mark an answer
    as "not found" rather than guess.
  - Every quote is independently checked in code against the raw transcript
    text (`verify_quote`), and its claimed timestamp is cross-checked
    against the actual segment the quote came from (`verify_quote_and_timestamp`)
    — not just trusted from the model's own output.
  - A confidence summary ("X/Y answers fully verified") is shown in the UI
    for every analysis run, making grounding visible at a glance.
  - Tested: asking about topics not covered in the transcripts (e.g. "US
    adoption") correctly returns "not found" instead of a fabricated answer.
    Questions requiring merging non-contiguous transcript lines are also
    correctly declined rather than answered with a fabricated composite quote.
- **Parsing**: `src/parser.py` converts each transcript's timestamp/speaker
  format into structured segments so timestamps can be reliably attributed
  and cross-checked.
- **Reliability**: Groq API failures or malformed model output are caught
  and shown as a clean UI error instead of crashing the app.
- **Efficiency**: per-expert interview answers and Q&A history are cached in
  session state to avoid redundant API calls.

## Testing
Unit tests cover transcript parsing and quote/timestamp verification logic:
```bash
python -m unittest tests.test_parser -v
```

## Scaling to 30+ transcripts
Full-context stuffing won't scale past a handful of transcripts (context
window limits, cost, latency). At scale, the approach would move to:
- Chunk transcripts (e.g. by Q&A turn, preserving timestamp/speaker metadata)
- Embed chunks and store in a vector database
- Retrieve top-k relevant chunks per question/query instead of sending full
  transcripts
- Keep the same quote-and-timestamp verification step, just applied to
  retrieved chunks instead of full documents

## Setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Create a `.env` file in the project root:
GROQ_API_KEY=your_groq_api_key_here


Place the transcript files in `data/`:
data/Transcript_1_France.txt
data/Transcript_2_Germany.txt
data/Transcript_3_UK.txt


## Run
```bash
python -m streamlit run app.py
```

## Project structure

hasamex/
├── app.py # Streamlit UI
├── src/
│ ├── parser.py # Transcript parsing + segment lookup
│ ├── groq_client.py # Groq API wrapper with error handling
│ └── analysis.py # Interview guide, cross-expert, Q&A logic + verification
├── tests/
│ └── test_parser.py # Unit tests for parsing and verification
├── data/ # Transcripts + interview guide
├── requirements.txt
└── .env # Groq API key (not committed)