import logging

import pandas as pd
from psycopg2.extras import execute_values

from ml.features import FEATURE_COLS

log = logging.getLogger("ml.predict")

MODEL_NAME = "catboost"


def predict_test(conn, model, test_df, as_of):
    df = test_df.copy()
    df["predicted_price_rub"] = model.predict(df[FEATURE_COLS])
    df["actual_price_rub"] = df["price_rub"]
    df["abs_error_rub"] = (df["actual_price_rub"] - df["predicted_price_rub"]).abs()
    df["ape_pct"] = df["abs_error_rub"] / df["actual_price_rub"] * 100
    return df


def predict_future(conn, model, all_df, as_of):
    df = all_df[all_df["loading_date"] > as_of].copy()
    if len(df) == 0:
        log.warning("no future rows for as_of=%s", as_of)
        return df
    df["predicted_price_rub"] = model.predict(df[FEATURE_COLS])
    df["actual_price_rub"] = None
    df["abs_error_rub"] = None
    df["ape_pct"] = None
    return df


def save_predictions(conn, df, model_name=MODEL_NAME):
    if len(df) == 0:
        return 0
    rows = [
        (
            int(r.price_id),
            r.loading_date,
            int(r.loading_city_gcid),
            int(r.unloading_city_gcid),
            int(r.body_group_id) if pd.notna(r.body_group_id) else None,
            float(r.actual_price_rub) if pd.notna(r.actual_price_rub) else None,
            float(r.predicted_price_rub),
            float(r.abs_error_rub) if pd.notna(r.abs_error_rub) else None,
            float(r.ape_pct) if pd.notna(r.ape_pct) else None,
            model_name,
        )
        for r in df.itertuples()
    ]
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO mart.ml_price_predictions (
                price_id, loading_date,
                loading_city_gcid, unloading_city_gcid, body_group_id,
                actual_price_rub, predicted_price_rub,
                abs_error_rub, ape_pct,
                model_name
            ) VALUES %s
            ON CONFLICT (price_id) DO UPDATE SET
                predicted_price_rub = EXCLUDED.predicted_price_rub,
                actual_price_rub = EXCLUDED.actual_price_rub,
                abs_error_rub = EXCLUDED.abs_error_rub,
                ape_pct = EXCLUDED.ape_pct,
                model_name = EXCLUDED.model_name,
                scored_at = now()
            """,
            rows,
            page_size=1000,
        )
    conn.commit()
    return len(rows)