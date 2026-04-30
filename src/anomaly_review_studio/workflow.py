from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any


SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}

ROLE_SEVERITY_BONUS = {
    "identifier": 1,
    "contact": 1,
    "financial": 1,
    "compliance": 1,
    "operational": 0,
}

DEFAULT_QUALITY_GATE_RULES = {
    "max_high_violations": 3,
    "min_quality_score": 70.0,
    "max_critical_missing_pct": 10.0,
    "warn_only": True,
}


@dataclass
class BaselineSummary:
    baseline_run_id: str | None
    new_findings: int
    resolved_findings: int
    worsened_findings: int
    improved_findings: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "baseline_run_id": self.baseline_run_id,
            "new_findings": self.new_findings,
            "resolved_findings": self.resolved_findings,
            "worsened_findings": self.worsened_findings,
            "improved_findings": self.improved_findings,
        }


def infer_column_role(column: str, semantic_type: str) -> str:
    name = column.lower()
    if any(token in name for token in ["email", "phone", "contact", "address"]):
        return "contact"
    if any(token in name for token in ["revenue", "value", "price", "cost", "amount", "income", "payment"]):
        return "financial"
    if any(token in name for token in ["ssn", "tax", "zipcode", "postal", "dob", "birth", "compliance"]):
        return "compliance"
    if semantic_type == "identifier":
        return "identifier"
    return "operational"


def fingerprint_finding(source_label: str, column: str, rule_type: str, expected_value: str | None) -> str:
    raw = f"{source_label}|{column}|{rule_type}|{expected_value or ''}"
    return sha256(raw.encode("utf-8")).hexdigest()[:20]


def apply_severity_policy(
    base_severity: str,
    column_role: str,
    severity_policy: dict[str, int] | None = None,
) -> str:
    severity_policy = severity_policy or ROLE_SEVERITY_BONUS
    base_rank = SEVERITY_ORDER.get(base_severity.lower(), 2)
    bonus = int(severity_policy.get(column_role, 0))
    adjusted_rank = max(1, min(3, base_rank + bonus))
    return next(level for level, rank in SEVERITY_ORDER.items() if rank == adjusted_rank)


def build_guidance(result: dict[str, Any]) -> dict[str, str]:
    column = result["column"]
    rule_type = result["rule_type"]
    if rule_type == "not_null":
        return {
            "why": f"Missing values in {column} can break joins, filters, and downstream KPIs.",
            "root_cause": "Upstream ingestion gaps, optional source field, or schema drift.",
            "steps": f"1) Trace null rows in {column}. 2) Backfill from source system. 3) Add ingestion validation for {column}.",
        }
    if rule_type == "unique":
        return {
            "why": f"Duplicate {column} values can cause double counting and entity ambiguity.",
            "root_cause": "Deduplication not enforced upstream or key generation collisions.",
            "steps": f"1) Group duplicates by {column}. 2) Resolve canonical record. 3) Add uniqueness constraint/check in pipeline.",
        }
    if rule_type == "range":
        return {
            "why": f"Out-of-range {column} values can distort models and metrics.",
            "root_cause": "Unit mismatch, bad parsing, or stale business limits.",
            "steps": f"1) Inspect outlier rows for {column}. 2) Validate source units. 3) Clamp/reject invalid values in ETL.",
        }
    if rule_type == "allowed_values":
        return {
            "why": f"Unexpected categories in {column} fragment reporting dimensions.",
            "root_cause": "Unmapped source values or typo variants.",
            "steps": f"1) List invalid categories in {column}. 2) Map to canonical set. 3) Enforce enum validation upstream.",
        }
    return {
        "why": f"Invalid format in {column} can break matching and compliance workflows.",
        "root_cause": "Input validation missing or format normalization not applied.",
        "steps": f"1) Isolate malformed {column} values. 2) Normalize format. 3) Add regex validation at ingestion.",
    }


