import json
import streamlit as st
from src.parser import parse_transcript
from src.analysis import answer_interview_guide, cross_expert_analysis, ask_across_transcripts
from src.groq_client import GroqCallError

st.set_page_config(page_title="Robotic Surgery Expert-Call Analyzer", layout="wide")
st.title("Robotic Surgery Expert-Call Analyzer")

TRANSCRIPT_FILES = [
    "data/Transcript_1_France.txt",
    "data/Transcript_2_Germany.txt",
    "data/Transcript_3_UK.txt",
]

QUESTIONS = [
    "How would you describe current adoption of robotic surgery in your market?",
    "What are the main barriers to adoption?",
    "How important are hospital budgets and ROI in purchasing decisions?",
    "How important are surgeon training and clinical outcomes?",
    "What adoption trend do you expect over the next 3–5 years?",
    "What is the typical hospital decision-making timeline for purchasing a new robotic system?",
]


@st.cache_resource
def load_transcripts():
    return [parse_transcript(f) for f in TRANSCRIPT_FILES]


transcripts = load_transcripts()

if "interview_cache" not in st.session_state:
    st.session_state.interview_cache = {}
if "cross_expert_cache" not in st.session_state:
    st.session_state.cross_expert_cache = None
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []


def show_quote(quote, timestamp, quote_verified, timestamp_verified, actual_timestamp=None):
    ts = timestamp.strip("[]") if timestamp else "?"
    if quote_verified and timestamp_verified:
        badge = "✅ quote + timestamp verified"
    elif quote_verified and not timestamp_verified:
        badge = f"⚠️ quote verified, but timestamp looks wrong (actual: {actual_timestamp or 'unknown'})"
    else:
        badge = "❌ quote not found verbatim in transcript"
    st.markdown(f"> \"{quote}\"  \n`[{ts}]` {badge}")


def confidence_summary(items: list[dict]) -> str:
    total = len(items)
    fully_verified = sum(1 for i in items if i.get("quote_verified") and i.get("timestamp_verified"))
    return f"**Grounding check: {fully_verified}/{total} answers fully verified (quote + timestamp).**"


tab1, tab2, tab3 = st.tabs(["Interview Guide Answers", "Cross-Expert Themes", "Ask a Question"])

with tab1:
    expert_names = [t.expert_name for t in transcripts]
    choice = st.selectbox("Select expert", expert_names)
    selected = next(t for t in transcripts if t.expert_name == choice)

    col1, col2 = st.columns([1, 1])
    run_clicked = col1.button("Answer interview guide for this expert")
    if choice in st.session_state.interview_cache:
        col2.button("Re-run (ignore cache)", key="rerun_interview")
        if st.session_state.get("rerun_interview"):
            run_clicked = True
            del st.session_state.interview_cache[choice]

    if run_clicked and choice not in st.session_state.interview_cache:
        try:
            with st.spinner("Analyzing transcript..."):
                answers = answer_interview_guide(selected, QUESTIONS)
            st.session_state.interview_cache[choice] = answers
        except GroqCallError as e:
            st.error(f"Could not get an answer from the model: {e}")

    if choice in st.session_state.interview_cache:
        answers = st.session_state.interview_cache[choice]
        st.markdown(confidence_summary(answers))
        for a in answers:
            st.subheader(a["question"])
            st.write(a["answer"])
            if a.get("found", True) and a.get("quote"):
                show_quote(
                    a["quote"], a.get("timestamp", "?"),
                    a.get("quote_verified", False), a.get("timestamp_verified", False),
                    a.get("actual_timestamp"),
                )
            st.divider()

        st.download_button(
            "Download this expert's answers (JSON)",
            data=json.dumps(answers, indent=2),
            file_name=f"{choice.replace(' ', '_')}_interview_answers.json",
            mime="application/json",
        )

with tab2:
    if st.button("Run cross-expert analysis"):
        try:
            with st.spinner("Comparing all 3 experts..."):
                st.session_state.cross_expert_cache = cross_expert_analysis(transcripts)
        except GroqCallError as e:
            st.error(f"Could not complete cross-expert analysis: {e}")

    result = st.session_state.cross_expert_cache
    if result:
        all_evidence = [
            ev
            for bucket in ("common_themes", "disagreements")
            for item in result.get(bucket, [])
            for ev in item.get("evidence", [])
        ]
        if all_evidence:
            st.markdown(confidence_summary(all_evidence))

        st.header("Common Themes")
        for theme in result.get("common_themes", []):
            st.subheader(theme["theme"])
            st.write(theme["summary"])
            for ev in theme.get("evidence", []):
                st.markdown(f"**{ev['expert']}**")
                show_quote(
                    ev["quote"], ev.get("timestamp", "?"),
                    ev.get("quote_verified", False), ev.get("timestamp_verified", False),
                    ev.get("actual_timestamp"),
                )
            st.divider()

        st.header("Disagreements")
        for dis in result.get("disagreements", []):
            st.subheader(dis["topic"])
            st.write(dis["summary"])
            for ev in dis.get("evidence", []):
                st.markdown(f"**{ev['expert']}**")
                show_quote(
                    ev["quote"], ev.get("timestamp", "?"),
                    ev.get("quote_verified", False), ev.get("timestamp_verified", False),
                    ev.get("actual_timestamp"),
                )
            st.divider()

        st.download_button(
            "Download cross-expert analysis (JSON)",
            data=json.dumps(result, indent=2),
            file_name="cross_expert_analysis.json",
            mime="application/json",
        )

with tab3:
    question = st.text_input("Ask a question across all 3 transcripts")
    if st.button("Ask") and question:
        try:
            with st.spinner("Searching transcripts..."):
                result = ask_across_transcripts(transcripts, question)
            st.session_state.qa_history.append({"question": question, "result": result})
        except GroqCallError as e:
            st.error(f"Could not get an answer from the model: {e}")

    for entry in reversed(st.session_state.qa_history):
        st.markdown(f"**Q: {entry['question']}**")
        result = entry["result"]
        if not result.get("found", True):
            st.warning(result["answer"])
        else:
            st.write(result["answer"])
            citations = result.get("citations", [])
            if citations:
                st.markdown(confidence_summary(citations))
            for c in citations:
                st.markdown(f"**{c['expert']}**")
                show_quote(
                    c["quote"], c.get("timestamp", "?"),
                    c.get("quote_verified", False), c.get("timestamp_verified", False),
                    c.get("actual_timestamp"),
                )
        st.divider()

    if st.session_state.qa_history:
        st.download_button(
            "Download Q&A history (JSON)",
            data=json.dumps(st.session_state.qa_history, indent=2),
            file_name="qa_history.json",
            mime="application/json",
        )