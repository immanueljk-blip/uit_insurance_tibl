import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

def get_data():
    db_host     = os.getenv('DB_HOST', 'localhost')
    db_user     = os.getenv('DB_USER', 'root')
    db_password = os.getenv('DB_PASSWORD', 'root')
    db_name     = os.getenv('DB_NAME', 'insurance_brokerage')

    df = None
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(
            f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}",
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10},
        )
        
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
            # 1. Perform COUNT pre-check first
            try:
                row_count = conn.execute(text("SELECT COUNT(*) FROM policies WHERE is_active = 1")).scalar()
                print(f"[db] Database pre-check: {row_count} active policies found in database.")
            except Exception as count_err:
                print(f"[db] Error performing count pre-check: {count_err}")
                row_count = 0
            
            # 2. Execute full raw data query
            df = pd.read_sql(text(query), conn)
        print(f"[db] Loaded {len(df)} rows from MySQL insurance_brokerage schema.")
    except Exception as e:
        print(f"[db] MySQL error: {e}")
        print("[db] Falling back to CSV …")

    if df is None:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            csv_path = os.path.join(script_dir, "data", "broker_master_data.csv")
            df = pd.read_csv(csv_path)
            print(f"[db] Loaded {len(df)} rows from CSV fallback.")
        except Exception as csv_e:
            print(f"[db] CSV error: {csv_e}")
            return pd.DataFrame()  

    # --- Cast numerics ---
    numeric_cols = ['premium_amount', 'claim_amount', 'commission_earned']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    # Dates
    if 'issue_date' in df.columns:
        df['issue_date'] = pd.to_datetime(df['issue_date'], errors='coerce')
    if 'expiry_date' in df.columns:
        df['expiry_date'] = pd.to_datetime(df['expiry_date'], errors='coerce')

    return df

df_global = get_data()

