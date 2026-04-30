from __future__ import annotations

from pathlib import Path
import random

import pandas as pd


def build_demo_dataframe() -> pd.DataFrame:
    random.seed(42)
    genders = ["Female", "Male", "Non-Binary"]
    sources = ["Web", "Mobile", "Store", "Partner", "Referral", "Affiliate"]
    zipcodes = ["02139", "94107", "10001", "30301", "60601", "75201", "19103", "11211", "77002", "98101"]

    rows = []
    for offset in range(200):
        customer_id = 1000 + offset
        row = {
            "customer_id": customer_id,
            "age": random.randint(18, 72),
            "gender": random.choice(genders),
            "zipcode": random.choice(zipcodes),
            "signup_source": random.choice(sources),
            "lifetime_value": round(random.uniform(20, 1200), 2),
        }
        rows.append(row)

    anomaly_overrides = {
        3: {"zipcode": "ABCDE"},
        7: {"gender": "Mle"},
        11: {"age": None},
        15: {"lifetime_value": None},
        22: {"signup_source": "Unknown"},
        31: {"age": -4},
        44: {"age": 121},
        58: {"zipcode": "3310A"},
        73: {"zipcode": ""},
        95: {"gender": "F"},
        111: {"lifetime_value": 9500.0},
        127: {"lifetime_value": 0.0},
        140: {"age": None, "zipcode": "60614-1234"},
        166: {"signup_source": "Email"},
        181: {"gender": "male"},
    }
    for index, patch in anomaly_overrides.items():
        rows[index].update(patch)

    rows[50]["customer_id"] = rows[49]["customer_id"]
    rows[120]["customer_id"] = rows[119]["customer_id"]
    rows[170]["zipcode"] = rows[169]["zipcode"]
    rows[170]["age"] = rows[169]["age"]
    rows[170]["lifetime_value"] = rows[169]["lifetime_value"]

    return pd.DataFrame(rows)


def write_demo_csv(path: Path) -> None:
    build_demo_dataframe().to_csv(path, index=False)
