import logging
from datetime import date

from catboost import CatBoostRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)
from sklearn.tree import DecisionTreeRegressor

from ml.features import CAT_FEATURES, FEATURE_COLS, TARGET

log = logging.getLogger("ml.train")

TRAIN_START = date(2026, 7, 26)
TRAIN_END = date(2026, 10, 5)
TEST_START = date(2026, 10, 5)
TEST_END = date(2026, 10, 26)

RANDOM_SEED = 42


def split(df):
    train = df[(df["loading_date"] >= TRAIN_START) & (df["loading_date"] < TRAIN_END)]
    test = df[(df["loading_date"] >= TEST_START) & (df["loading_date"] <= TEST_END)]
    return train.copy(), test.copy()


def evaluate(y_true, y_pred):
    return {
        "r2": float(r2_score(y_true, y_pred)),
        "mape": float(mean_absolute_percentage_error(y_true, y_pred) * 100),
        "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "n": int(len(y_true)),
    }


def train_catboost(train):
    model = CatBoostRegressor(
        iterations=500,
        depth=6,
        learning_rate=0.05,
        random_seed=RANDOM_SEED,
        verbose=False,
    )
    model.fit(train[FEATURE_COLS], train[TARGET],
              cat_features=CAT_FEATURES)
    return model


def train_baseline(train):
    model = DecisionTreeRegressor(max_depth=10, random_state=RANDOM_SEED)
    model.fit(_prepare_baseline(train[FEATURE_COLS]),
              train[TARGET])
    return model


def _prepare_baseline(X):
    # DecisionTree не понимает категориальные строки — кодируем в int
    X = X.copy()
    for c in CAT_FEATURES:
        X[c] = X[c].astype(str).astype("category").cat.codes
    return X


def train_all(df):
    train, test = split(df)
    if len(train) == 0 or len(test) == 0:
        raise ValueError(
            f"empty train ({len(train)}) or test ({len(test)}) split"
        )
    log.info("train=%d test=%d", len(train), len(test))

    cb = train_catboost(train)
    cb_pred = cb.predict(test[FEATURE_COLS])
    cb_metrics = evaluate(test[TARGET], cb_pred)
    log.info("catboost: %s", cb_metrics)

    dt = train_baseline(train)
    dt_pred = dt.predict(_prepare_baseline(test[FEATURE_COLS]))
    dt_metrics = evaluate(test[TARGET], dt_pred)
    log.info("decision_tree: %s", dt_metrics)

    return {
        "model": cb,
        "metrics": cb_metrics,
        "baseline_metrics": dt_metrics,
        "train": train,
        "test": test,
    }