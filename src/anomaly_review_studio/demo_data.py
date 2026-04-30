from __future__ import annotations

from pathlib import Path

import pandas as pd


DEMO_ROWS = [
    {"customer_id": 1001, "age": 34, "gender": "Female", "zipcode": "02139", "signup_source": "Web", "lifetime_value": 120.5},
    {"customer_id": 1002, "age": 41, "gender": "Male", "zipcode": "94107", "signup_source": "Web", "lifetime_value": 98.0},
    {"customer_id": 1003, "age": None, "gender": "Mle", "zipcode": "10001", "signup_source": "Mobile", "lifetime_value": 45.2},
    {"customer_id": 1004, "age": 29, "gender": "Female", "zipcode": "ABCDE", "signup_source": "Partner", "lifetime_value": 200.0},
    {"customer_id": 1005, "age": 52, "gender": "Female", "zipcode": "60601", "signup_source": "Web", "lifetime_value": None},
    {"customer_id": 1005, "age": 52, "gender": "Female", "zipcode": "60601", "signup_source": "Web", "lifetime_value": 175.0},
    {"customer_id": 1006, "age": 24, "gender": "Female", "zipcode": "30301", "signup_source": "Mobile", "lifetime_value": 39.8},
    {"customer_id": 1007, "age": 67, "gender": "Male", "zipcode": "77002", "signup_source": "Partner", "lifetime_value": 640.0},
    {"customer_id": 1008, "age": 15, "gender": "Female", "zipcode": "90012", "signup_source": "Web", "lifetime_value": 8.5},
    {"customer_id": 1009, "age": 92, "gender": "Male", "zipcode": "10011", "signup_source": "Store", "lifetime_value": 12.0},
    {"customer_id": 1010, "age": 43, "gender": "Unknown", "zipcode": "3310A", "signup_source": "Mobile", "lifetime_value": 333.4},
    {"customer_id": 1011, "age": None, "gender": "Female", "zipcode": "60614-1234", "signup_source": "Email", "lifetime_value": 220.0},
    {"customer_id": 1012, "age": 38, "gender": "Male", "zipcode": "73301", "signup_source": "Referral", "lifetime_value": 0.0},
    {"customer_id": 1013, "age": 38, "gender": "male", "zipcode": "73301", "signup_source": "Referral", "lifetime_value": 5100.0},
    {"customer_id": 1014, "age": 47, "gender": "Female", "zipcode": "98101", "signup_source": "Web", "lifetime_value": 415.2},
    {"customer_id": 1015, "age": 61, "gender": "Female", "zipcode": "02139", "signup_source": "Partner", "lifetime_value": 920.0},
    {"customer_id": 1016, "age": 31, "gender": "Non-Binary", "zipcode": "", "signup_source": "Mobile", "lifetime_value": 140.0},
    {"customer_id": 1017, "age": 55, "gender": "Female", "zipcode": "99999", "signup_source": "Web", "lifetime_value": 300.0},
    {"customer_id": 1018, "age": -2, "gender": "Male", "zipcode": "45202", "signup_source": "Store", "lifetime_value": 89.0},
    {"customer_id": 1019, "age": 120, "gender": "Female", "zipcode": "19103", "signup_source": "Web", "lifetime_value": 67.0},
    {"customer_id": 1020, "age": 44, "gender": "Female", "zipcode": "75201", "signup_source": "Web", "lifetime_value": 880.0},
    {"customer_id": 1021, "age": 44, "gender": "Female", "zipcode": "75201", "signup_source": "Affiliate", "lifetime_value": 880.0},
    {"customer_id": 1022, "age": 27, "gender": "Male", "zipcode": "11211", "signup_source": "Mobile", "lifetime_value": 75.4},
    {"customer_id": 1023, "age": 36, "gender": "Female", "zipcode": "94107", "signup_source": "Web", "lifetime_value": ""},
    {"customer_id": 1024, "age": None, "gender": "F", "zipcode": "07030", "signup_source": "Unknown", "lifetime_value": 130.0},
]


def build_demo_dataframe() -> pd.DataFrame:
    return pd.DataFrame(DEMO_ROWS)


def write_demo_csv(path: Path) -> None:
    build_demo_dataframe().to_csv(path, index=False)
