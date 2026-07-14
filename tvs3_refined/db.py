import os
import time
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ── TTL cache for the live database query ──────────────────────────────────────
# Caches the full dataset for up to 30 seconds so that tab switches don't each
# fire a full MySQL round-trip, while still guaranteeing fresh data is visible
# within 30 s of a commit (or immediately after force_refresh() is called).

_CACHE_TTL      = 30          # seconds before re-querying MySQL
_cache_df       = None        # cached DataFrame
_cache_ts       = 0.0         # Unix timestamp of last successful load
_engine         = None        # Cached SQLAlchemy engine reference

def _get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine
        db_host     = os.getenv('DB_HOST', 'localhost')
        db_user     = os.getenv('DB_USER', 'root')
        db_password = os.getenv('DB_PASSWORD', 'root')
        db_name     = os.getenv('DB_NAME', 'insurance_brokerage')
        _engine = create_engine(
            f"mysql+mysqldb://{db_user}:{db_password}@{db_host}/{db_name}",
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )
    return _engine

def _load_from_db() -> pd.DataFrame | None:
    """Execute the full policy join query and return a DataFrame, or None on error."""
    try:
        from sqlalchemy import text
        engine = _get_engine()

        query = """
            SELECT
                p.policy_number,
                c.name as client_name,
                c.client_type,
                ca.carrier_name,
                pr.category,
                pr.sub_category,
                p.issue_date,
                p.expiry_date,
                p.premium_amount,
                p.status as policy_status,
                p.distribution_channel,
                c.region_name as region,
                IFNULL(cl.claim_amount, 0) as claim_amount,
                IFNULL(cl.status, 'No Claim') as claim_status,
                sc.calculated_amount as commission_earned
            FROM policies p
            LEFT JOIN clients c ON p.client_id = c.client_id AND c.is_active = 1
            LEFT JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
            LEFT JOIN carriers ca ON pr.carrier_id = ca.carrier_id AND ca.is_active = 1
            LEFT JOIN (
                SELECT policy_id, SUM(quote_approved_amount) as claim_amount, MAX(status) as status
                FROM claims
                WHERE is_active = 1
                GROUP BY policy_id
            ) cl ON p.policy_id = cl.policy_id
            LEFT JOIN (
                SELECT policy_id, SUM(calculated_amount) as calculated_amount
                FROM sales_commissions
                WHERE is_active = 1
                GROUP BY policy_id
            ) sc ON p.policy_id = sc.policy_id
            WHERE p.is_active = 1
        """
        with engine.connect() as conn:
            try:
                row_count = conn.execute(text("SELECT COUNT(*) FROM policies WHERE is_active = 1")).scalar()
                print(f"[db] Database pre-check: {row_count} active policies found in database.")
            except Exception as count_err:
                print(f"[db] Error performing count pre-check: {count_err}")

            df = pd.read_sql(text(query), conn)
        print(f"[db] Loaded {len(df)} rows from MySQL insurance_brokerage schema.")
        return df

    except Exception as e:
        print(f"[db] MySQL error: {e}")
        return None


def _cast(df: pd.DataFrame) -> pd.DataFrame:
    """Apply numeric and date coercions to a raw DataFrame."""
    for col in ['premium_amount', 'claim_amount', 'commission_earned']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    if 'issue_date' in df.columns:
        df['issue_date'] = pd.to_datetime(df['issue_date'], errors='coerce')
    if 'expiry_date' in df.columns:
        df['expiry_date'] = pd.to_datetime(df['expiry_date'], errors='coerce')
    return df


def get_data(force: bool = False) -> pd.DataFrame:
    """
    Return the live dataset.

    Uses a 30-second TTL cache so that rapid tab switches don't each fire a
    full MySQL round-trip, while still guaranteeing fresh data within 30 s of
    any DB commit.  Call ``force_refresh()`` right after a commit to bust the
    cache immediately.
    """
    global _cache_df, _cache_ts, df_global

    now = time.monotonic()
    if not force and _cache_df is not None and (now - _cache_ts) < _CACHE_TTL:
        return _cache_df

    df = _load_from_db()

    if df is None:
        # Fallback to bundled CSV
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            csv_path   = os.path.join(script_dir, "data", "broker_master_data.csv")
            df = pd.read_csv(csv_path)
            print(f"[db] Loaded {len(df)} rows from CSV fallback.")
        except Exception as csv_e:
            print(f"[db] CSV error: {csv_e}")
            return pd.DataFrame()

    df = _cast(df)
    _cache_df = df
    _cache_ts = now
    df_global = df
    return _cache_df


def force_refresh() -> pd.DataFrame:
    """Bust the TTL cache, reload from MySQL, and update df_global in-process."""
    global df_global
    fresh = get_data(force=True)
    df_global = fresh
    return fresh


# df_global is lazily loaded on first request to prevent slow application startup
df_global = None


import logging
from logging.handlers import RotatingFileHandler
from threading import Lock

_loggers = {}
_logger_lock = Lock()

def get_rotating_logger(logger_name: str, log_file: str, max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5) -> logging.Logger:
    """Return a thread-safe logger configured with RotatingFileHandler."""
    with _logger_lock:
        if logger_name in _loggers:
            return _loggers[logger_name]
            
        logger = logging.getLogger(logger_name)
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
            # Standard formatting without extra prefix because our raw strings already contain custom timestamps
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        _loggers[logger_name] = logger
        return logger
