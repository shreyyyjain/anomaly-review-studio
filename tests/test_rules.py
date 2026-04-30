import pandas as pd

from src.anomaly_review_studio.profiling import profile_dataframe
from src.anomaly_review_studio.rules import evaluate_rules, generate_rules


def test_generate_rules_covers_nulls_uniqueness_and_format():
    dataframe = pd.DataFrame(
        {
            "customer_id": [1, 2, 2, 4],
            "age": [34, None, 41, 52],
            "zipcode": ["02139", "94107", "10001", "ABCDE"],
            "status": ["active", "active", "inactive", "inactive"],
        }
    )

    profile = profile_dataframe(dataframe)
    rules = generate_rules(dataframe, profile)

    rule_types = {rule.rule_type for rule in rules}
    assert "unique" in rule_types
    assert "range" in rule_types
    assert "format" in rule_types or "allowed_values" in rule_types


def test_postal_code_format_rule_is_high_severity():
    dataframe = pd.DataFrame(
        {
            "customer_id": [1, 2, 3, 4],
            "zipcode": ["02139", "94107", "10001", "ABCDE"],
        }
    )

    profile = profile_dataframe(dataframe)
    rules = generate_rules(dataframe, profile)

    zipcode_rule = next(rule for rule in rules if rule.column == "zipcode" and rule.rule_type == "format")
    assert zipcode_rule.severity == "high"


def test_evaluate_rules_counts_violations():
    dataframe = pd.DataFrame(
        {
            "customer_id": [1, 2, 2, 4],
            "age": [34, None, 41, 200],
            "zipcode": ["02139", "94107", "10001", "ABCDE"],
        }
    )
    profile = profile_dataframe(dataframe)
    rules = generate_rules(dataframe, profile)
    results, summary = evaluate_rules(dataframe, rules)

    assert summary["rule_count"] == len(rules)
    assert summary["total_violations"] >= 1
    assert any(result["violations"] >= 1 for result in results)
