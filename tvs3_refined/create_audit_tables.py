import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def get_engine():
    db_host = os.getenv('DB_HOST', 'localhost')
    db_user = os.getenv('DB_USER', 'root')
    db_password = os.getenv('DB_PASSWORD', 'root')
    db_name = os.getenv('DB_NAME', 'insurance_brokerage')
    return create_engine(f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}")

def init_tables():
    engine = get_engine()
    
    queries = [
        # Table 1: Ingestion Audit Track
        """
        CREATE TABLE IF NOT EXISTS audit_ingestions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            filename VARCHAR(255),
            row_count INT,
            status VARCHAR(100)
        );
        """,
        
        # Table 2: Claim Status Change History
        """
        CREATE TABLE IF NOT EXISTS audit_claim_status_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            claim_number VARCHAR(100),
            old_status VARCHAR(100),
            new_status VARCHAR(100),
            changed_by VARCHAR(100)
        );
        """,
        
        # Table 3: Detailed Dataset Updates
        """
        CREATE TABLE IF NOT EXISTS audit_dataset_updates (
            id INT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            claim_number VARCHAR(100),
            policy_number VARCHAR(100),
            message TEXT
        );
        """,
        
        # Table 4: Dataset Full Revisions
        """
        CREATE TABLE IF NOT EXISTS dataset_revisions (
            revision_id INT AUTO_INCREMENT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            filename VARCHAR(255),
            csv_content LONGTEXT
        );
        """
    ]
    
    print("[db_init] Checking / creating audit and revision tables in database...")
    try:
        with engine.connect() as conn:
            for q in queries:
                conn.execute(text(q))
            conn.execute(text("COMMIT;"))
        print("[db_init] Audit and revision tables initialized successfully.")
    except Exception as e:
        print(f"[db_init] Error initializing database tables: {e}")

if __name__ == "__main__":
    init_tables()
