from src.anomaly_review_studio.workflow import (
    apply_severity_policy,
    compute_baseline_delta,
    evaluate_quality_gates,
    infer_column_role,
)


def test_severity_policy_escalates_compliance_format_issue():
    role = infer_column_role("zipcode", "postal_code")
    effective = apply_severity_policy("medium", role, {"compliance": 1, "operational": 0})
    assert effective == "high"


def test_compute_baseline_delta_classifies_new_worsened_improved_and_resolved():
    baseline = [
        {
            "finding_id": "a",
            "effective_severity": "medium",
            "violations": 2,
        },
        {
            "finding_id": "b",
            "effective_severity": "high",
            "violations": 4,
        },
    ]
    current = [
        {
            "finding_id": "a",
            "effective_severity": "high",
            "violations": 5,
        },
        {
            "finding_id": "c",
            "effective_severity": "low",
            "violations": 1,
        },
    ]
    updated, summary = compute_baseline_delta(current, baseline, "run-1")
    delta_by_id = {item["finding_id"]: item["baseline_delta"] for item in updated}
    assert delta_by_id["a"] == "worsened"
    assert delta_by_id["c"] == "new"
    assert summary.resolved_findings == 1
    assert summary.new_findings == 1
    assert summary.worsened_findings == 1


def test_quality_gate_warn_on_threshold_breach():
    findings = [
        {"effective_severity": "high", "violations": 2},
        {"effective_severity": "medium", "violations": 1},
    ]
    profile = [
        {"column": "customer_id", "inferred_semantics": "identifier", "missing_pct": 0.0},
        {"column": "zipcode", "inferred_semantics": "postal_code", "missing_pct": 7.0},
    ]
    gates = evaluate_quality_gates(
        results=findings,
        quality_score=72.0,
        profile_records=profile,
        rules={
            "max_high_violations": 0,
            "min_quality_score": 80.0,
            "max_critical_missing_pct": 5.0,
            "warn_only": True,
        },
    )
    assert gates["status"] == "warn"
    assert gates["warn_only"] is True
    assert gates["passed"] is False
