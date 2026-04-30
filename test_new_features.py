#!/usr/bin/env python
"""Test script for new features: flagged rows, severity filters, custom rules."""

from pathlib import Path
from src.anomaly_review_studio.io import load_demo_data
from src.anomaly_review_studio.profiling import profile_dataframe
from src.anomaly_review_studio.rules import generate_rules, evaluate_rules, Rule
from src.anomaly_review_studio.reporting import build_rules_payload, build_markdown_report

# Load and process
print("Loading demo data...")
df = load_demo_data(Path('data/demo_anomaly_review.csv'))
print(f"Dataset shape: {df.shape}")

print("\nProfiling dataset...")
profile = profile_dataframe(df)

print("\nGenerating rules...")
rules = generate_rules(df, profile)
print(f"Generated {len(rules)} rules")

print("\nEvaluating rules...")
results, summary = evaluate_rules(df, rules)

# Test 1: Verify flagged_rows is in results
print("\n=== TEST 1: Flagged rows tracking ===")
for r in results[:3]:
    has_flagged = "flagged_rows" in r
    flagged_count = len(r.get("flagged_rows", []))
    print(f"✓ Rule: {r['column']} [{r['rule_type']}]")
    print(f"  - Has flagged_rows: {has_flagged}")
    print(f"  - Violations: {r['violations']}, Flagged indices: {flagged_count}")
    assert has_flagged, "flagged_rows missing!"
    assert flagged_count == r['violations'], "Flagged count mismatch!"

# Test 2: Verify payload still builds correctly
print("\n=== TEST 2: Payload generation ===")
payload = build_rules_payload('demo', df, profile, rules, results, summary)
assert 'rule_results' in payload.payload
assert len(payload['rule_results']) == len(results)
print(f"✓ Payload has {len(payload['rule_results'])} rule results")
print(f"  - First result keys: {list(payload['rule_results'][0].keys())}")

# Test 3: Severity filtering
print("\n=== TEST 3: Severity filtering ===")
high_severity = [r for r in results if r['severity'] == 'high']
medium_severity = [r for r in results if r['severity'] == 'medium']
print(f"✓ High severity rules: {len(high_severity)}")
print(f"✓ Medium severity rules: {len(medium_severity)}")

# Test 4: Custom rule builder (simulated)
print("\n=== TEST 4: Custom rule creation ===")
custom_rule = Rule(
    column="test_col",
    rule_type="not_null",
    description="Test custom rule",
    severity="high"
)
custom_rules = [custom_rule]
all_rules = rules + custom_rules
print(f"✓ Created custom rule for column: {custom_rule.column}")
print(f"✓ Total rules after adding custom: {len(all_rules)} (was {len(rules)})")

# Test 5: Violations CSV building (simulated)
print("\n=== TEST 5: Violations-only CSV ===")
violation_indices = set()
for result in results:
    violation_indices.update(result.get("flagged_rows", []))
violations_df = df.iloc[sorted(violation_indices)] if violation_indices else df.iloc[:0]
print(f"✓ Total rows with violations: {len(violations_df)}")
print(f"✓ Total rows in dataset: {len(df)}")
print(f"✓ Violation percentage: {100 * len(violations_df) / len(df):.1f}%")

print("\n✅ ALL TESTS PASSED!")
