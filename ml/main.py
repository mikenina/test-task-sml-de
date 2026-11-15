import logging

from ml.features import load_features
from ml.predict import predict_future, predict_test, save_predictions
from ml.train import train_all

log = logging.getLogger("ml")

def run_ml_pipeline(conn, as_of):
    df = load_features(conn)
    log.info("features loaded: %d rows", len(df))

    result = train_all(df)
    model = result["model"]
    metrics = result["metrics"]
    baseline = result["baseline_metrics"]

    test_pred = predict_test(conn, model, result["test"], as_of)
    n_test = save_predictions(conn, test_pred)

    future_pred = predict_future(conn, model, df, as_of)
    n_future = save_predictions(conn, future_pred)

    log.info(
        "predictions saved: test=%d future=%d", n_test, n_future
    )
    return {
        "rows_out": n_test + n_future,
        "details": {
            "metrics_catboost": metrics,
            "metrics_decision_tree": baseline,
            "predictions_test": n_test,
            "predictions_future": n_future,
        },
    }