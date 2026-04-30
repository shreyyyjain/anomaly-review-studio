from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .profiling import DatasetProfile


@dataclass
class Rule:
    column: str
    rule_type: str
    description: str
    severity: str
    expected_value: str | None = None
    min_value: float | None = None
    max_value: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "rule_type": self.rule_type,
            "description": self.description,
            "severity": self.severity,
            "expected_value": self.expected_value,
            "min_value": self.min_value,
            "max_value": self.max_value,
        }


def generate_rules(dataframe: pd.DataFrame, profile: DatasetProfile) -> list[Rule]:
    rules: list[Rule] = []
    row_count = len(dataframe)

    for column_profile in profile.columns:
        column = column_profile.column
        series = dataframe[column]
        non_null_ratio = column_profile.non_null_count / row_count if row_count else 0

        if column_profile.missing_count == 0 and column_profile.inferred_semantics == "identifier":
            rules.append(
                Rule(
                    column=column,
                    rule_type="not_null",
                    description=f"{column} should never be null.",
                    severity="high",
                )
            )

        if column_profile.inferred_semantics == "identifier":
            rules.append(
                Rule(
                    column=column,
                    rule_type="unique",
                    description=f"{column} should be unique across the dataset.",
                    severity="high",
                )
            )

        if column_profile.inferred_semantics == "numeric" and column_profile.mean_value is not None:
            numeric = pd.to_numeric(series, errors="coerce")
            valid = numeric.dropna()
            if not valid.empty:
                lower = float(valid.quantile(0.01))
                upper = float(valid.quantile(0.99))
                rules.append(
                    Rule(
                        column=column,
                        rule_type="range",
                        description=f"{column} should stay between {lower:.2f} and {upper:.2f} based on observed data.",
                        severity="medium",
                        min_value=lower,
                        max_value=upper,
                    )
                )

        if column_profile.inferred_semantics == "categorical" and column_profile.unique_count <= 10 and non_null_ratio > 0.7:
            allowed_values = series.dropna().astype(str).value_counts().index.tolist()[:10]
            rules.append(
                Rule(
                    column=column,
                    rule_type="allowed_values",
                    description=f"{column} should contain only known values such as {', '.join(allowed_values[:5])}.",
                    severity="medium",
                    expected_value="|".join(map(str, allowed_values)),
                )
            )

        if column_profile.inferred_semantics == "postal_code":
            rules.append(
                Rule(
                    column=column,
                    rule_type="format",
                    description=f"{column} should match a 5-digit postal code format.",
                    severity="high",
                    expected_value=r"^\d{5}(-\d{4})?$",
                )
            )

    return rules


def evaluate_rules(dataframe: pd.DataFrame, rules: list[Rule]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    results: list[dict[str, Any]] = []
    total_violations = 0

    for rule in rules:
        series = dataframe[rule.column]
        violations, flagged_indices = _get_violations_and_indices(series, rule)
        total_violations += violations
        results.append(
            {
                **rule.as_dict(),
                "violations": violations,
                "pass_rate_pct": round(100.0 * (1 - violations / len(dataframe)), 2) if len(dataframe) else 0.0,
                "flagged_rows": flagged_indices,
            }
        )

    return results, {"total_violations": total_violations, "rule_count": len(rules)}


def _count_violations(series: pd.Series, rule: Rule) -> int:
    if rule.rule_type == "not_null":
        return int(series.isna().sum())
    if rule.rule_type == "unique":
        return int(series.duplicated(keep=False).sum())
    if rule.rule_type == "range":
        numeric = pd.to_numeric(series, errors="coerce")
        mask = numeric.notna()
        if rule.min_value is None or rule.max_value is None:
            return 0
        return int(((numeric[mask] < rule.min_value) | (numeric[mask] > rule.max_value)).sum())
    if rule.rule_type == "allowed_values":
        allowed = set((rule.expected_value or "").split("|"))
        return int((~series.astype(str).isin(allowed) & series.notna()).sum())
    if rule.rule_type == "format":
        return int((~series.astype(str).str.match(rule.expected_value or ".*", na=False) & series.notna()).sum())
    return 0


def _get_violations_and_indices(series: pd.Series, rule: Rule) -> tuple[int, list[int]]:
    """Return violation count and list of flagged row indices."""
    if rule.rule_type == "not_null":
        mask = series.isna()
        indices = series[mask].index.tolist()
        return int(mask.sum()), indices
    if rule.rule_type == "unique":
        mask = series.duplicated(keep=False)
        indices = series[mask].index.tolist()
        return int(mask.sum()), indices
    if rule.rule_type == "range":
        numeric = pd.to_numeric(series, errors="coerce")
        mask = numeric.notna()
        if rule.min_value is None or rule.max_value is None:
            return 0, []
        violation_mask = ((numeric[mask] < rule.min_value) | (numeric[mask] > rule.max_value))
        indices = numeric[mask][violation_mask].index.tolist()
        return int(violation_mask.sum()), indices
    if rule.rule_type == "allowed_values":
        allowed = set((rule.expected_value or "").split("|"))
        mask = (~series.astype(str).isin(allowed) & series.notna())
        indices = series[mask].index.tolist()
        return int(mask.sum()), indices
    if rule.rule_type == "format":
        mask = (~series.astype(str).str.match(rule.expected_value or ".*", na=False) & series.notna())
        indices = series[mask].index.tolist()
        return int(mask.sum()), indices
    return 0, []
