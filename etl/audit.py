import json

class Audit:
    def __init__(self, conn):
        self.conn = conn
        self.run_id = None

    def start_run(self, interval_start, interval_end, triggered_by):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO dq.etl_runs "
                "(data_interval_start, data_interval_end, triggered_by) "
                "VALUES (%s, %s, %s) RETURNING id",
                (interval_start, interval_end, triggered_by),
            )
            self.run_id = cur.fetchone()[0]

    def finish_run(self, status, error_message=None):
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE dq.etl_runs "
                "SET run_finished_at = now(), status = %s, error_message = %s "
                "WHERE id = %s",
                (status, error_message, self.run_id),
            )

    def start_stage(self, name):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO dq.etl_run_stages (run_id, stage_name) "
                "VALUES (%s, %s) RETURNING id",
                (self.run_id, name),
            )
            return cur.fetchone()[0]

    def finish_stage(self, stage_id, status, rows_in=None, rows_out=None,
                     rows_quarantined=None, details=None, error_message=None):
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE dq.etl_run_stages "
                "SET stage_finished_at = now(), status = %s, "
                "rows_in = %s, rows_out = %s, rows_quarantined = %s, "
                "details = %s, error_message = %s "
                "WHERE id = %s",
                (
                    status, rows_in, rows_out, rows_quarantined,
                    json.dumps(details) if details else None,
                    error_message, stage_id,
                ),
            )