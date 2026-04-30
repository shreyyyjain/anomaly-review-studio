import pandas as pd

from src.anomaly_review_studio.profiling import profile_dataframe
from src.anomaly_review_studio.reporting import build_markdown_report, build_rules_payload
from src.anomaly_review_studio.rules import generate_rules


def test_markdown_report_includes_baseline_and_gate_sections():
    dataframe = pd.DataFrame(
        {
            "customer_id": [1, 2, 2, 4],
            "age": [34, None, 41, 200],
            "zipcode": ["02139", "94107", "10001", "ABCDE"],
        }
    )
    profile = profile_dataframe(dataframe)
    rules = generate_rules(dataframe, profile)
    result_rows = [
        {
            **rules[0].as_dict(),
            "violations": 1,
            "pass_rate_pct": 75.0,
            "effective_severity": "high",
            "guidance": {"steps": "fix it"},
        }
    ]
    payload = build_rules_payload(
        source_name="demo",
        dataframe=dataframe,
        profile=profile,
        rules=rules,
        rule_results=result_rows,
        violation_summary={"rule_count": len(rules), "total_violations": 1},
        baseline_summary={
            "new_findings": 1,
            "resolved_findings": 0,
            "worsened_findings": 0,
            "improved_findings": 0,
        },
        gate_summary={"status": "warn", "warn_only": True},
    )
    markdown = build_markdown_report(payload)
    assert "What changed since baseline" in markdown
    assert "Quality gate status" in markdown
    assert "Remediation guidance" in markdown
