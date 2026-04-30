from pathlib import Path
from datetime import datetime
from uuid import uuid4

import pandas as pd
import streamlit as st

from src.anomaly_review_studio.io import load_csv_data, load_demo_data, validate_dataframe
from src.anomaly_review_studio.profiling import profile_dataframe
from src.anomaly_review_studio.reporting import build_markdown_report, build_pdf_report, build_rules_payload
from src.anomaly_review_studio.rules import evaluate_rules, generate_rules, Rule
from src.anomaly_review_studio.store import SupabaseStore
from src.anomaly_review_studio.workflow import DEFAULT_QUALITY_GATE_RULES, compute_baseline_delta, enrich_rule_results, evaluate_quality_gates

APP_TITLE = "Anomaly Review Studio"
APP_SUBTITLE = "Upload a CSV, inspect data quality, and generate review-ready rules."
DEMO_FILE = Path(__file__).parent / "data" / "demo_anomaly_review.csv"

st.set_page_config(page_title=APP_TITLE, page_icon="🧭", layout="wide")

# Initialize session state for multi-upload tracking and custom rules
if "upload_history" not in st.session_state:
    st.session_state.upload_history = []
if "custom_rules" not in st.session_state:
    st.session_state.custom_rules = []
if "issue_queue_cache" not in st.session_state:
    st.session_state.issue_queue_cache = []
if "role_overrides" not in st.session_state:
    st.session_state.role_overrides = {}
if "severity_policy" not in st.session_state:
    st.session_state.severity_policy = {
        "identifier": 1,
        "contact": 1,
        "financial": 1,
        "compliance": 1,
        "operational": 0,
    }
if "quality_gate_rules" not in st.session_state:
    st.session_state.quality_gate_rules = dict(DEFAULT_QUALITY_GATE_RULES)
elif (
    st.session_state.quality_gate_rules.get("max_high_violations") == 0
    and float(st.session_state.quality_gate_rules.get("min_quality_score", 0)) == 80.0
    and float(st.session_state.quality_gate_rules.get("max_critical_missing_pct", 0)) == 5.0
    and bool(st.session_state.quality_gate_rules.get("warn_only", True))
):
    st.session_state.quality_gate_rules = dict(DEFAULT_QUALITY_GATE_RULES)
if "diff_baseline_policy" not in st.session_state:
    st.session_state.diff_baseline_policy = "most_recent_same_source"
if "required_columns_input" not in st.session_state:
    st.session_state.required_columns_input = ""

