from __future__ import annotations

import io
import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .llm import enrich_rule_descriptions
from .profiling import DatasetProfile
from .rules import Rule


class RulesPayload:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def to_json(self) -> str:
        return json.dumps(self.payload, indent=2, default=str)

    def __getitem__(self, item: str) -> Any:
        return self.payload[item]


def build_rules_payload(
    source_name: str,
    dataframe,
    profile: DatasetProfile,
    rules: list[Rule],
    rule_results: list[dict[str, Any]],
    violation_summary: dict[str, int],
    baseline_summary: dict[str, Any] | None = None,
    gate_summary: dict[str, Any] | None = None,
    workflow_config: dict[str, Any] | None = None,
) -> RulesPayload:
    dataset_summary = {
        "rows": int(len(dataframe)),
        "columns": int(len(dataframe.columns)),
        "missing_cells": int(profile.total_missing),
    }
    quality_summary = {
        "total_rules": int(violation_summary["rule_count"]),
        "total_violations": int(violation_summary["total_violations"]),
        "quality_score": round(_quality_score(len(dataframe), violation_summary["total_violations"]), 2),
    }
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_name": source_name,
        "dataset_summary": dataset_summary,
        "quality_summary": quality_summary,
        "column_profile": profile.as_records(),
        "rules": [asdict(rule) if hasattr(rule, "__dataclass_fields__") else rule.as_dict() for rule in rules],
        "rule_results": rule_results,
        "data_dictionary": _build_data_dictionary(profile),
        "baseline_summary": baseline_summary or {},
        "gate_summary": gate_summary or {},
        "workflow_config": workflow_config or {},
    }
    payload["rule_explanations"] = enrich_rule_descriptions(payload["rules"], payload["data_dictionary"])
    return RulesPayload(payload)


def build_markdown_report(payload: RulesPayload) -> str:
    data = payload.payload
    lines = [
        f"# Anomaly Review Studio — Summary",
        f"",
        f"**Source:** {data['source_name']}",
        f"",
        f"### Key metrics",
        f"- Rows: {data['dataset_summary']['rows']}",
        f"- Columns: {data['dataset_summary']['columns']}",
        f"- Missing cells: {data['dataset_summary']['missing_cells']}",
        f"- Quality score: {data['quality_summary']['quality_score']} (100 = perfect)",
        f"",
    ]
    if data.get("baseline_summary"):
        baseline = data["baseline_summary"]
        lines.extend(
            [
                "### What changed since baseline",
                f"- New findings: {baseline.get('new_findings', 0)}",
                f"- Resolved findings: {baseline.get('resolved_findings', 0)}",
                f"- Worsened findings: {baseline.get('worsened_findings', 0)}",
                f"- Improved findings: {baseline.get('improved_findings', 0)}",
                "",
            ]
        )
    if data.get("gate_summary"):
        gate = data["gate_summary"]
        lines.extend(
            [
                "### Quality gate status",
                f"- Status: {gate.get('status', 'unknown')}",
                f"- Warn only: {gate.get('warn_only', True)}",
                "",
            ]
        )
    lines.extend(
        [
        f"### Top recommendations",
    ])
    # concise top recommendations: show highest-violations and highest-missing
    rule_results_sorted = sorted(data.get("rule_results", []), key=lambda r: r.get("violations", 0), reverse=True)
    if rule_results_sorted:
        top = rule_results_sorted[0]
        lines.append(f"- Fix {top['column']} ({top['rule_type']}) — {top['violations']} violations detected.")
    missing_sorted = sorted(data.get("column_profile", []), key=lambda c: c.get("missing_pct", 0), reverse=True)
    if missing_sorted and missing_sorted[0]["missing_pct"] > 0:
        lines.append(f"- Address missing values in {missing_sorted[0]['column']} ({missing_sorted[0]['missing_pct']}% missing).")
    lines.extend(["", "## Suggested Rules"]) 
    for rule in data["rules"]:
        lines.append(f"- {rule['column']} [{rule['rule_type']}]: {rule['description']}")
    lines.extend([
        f"",
        f"## Data Dictionary",
    ])
    for entry in data["data_dictionary"]:
        lines.append(f"- **{entry['column']}**: {entry['description']}")
    lines.extend(["", "## Rule Results"])
    for result in data["rule_results"]:
        lines.append(
            f"- {result['column']} [{result['rule_type']}]: {result['violations']} violations, "
            f"pass rate {result['pass_rate_pct']}%, severity {result.get('effective_severity', result.get('severity', 'medium'))}"
        )
    lines.extend(["", "## Remediation guidance"])
    for result in data["rule_results"]:
        guidance = result.get("guidance")
        if not guidance:
            continue
        lines.append(f"- {result['column']} [{result['rule_type']}]: {guidance.get('steps', '')}")
    lines.extend(["", "## Rule Explanations"])
    for item in data.get("rule_explanations", []):
        lines.append(f"- {item['column']} [{item['rule_type']}]: {item['explanation']}")
    return "\n".join(lines)


