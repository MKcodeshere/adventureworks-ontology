"""AdventureWorks ontology Text-to-SQL — step-by-step Streamlit guide."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "app"))

from ask import (  # noqa: E402
    ROOT as ASK_ROOT,
    ask_traced,
    load_ontology,
    load_dotenv,
)
from provenance import enrich_provenance, badge_for  # noqa: E402
from evaluate import results_match, load_gold, accuracy  # noqa: E402
from llm import LLMError  # noqa: E402

load_dotenv()

st.set_page_config(
    page_title="AdventureWorks Ontology · Text-to-SQL",
    page_icon="🧭",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

@st.cache_data
def load_questions():
    data = yaml.safe_load((ROOT / "eval" / "questions.yaml").read_text())
    return data["questions"]


@st.cache_data
def load_ont():
    return load_ontology()


@st.cache_data
def load_sources_md():
    return (ROOT / "docs" / "SOURCES.md").read_text(encoding="utf-8")


def env_get(k, default=""):
    return os.environ.get(k, default)


def apply_provider(choice: str, ollama_model: str | None = None):
    """Set process env for llm.complete() based on sidebar selection."""
    if choice.startswith("Gemini"):
        os.environ["LLM_PROVIDER"] = "gemini"
        os.environ["GEMINI_MODEL"] = env_get("GEMINI_MODEL", "gemini-2.5-flash")
    elif choice.startswith("Ollama"):
        os.environ["LLM_PROVIDER"] = "ollama"
        os.environ["OLLAMA_HOST"] = env_get("OLLAMA_HOST", "https://ollama.com")
        os.environ["OLLAMA_MODEL"] = ollama_model or "gpt-oss:120b"
    elif choice.startswith("OpenAI"):
        os.environ["LLM_PROVIDER"] = "openai"
    elif choice.startswith("Anthropic"):
        os.environ["LLM_PROVIDER"] = "anthropic"


def provider_ready(choice: str) -> tuple[bool, str]:
    if choice.startswith("Gemini"):
        ok = bool(env_get("GEMINI_API_KEY"))
        return ok, "GEMINI_API_KEY" if not ok else env_get("GEMINI_MODEL", "gemini-2.5-flash")
    if choice.startswith("Ollama"):
        ok = bool(env_get("OLLAMA_API_KEY")) or env_get("OLLAMA_HOST", "").startswith("http://127")
        return ok, "OLLAMA_API_KEY (cloud) or local OLLAMA_HOST" if not ok else "ok"
    if choice.startswith("OpenAI"):
        return bool(env_get("OPENAI_API_KEY")), "OPENAI_API_KEY"
    if choice.startswith("Anthropic"):
        return bool(env_get("ANTHROPIC_API_KEY")), "ANTHROPIC_API_KEY"
    return False, "unknown"


def tag_badge(tag: str) -> str:
    colors = {"structured": "🔵", "needs-docs": "🟠", "both": "🟣"}
    return f"{colors.get(tag, '⚪')} `{tag}`"


def diff_badge(d: str) -> str:
    return {"simple": "🟩 simple", "medium": "🟨 medium", "complex": "🟥 complex"}.get(d, d)


def render_source_card(item: dict, title_key: str = "name"):
    enriched = enrich_provenance(item, needle=item.get("description") or item.get("name"))
    badge = enriched["source_badge"]
    color = {"From tables": "green", "From docs": "orange", "Both": "violet", "Unknown": "gray"}[badge]
    st.markdown(f"**{enriched.get(title_key) or enriched.get('column') or 'item'}** · :{color}[**{badge}**]")
    if enriched.get("description"):
        st.caption(enriched["description"])
    if enriched.get("sql_hint"):
        st.code(enriched["sql_hint"], language="sql")
    if enriched.get("sql") and not enriched.get("sql_hint"):
        st.code(enriched["sql"], language="sql")
    if enriched.get("values"):
        st.json(enriched["values"])
    cols = st.columns([2, 3])
    with cols[0]:
        st.markdown(f"SOURCE: `{enriched.get('source_label')}`")
        if enriched.get("source_url"):
            st.markdown(f"[Original URL]({enriched['source_url']})")
    with cols[1]:
        if enriched.get("source_snippet"):
            st.info(enriched["source_snippet"])
        elif enriched["source_kind"] == "structured":
            st.caption("Derived from schema / table-column profile (not a free-text doc).")


def entity_graph_agraph(entities, relationships, paths=None, height=360):
    try:
        from streamlit_agraph import agraph, Node, Edge, Config
    except Exception:
        st.warning("streamlit-agraph not installed; showing text paths only.")
        return
    nodes, edges = [], []
    seen_n, seen_e = set(), set()
    seed = {e["name"] for e in entities}
    bridge = set()
    if paths:
        for p in paths:
            for n in p.get("nodes") or []:
                if n not in seed:
                    bridge.add(n)
    for e in entities:
        name = e["name"]
        color = "#27ae60" if name in seed and name not in bridge else "#2980b9"
        if name in bridge:
            color = "#8e44ad"
        nodes.append(Node(id=name, label=name, size=22, color=color,
                          title=e.get("table") or ""))
        seen_n.add(name)
    for rel in relationships:
        a, b = rel.get("from"), rel.get("to")
        if not a or not b:
            continue
        for endpoint, label in ((a, a), (b, b)):
            if endpoint not in seen_n and not str(endpoint).startswith("wh."):
                nodes.append(Node(id=endpoint, label=str(endpoint), size=16, color="#95a5a6"))
                seen_n.add(endpoint)
        key = (a, b, rel.get("name"))
        if key in seen_e:
            continue
        if a in seen_n and b in seen_n:
            join = rel.get("join") or {}
            title = rel.get("name") or ""
            if isinstance(join, dict):
                title += f"\n{join.get('left')} = {join.get('right')}"
            edges.append(Edge(source=a, target=b, label=rel.get("name") or "", title=title))
            seen_e.add(key)
    if not nodes:
        st.caption("No entities to graph.")
        return
    cfg = Config(width="100%", height=height, directed=True, physics=True,
                 hierarchical=False, nodeHighlightBehavior=True)
    agraph(nodes=nodes, edges=edges, config=cfg)


def check_gold(qid: str | None, rows, error) -> dict | None:
    if not qid:
        return None
    try:
        gold = load_gold(qid)
    except Exception as e:
        return {"ok": False, "detail": f"No gold file: {e}"}
    if error:
        return {"ok": False, "detail": f"Exec error — {error}"}
    ok = results_match(rows, gold)
    return {"ok": ok, "detail": "Matches gold denotation" if ok else "Does not match gold",
            "gold_preview": gold[:5]}


def run_one(question: str, mode: str) -> dict:
    return ask_traced(question, mode=mode, row_limit=200)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.title("🧭 Ontology Text-to-SQL")
st.sidebar.caption("AdventureWorks scrambled `wh` schema + business docs")

_provider_options = [
    "Gemini (gemini-2.5-flash)",
    "Ollama Cloud · gpt-oss:120b",
    "Ollama Cloud · nemotron-3-super",
    "OpenAI",
    "Anthropic",
]
# Prefer a provider that has credentials. Gemini may be set but out of credit;
# Ollama Cloud is the reliable demo default when OLLAMA_API_KEY is present.
_default_idx = 0
if env_get("OLLAMA_API_KEY"):
    _default_idx = 2  # nemotron-3-super
elif env_get("GEMINI_API_KEY"):
    _default_idx = 0
elif env_get("OPENAI_API_KEY"):
    _default_idx = 3
elif env_get("ANTHROPIC_API_KEY"):
    _default_idx = 4
# Query-param override: ?provider=ollama&model=nemotron-3-super
_qp_early = st.query_params
if str(_qp_early.get("provider", "")).lower() in {"ollama", "ollama-cloud"}:
    _model_q = str(_qp_early.get("model", "nemotron-3-super")).lower()
    _default_idx = 1 if "gpt-oss" in _model_q else 2
elif str(_qp_early.get("provider", "")).lower() == "gemini":
    _default_idx = 0
provider = st.sidebar.selectbox(
    "Provider / model",
    _provider_options,
    index=_default_idx,
)
ollama_model = None
if "gpt-oss" in provider:
    ollama_model = "gpt-oss:120b"
elif "nemotron" in provider:
    ollama_model = "nemotron-3-super"
apply_provider(provider, ollama_model)
ready, hint = provider_ready(provider)
if ready:
    st.sidebar.success(f"Ready · {hint if hint != 'ok' else provider}")
else:
    st.sidebar.error(f"Missing credentials: {hint}")

mode_ui = st.sidebar.radio(
    "Mode",
    ["Ontology", "Schema-only", "Compare both"],
    index=0,
)
mode_map = {"Ontology": "ontology", "Schema-only": "baseline", "Compare both": "compare"}

questions = load_questions()
q_labels = [
    f"{q['id']} · {q['difficulty']} · {q['tag']} — {q['question'][:60]}"
    for q in questions
]
sample = st.sidebar.selectbox("Sample question", ["(free text)"] + q_labels, index=1)
selected = None
if sample != "(free text)":
    selected = questions[q_labels.index(sample)]

free = st.sidebar.text_area(
    "Or type your own question",
    value="" if selected else "How many internet (online) sales orders are there?",
    height=90,
)
question = (selected["question"] if selected and not free.strip() else free.strip()) or (
    selected["question"] if selected else ""
)
qid = selected["id"] if selected else None

# Deep-link / screenshot helpers: ?qid=Q08&mode=compare&autorun=1
_qp = st.query_params
if _qp.get("qid"):
    _want = str(_qp.get("qid")).upper()
    for q in questions:
        if q["id"].upper() == _want:
            selected = q
            question = q["question"]
            qid = q["id"]
            break
if _qp.get("mode"):
    _m = str(_qp.get("mode")).lower()
    if _m in {"ontology", "baseline", "schema", "schema-only"}:
        mode_ui = "Ontology" if _m == "ontology" else "Schema-only"
    elif _m in {"compare", "both"}:
        mode_ui = "Compare both"

if selected:
    st.sidebar.markdown(
        f"{diff_badge(selected['difficulty'])}  {tag_badge(selected['tag'])}"
    )
_autorun_flag = str(_qp.get("autorun", "")).lower() in {"1", "true", "yes"}
_autorun_key = f"autorun_done::{_qp.get('qid')}::{_qp.get('mode')}::{provider}"
autorun = False
if _autorun_flag and not st.session_state.get(_autorun_key):
    autorun = True
    st.session_state[_autorun_key] = True
go = st.sidebar.button("Ask →", type="primary", width='stretch') or autorun

tab_ask, tab_ont, tab_bench = st.tabs(["Ask (guided)", "Ontology explorer", "Benchmark"])

# ---------------------------------------------------------------------------
# Ask tab
# ---------------------------------------------------------------------------

with tab_ask:
    st.title("Step-by-step guided answer")
    st.markdown(
        "See how a question becomes tokens → ontology slice → prompt → SQL → live rows, "
        "and whether each business fact came **from tables** or **from docs**."
    )
    if not question:
        st.info("Pick a sample question or type one in the sidebar.")
    elif go:
        if not ready:
            st.error("Configure API credentials in `.env` first.")
        else:
            modes = ["ontology", "baseline"] if mode_ui == "Compare both" else [mode_map[mode_ui]]
            traces = {}
            for m in modes:
                with st.spinner(f"Running {m}…"):
                    try:
                        traces[m] = run_one(question, m)
                    except LLMError as e:
                        st.error(f"LLM error: {e}")
                        traces[m] = None
                    except Exception as e:
                        st.exception(e)
                        traces[m] = None

            def render_trace(tr: dict, header: str):
                if not tr:
                    st.error(f"{header}: failed")
                    return
                st.subheader(header)
                lat = tr.get("latency_sec") or {}
                st.caption(
                    f"Latency total **{lat.get('total', '?')}s** "
                    f"(LLM {lat.get('llm', '?')}s · SQL {lat.get('sql', '?')}s)"
                )

                # Step 1
                with st.expander("Step 1 · Question understanding", expanded=True):
                    ex = tr.get("expansions") or {}
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**Question tokens**")
                        st.write(", ".join(f"`{t}`" for t in (ex.get("question_tokens") or [])[:40]) or "—")
                    with c2:
                        st.markdown("**Synonym expansions added**")
                        st.write(", ".join(f"`{t}`" for t in (ex.get("added_tokens") or [])[:40]) or "_(none)_")
                    hits = ex.get("synonym_hits") or []
                    if hits:
                        st.markdown("**Synonym index hits**")
                        for h in hits[:12]:
                            st.markdown(
                                f"- `{h['key']}` → {', '.join(h['values'][:6])} "
                                f"(matched: {', '.join(h['matched_tokens'])})"
                            )

                # Step 2
                with st.expander("Step 2 · Ontology retrieval", expanded=(tr["mode"] == "ontology")):
                    if tr["mode"] != "ontology":
                        st.caption("Schema-only mode: no ontology retrieval. Full schema hints go to the LLM.")
                    else:
                        ret = tr.get("retrieval") or {}
                        st.markdown("**Matched entities → `wh` tables**")
                        for e in tr.get("entities") or []:
                            role = "seed" if e["name"] in set(ret.get("seed_entities") or []) else (
                                "bridge" if e["name"] in set(ret.get("bridge_entities") or []) else "related"
                            )
                            st.markdown(f"- **{e['name']}** → `{e.get('table')}` · _{role}_")
                        st.markdown("**Multi-hop join paths**")
                        paths = tr.get("paths") or []
                        if paths:
                            for p in paths:
                                st.code(" → ".join(p["nodes"]) + f"  ({p['hops']} hop)", language=None)
                        else:
                            st.caption("No multi-hop path between seed pairs (single entity or disconnected).")
                        entity_graph_agraph(tr.get("entities") or [], tr.get("relationships") or [], paths)
                        st.markdown("**Relationships + join keys**")
                        for rel in tr.get("relationships") or []:
                            join = rel.get("join") or {}
                            if isinstance(join, dict) and join:
                                jk = f"`{join.get('left')}` = `{join.get('right')}`"
                            else:
                                jk = rel.get("join_hint") or rel.get("via") or "—"
                            st.markdown(f"- `{rel.get('name')}`: {rel.get('from')} → {rel.get('to')} · {jk}")

                # Step 3
                with st.expander("Step 3 · Business knowledge", expanded=True):
                    if tr["mode"] != "ontology":
                        st.caption("No ontology rules/metrics in schema-only mode.")
                    else:
                        rules = tr.get("rules") or []
                        metrics = tr.get("metrics") or []
                        vals = tr.get("value_meanings") or []
                        if not (rules or metrics or vals):
                            st.warning("No rules, metrics, or value meanings retrieved.")
                        for r in rules:
                            render_source_card(r)
                            st.divider()
                        for m in metrics:
                            render_source_card(m)
                            st.divider()
                        for v in vals:
                            render_source_card(v, title_key="column")
                            st.divider()

                # Step 4
                with st.expander("Step 4 · Prompt sent to the LLM"):
                    st.caption(
                        f"{tr.get('prompt_chars', 0):,} characters · "
                        f"~{tr.get('prompt_approx_tokens', 0):,} approx tokens (chars/4)"
                    )
                    st.code(tr.get("prompt") or "", language="markdown")

                # Step 5
                with st.expander("Step 5 · Generated SQL", expanded=True):
                    if tr.get("sql"):
                        st.code(tr["sql"], language="sql")
                    else:
                        st.error("No SQL extracted")
                    if tr.get("raw") and tr.get("sql") and tr["raw"].strip() != tr["sql"].strip():
                        with st.popover("Raw model output"):
                            st.text(tr["raw"][:4000])

                # Step 6
                with st.expander("Step 6 · Live result", expanded=True):
                    if tr.get("error"):
                        st.error(tr["error"])
                    rows = tr.get("rows") or []
                    st.caption(f"{len(rows)} row(s) shown (limit 200)")
                    if rows:
                        st.dataframe(rows, width='stretch')
                    gold = check_gold(qid, rows, tr.get("error"))
                    if gold is not None:
                        if gold["ok"]:
                            st.success(f"Eval check · {qid}: ✅ {gold['detail']}")
                        else:
                            st.error(f"Eval check · {qid}: ❌ {gold['detail']}")
                            if gold.get("gold_preview"):
                                st.caption("Gold preview")
                                st.json(gold["gold_preview"])

                with st.expander("Nuances"):
                    for n in tr.get("nuances") or []:
                        st.markdown(f"- {n}")

            if mode_ui == "Compare both":
                left, right = st.columns(2)
                with left:
                    render_trace(traces.get("ontology"), "Ontology mode")
                with right:
                    render_trace(traces.get("baseline"), "Schema-only mode")
                st.markdown("---")
                st.subheader("Compare diff")
                o, b = traces.get("ontology"), traces.get("baseline")
                if o and b:
                    diffs = []
                    if (o.get("sql") or "") != (b.get("sql") or ""):
                        diffs.append("SQL differs between modes.")
                    go_ = check_gold(qid, o.get("rows") or [], o.get("error"))
                    gb_ = check_gold(qid, b.get("rows") or [], b.get("error"))
                    if go_ and gb_:
                        diffs.append(
                            f"Gold: ontology={'✅' if go_['ok'] else '❌'} · "
                            f"schema-only={'✅' if gb_['ok'] else '❌'}"
                        )
                    if (o.get("error") or None) != (b.get("error") or None):
                        diffs.append(
                            f"Errors: ontology=`{o.get('error')}` · baseline=`{b.get('error')}`"
                        )
                    ret = o.get("retrieval") or {}
                    diffs.append(
                        "Ontology injected entities: "
                        + (", ".join(ret.get("entities") or []) or "—")
                    )
                    for d in diffs:
                        st.markdown(f"- {d}")
            else:
                m = modes[0]
                render_trace(traces.get(m), f"{mode_ui} mode")
    else:
        st.info("Configure the sidebar, then click **Ask →**.")

# ---------------------------------------------------------------------------
# Ontology explorer
# ---------------------------------------------------------------------------

with tab_ont:
    st.title("Ontology explorer")
    ont = load_ont()
    ents = ont.get("entities") or []
    rels = ont.get("relationships") or []
    rules = ont.get("rules") or []
    metrics = ont.get("metrics") or []
    vals = ont.get("value_meanings") or []

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Entities", len(ents))
    c2.metric("Relationships", len(rels))
    c3.metric("Rules", len(rules))
    c4.metric("Metrics", len(metrics))

    st.subheader("Interactive graph")
    entity_graph_agraph(ents, rels, height=520)

    st.subheader("Browse")
    kind = st.selectbox("Show", ["Entities", "Relationships", "Rules", "Metrics", "Value meanings"])
    if kind == "Entities":
        for e in ents:
            with st.expander(f"{e['name']} · `{e.get('table')}`"):
                render_source_card(e)
                st.json({k: e.get(k) for k in ("attributes", "synonyms", "primary_key") if k in e})
    elif kind == "Relationships":
        for r in rels:
            with st.expander(f"{r.get('name')}: {r.get('from')} → {r.get('to')}"):
                render_source_card(r)
                st.json({k: r.get(k) for k in ("join", "join_hint", "via") if k in r})
    elif kind == "Rules":
        for r in rules:
            with st.expander(r.get("name", "?")):
                render_source_card(r)
    elif kind == "Metrics":
        for m in metrics:
            with st.expander(m.get("name", "?")):
                render_source_card(m)
    else:
        for v in vals:
            with st.expander(str(v.get("column"))):
                render_source_card(v, title_key="column")

# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

with tab_bench:
    st.title("Benchmark")
    report = ROOT / "eval" / "report.md"
    if report.exists():
        st.markdown(report.read_text(encoding="utf-8"))
    else:
        st.warning("No eval/report.md yet.")
    charts_dir = ROOT / "eval" / "charts"
    st.subheader("Charts")
    for name in (
        "model_comparison.png",
        "model_comparison_by_tag.png",
        "overall_accuracy.png",
        "accuracy_by_difficulty.png",
        "accuracy_by_tag.png",
    ):
        p = charts_dir / name
        if p.exists():
            st.image(str(p), caption=name, width='stretch')
    st.subheader("Per-model run folders")
    runs = ROOT / "eval" / "runs"
    if runs.exists():
        for d in sorted(runs.iterdir()):
            if d.is_dir() and d.name.startswith("v1_"):
                st.markdown(f"- `{d.relative_to(ROOT)}/`")
