import pandas as pd
import numpy as np
import random
try:
    from faker import Faker
    fake = Faker('en_IN')
except ImportError:
    fake = None

def main():
    print("Loading Excel file...")
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.abspath(os.path.join(script_dir, "..", "data", "Insurance Sale CS - 2 .xlsx"))
    df = pd.read_excel(input_path, sheet_name='Raw Data')
    
    print("Mapping columns...")
    # Rename columns to match expected dashboard schema
    rename_map = {
        'Created On': 'issue_date',
        'Policy Number': 'policy_number',
        'Insurer Name': 'carrier_name',
        'Premium Amount': 'premium_amount',
        'Status': 'policy_status',
        'Booking Mode': 'distribution_channel',
        'Region Code': 'region'
    }
    df = df.rename(columns=rename_map)
    
    print("Splitting Product category...")
    # Map Product to category and sub_category
    def map_product(prod):
        p = str(prod).lower()
        if 'motor' in p or 'wheeler' in p or 'car' in p or 'bike' in p:
            cat = 'Motor'
            sub = '4W' if 'four' in p or 'car' in p else '2W' if 'two' in p or 'bike' in p else 'CV'
        elif 'health' in p or 'medical' in p:
            cat = 'Health'
            sub = 'Group Medi' if 'group' in p else 'Individual'
        elif 'home' in p or 'property' in p:
            cat = 'Home'
            sub = 'Damage'
        elif 'travel' in p:
            cat = 'Travel'
            sub = 'Overseas' if 'overseas' in p else 'Flight'
        else:
            cat = 'Other'
            sub = str(prod).title()
        return pd.Series([cat, sub])

    if 'Product' in df.columns:
        df[['category', 'sub_category']] = df['Product'].apply(map_product)
    else:
        df['category'] = 'Other'
        df['sub_category'] = 'Other'

    print("Generating dummy data for missing columns...")
    n = len(df)
    
    # client_name and client_type
    client_types = ['Individual/B2C', 'Corporate/B2B']
    c_types = [random.choice(client_types) for _ in range(n)]
    df['client_type'] = c_types
    
    if fake:
        df['client_name'] = [fake.name() if ct == 'Individual/B2C' else fake.company() for ct in c_types]
    else:
        df['client_name'] = [f"Client_{i}" for i in range(n)]
        
    # commission_earned (randomly between 5% and 15% of premium)
    rates = np.random.uniform(0.05, 0.15, n)
    df['commission_earned'] = (df['premium_amount'] * rates).round(2)
    
    # claim_amount & claim_status (about 10% have claims)
    has_claim = np.random.choice([True, False], n, p=[0.1, 0.9])
    df['claim_amount'] = np.where(has_claim, (df['premium_amount'] * np.random.uniform(0.5, 2.0, n)).round(2), 0)
    df['claim_status'] = np.where(has_claim, np.random.choice(['Registered', 'Approved', 'Settled'], n), 'No Claim')
    
    # expiry_date (1 year after issue_date)
    df['issue_date'] = pd.to_datetime(df['issue_date'], errors='coerce')
    df['expiry_date'] = df['issue_date'] + pd.DateOffset(years=1)
    
    # Ensure policy_status matches roughly
    status_map = {
        'closed': 'Active',
        'won': 'Active',
        'lost': 'Cancelled',
        'active': 'Active',
        'expired': 'Expired',
        'renewed': 'Renewed',
        'cancelled': 'Cancelled'
    }
    df['policy_status'] = df['policy_status'].apply(lambda x: status_map.get(str(x).lower().strip(), str(x).title()))

    # Write to CSV
    expected_cols = [
        'policy_number', 'client_name', 'client_type', 'carrier_name', 
        'category', 'sub_category', 'issue_date', 'expiry_date', 
        'premium_amount', 'policy_status', 'distribution_channel', 
        'claim_amount', 'claim_status', 'commission_earned', 'region'
    ]
    final_cols = [c for c in expected_cols if c in df.columns]
    
    output_file = os.path.abspath(os.path.join(script_dir, "..", "data", "new_kaggle.csv"))
    df[final_cols].to_csv(output_file, index=False)
    print(f"Successfully transformed {n} rows and saved to {output_file}!")

if __name__ == "__main__":
    main()