def build_pdf_report(payload: RulesPayload) -> bytes:
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [Paragraph("Anomaly Review Studio Report", styles["Title"]), Spacer(1, 12)]
    data = payload.payload
    # Header info
    story.append(Paragraph(f"Source: {data['source_name']}", styles["BodyText"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Quality score: <strong>{data['quality_summary']['quality_score']}</strong>", styles["Heading2"]))
    story.append(Spacer(1, 12))
    baseline = data.get("baseline_summary", {})
    if baseline:
        story.append(Paragraph("What changed since baseline", styles["Heading3"]))
        story.append(
            Paragraph(
                f"New: {baseline.get('new_findings', 0)} | Resolved: {baseline.get('resolved_findings', 0)} | "
                f"Worsened: {baseline.get('worsened_findings', 0)} | Improved: {baseline.get('improved_findings', 0)}",
                styles["BodyText"],
            )
        )
        story.append(Spacer(1, 8))

    # Top rule violations table
    table_data = [["Column", "Rule", "Severity", "Violations"]]
    for result in data.get("rule_results", [])[:10]:
        table_data.append(
            [
                result.get("column", ""),
                result.get("rule_type", ""),
                str(result.get("effective_severity", result.get("severity", "medium"))).upper(),
                str(result.get("violations", 0)),
            ]
        )
    table = Table(table_data, hAlign="LEFT", colWidths=[150, 140, 110, 60])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e6eef8")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
            ]
        )
    )
    story.append(Paragraph("Top rule violations", styles["Heading3"]))
    story.append(Spacer(1, 6))
    story.append(table)
    story.append(Spacer(1, 12))

    # Data dictionary sample
    story.append(Paragraph("Data dictionary (sample)", styles["Heading3"]))
    dd = data.get("data_dictionary", [])[:10]
    for entry in dd:
        story.append(Paragraph(f"<b>{entry.get('column')}</b>: {entry.get('description')}", styles["BodyText"]))
        story.append(Spacer(1, 4))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Remediation guidance (sample)", styles["Heading3"]))
    for item in data.get("rule_results", [])[:5]:
        guidance = item.get("guidance")
        if not guidance:
            continue
        story.append(Paragraph(f"<b>{item.get('column')} [{item.get('rule_type')}]</b>: {guidance.get('steps', '')}", styles["BodyText"]))
        story.append(Spacer(1, 4))
    document.build(story)
    return buffer.getvalue()


def _quality_score(row_count: int, total_violations: int) -> float:
    if row_count <= 0:
        return 100.0
    violation_rate = min(total_violations / max(row_count, 1), 1.0)
    return 100.0 * (1 - violation_rate)


def _build_data_dictionary(profile: DatasetProfile) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for column in profile.columns:
        entries.append(
            {
                "column": column.column,
                "description": _describe_column(column),
            }
        )
    return entries


def _describe_column(column) -> str:
    if column.inferred_semantics == "identifier":
        return f"Unique identifier field with {column.unique_count} observed values."
    if column.inferred_semantics == "numeric":
        return f"Numeric field ranging from {column.min_value} to {column.max_value}."
    if column.inferred_semantics == "postal_code":
        return "Postal code field expected to use a 5-digit format."
    if column.inferred_semantics == "datetime":
        return "Date or timestamp field used for time-based analysis."
    return f"Categorical field with {column.unique_count} unique values."