def enrich_rule_results(
    source_label: str,
    profile_records: list[dict[str, Any]],
    rule_results: list[dict[str, Any]],
    severity_policy: dict[str, int] | None = None,
    role_overrides: dict[str, str] | None = None,
    default_status: str = "new",
) -> list[dict[str, Any]]:
    semantics_by_column = {
        row["column"]: row.get("inferred_semantics", row.get("semantic_type", "unknown")) for row in profile_records
    }
    role_overrides = role_overrides or {}
    enriched = []
    for result in rule_results:
        base_severity = str(result["severity"]).lower()
        column_role = role_overrides.get(
            result["column"],
            infer_column_role(result["column"], semantics_by_column.get(result["column"], "unknown")),
        )
        effective_severity = apply_severity_policy(base_severity, column_role, severity_policy)
        guidance = build_guidance(result)
        finding_id = fingerprint_finding(source_label, result["column"], result["rule_type"], result.get("expected_value"))
        enriched.append(
            {
                **result,
                "finding_id": finding_id,
                "source_label": source_label,
                "base_severity": base_severity,
                "effective_severity": effective_severity,
                "column_role": column_role,
                "guidance": guidance,
                "status": default_status,
                "owner": "",
                "notes": "",
                "run_id": "",
                "baseline_delta": "unchanged",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return enriched


def compute_baseline_delta(
    current_results: list[dict[str, Any]],
    baseline_results: list[dict[str, Any]],
    baseline_run_id: str | None = None,
) -> tuple[list[dict[str, Any]], BaselineSummary]:
    baseline_map = {item["finding_id"]: item for item in baseline_results}
    current_map = {item["finding_id"]: item for item in current_results}
    new_count = 0
    worsened_count = 0
    improved_count = 0
    updated: list[dict[str, Any]] = []

    for item in current_results:
        previous = baseline_map.get(item["finding_id"])
        delta = "unchanged"
        if previous is None:
            delta = "new"
            new_count += 1
        else:
            current_tuple = (
                SEVERITY_ORDER.get(item["effective_severity"], 2),
                int(item.get("violations", 0)),
            )
            previous_tuple = (
                SEVERITY_ORDER.get(previous.get("effective_severity", previous.get("severity", "medium")), 2),
                int(previous.get("violations", 0)),
            )
            if current_tuple > previous_tuple:
                delta = "worsened"
                worsened_count += 1
            elif current_tuple < previous_tuple:
                delta = "improved"
                improved_count += 1

        updated.append({**item, "baseline_delta": delta})

    resolved_count = len([key for key in baseline_map if key not in current_map])
    summary = BaselineSummary(
        baseline_run_id=baseline_run_id,
        new_findings=new_count,
        resolved_findings=resolved_count,
        worsened_findings=worsened_count,
        improved_findings=improved_count,
    )
    return updated, summary


def evaluate_quality_gates(
    results: list[dict[str, Any]],
    quality_score: float,
    profile_records: list[dict[str, Any]],
    rules: dict[str, float] | None = None,
) -> dict[str, Any]:
    configured = {**DEFAULT_QUALITY_GATE_RULES, **(rules or {})}
    high_violations = sum(item.get("violations", 0) for item in results if item.get("effective_severity") == "high")
    critical_columns = [row for row in profile_records if infer_column_role(row["column"], row.get("inferred_semantics", "unknown")) in {"identifier", "contact", "compliance"}]
    critical_missing = max((float(row.get("missing_pct", 0)) for row in critical_columns), default=0.0)

    checks = [
        {
            "name": "max_high_violations",
            "actual": high_violations,
            "threshold": configured["max_high_violations"],
            "passed": high_violations <= configured["max_high_violations"],
        },
        {
            "name": "min_quality_score",
            "actual": quality_score,
            "threshold": configured["min_quality_score"],
            "passed": quality_score >= configured["min_quality_score"],
        },
        {
            "name": "max_critical_missing_pct",
            "actual": round(critical_missing, 2),
            "threshold": configured["max_critical_missing_pct"],
            "passed": critical_missing <= configured["max_critical_missing_pct"],
        },
    ]
    passed_all = all(check["passed"] for check in checks)
    return {
        "warn_only": bool(configured.get("warn_only", True)),
        "passed": passed_all,
        "status": "pass" if passed_all else "warn",
        "checks": checks,
    }
