from __future__ import annotations

import os
from typing import Any


def enrich_rule_descriptions(rules: list[dict[str, Any]], data_dictionary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return [
            {
                **rule,
                "explanation": f"Suggested because the observed data pattern for {rule['column']} matches a {rule['rule_type']} check.",
            }
            for rule in rules
        ]
    # Lightweight placeholder: keep the app offline-first by default.
    return [
        {
            **rule,
            "explanation": f"LLM-enhanced explanation would be generated here for {rule['column']}.",
        }
        for rule in rules
    ]
