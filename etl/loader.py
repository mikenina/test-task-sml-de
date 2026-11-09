REFERENCE_TABLES = ("cities", "body_types", "exchange_rates")


def load_prices(conn, interval_start, interval_end):
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM raw.prices "
            "WHERE loading_date >= %s AND loading_date < %s",
            (interval_start, interval_end),
        )
        cur.execute(
            "INSERT INTO raw.prices "
            "SELECT * FROM public.prices "
            "WHERE loading_date >= %s AND loading_date < %s",
            (interval_start, interval_end),
        )
        return cur.rowcount


def load_price_dates(conn, interval_start, interval_end):
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM raw.price_dates "
            "WHERE price_id IN ("
            "  SELECT id FROM public.prices "
            "   WHERE loading_date >= %s AND loading_date < %s"
            ")",
            (interval_start, interval_end),
        )
        cur.execute(
            "INSERT INTO raw.price_dates "
            "SELECT pd.* FROM public.price_dates pd "
            "  JOIN public.prices p ON p.id = pd.price_id "
            " WHERE p.loading_date >= %s AND p.loading_date < %s",
            (interval_start, interval_end),
        )
        return cur.rowcount

def load_price_body_types(conn, interval_start, interval_end):
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM raw.price_body_types "
            "WHERE price_id IN ("
            "  SELECT id FROM public.prices "
            "   WHERE loading_date >= %s AND loading_date < %s"
            ")",
            (interval_start, interval_end),
        )
        cur.execute(
            "INSERT INTO raw.price_body_types "
            "SELECT pbt.* FROM public.price_body_types pbt "
            "  JOIN public.prices p ON p.id = pbt.price_id "
            " WHERE p.loading_date >= %s AND p.loading_date < %s",
            (interval_start, interval_end),
        )
        return cur.rowcount

def load_reference(conn):
    counts = {}
    with conn.cursor() as cur:
        for table in REFERENCE_TABLES:
            cur.execute(f"TRUNCATE raw.{table}")
            cur.execute(f"INSERT INTO raw.{table} SELECT * FROM public.{table}")
            counts[table] = cur.rowcount
    return counts