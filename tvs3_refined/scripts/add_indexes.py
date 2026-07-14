import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def add_indexes():
    db_host = os.getenv('DB_HOST', 'localhost')
    db_user = os.getenv('DB_USER', 'root')
    db_password = os.getenv('DB_PASSWORD', 'root')
    db_name = os.getenv('DB_NAME', 'insurance_brokerage')
    
    engine = create_engine(f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}")
    
    # We will check table columns and add Primary Keys / Indexes
    commands = [
        # clients
        "ALTER TABLE clients MODIFY COLUMN client_id INT;",
        "ALTER TABLE clients ADD PRIMARY KEY (client_id);",
        "ALTER TABLE clients ADD INDEX idx_clients_active (is_active);",
        
        # carriers
        "ALTER TABLE carriers MODIFY COLUMN carrier_id INT;",
        "ALTER TABLE carriers ADD PRIMARY KEY (carrier_id);",
        "ALTER TABLE carriers ADD INDEX idx_carriers_active (is_active);",
        
        # products
        "ALTER TABLE products MODIFY COLUMN product_id INT;",
        "ALTER TABLE products ADD PRIMARY KEY (product_id);",
        "ALTER TABLE products ADD INDEX idx_products_active (is_active);",
        "ALTER TABLE products ADD INDEX idx_products_carrier (carrier_id);",
        
        # policies
        "ALTER TABLE policies MODIFY COLUMN policy_id INT;",
        "ALTER TABLE policies ADD PRIMARY KEY (policy_id);",
        "ALTER TABLE policies ADD INDEX idx_policies_client (client_id);",
        "ALTER TABLE policies ADD INDEX idx_policies_product (product_id);",
        "ALTER TABLE policies ADD INDEX idx_policies_active (is_active);",
        "ALTER TABLE policies MODIFY COLUMN policy_number VARCHAR(255);",
        "ALTER TABLE policies ADD INDEX idx_policies_number (policy_number);",
        
        # claims
        "ALTER TABLE claims MODIFY COLUMN claim_id INT;",
        "ALTER TABLE claims ADD PRIMARY KEY (claim_id);",
        "ALTER TABLE claims ADD INDEX idx_claims_policy (policy_id);",
        "ALTER TABLE claims ADD INDEX idx_claims_active (is_active);",
        
        # sales_commissions
        "ALTER TABLE sales_commissions MODIFY COLUMN commission_id INT;",
        "ALTER TABLE sales_commissions ADD PRIMARY KEY (commission_id);",
        "ALTER TABLE sales_commissions ADD INDEX idx_commissions_policy (policy_id);",
        "ALTER TABLE sales_commissions ADD INDEX idx_commissions_active (is_active);",

        # backoffice_users
        "ALTER TABLE backoffice_users MODIFY COLUMN user_id INT;",
        "ALTER TABLE backoffice_users ADD PRIMARY KEY (user_id);",
        "ALTER TABLE backoffice_users ADD INDEX idx_backoffice_users_active (is_active);",

        # commission_rates
        "ALTER TABLE commission_rates MODIFY COLUMN rate_id INT;",
        "ALTER TABLE commission_rates ADD PRIMARY KEY (rate_id);",
        "ALTER TABLE commission_rates ADD INDEX idx_commission_rates_active (is_active);"
    ]
    
    print("[indexes] Connecting to database to apply schema and index optimizations...")
    with engine.connect() as conn:
        for cmd in commands:
            # We wrap in try-except in case PK/index already exists
            try:
                print(f"[indexes] Executing: {cmd}")
                conn.execute(text(cmd))
                conn.execute(text("COMMIT;"))
            except Exception as e:
                print(f"[indexes] Skip or Error: {e}")
                
    print("[indexes] Indexing operations completed.")

if __name__ == "__main__":
    add_indexes()
