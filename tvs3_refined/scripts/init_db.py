"""
Run once to load VehicleInsuranceData.csv into MySQL.
Usage: python init_db.py
Reads credentials from .env file (copy .env.example → .env first).
"""
import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

def load_data_to_mysql(csv_path=None):
    if csv_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.abspath(os.path.join(script_dir, "..", "data", "VehicleInsuranceData.csv"))
    print("Loading CSV data…")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows.")

    db_user     = os.getenv('DB_USER', 'root')
    db_password = os.getenv('DB_PASSWORD', 'root')
    db_host     = os.getenv('DB_HOST', 'localhost')
    db_name     = os.getenv('DB_NAME', 'vehicle_insurance')

    try:
        engine = create_engine(
            f'mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}'
        )
        df.to_sql('vehicle_insurance', con=engine, if_exists='replace', index=False)
        print("Data loaded successfully into MySQL.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    load_data_to_mysql()
