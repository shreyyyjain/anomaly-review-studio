import pandas as pd

from src.anomaly_review_studio.profiling import profile_dataframe


def test_profile_dataframe_identifies_missing_and_unique_counts():
    dataframe = pd.DataFrame(
        {
            "customer_id": [1, 2, 2, 4],
            "age": [34, None, 41, 52],
            "zipcode": ["02139", "94107", "10001", "ABCDE"],
        }
    )

    profile = profile_dataframe(dataframe)

    customer_profile = next(item for item in profile.columns if item.column == "customer_id")
    assert customer_profile.unique_count == 3
    assert customer_profile.inferred_semantics == "identifier"

    age_profile = next(item for item in profile.columns if item.column == "age")
    assert age_profile.missing_count == 1
    assert age_profile.inferred_semantics == "numeric"

    zipcode_profile = next(item for item in profile.columns if item.column == "zipcode")
    assert zipcode_profile.inferred_semantics == "postal_code"
