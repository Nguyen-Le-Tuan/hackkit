"""Demo shell. Pick a feature, give it input, show extracted data, numbers and review flags.

Run: streamlit run app/streamlit_app.py
"""

from __future__ import annotations

from dataclasses import replace

import streamlit as st

from hackkit.cache import DiskCache
from hackkit.config import PROVIDERS, Settings
from hackkit.export import to_json, to_markdown
from hackkit.feature import discover
from hackkit.llm import Attachment, LLMError, get_client
from hackkit.pipeline import RunResult, run_feature

UPLOAD_TYPES = {"image": ["png", "jpg", "jpeg", "webp"], "pdf": ["pdf"]}

st.set_page_config(page_title="hackkit", layout="wide")


@st.cache_resource
def load_features():
    return discover()


def sidebar(settings: Settings, feature_keys: list[str]) -> tuple[str, Settings]:
    with st.sidebar:
        st.header("Setup")
        key = st.selectbox("Feature", feature_keys, format_func=lambda k: features[k].title)
        provider = st.selectbox(
            "Model provider",
            PROVIDERS,
            index=PROVIDERS.index(settings.llm_provider),
            help="fake needs no key and no network. Use it to rehearse the demo.",
        )
        demo_mode = st.toggle(
            "Demo mode",
            value=settings.demo_mode,
            help="Replay saved results only. Turn it on before you present.",
        )
        cache = DiskCache(settings.cache_dir)
        if st.button("Clear saved results"):
            st.toast(f"Cleared {cache.clear()} saved result(s).")
    return key, replace(settings, llm_provider=provider, demo_mode=demo_mode)


def show_result(result: RunResult) -> None:
    extraction = result.extraction
    if not extraction.ok:
        st.error(f"Could not extract data. {extraction.error or ''}".strip())
        if extraction.raw_text:
            with st.expander("Model output"):
                st.code(extraction.raw_text)
        return

    source = "saved result" if extraction.from_cache else f"{extraction.attempts} model call(s)"
    st.caption(f"From {source}.")
    if result.rules and result.rules.summary:
        st.subheader(result.rules.summary)
    if result.rules and result.rules.metrics:
        columns = st.columns(len(result.rules.metrics))
        for column, (name, value) in zip(columns, result.rules.metrics.items(), strict=True):
            column.metric(name.replace("_", " ").capitalize(), value)

    if result.flags:
        st.markdown("**Needs human review**")
        for flag in result.flags:
            st.warning(f"{flag.field}: {flag.reason}")
    else:
        st.success("Nothing flagged for review.")

    with st.expander("Extracted data", expanded=True):
        st.json(extraction.data.model_dump(mode="json"))
    left, right = st.columns(2)
    left.download_button("Download report (.md)", to_markdown(result), "report.md")
    right.download_button("Download data (.json)", to_json(result), "result.json")


features = load_features()
if not features:
    st.info("No features yet. Create one with: python -m hackkit.scaffold my_feature")
    st.stop()

feature_key, settings = sidebar(Settings.from_env(), sorted(features))
feature = features[feature_key]

st.title(feature.title)
st.write(feature.description)

text = st.text_area("Input text", value=feature.sample_text, height=220)
upload_kinds = [k for k in feature.accepts if k in UPLOAD_TYPES]
uploads = []
if upload_kinds:
    allowed = [ext for kind in upload_kinds for ext in UPLOAD_TYPES[kind]]
    uploads = st.file_uploader("Or add files", type=allowed, accept_multiple_files=True) or []

if st.button("Run", type="primary", key="run"):
    attachments = [
        Attachment.from_bytes(f.getvalue(), f.type or "application/pdf") for f in uploads
    ]
    try:
        client = get_client(settings, fake_responder=lambda _req: feature.sample_response)
        with st.spinner("Reading the input..."):
            st.session_state["result"] = run_feature(
                feature,
                client,
                text=text,
                attachments=attachments,
                cache=DiskCache(settings.cache_dir),
                demo_mode=settings.demo_mode,
            )
    except LLMError as exc:
        st.error(str(exc))

result = st.session_state.get("result")
if result is not None and result.feature.key == feature.key:
    show_result(result)
