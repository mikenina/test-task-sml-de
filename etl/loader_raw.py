REFERENCE_TABLES = ("cities", "body_types", "exchange_rates")


def load_reference(conn, run_id):
    counts = {}
    with conn.cursor() as cur:
        for table in REFERENCE_TABLES:
            cur.execute(
                f"INSERT INTO raw.{table} "
                f"SELECT t.*, %s, now() FROM public.{table} t",
                (run_id,),
            )
            counts[table] = cur.rowcount
    return counts


def load_prices(conn, run_id, interval_start, interval_end):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO raw.prices "
            "SELECT p.*, %s, now() "
            "FROM public.prices p "
            "WHERE p.loading_date >= %s AND p.loading_date < %s",
            (run_id, interval_start, interval_end),
        )
        return cur.rowcount


def load_price_dates(conn, run_id, interval_start, interval_end):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO raw.price_dates "
            "SELECT pd.*, %s, now() "
            "FROM public.price_dates pd "
            "JOIN public.prices p ON p.id = pd.price_id "
            "WHERE p.loading_date >= %s AND p.loading_date < %s",
            (run_id, interval_start, interval_end),
        )
        return cur.rowcount


def load_price_body_types(conn, run_id, interval_start, interval_end):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO raw.price_body_types "
            "SELECT pbt.*, %s, now() "
            "FROM public.price_body_types pbt "
            "JOIN public.prices p ON p.id = pbt.price_id "
            "WHERE p.loading_date >= %s AND p.loading_date < %s",
            (run_id, interval_start, interval_end),
        )
        return cur.rowcount