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

    for index in range(7, 200, 17):
        rows[index]["zipcode"] = random.choice(["ABCDE", "33A10", "", "9999", "12-345"])
    for index in range(11, 200, 19):
        rows[index]["gender"] = random.choice(["Mle", "F", "male", "Unknown"])
    for index in range(13, 200, 23):
        rows[index]["age"] = None
    for index in range(15, 200, 29):
        rows[index]["lifetime_value"] = None
    for index in range(18, 200, 31):
        rows[index]["signup_source"] = random.choice(["Email", "Unknown", "Kiosk"])
    for index in range(21, 200, 37):
        rows[index]["age"] = random.choice([-4, 0, 121, 133])
    for index in range(27, 200, 41):
        rows[index]["lifetime_value"] = random.choice([0.0, 8900.0, 12500.0])

    duplicate_pairs = [(50, 49), (77, 76), (120, 119), (161, 160)]
    for target, source in duplicate_pairs:
        rows[target]["customer_id"] = rows[source]["customer_id"]

    near_duplicate_rows = [(170, 169), (190, 189)]
    for target, source in near_duplicate_rows:
        rows[target]["zipcode"] = rows[source]["zipcode"]
        rows[target]["age"] = rows[source]["age"]
        rows[target]["lifetime_value"] = rows[source]["lifetime_value"]

    return pd.DataFrame(rows)


def write_demo_csv(path: Path) -> None:
    build_demo_dataframe().to_csv(path, index=False)
