import pandas as pd

from src.anomaly_review_studio.io import validate_dataframe


def test_validate_dataframe_reports_missing_columns():
    dataframe = pd.DataFrame({"customer_id": [1, 2], "age": [30, 41]})

    message = validate_dataframe(dataframe, expected_columns=["customer_id", "zipcode"])

    assert message == "Missing required columns: zipcode"
