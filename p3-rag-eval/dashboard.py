"""
P3 — RAG Quality Gate Dashboard
Run: streamlit run dashboard.py  (from p3-rag-eval/)
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── constants ─────────────────────────────────────────────────────────────────
RESULTS_DIR = Path(__file__).parent / "results"

THRESHOLDS = {
    "context_precision": 0.70,
    "context_recall":    0.60,
    "faithfulness":      0.80,
    "answer_relevancy":  0.70,
    "refusal_accuracy":  0.90,
}
LABELS = {
    "context_precision": "Context Precision",
    "context_recall":    "Context Recall",
    "faithfulness":      "Faithfulness",
    "answer_relevancy":  "Answer Relevancy",
    "refusal_accuracy":  "Refusal Accuracy",
}
DESCRIPTIONS = {
    "context_precision": "Relevant chunks retrieved vs total retrieved",
    "context_recall":    "Relevant chunks found vs all relevant in DB",
    "faithfulness":      "Answer grounded in context — no hallucination",
    "answer_relevancy":  "Answer addresses the question asked",
    "refusal_accuracy":  "Correct refusals on unanswerable questions",
}

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RAG Quality Gate",
    layout="wide",
    page_icon="◈",
    initial_sidebar_state="collapsed",
)

# ── global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue",
                 Arial, sans-serif !important;
}
.stApp { background: #080808 !important; }
.block-container { padding: 0 2.5rem 5rem !important; max-width: 1440px !important; }

/* ── header ────────────────────────────────────────────────── */
.acn-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.5rem 0 1.25rem; border-bottom: 1px solid #181818; margin-bottom: 2rem;
}
.acn-brand { display: flex; align-items: center; gap: 14px; }
.acn-wordmark {
    font-size: 11px; font-weight: 800; letter-spacing: 0.2em;
    color: #A100FF; text-transform: uppercase;
}
.acn-chevron { color: #A100FF; font-weight: 900; font-size: 14px; }
.acn-divider { width: 1px; height: 20px; background: #222; }
.acn-title {
    font-size: 18px; font-weight: 700; color: #fff;
    letter-spacing: -0.02em; margin: 0;
}
.acn-run-meta { text-align: right; }
.acn-run-label { font-size: 10px; color: #333; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 2px; }
.acn-run-value { font-size: 12px; color: #666; }

/* ── verdict ───────────────────────────────────────────────── */
.verdict {
    display: flex; align-items: center; justify-content: space-between;
    padding: 20px 28px; border-radius: 3px; margin-bottom: 2rem;
}
.verdict-fail { background: rgba(255,59,48,.07); border: 1px solid rgba(255,59,48,.18); }
.verdict-pass { background: rgba(0,200,81,.07);  border: 1px solid rgba(0,200,81,.18);  }
.v-left  { display: flex; flex-direction: column; gap: 4px; }
.v-eye   { font-size: 10px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; }
.verdict-fail .v-eye { color: #FF3B30; }
.verdict-pass .v-eye { color: #00C851; }
.v-msg  { font-size: 15px; font-weight: 600; color: #ddd; }
.v-word {
    font-size: 44px; font-weight: 800; letter-spacing: -0.04em;
    line-height: 1; font-variant-numeric: tabular-nums;
}
.verdict-fail .v-word { color: #FF3B30; }
.verdict-pass .v-word { color: #00C851; }

/* ── metric card ───────────────────────────────────────────── */
.m-card {
    background: #0d0d0d; border-radius: 3px; border: 1px solid #181818;
    padding: 18px 18px 14px; position: relative; overflow: hidden;
}
.m-card-pass { border-color: rgba(0,200,81,.12); }
.m-card-fail { border-color: rgba(255,59,48,.15); }
.m-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
}
.m-card-pass::before { background: #00C851; }
.m-card-fail::before { background: #FF3B30; }
.m-label {
    font-size: 10px; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #444; margin-bottom: 10px;
}
.m-score {
    font-size: 40px; font-weight: 800; letter-spacing: -0.04em;
    line-height: 1; margin-bottom: 14px; color: #fff;
    font-variant-numeric: tabular-nums;
}
.m-card-fail .m-score { color: #FF3B30; }
.m-bar-bg  { height: 2px; background: #1a1a1a; border-radius: 1px; margin-bottom: 12px; }
.m-bar-fill { height: 2px; border-radius: 1px; transition: width .4s; }
.m-card-pass .m-bar-fill { background: #00C851; }
.m-card-fail .m-bar-fill { background: #FF3B30; }
.m-footer  { display: flex; justify-content: space-between; align-items: center; }
.m-thr     { font-size: 10px; color: #2e2e2e; }
.m-badge-pass { font-size: 10px; font-weight: 700; letter-spacing: 0.1em; color: #00C851; }
.m-badge-fail { font-size: 10px; font-weight: 700; letter-spacing: 0.1em; color: #FF3B30; }
.m-desc    { font-size: 10px; color: #333; margin-top: 8px; line-height: 1.5; }

/* ── section label ─────────────────────────────────────────── */
.sec {
    display: block; font-size: 10px; font-weight: 700; letter-spacing: 0.15em;
    text-transform: uppercase; color: #2e2e2e;
    padding: 1.75rem 0 0.875rem; border-top: 1px solid #141414;
}

/* ── worst cards ───────────────────────────────────────────── */
.w-card {
    background: #0d0d0d; border: 1px solid #181818; border-radius: 3px;
    padding: 14px 15px; min-height: 162px; overflow: hidden; position: relative;
}
.w-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: #FF3B30;
}
.w-id    { font-size: 10px; color: #333; font-weight: 700; letter-spacing: 0.06em; margin-bottom: 6px; }
.w-q     { font-size: 11.5px; line-height: 1.5; color: #777; margin-bottom: 10px; }
.w-score { font-size: 28px; font-weight: 800; letter-spacing: -0.03em; color: #FF3B30; line-height: 1; }
.w-clf   { font-size: 10px; color: #FF9F0A; margin-top: 3px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }

/* ── detail cards ──────────────────────────────────────────── */
.d-card { background: #0d0d0d; border: 1px solid #181818; border-radius: 3px; padding: 14px 18px; margin-bottom: 10px; }
.d-lbl  { font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #3a3a3a; margin-bottom: 8px; }
.d-txt  { font-size: 13px; line-height: 1.65; color: #aaa; }

/* ── score bar (table) ─────────────────────────────────────── */
.sbar { display:flex; align-items:center; gap:7px; }
.sbar-bg { flex:1; background:#181818; border-radius:1px; height:3px; }
.sbar-fill { height:3px; border-radius:1px; }
.sbar-val { font-size:11px; min-width:38px; font-variant-numeric:tabular-nums; font-weight:600; }

/* ── Streamlit widget polish ───────────────────────────────── */
[data-testid="stMetric"] {
    background: #0d0d0d !important; border: 1px solid #181818 !important;
    border-radius: 3px !important; padding: 14px 16px !important;
}
[data-testid="stMetric"] label {
    font-size: 10px !important; color: #3a3a3a !important;
    text-transform: uppercase; letter-spacing: 0.1em !important; font-weight: 700 !important;
}
[data-testid="stMetricValue"] {
    font-size: 22px !important; font-weight: 800 !important; color: #fff !important;
}
[data-testid="stMetricDelta"] { font-size: 11px !important; }
.stDataFrame { border: 1px solid #181818 !important; border-radius: 3px !important; }
[data-testid="stExpander"] {
    background: #0d0d0d !important; border: 1px solid #181818 !important;
    border-radius: 3px !important;
}
div[data-testid="stVerticalBlock"] > div { gap: 0 !important; }

/* scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #0a0a0a; }
::-webkit-scrollbar-thumb { background: #222; border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: #A100FF; }

/* strip Streamlit chrome */
#MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }
[data-testid="stHeader"] { background: transparent !important; border: none !important; }
</style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def list_reports():
    return sorted(RESULTS_DIR.glob("report_*.json"), reverse=True)


def load_report(path: Path) -> dict:
    return json.loads(path.read_text())


def question_passes(row) -> bool:
    if not row.get("answerable", True):
        return "could not find" in str(row.get("answer", "")).lower()
    return all(
        (row.get(m) or 0) >= THRESHOLDS[m]
        for m in ("context_precision", "context_recall", "faithfulness", "answer_relevancy")
        if row.get(m) is not None
    )


def metric_card(label: str, score: float, threshold: float, desc: str) -> str:
    passed = score >= threshold
    cls    = "m-card-pass" if passed else "m-card-fail"
    badge  = (
        '<span class="m-badge-pass">PASS</span>' if passed
        else '<span class="m-badge-fail">FAIL</span>'
    )
    pct = min(score / 1.0 * 100, 100)
    return f"""
    <div class="m-card {cls}">
        <div class="m-label">{label}</div>
        <div class="m-score">{score:.3f}</div>
        <div class="m-bar-bg">
            <div class="m-bar-fill" style="width:{pct:.1f}%"></div>
        </div>
        <div class="m-footer">
            <span class="m-thr">threshold ≥ {threshold:.2f}</span>
            {badge}
        </div>
        <div class="m-desc">{desc}</div>
    </div>"""


def score_bar(value, threshold) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "<span style='color:#333;font-size:11px'>—</span>"
    v = float(value)
    pct   = min(v * 100, 100)
    color = "#00C851" if v >= threshold else "#FF3B30"
    return (
        f"<div class='sbar'>"
        f"<div class='sbar-bg'><div class='sbar-fill' style='width:{pct:.0f}%;background:{color}'></div></div>"
        f"<span class='sbar-val' style='color:{color}'>{v:.3f}</span>"
        f"</div>"
    )


# ── data ──────────────────────────────────────────────────────────────────────
reports = list_reports()
if not reports:
    st.error("No reports found in `results/`. Run `python run_eval.py` first.")
    st.stop()


# ── header ────────────────────────────────────────────────────────────────────
h_left, h_right = st.columns([3, 2])
with h_left:
    st.markdown("""
    <div class="acn-header" style="border-bottom:none;margin-bottom:0;padding-bottom:0;">
        <div class="acn-brand">
            <span class="acn-wordmark">Accenture</span>
            <span class="acn-chevron">&#8250;</span>
            <div class="acn-divider"></div>
            <span class="acn-title">RAG Quality Gate — P3</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with h_right:
    def fmt_label(p: Path) -> str:
        ts = p.stem.replace("report_", "")
        try:
            dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
            return dt.strftime("%Y-%m-%d  %H:%M")
        except Exception:
            return ts

    rc1, rc2 = st.columns([4, 1])
    with rc1:
        selected_idx = st.selectbox(
            "Run",
            range(len(reports)),
            format_func=lambda i: fmt_label(reports[i]),
            label_visibility="collapsed",
        )
    with rc2:
        if st.button("↺", help="Refresh reports", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

st.markdown("<div style='border-bottom:1px solid #181818;margin-bottom:2rem'></div>", unsafe_allow_html=True)

report      = load_report(reports[selected_idx])
aggregates  = report["aggregates"]
overall_pass = report["overall_pass"]
per_q       = report.get("per_question", [])
df          = pd.DataFrame(per_q)


# ── verdict ───────────────────────────────────────────────────────────────────
n_pass = sum(1 for m, v in aggregates.items() if v >= THRESHOLDS.get(m, 0))
n_fail = len(THRESHOLDS) - n_pass
v_cls  = "verdict-pass" if overall_pass else "verdict-fail"
v_word = "PASS" if overall_pass else "FAIL"
v_msg  = (
    "All metrics cleared — system ready to ship"
    if overall_pass
    else f"{n_fail} of {len(THRESHOLDS)} metrics below threshold"
)
st.markdown(f"""
<div class="verdict {v_cls}">
    <div class="v-left">
        <span class="v-eye">Overall verdict</span>
        <span class="v-msg">{v_msg}</span>
    </div>
    <span class="v-word">{v_word}</span>
</div>
""", unsafe_allow_html=True)


# ── metric strip ──────────────────────────────────────────────────────────────
st.markdown('<span class="sec">Evaluation Metrics</span>', unsafe_allow_html=True)
m_cols = st.columns(5, gap="small")
for i, (key, label) in enumerate(LABELS.items()):
    score = float(aggregates.get(key) or 0)
    with m_cols[i]:
        st.markdown(
            metric_card(label, score, THRESHOLDS[key], DESCRIPTIONS[key]),
            unsafe_allow_html=True,
        )


# ── run metadata ──────────────────────────────────────────────────────────────
st.markdown('<span class="sec">Run Information</span>', unsafe_allow_html=True)
info_cols = st.columns(5, gap="small")
n_total   = len(per_q)
n_ans     = sum(1 for r in per_q if r.get("answerable"))
run_at    = report.get("run_at", "")
run_str   = "—"
if run_at:
    try:
        run_str = datetime.fromisoformat(run_at.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        run_str = run_at

with info_cols[0]:
    st.metric("Questions", n_total)
with info_cols[1]:
    st.metric("Answerable", n_ans)
with info_cols[2]:
    st.metric("Unanswerable", n_total - n_ans)
with info_cols[3]:
    st.metric("Generator", report.get("eval_model", "—").split("/")[-1])
with info_cols[4]:
    st.metric("Judge", report.get("judge_model", "—").split("/")[-1])


# ── per-question table ────────────────────────────────────────────────────────
st.markdown('<span class="sec">Results by Question</span>', unsafe_allow_html=True)

df["_pass"] = df.apply(lambda r: question_passes(r.to_dict()), axis=1)
df["Status"] = df["_pass"].map({True: "PASS", False: "FAIL"})

f1, f2, f3 = st.columns([2, 2, 2], gap="small")
with f1:
    cats = sorted(df["category"].unique().tolist())
    sel_cats = st.multiselect("Category", cats, default=cats, label_visibility="collapsed",
                              placeholder="All categories")
with f2:
    sel_type = st.multiselect("Type", ["Answerable", "Unanswerable"],
                              default=["Answerable", "Unanswerable"],
                              label_visibility="collapsed", placeholder="All types")
with f3:
    sel_status = st.multiselect("Status", ["PASS", "FAIL"],
                                default=["PASS", "FAIL"],
                                label_visibility="collapsed", placeholder="All statuses")

fdf = df.copy()
if sel_cats:
    fdf = fdf[fdf["category"].isin(sel_cats)]
if "Answerable" not in sel_type:
    fdf = fdf[~fdf["answerable"]]
if "Unanswerable" not in sel_type:
    fdf = fdf[fdf["answerable"]]
if sel_status:
    fdf = fdf[fdf["Status"].isin(sel_status)]

def _fmt(v, thr=None):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    v = float(v)
    if thr is not None:
        return f"{'↑' if v >= thr else '↓'} {v:.3f}"
    return f"{v:.3f}"

tbl = fdf[[
    "id", "category", "question",
    "context_precision", "context_recall", "faithfulness", "answer_relevancy",
    "composite", "classification", "Status",
]].copy()
tbl.columns = ["ID", "Category", "Question", "Precision", "Recall", "Faithfulness", "Relevancy",
               "Composite", "Root Cause", "Status"]
for col, key in [("Precision","context_precision"), ("Recall","context_recall"),
                 ("Faithfulness","faithfulness"), ("Relevancy","answer_relevancy"), ("Composite", None)]:
    thr = THRESHOLDS.get(key) if key else None
    tbl[col] = tbl[col].apply(lambda x, t=thr: _fmt(x, t))

st.dataframe(
    tbl, use_container_width=True, hide_index=True, height=400,
    column_config={
        "ID":         st.column_config.NumberColumn(width="small"),
        "Category":   st.column_config.TextColumn(width="small"),
        "Question":   st.column_config.TextColumn(width="large"),
        "Precision":  st.column_config.TextColumn(width="small"),
        "Recall":     st.column_config.TextColumn(width="small"),
        "Faithfulness": st.column_config.TextColumn(width="small"),
        "Relevancy":  st.column_config.TextColumn(width="small"),
        "Composite":  st.column_config.TextColumn(width="small"),
        "Root Cause": st.column_config.TextColumn(width="medium"),
        "Status":     st.column_config.TextColumn(width="small"),
    },
)
st.markdown(
    f"<div style='font-size:10px;color:#333;margin-top:6px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase'>"
    f"{len(fdf)} of {len(df)} questions</div>",
    unsafe_allow_html=True,
)


# ── question drill-down ───────────────────────────────────────────────────────
st.markdown('<span class="sec">Question Detail</span>', unsafe_allow_html=True)

q_ids = fdf["id"].tolist() if not fdf.empty else df["id"].tolist()
if not q_ids:
    st.markdown("<div style='color:#333;font-size:13px'>No questions match current filters.</div>",
                unsafe_allow_html=True)
else:
    def q_label(qid):
        row = df[df["id"] == qid].iloc[0]
        cat = row["category"].upper()
        return f"Q{qid}  [{cat}]  {str(row['question'])[:72]}…"

    sel_id = st.selectbox("Question", q_ids, format_func=q_label, label_visibility="collapsed")
    row = df[df["id"] == sel_id].iloc[0].to_dict()

    d1, d2 = st.columns(2, gap="small")
    with d1:
        st.markdown(
            f"<div class='d-card'><div class='d-lbl'>Question</div>"
            f"<div class='d-txt'>{row['question']}</div></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='d-card'><div class='d-lbl'>Ground Truth</div>"
            f"<div class='d-txt' style='color:#00C851'>{row['ground_truth']}</div></div>",
            unsafe_allow_html=True,
        )
        cat_ans = row.get("answerable", True)
        cat_str = row.get("category", "")
        st.markdown(
            f"<div style='font-size:10px;color:#333;font-weight:700;letter-spacing:0.08em;"
            f"text-transform:uppercase;margin-top:6px'>"
            f"{cat_str} · {'Answerable' if cat_ans else 'Unanswerable'}</div>",
            unsafe_allow_html=True,
        )
    with d2:
        passed = question_passes(row)
        ans_color = "#00C851" if passed else "#FF3B30"
        st.markdown(
            f"<div class='d-card'><div class='d-lbl'>System Answer</div>"
            f"<div class='d-txt' style='color:{ans_color}'>{row.get('answer','—')}</div></div>",
            unsafe_allow_html=True,
        )
        reasoning = str(row.get("judge_reasoning", "")).strip()
        if reasoning:
            st.markdown(
                f"<div class='d-card'><div class='d-lbl'>Judge Reasoning</div>"
                f"<div class='d-txt' style='font-size:12px;color:#666'>{reasoning}</div></div>",
                unsafe_allow_html=True,
            )

    if row.get("answerable"):
        dm = st.columns(5, gap="small")
        for i, (key, label) in enumerate([
            ("context_precision","Precision"), ("context_recall","Recall"),
            ("faithfulness","Faithfulness"), ("answer_relevancy","Relevancy"),
        ]):
            val = row.get(key)
            thr = THRESHOLDS[key]
            with dm[i]:
                if val is not None and str(val) != "nan":
                    val = float(val)
                    st.metric(label, f"{val:.3f}", f"{val-thr:+.3f}",
                              delta_color="normal" if val >= thr else "inverse")
                else:
                    st.metric(label, "—")
        with dm[4]:
            jc = row.get("judge_correctness")
            if jc is not None and str(jc) != "nan":
                st.metric("Judge /5", int(jc), f"{int(jc)-3:+d} vs mid")
            else:
                st.metric("Judge /5", "—")

    contexts = row.get("contexts") or []
    if contexts:
        with st.expander(f"Retrieved chunks — {len(contexts)} total"):
            for i, ctx in enumerate(contexts, 1):
                st.markdown(
                    f"<div style='font-size:10px;font-weight:700;color:#333;letter-spacing:0.08em;"
                    f"text-transform:uppercase;margin-bottom:4px;margin-top:{'0' if i==1 else '12px'}'>Chunk {i}</div>",
                    unsafe_allow_html=True,
                )
                st.text_area(f"ctx_{i}", str(ctx), height=90, disabled=True, label_visibility="collapsed")


# ── worst-5 ───────────────────────────────────────────────────────────────────
st.markdown('<span class="sec">Worst Performers</span>', unsafe_allow_html=True)

ans_df = df[df["answerable"]].copy()
ans_df["composite"] = pd.to_numeric(ans_df["composite"], errors="coerce").fillna(0)
worst5 = ans_df.nsmallest(5, "composite")

if worst5.empty:
    st.markdown("<div style='color:#333;font-size:13px'>No answerable questions.</div>", unsafe_allow_html=True)
else:
    w_cols = st.columns(5, gap="small")
    for i, (_, r) in enumerate(worst5.iterrows()):
        comp = float(r.get("composite") or 0)
        clf  = str(r.get("classification") or "—").upper()
        q    = str(r["question"])
        with w_cols[i]:
            st.markdown(
                f"<div class='w-card'>"
                f"<div class='w-id'>Q{int(r['id'])} · {r['category'].upper()}</div>"
                f"<div class='w-q'>{q[:88]}{'…' if len(q)>88 else ''}</div>"
                f"<div class='w-score'>{comp:.3f}</div>"
                f"<div class='w-clf'>{clf}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )


# ── composite distribution ────────────────────────────────────────────────────
st.markdown('<span class="sec">Composite Score Distribution</span>', unsafe_allow_html=True)

plot_df = ans_df.sort_values("composite").reset_index(drop=True)
colors  = [
    "#00C851" if float(v or 0) >= 0.75 else
    "#FF9F0A" if float(v or 0) >= 0.60 else
    "#FF3B30"
    for v in plot_df["composite"]
]
fig = go.Figure(go.Bar(
    x=plot_df["id"].astype(str),
    y=pd.to_numeric(plot_df["composite"], errors="coerce"),
    marker_color=colors,
    marker_line_width=0,
    text=plot_df["composite"].apply(lambda x: f"{float(x or 0):.2f}"),
    textposition="outside",
    textfont={"size": 9, "color": "#444"},
    hovertemplate="Q%{x}<br>Composite: %{y:.3f}<extra></extra>",
))
fig.add_hline(
    y=0.75, line_dash="dot", line_color="#A100FF", line_width=1,
    annotation_text="0.75", annotation_font_color="#A100FF", annotation_font_size=10,
)
fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font_color="#555", height=280, margin=dict(t=24, b=32, l=36, r=16),
    xaxis={
        "title": {"text": "Question ID", "font": {"size": 10, "color": "#333"}},
        "gridcolor": "rgba(255,255,255,.03)", "tickfont": {"size": 9, "color": "#333"},
        "linecolor": "#181818",
    },
    yaxis={
        "title": {"text": "Score", "font": {"size": 10, "color": "#333"}},
        "gridcolor": "rgba(255,255,255,.04)", "tickfont": {"size": 9, "color": "#333"},
        "range": [0, 1.12], "linecolor": "#181818",
    },
    showlegend=False,
    bargap=0.35,
)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