st.markdown(
    """
    <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(88, 166, 255, 0.1), transparent 24%),
                linear-gradient(180deg, #0f172a 0%, #111827 100%);
        }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        .hero {
            padding: 1.4rem 1.5rem;
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 18px;
            background: rgba(30, 41, 59, 0.82);
            backdrop-filter: blur(10px);
            box-shadow: 0 18px 45px rgba(0, 0, 0, 0.35);
            margin-bottom: 1rem;
        }
        .hero h1 {
            margin: 0;
            font-size: 2rem;
            color: #f8fafc;
        }
        .hero p {
            margin: 0.35rem 0 0;
            color: #cbd5e1;
            font-size: 1rem;
            line-height: 1.5;
        }
        .kpi-card {
            padding: 1rem 1rem 0.85rem;
            border-radius: 16px;
            border: 1px solid rgba(148, 163, 184, 0.2);
            background: rgba(30, 41, 59, 0.8);
            box-shadow: 0 10px 24px rgba(0, 0, 0, 0.3);
        }
        .kpi-label {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #94a3b8;
            margin-bottom: 0.2rem;
        }
        .kpi-value {
            font-size: 1.7rem;
            font-weight: 700;
            color: #f8fafc;
            line-height: 1.1;
        }
        .kpi-subtext {
            font-size: 0.88rem;
            color: #cbd5e1;
            margin-top: 0.25rem;
        }
        .section-card {
            padding: 1rem 1.1rem;
            border-radius: 18px;
            background: rgba(30, 41, 59, 0.75);
            border: 1px solid rgba(148, 163, 184, 0.2);
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.28);
        }
        .summary-list li {
            margin-bottom: 0.45rem;
        }
        div[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
            border-right: 1px solid rgba(148, 163, 184, 0.2);
        }
        div[data-testid="stSidebar"] .stButton > button {
            width: 100%;
            white-space: nowrap;
            min-height: 2.75rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def _metric_cards(summary: dict) -> None:
    cols = st.columns(4)
    cards = [
        ("Rows", summary["rows"], f"Source: {summary['source_label']}"),
        ("Columns", summary["columns"], f"Required: {summary['required_columns_count']}"),
        ("Missing cells", summary["missing_cells"], f"Completeness: {summary['completeness_pct']}%"),
        ("Rule violations", summary["violations"], f"Quality score: {summary['quality_score']}"),
    ]
    for col, (label, value, subtext) in zip(cols, cards):
        col.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
                <div class="kpi-subtext">{subtext}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_column_summary(profile_rows: list[dict]) -> None:
    if not profile_rows:
        st.info("No columns available for profiling.")
        return
    display_rows = [
        {
            "column": row["column"],
            "dtype": row["dtype"],
            "semantic_type": row.get("semantic_type") or row.get("inferred_semantics", "unknown"),
            "missing_count": row["missing_count"],
            "missing_pct": row["missing_pct"],
            "unique_count": row["unique_count"],
        }
        for row in profile_rows
    ]
    st.dataframe(
        display_rows,
        use_container_width=True,
        hide_index=True,
    )


def _render_rule_table(rule_results: list[dict]) -> None:
    if not rule_results:
        st.info("No rules were generated for this dataset.")
        return
    display_rows = []
    for row in rule_results:
        display_rows.append(
            {
                "column": row["column"],
                "rule_type": row["rule_type"],
                "severity": row.get("effective_severity", row["severity"]).upper(),
                "violations": row["violations"],
                "pass_rate_pct": row["pass_rate_pct"],
                "status": row.get("status", "new"),
                "delta": row.get("baseline_delta", "unchanged"),
                "description": row["description"],
            }
        )
    st.dataframe(display_rows, use_container_width=True, hide_index=True)


def _render_charts(profile_rows: list[dict]) -> None:
    if not profile_rows:
        return
    chart_df = pd.DataFrame(
        {
            "column": [row["column"] for row in profile_rows],
            "missing_pct": [row["missing_pct"] for row in profile_rows],
            "unique_count": [row["unique_count"] for row in profile_rows],
        }
    )
    st.subheader("Column signals")
    left, right = st.columns(2)
    with left:
        st.caption("Missing values (%) by column")
        st.bar_chart(chart_df.set_index("column")["missing_pct"])
    with right:
        st.caption("Unique values by column")
        st.bar_chart(chart_df.set_index("column")["unique_count"])


def _render_summary_panel(summary: dict, top_findings: list[str]) -> None:
    issue_count = len(top_findings)
    summary_text = "Your dataset is clean enough to review quickly." if summary["quality_score"] >= 90 else "Your dataset needs targeted fixes before downstream use."
    st.markdown(
        f"""
        <div class="hero">
            <h1>Anomaly Review Studio</h1>
            <p>{summary_text} The app detected <strong>{summary['violations']}</strong> rule violations across <strong>{summary['columns']}</strong> columns and surfaced <strong>{issue_count}</strong> review priorities.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if top_findings:
        with st.container(border=True):
            st.markdown("### Summary")
            st.markdown("<ul class='summary-list'>" + "".join(f"<li>{item}</li>" for item in top_findings) + "</ul>", unsafe_allow_html=True)


def _render_flagged_rows(dataframe: pd.DataFrame, rule_result: dict) -> None:
    """Display rows that violated a specific rule."""
    flagged_indices = rule_result.get("flagged_rows", [])
    if not flagged_indices:
        st.info("No violations for this rule.")
        return
    
    flagged_df = dataframe.iloc[flagged_indices].reset_index(drop=True)
    st.markdown(f"**Flagged rows** ({len(flagged_indices)} violations)")
    st.dataframe(flagged_df, use_container_width=True, hide_index=True)


def _build_violations_csv(dataframe: pd.DataFrame, rule_results: list[dict]) -> bytes:
    """Build CSV of only rows that violated at least one rule."""
    violation_indices = set()
    for result in rule_results:
        violation_indices.update(result.get("flagged_rows", []))
    
    if not violation_indices:
        return b"No violations found\n"
    
    violations_df = dataframe.iloc[sorted(violation_indices)].reset_index(drop=True)
    return violations_df.to_csv(index=False).encode()


def _build_local_issue_queue(upload_history: list[dict]) -> list[dict]:
    latest_by_finding = {}
    for run in upload_history:
        for finding in run.get("findings", []):
            key = finding["finding_id"]
            existing = latest_by_finding.get(key)
            if existing is None or run["timestamp"] >= existing["timestamp"]:
                latest_by_finding[key] = {
                    **finding,
                    "source_label": run.get("source", ""),
                    "timestamp": run["timestamp"],
                }
    return list(latest_by_finding.values())


with st.sidebar:
    st.header("Input")
    if st.button("Reset session", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    use_demo = st.button("Load demo dataset", use_container_width=True)
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    expected_columns_input = st.text_input(
        "Required columns (comma separated)",
        key="required_columns_input",
        help="Optional. If provided, checks only whether these column names exist in the uploaded dataset.",
    )
    st.caption("Leave blank to accept any dataset schema. If set, this validates column presence only.")
    st.divider()
    st.markdown("### Workflow Settings")
    st.caption("Supabase: set `SUPABASE_URL` and `SUPABASE_KEY` env vars to persist runs/findings.")
    with st.expander("Severity policy", expanded=False):
        st.session_state.severity_policy["identifier"] = st.selectbox("Identifier weight", [0, 1], index=1 if st.session_state.severity_policy["identifier"] else 0)
        st.session_state.severity_policy["contact"] = st.selectbox("Contact weight", [0, 1], index=1 if st.session_state.severity_policy["contact"] else 0)
        st.session_state.severity_policy["financial"] = st.selectbox("Financial weight", [0, 1], index=1 if st.session_state.severity_policy["financial"] else 0)
        st.session_state.severity_policy["compliance"] = st.selectbox("Compliance weight", [0, 1], index=1 if st.session_state.severity_policy["compliance"] else 0)
        st.session_state.severity_policy["operational"] = st.selectbox("Operational weight", [0, 1], index=1 if st.session_state.severity_policy["operational"] else 0)
    with st.expander("Quality gates", expanded=False):
        st.session_state.quality_gate_rules["max_high_violations"] = st.number_input(
            "Max high-severity violations",
            min_value=0,
            value=int(st.session_state.quality_gate_rules["max_high_violations"]),
        )
        st.session_state.quality_gate_rules["min_quality_score"] = st.number_input(
            "Min quality score",
            min_value=0.0,
            max_value=100.0,
            value=float(st.session_state.quality_gate_rules["min_quality_score"]),
            step=1.0,
        )
        st.session_state.quality_gate_rules["max_critical_missing_pct"] = st.number_input(
            "Max critical-column missing %",
            min_value=0.0,
            max_value=100.0,
            value=float(st.session_state.quality_gate_rules["max_critical_missing_pct"]),
            step=0.5,
        )
        st.session_state.quality_gate_rules["warn_only"] = st.toggle(
            "Warn only (do not block exports)",
            value=bool(st.session_state.quality_gate_rules["warn_only"]),
        )
    
    # Severity filter
    st.markdown("### Rule Filters")
    severity_filter = st.multiselect(
        "Filter by severity",
        options=["high", "medium", "low"],
        default=["high", "medium", "low"],
        help="Show only rules matching selected severity levels.",
    )
    
    # Custom rule builder
    with st.expander("➕ Add custom rule", expanded=False):
        rule_column = st.text_input("Column name", placeholder="e.g., age", key="rule_col_input")
        rule_type = st.selectbox("Rule type", ["not_null", "unique", "range", "allowed_values", "format"], key="rule_type_select")
        rule_severity = st.selectbox("Severity", ["high", "medium", "low"], key="rule_sev_select")
        
        if rule_type == "range":
            rule_min = st.number_input("Min value", key="rule_min_input")
            rule_max = st.number_input("Max value", key="rule_max_input")
            rule_expected = None
        elif rule_type == "allowed_values":
            rule_expected = st.text_input("Allowed values (pipe-separated)", placeholder="val1|val2|val3", key="rule_allowed_input")
            rule_min, rule_max = None, None
        elif rule_type == "format":
            rule_expected = st.text_input("Regex pattern", placeholder=r"^\d{5}$", key="rule_format_input")
            rule_min, rule_max = None, None
        else:
            rule_expected = None
            rule_min, rule_max = None, None
        
        if st.button("Add rule", key="add_rule_btn"):
            if rule_column:
                new_rule = Rule(
                    column=rule_column.strip().lower().replace(" ", "_"),
                    rule_type=rule_type,
                    description=f"Custom rule: {rule_type} on {rule_column}",
                    severity=rule_severity,
                    expected_value=rule_expected,
                    min_value=rule_min if rule_type == "range" else None,
                    max_value=rule_max if rule_type == "range" else None,
                )
                st.session_state.custom_rules.append(new_rule)
                st.success(f"Added custom rule for {rule_column}!")
            else:
                st.error("Enter a column name")
    
    st.divider()
    st.markdown("### What it does")
    st.markdown(
        "- Profiles columns\n"
        "- Flags nulls, outliers, and inconsistent formats\n"
        "- Generates human-readable data rules\n"
        "- Exports JSON, Markdown, and PDF reports"
    )

if use_demo:
    dataframe = load_demo_data(DEMO_FILE)
    source_label = "demo dataset"
elif uploaded_file is not None:
    try:
        dataframe = load_csv_data(uploaded_file)
        source_label = uploaded_file.name
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
else:
    st.info("Load the bundled demo dataset or upload a CSV to begin.")
    st.stop()

expected_columns = [item.strip().lower().replace(" ", "_") for item in expected_columns_input.split(",") if item.strip()]
validation_error = validate_dataframe(dataframe, expected_columns=expected_columns)
if validation_error:
    st.error(validation_error)
    st.stop()

profile = profile_dataframe(dataframe)
rules = generate_rules(dataframe, profile)

# Add user-defined custom rules
if st.session_state.custom_rules:
    rules.extend(st.session_state.custom_rules)

rule_results, violation_summary = evaluate_rules(dataframe, rules)

store = SupabaseStore()
run_id = str(uuid4())
profile_records = profile.as_records()
enriched_results = enrich_rule_results(
    source_label=source_label,
    profile_records=profile_records,
    rule_results=rule_results,
    severity_policy=st.session_state.severity_policy,
    role_overrides=st.session_state.role_overrides,
)
for item in enriched_results:
    item["run_id"] = run_id

baseline_results = []
baseline_run_id = None
if store.enabled:
    latest_run = store.fetch_latest_run_for_source(source_label)
    if latest_run and latest_run.get("run_id"):
        baseline_run_id = latest_run["run_id"]
        baseline_results = store.fetch_findings_for_run(baseline_run_id)
elif st.session_state.upload_history:
    for past_run in reversed(st.session_state.upload_history):
        if past_run.get("source") == source_label and past_run.get("findings"):
            baseline_run_id = past_run.get("run_id")
            baseline_results = past_run.get("findings", [])
            break

enriched_results, baseline_summary_obj = compute_baseline_delta(enriched_results, baseline_results, baseline_run_id)
baseline_summary = baseline_summary_obj.as_dict()
quality_score_preview = round(
    100.0 * (1 - min(violation_summary["total_violations"] / max(len(dataframe), 1), 1.0)),
    2,
) if len(dataframe) else 100.0
gate_summary = evaluate_quality_gates(
    results=enriched_results,
    quality_score=quality_score_preview,
    profile_records=profile_records,
    rules=st.session_state.quality_gate_rules,
)

# Apply severity filter based on effective severity
filtered_rule_results = [r for r in enriched_results if r["effective_severity"] in severity_filter]

# Track upload history for multi-upload trend view
payload = build_rules_payload(
    source_name=source_label,
    dataframe=dataframe,
    profile=profile,
    rules=rules,
    rule_results=enriched_results,
    violation_summary=violation_summary,
    baseline_summary=baseline_summary,
    gate_summary=gate_summary,
    workflow_config={
        "severity_policy": st.session_state.severity_policy,
        "column_role_overrides": st.session_state.role_overrides,
        "quality_gate_rules": st.session_state.quality_gate_rules,
        "diff_baseline_policy": st.session_state.diff_baseline_policy,
    },
)

# Store in session history
st.session_state.upload_history.append({
    "run_id": run_id,
    "timestamp": datetime.now().isoformat(),
    "source": source_label,
    "rows": payload["dataset_summary"]["rows"],
    "columns": payload["dataset_summary"]["columns"],
    "violations": payload["quality_summary"]["total_violations"],
    "quality_score": payload["quality_summary"]["quality_score"],
    "findings": enriched_results,
})

if store.enabled:
    stored_run_id = store.save_run(
        {
            "run_id": run_id,
            "source_label": source_label,
            "rows": payload["dataset_summary"]["rows"],
            "columns": payload["dataset_summary"]["columns"],
            "missing_cells": payload["dataset_summary"]["missing_cells"],
            "total_violations": payload["quality_summary"]["total_violations"],
            "quality_score": payload["quality_summary"]["quality_score"],
            "baseline_run_id": baseline_run_id,
            "baseline_summary": baseline_summary,
            "workflow_config": payload["workflow_config"],
        }
    )
    if stored_run_id:
        run_id = stored_run_id
        for item in enriched_results:
            item["run_id"] = run_id
    store.save_findings(
        [
            {
                key: value
                for key, value in item.items()
                if key not in {"flagged_rows"}
            }
            for item in enriched_results
        ]
    )
    store.save_gate_result(
        {
            "run_id": run_id,
            "source_label": source_label,
            "gate_summary": gate_summary,
            "status": gate_summary["status"],
        }
    )

markdown_report = build_markdown_report(payload)
pdf_bytes = build_pdf_report(payload)
top_findings = []
sorted_by_missing = sorted(profile_records, key=lambda row: row["missing_pct"], reverse=True)
if sorted_by_missing and sorted_by_missing[0]["missing_pct"] > 0:
    top_findings.append(
        f"{sorted_by_missing[0]['column']} has the highest missing rate at {sorted_by_missing[0]['missing_pct']}%."
    )

most_violated = sorted(enriched_results, key=lambda row: row["violations"], reverse=True)
if most_violated and most_violated[0]["violations"] > 0:
    top_findings.append(
        f"{most_violated[0]['column']} [{most_violated[0]['rule_type']}] produced {most_violated[0]['violations']} violations."
    )

summary = {
    "source_label": source_label,
    "rows": payload["dataset_summary"]["rows"],
    "columns": payload["dataset_summary"]["columns"],
    "missing_cells": payload["dataset_summary"]["missing_cells"],
    "violations": payload["quality_summary"]["total_violations"],
    "quality_score": payload["quality_summary"]["quality_score"],
    "completeness_pct": round(100 - (payload["dataset_summary"]["missing_cells"] / max(payload["dataset_summary"]["rows"] * payload["dataset_summary"]["columns"], 1) * 100), 1),
    "required_columns_count": len(expected_columns),
}

_render_summary_panel(summary, top_findings)
_metric_cards(summary)

st.markdown(f"**Source:** {source_label}")

overview_tab, columns_tab, rules_tab, queue_tab, analytics_tab, report_tab = st.tabs(
    ["Overview", "Columns", "Rules", "Issue Queue", "Trends", "Report"]
)

with overview_tab:
    baseline_summary_view = payload["baseline_summary"] if payload["baseline_summary"] else {}
    if baseline_summary_view:
        st.markdown("#### What changed since baseline")
        bc1, bc2, bc3, bc4 = st.columns(4)
        bc1.metric("New", baseline_summary_view.get("new_findings", 0))
        bc2.metric("Resolved", baseline_summary_view.get("resolved_findings", 0))
        bc3.metric("Worsened", baseline_summary_view.get("worsened_findings", 0))
        bc4.metric("Improved", baseline_summary_view.get("improved_findings", 0))
    gate = payload["gate_summary"] if payload["gate_summary"] else {}
    if gate:
        if gate["passed"]:
            st.success("Quality gate: PASS")
        else:
            if gate.get("warn_only", True):
                st.info("Quality gate: WARN (advisory only, thresholds not fully met)")
            else:
                st.warning("Quality gate: WARN (thresholds not fully met)")

    _render_charts(profile_records)

    left, right = st.columns([1.2, 0.8])
    with left:
        st.markdown("#### Review priorities")
        if top_findings:
            st.markdown("\n".join([f"- {item}" for item in top_findings]))
        else:
            st.success("No major quality risks were detected in this dataset.")
    with right:
        st.markdown("#### Dataset snapshot")
        st.write(
            {
                "rows": summary["rows"],
                "columns": summary["columns"],
                "missing_cells": summary["missing_cells"],
                "quality_score": summary["quality_score"],
            }
        )

with columns_tab:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Column profile")
    _render_column_summary(profile_records)
    st.markdown("</div>", unsafe_allow_html=True)

with rules_tab:
    left, right = st.columns([1.05, 0.95])
    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Suggested rules")
        
        # Violations CSV download
        violations_csv = _build_violations_csv(dataframe, filtered_rule_results)
        st.download_button(
            label="📥 Download violations CSV",
            data=violations_csv,
            file_name=f"violations_{source_label.split('.')[0]}.csv",
            mime="text/csv",
        )
        
        _render_rule_table(filtered_rule_results)
        
        # Show flagged rows for each rule with violations
        st.markdown("---")
        st.markdown("### Drill-down: Flagged rows")
        for i, result in enumerate(filtered_rule_results):
            if result.get("violations", 0) > 0:
                with st.expander(f"🚩 {result['column']} [{result['rule_type']}] — {result['violations']} violations", expanded=False):
                    _render_flagged_rows(dataframe, result)
                    guidance = result.get("guidance", {})
                    if guidance:
                        st.markdown("**Fix checklist**")
                        checklist_text = (
                            f"- Why it matters: {guidance.get('why', '')}\n"
                            f"- Likely root cause: {guidance.get('root_cause', '')}\n"
                            f"- Steps: {guidance.get('steps', '')}"
                        )
                        st.code(checklist_text, language="markdown")
                        st.download_button(
                            label="Download fix checklist",
                            data=checklist_text,
                            file_name=f"fix_checklist_{result['column']}_{result['rule_type']}.md",
                            mime="text/markdown",
                            key=f"fix_checklist_{i}",
                        )
        
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Rule interpretation")
        if payload["rule_explanations"]:
            for item in payload["rule_explanations"][:5]:
                st.markdown(f"- **{item['column']}**: {item['explanation']}")
        st.markdown("</div>", unsafe_allow_html=True)

with queue_tab:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Issue queue")
    if store.enabled:
        queue_rows = store.fetch_issue_queue(source_label)
    else:
        queue_rows = _build_local_issue_queue(st.session_state.upload_history)

    if not queue_rows:
        st.info("No tracked findings yet. Run at least one dataset review.")
    else:
        queue_df = pd.DataFrame(queue_rows)
        if "effective_severity" not in queue_df.columns and "severity" in queue_df.columns:
            queue_df["effective_severity"] = queue_df["severity"]
        if "source_label" not in queue_df.columns:
            queue_df["source_label"] = source_label
        status_options = ["new", "acknowledged", "resolved"]
        status_filter = st.multiselect("Status", options=status_options, default=status_options, key="queue_status_filter")
        severity_options = ["high", "medium", "low"]
        severity_filter_queue = st.multiselect("Severity", options=severity_options, default=severity_options, key="queue_sev_filter")
        source_filter = st.multiselect("Source", options=sorted(queue_df["source_label"].dropna().unique().tolist()), default=sorted(queue_df["source_label"].dropna().unique().tolist()))
        new_only = st.toggle("New since baseline only", value=False, key="queue_new_only")

        filtered_queue = queue_df[
            queue_df["status"].isin(status_filter)
            & queue_df["effective_severity"].isin(severity_filter_queue)
            & queue_df["source_label"].isin(source_filter)
        ]
        if new_only and "baseline_delta" in filtered_queue.columns:
            filtered_queue = filtered_queue[filtered_queue["baseline_delta"] == "new"]

        display_cols = [
            "finding_id",
            "source_label",
            "column",
            "rule_type",
            "effective_severity",
            "violations",
            "status",
            "owner",
            "notes",
            "baseline_delta",
            "updated_at",
        ]
        existing_cols = [col for col in display_cols if col in filtered_queue.columns]
        st.dataframe(filtered_queue[existing_cols], use_container_width=True, hide_index=True)

        finding_options = filtered_queue["finding_id"].dropna().tolist()
        if finding_options:
            selected_finding = st.selectbox("Select finding to update", options=finding_options)
            row = filtered_queue[filtered_queue["finding_id"] == selected_finding].iloc[0].to_dict()
            new_status = st.selectbox("New status", options=status_options, index=status_options.index(row.get("status", "new")))
            owner_value = st.text_input("Owner", value=row.get("owner", ""))
            notes_value = st.text_area("Notes", value=row.get("notes", ""))
            if st.button("Update finding"):
                updates = {"status": new_status, "owner": owner_value, "notes": notes_value}
                if store.enabled:
                    store.update_finding(selected_finding, updates)
                    store.save_status_event(
                        {
                            "finding_id": selected_finding,
                            "source_label": row.get("source_label", source_label),
                            "status": new_status,
                            "owner": owner_value,
                            "notes": notes_value,
                        }
                    )
                else:
                    for run_item in st.session_state.upload_history:
                        for finding in run_item.get("findings", []):
                            if finding["finding_id"] == selected_finding:
                                finding.update(updates)
                st.success("Finding updated.")
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with analytics_tab:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Upload trend analytics")
    
    if st.session_state.upload_history:
        history_df = pd.DataFrame(st.session_state.upload_history)
        if "findings" in history_df.columns:
            history_df = history_df.drop(columns=["findings"])
        history_df["timestamp"] = pd.to_datetime(history_df["timestamp"])
        history_df = history_df.sort_values("timestamp", ascending=False).reset_index(drop=True)
        
        # Display trend
        st.markdown("**Upload history** (most recent first)")
        st.dataframe(history_df, use_container_width=True, hide_index=True)
        
        # Show trend charts
        left, right = st.columns(2)
        with left:
            st.caption("Quality score trend")
            trend_chart = history_df[["timestamp", "quality_score"]].sort_values("timestamp").set_index("timestamp")
            st.line_chart(trend_chart)
        with right:
            st.caption("Violations trend")
            violations_chart = history_df[["timestamp", "violations"]].sort_values("timestamp").set_index("timestamp")
            st.line_chart(violations_chart)
        
        # Summary stats
        col1, col2, col3 = st.columns(3)
        with col1:
            avg_quality = history_df["quality_score"].mean()
            st.metric("Avg quality score", f"{avg_quality:.1f}")
        with col2:
            total_uploads = len(history_df)
            st.metric("Total uploads", total_uploads)
        with col3:
            best_quality = history_df["quality_score"].max()
            st.metric("Best score", f"{best_quality:.1f}")
    else:
        st.info("Upload multiple datasets to see trends over time.")
    
    st.markdown("</div>", unsafe_allow_html=True)

with report_tab:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Narrative report")
    baseline = payload["baseline_summary"] if payload["baseline_summary"] else {}
    gate = payload["gate_summary"] if payload["gate_summary"] else {}
    if baseline:
        st.markdown(
            f"**Since baseline** — New: {baseline.get('new_findings', 0)}, "
            f"Resolved: {baseline.get('resolved_findings', 0)}, "
            f"Worsened: {baseline.get('worsened_findings', 0)}, "
            f"Improved: {baseline.get('improved_findings', 0)}"
        )
    if gate:
        st.markdown(f"**Quality gate** — Status: `{gate.get('status', 'unknown')}`, Warn-only: `{gate.get('warn_only', True)}`")
    st.markdown(markdown_report)
    st.markdown("---")
    st.subheader("Downloads")
    st.download_button(
        label="Download JSON report",
        data=payload.to_json(),
        file_name="anomaly_review_report.json",
        mime="application/json",
    )
    st.download_button(
        label="Download Markdown report",
        data=markdown_report,
        file_name="anomaly_review_report.md",
        mime="text/markdown",
    )
    st.download_button(
        label="Download PDF report",
        data=pdf_bytes,
        file_name="anomaly_review_report.pdf",
        mime="application/pdf",
    )
    st.markdown("</div>", unsafe_allow_html=True)
