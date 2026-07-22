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
            f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}",
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )
    return _engine

def _load_from_db() -> pd.DataFrame | None:
    """Execute the claims query and return a DataFrame, or None on error."""
    try:
        from sqlalchemy import text
        engine = _get_engine()
        with engine.connect() as conn:
            df = pd.read_sql(text("SELECT * FROM claims"), conn)
        print(f"[db] Loaded {len(df)} rows from MySQL.")
        return df

    except Exception as e:
        print(f"[db] MySQL error: {e}")
        return None


_motor_cache_df = None
_motor_cache_ts = 0.0

def get_motor_claims_data(force: bool = False) -> pd.DataFrame:
    """Fetch 67-column Motor claims operational dataset from MySQL."""
    global _motor_cache_df, _motor_cache_ts
    now = time.monotonic()
    if not force and _motor_cache_df is not None and (now - _motor_cache_ts) < _CACHE_TTL:
        return _motor_cache_df
    try:
        from sqlalchemy import text
        engine = _get_engine()
        with engine.connect() as conn:
            df = pd.read_sql(text("SELECT * FROM motor_claims_detailed"), conn)
        print(f"[db] Loaded {len(df)} motor claims from MySQL.")
        _motor_cache_df = df
        _motor_cache_ts = now
        return df
    except Exception as e:
        print(f"[db] MySQL motor_claims_detailed error: {e}")
        return pd.DataFrame()


def _cast(df: pd.DataFrame) -> pd.DataFrame:
    """Apply numeric and date coercions to a raw DataFrame."""
    for col in ['estimate', 'claim_settlement_amount', 'estimate_of_loss']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    for col in ['date_of_loss_date_of_admission', 'month_of_claim']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
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


# df_global is eagerly pre-warmed in a background thread so the first browser
# request hits the in-memory cache instead of waiting for a full MySQL round-trip.
df_global = None


def _prewarm_cache() -> None:
    """Background thread target: load data into cache and warm up Plotly at server startup."""
    try:
        get_data(force=True)
        print("[db] Background pre-warm: claims data loaded.")
    except Exception as e:
        print(f"[db] Background pre-warm data error: {e}")

    # Trigger Plotly's lazy import chain so it completes during boot,
    # not on the first user click (which would add ~2-4 seconds to the response).
    try:
        import pandas as _pd
        import plotly.express as _px
        _dummy = _px.pie(_pd.DataFrame({'v': [1], 'n': ['x']}), values='v', names='n')
        del _dummy, _px, _pd
        print("[db] Background pre-warm: Plotly warmed up.")
    except Exception as e:
        print(f"[db] Background pre-warm Plotly error: {e}")


import threading as _threading
_prewarm_thread = _threading.Thread(target=_prewarm_cache, daemon=True, name="db-prewarm")
_prewarm_thread.start()


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
