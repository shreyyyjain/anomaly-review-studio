# Anomaly Review Studio

Live app: [https://anomaly-review-studio.streamlit.app/](https://anomaly-review-studio.streamlit.app/)

Anomaly Review Studio is a Streamlit app for fast data quality review on any CSV.

## What it does

- Profiles column quality and schema signals
- Generates suggested quality rules
- Flags violations with severity and remediation guidance
- Tracks findings in an Issue Queue (`new`, `acknowledged`, `resolved`)
- Compares each run against a baseline to show what changed
- Evaluates quality gates (warn-only by default)
- Produces a narrative report for review

## How to use

1. Open the live app.
2. Upload your CSV (or load demo data).
3. Review `Overview`, `Rules`, and `Issue Queue`.
4. Use `Report` for a concise narrative summary.
