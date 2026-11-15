import numpy as np
import pandas as pd


FEATURE_COLS = [
    "distance",
    "total_weight",
    "total_volume",
    "weight_category",
    "volume_category",
    "body_group_id",
    "origin_region",
    "destination_region",
    "origin_lat",
    "origin_lon",
    "destination_lat",
    "destination_lon",
    "year",
    "month_sin", "month_cos",
    "dow_sin", "dow_cos",
    "doy_sin", "doy_cos",
]

CAT_FEATURES = [
    "weight_category",
    "volume_category",
    "body_group_id",
    "origin_region",
    "destination_region",
]

TARGET = "price_rub"


def load_features(conn):
    query = """
        SELECT
            p.price_id,
            p.loading_date,
            p.loading_city_gcid,
            p.unloading_city_gcid,
            p.price_rub,
            p.distance,
            p.total_weight,
            p.total_volume,
            p.weight_category,
            p.volume_category,
            bt.body_group_id,
            c1.region AS origin_region,
            c2.region AS destination_region,
            c1.latitude AS origin_lat,
            c1.longitude AS origin_lon,
            c2.latitude AS destination_lat,
            c2.longitude AS destination_lon
        FROM core.price p
        LEFT JOIN core.body_type bt ON bt.id = p.main_body_type_id
        LEFT JOIN core.city c1 ON c1.gc_id = p.loading_city_gcid
        LEFT JOIN core.city c2 ON c2.gc_id = p.unloading_city_gcid
        WHERE p.outlier_mark = false
          AND p.price_rub > 0
          AND p.distance > 0
    """
    df = pd.read_sql(query, conn)
    df = _add_time_features(df)
    df = _fill_cats(df)
    return df


def _add_time_features(df):
    d = pd.to_datetime(df["loading_date"])
    df["year"] = d.dt.year.astype(int)
    month = d.dt.month.astype(int)
    dow = d.dt.dayofweek.astype(int)
    doy = d.dt.dayofyear.astype(int)

    df["month_sin"] = np.sin(2 * np.pi * month / 12)
    df["month_cos"] = np.cos(2 * np.pi * month / 12)
    df["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    df["dow_cos"] = np.cos(2 * np.pi * dow / 7)
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return df


def _fill_cats(df):
    df["origin_region"] = df["origin_region"].fillna("unknown")
    df["destination_region"] = df["destination_region"].fillna("unknown")
    df["weight_category"] = df["weight_category"].fillna("OTH")
    df["volume_category"] = df["volume_category"].fillna("OTH")
    df["body_group_id"] = df["body_group_id"].fillna(0).astype(int)
    return df