import os
import pandas as pd
import numpy as np
import random
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

from faker import Faker
fake = Faker('en_IN')



# Database connection
db_host = os.getenv('DB_HOST', 'localhost')
db_user = os.getenv('DB_USER', 'root')
db_password = os.getenv('DB_PASSWORD', 'root')
db_name = os.getenv('DB_NAME', 'insurance_brokerage')

engine = create_engine(f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}")

def generate_mock_data():
    print("Dropping existing tables to refresh schema...")
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        tables = ['sales_commissions', 'commission_rates', 'claims', 'policies', 'products', 'backoffice_users', 'carriers', 'clients']
        for t in tables:
            conn.execute(text(f"DROP TABLE IF EXISTS {t};"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        try: conn.commit()
        except: pass
        
    print("Generating mock data...")

    regions = [
        ('MH', 'Maharashtra'),
        ('DL', 'Delhi'),
        ('TN', 'Tamil Nadu'),
        ('KA', 'Karnataka'),
        ('UP', 'Uttar Pradesh'),
        ('GJ', 'Gujarat'),
        ('WB', 'West Bengal')
    ]

    # 1. Clients
    clients_data = []
    for i in range(500):
        client_type = random.choice(['Individual/B2C', 'Corporate/B2B'])
        name = fake.name() if client_type == 'Individual/B2C' else fake.company()
        rc, rn = random.choice(regions)
        clients_data.append({
            'client_id': i + 1,
            'client_type': client_type,
            'name': name,
            'email': fake.email(),
            'phone': fake.phone_number()[:20],
            'address': fake.city(),
            'region_code': rc,
            'region_name': rn
        })
    df_clients = pd.DataFrame(clients_data)

    # 2. Carriers
    carriers = ['TATA AIG', 'ICICI Lombard', 'United India', 'New India Assurance', 'HDFC ERGO', 'Bajaj Allianz']
    df_carriers = pd.DataFrame({'carrier_id': range(1, len(carriers) + 1), 'carrier_name': carriers})

    # 3. Backoffice Users
    users = ['arun.kumar', 'priya.sharma', 'rahul.verma', 'sneha.patel']
    df_users = pd.DataFrame({'user_id': range(1, len(users) + 1), 'username': users, 'system_role': 'ITS System'})

    # 4. Products
    products_data = []
    categories = ['Motor', 'Health', 'Home', 'Travel']
    sub_categories = {
        'Motor': ['2W', '4W', 'CV'],
        'Health': ['Individual', 'Group Medi'],
        'Home': ['Theft', 'Damage'],
        'Travel': ['Flight', 'Overseas']
    }
    prod_id = 1
    for carrier_id in range(1, len(carriers) + 1):
        for cat in categories:
            for sub in sub_categories[cat]:
                products_data.append({
                    'product_id': prod_id,
                    'carrier_id': carrier_id,
                    'category': cat,
                    'sub_category': sub
                })
                prod_id += 1
    df_products = pd.DataFrame(products_data)

    with engine.connect() as conn:
        df_clients.to_sql('clients', con=conn, if_exists='append', index=False)
        df_carriers.to_sql('carriers', con=conn, if_exists='append', index=False)
        df_users.to_sql('backoffice_users', con=conn, if_exists='append', index=False)
        df_products.to_sql('products', con=conn, if_exists='append', index=False)
        
        # Get generated IDs
        client_ids = [r[0] for r in conn.execute(text("SELECT client_id FROM clients")).fetchall()]
        product_ids = [r[0] for r in conn.execute(text("SELECT product_id FROM products")).fetchall()]
        user_ids = [r[0] for r in conn.execute(text("SELECT user_id FROM backoffice_users")).fetchall()]

    # 5. Policies
    policies_data = []
    for i in range(1000):
        issue_date = fake.date_between(start_date='-2y', end_date='today')
        expiry_date = fake.date_between_dates(date_start=issue_date, date_end=issue_date.replace(year=issue_date.year + 1))
        policies_data.append({
            'policy_id': i + 1,
            'policy_number': f"POL-{fake.unique.random_number(digits=8)}",
            'client_id': random.choice(client_ids),
            'product_id': random.choice(product_ids),
            'created_by_user_id': random.choice(user_ids),
            'issue_date': issue_date,
            'expiry_date': expiry_date,
            'premium_amount': round(random.uniform(5000, 50000), 2),
            'status': random.choice(['Active', 'Expired', 'Renewed', 'Cancelled']),
            'distribution_channel': random.choice(['Direct', 'Broker', 'Agency', 'Online'])
        })
    df_policies = pd.DataFrame(policies_data)
    
    with engine.connect() as conn:
        df_policies.to_sql('policies', con=conn, if_exists='append', index=False)
        policy_ids = [r[0] for r in conn.execute(text("SELECT policy_id FROM policies")).fetchall()]

    # 6. Claims
    claims_data = []
    claim_id = 1
    for policy_id in random.sample(policy_ids, 200):  # 200 claims
        reg_date = fake.date_between(start_date='-1y', end_date='today')
        claims_data.append({
            'claim_id': claim_id,
            'policy_id': policy_id,
            'claim_number': f"CLM-{fake.unique.random_number(digits=7)}",
            'registered_date': reg_date,
            'quote_approved_amount': round(random.uniform(1000, 40000), 2),
            'status': random.choice(['Registered', 'Under Review', 'Approved', 'Rejected', 'Settled'])
        })
        claim_id += 1
    df_claims = pd.DataFrame(claims_data)

    # 7. Commission Rates
    rates_data = []
    rate_id = 1
    for cat in categories:
        for sub in sub_categories[cat]:
            rates_data.append({
                'rate_id': rate_id,
                'category': cat,
                'sub_category': sub,
                'base_rate_percent': round(random.uniform(5.0, 15.0), 2)
            })
            rate_id += 1
    df_rates = pd.DataFrame(rates_data)

    with engine.connect() as conn:
        df_claims.to_sql('claims', con=conn, if_exists='append', index=False)
        df_rates.to_sql('commission_rates', con=conn, if_exists='append', index=False)
        
    # 8. Sales Commissions
    comm_data = []
    comm_id = 1
    # Dynamic commission rates instead of a flat 10%
    for p in policies_data:
        rate = round(random.uniform(0.08, 0.18), 3)
        comm_data.append({
            'commission_id': comm_id,
            'policy_id': p['policy_id'],
            'calculated_amount': round(p['premium_amount'] * rate, 2),
            'status': 'Received'
        })
        comm_id += 1
    df_comm = pd.DataFrame(comm_data)
    
    with engine.connect() as conn:
        df_comm.to_sql('sales_commissions', con=conn, if_exists='append', index=False)

    print("Successfully generated and loaded mock data into the insurance_brokerage database.")
    
    # Generate the flattened CSV for fallback/upload testing
    print("Generating flattened CSV (broker_master_data.csv) for dashboard fallback...")
    with engine.connect() as conn:
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
            JOIN clients c ON p.client_id = c.client_id
            JOIN products pr ON p.product_id = pr.product_id
            JOIN carriers ca ON pr.carrier_id = ca.carrier_id
            LEFT JOIN (SELECT policy_id, SUM(quote_approved_amount) as claim_amount, status FROM claims GROUP BY policy_id, status) cl ON p.policy_id = cl.policy_id
            LEFT JOIN sales_commissions sc ON p.policy_id = sc.policy_id
        """
        flattened_df = pd.read_sql(text(query), conn)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_out_path = os.path.abspath(os.path.join(script_dir, "..", "data", "broker_master_data.csv"))
        main_out_path = os.path.abspath(os.path.join(script_dir, "..", "data", "MAIN.csv"))
        flattened_df.to_csv(csv_out_path, index=False)
        flattened_df.to_csv(main_out_path, index=False)
        print("Created broker_master_data.csv and MAIN.csv successfully!")

def load_live_kaggle_data():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.abspath(os.path.join(script_dir, "..", "data", "new_kaggle.csv"))
    
    if not os.path.exists(csv_path):
        print(f"[loader] Live Kaggle dataset not found at {csv_path}. Falling back to generate mock data.")
        generate_mock_data()
        return

    print(f"[loader] Loading live Kaggle dataset from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # 1. Clean data and apply date offset shift
    # 1. Clean data and apply staggered date offset to get a realistic status mix
    today = pd.Timestamp.now().normalize()
    
    # We will distribute issue dates over the last 500 days to get a realistic status mix
    # of Active, Expired, and Renewed policies, instead of them all expiring on the same day.
    np.random.seed(42)  # For deterministic behavior
    random_days = np.random.randint(0, 500, size=len(df))
    
    df['issue_date'] = today - pd.to_timedelta(random_days, unit='D')
    df['expiry_date'] = df['issue_date'] + pd.DateOffset(years=1)
    print(f"[loader] Staggered simulation issue dates over the last 500 days to align with today ({today.strftime('%Y-%m-%d')}).")


    # Convert back to strings for MySQL storage
    df['issue_date_str'] = df['issue_date'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df['expiry_date_str'] = df['expiry_date'].dt.strftime('%Y-%m-%d %H:%M:%S')

    # Normalize numeric columns
    df['premium_amount'] = pd.to_numeric(df['premium_amount'], errors='coerce').fillna(0.0)
    df['claim_amount'] = pd.to_numeric(df['claim_amount'], errors='coerce').fillna(0.0)
    df['commission_earned'] = pd.to_numeric(df['commission_earned'], errors='coerce').fillna(0.0)
    
    for col in df.select_dtypes(include=['object']):
        if col not in ['policy_number', 'client_name', 'issue_date_str', 'expiry_date_str']:
            df[col] = df[col].astype(str).str.strip().str.title()

    # 2. Map status to the 4 standard statuses (deterministic using hash of policy number)
    def determine_status(row):
        status_str = str(row['policy_status']).lower().strip()
        prem = float(row['premium_amount'])
        carrier = str(row['carrier_name']).lower()
        
        # Lead / unassigned carrier / 0 premium -> Cancelled
        if 'lead' in status_str or prem <= 0 or pd.isna(row['carrier_name']) or carrier in ['', 'nan', 'none']:
            return 'Cancelled'
            
        if any(x in status_str for x in ['lost', 'cancel', 'reject', 'lapse']):
            return 'Cancelled'
            
        # Compare shifted expiry with today
        exp = row['expiry_date']
        if exp < today:
            # Expired: map to Renewed or Expired deterministically using policy_number hash
            val = hash(str(row['policy_number'])) % 10
            if val < 4:
                return 'Renewed' # 40% renewal rate
            else:
                return 'Expired' # 60% expiration rate
        else:
            # Active
            # Let's keep 98% Active, 2% Cancelled
            val = hash(str(row['policy_number'])) % 100
            if val < 98:
                return 'Active'
            else:
                return 'Cancelled'

    df['mapped_status'] = df.apply(determine_status, axis=1)

    print("[loader] Dropping existing tables to refresh schema...")
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        tables = ['sales_commissions', 'commission_rates', 'claims', 'policies', 'products', 'backoffice_users', 'carriers', 'clients']
        for t in tables:
            conn.execute(text(f"DROP TABLE IF EXISTS {t};"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        try: conn.commit()
        except: pass

    # 3. Load relational data

    # 3.1 Clients
    region_map = {
        'MH': 'Maharashtra',
        'DL': 'Delhi',
        'TN': 'Tamil Nadu',
        'KA': 'Karnataka',
        'UP': 'Uttar Pradesh',
        'GJ': 'Gujarat',
        'WB': 'West Bengal',
        'TS': 'Telangana',
        'AP': 'Andhra Pradesh',
        'AR': 'Arunachal Pradesh',
        'AN': 'Andaman and Nicobar',
        'KL': 'Kerala'
    }
    
    unique_clients = df[['client_name', 'client_type', 'region']].drop_duplicates(subset=['client_name']).copy()
    clients_list = []
    client_name_to_id = {}
    
    for idx, row in enumerate(unique_clients.itertuples()):
        client_id = idx + 1
        name = row.client_name
        c_type = row.client_type if pd.notna(row.client_type) else 'Individual/B2C'
        
        # Region
        raw_reg = str(row.region).strip().upper() if pd.notna(row.region) else 'DL'
        r_code = raw_reg[:2]
        r_name = region_map.get(r_code, 'Other')
        if r_name == 'Other':
            r_name = raw_reg
            
        clients_list.append({
            'client_id': client_id,
            'client_type': c_type,
            'name': name,
            'email': f"{str(name).lower().replace(' ', '.').replace(',', '')}@example.com",
            'phone': f"+91 {9800000000 + client_id}",
            'address': f"{r_name} Area",
            'region_code': r_code,
            'region_name': r_name
        })
        client_name_to_id[name] = client_id
        
    df_clients = pd.DataFrame(clients_list)

    # 3.2 Carriers
    unique_carriers = df['carrier_name'].dropna().unique()
    carriers_list = []
    carrier_name_to_id = {}
    
    for idx, cname in enumerate(unique_carriers):
        carrier_id = idx + 1
        carriers_list.append({
            'carrier_id': carrier_id,
            'carrier_name': cname
        })
        carrier_name_to_id[cname] = carrier_id
        
    unassigned_id = len(unique_carriers) + 1
    carriers_list.append({
        'carrier_id': unassigned_id,
        'carrier_name': 'Unassigned'
    })
    carrier_name_to_id['Unassigned'] = unassigned_id
    
    df_carriers = pd.DataFrame(carriers_list)

    # 3.3 Backoffice Users
    users = ['arun.kumar', 'priya.sharma', 'rahul.verma', 'sneha.patel']
    df_users = pd.DataFrame({'user_id': range(1, len(users) + 1), 'username': users, 'system_role': 'ITS System'})
    user_ids = list(range(1, len(users) + 1))

    # 3.4 Products
    df_temp = df.copy()
    df_temp['carrier_name'] = df_temp['carrier_name'].fillna('Unassigned')
    
    unique_prods = df_temp[['carrier_name', 'category', 'sub_category']].drop_duplicates().copy()
    products_list = []
    prod_lookup = {}
    
    for idx, row in enumerate(unique_prods.itertuples()):
        product_id = idx + 1
        carrier_id = carrier_name_to_id.get(row.carrier_name, unassigned_id)
        cat = row.category if pd.notna(row.category) else 'Other'
        sub = row.sub_category if pd.notna(row.sub_category) else 'Other'
        
        products_list.append({
            'product_id': product_id,
            'carrier_id': carrier_id,
            'category': cat,
            'sub_category': sub
        })
        prod_lookup[(row.carrier_name, cat, sub)] = product_id
        
    df_products = pd.DataFrame(products_list)

    with engine.connect() as conn:
        df_clients.to_sql('clients', con=conn, if_exists='append', index=False)
        df_carriers.to_sql('carriers', con=conn, if_exists='append', index=False)
        df_users.to_sql('backoffice_users', con=conn, if_exists='append', index=False)
        df_products.to_sql('products', con=conn, if_exists='append', index=False)

    # 3.5 Policies
    policies_list = []
    policy_lookup = {}
    
    for idx, row in enumerate(df.itertuples()):
        policy_id = idx + 1
        p_num = row.policy_number if pd.notna(row.policy_number) else f"POL-{100000 + policy_id}"
        
        c_name = row.client_name
        client_id = client_name_to_id.get(c_name, 1)
        
        carrier = row.carrier_name if pd.notna(row.carrier_name) else 'Unassigned'
        cat = row.category if pd.notna(row.category) else 'Other'
        sub = row.sub_category if pd.notna(row.sub_category) else 'Other'
        product_id = prod_lookup.get((carrier, cat, sub), 1)
        
        user_id = user_ids[policy_id % len(user_ids)]
        
        policies_list.append({
            'policy_id': policy_id,
            'policy_number': p_num,
            'client_id': client_id,
            'product_id': product_id,
            'created_by_user_id': user_id,
            'issue_date': row.issue_date_str,
            'expiry_date': row.expiry_date_str,
            'premium_amount': float(row.premium_amount),
            'status': row.mapped_status,
            'distribution_channel': row.distribution_channel if pd.notna(row.distribution_channel) else 'Online'
        })
        policy_lookup[p_num] = policy_id
        
    df_policies = pd.DataFrame(policies_list)
    
    with engine.connect() as conn:
        df_policies.to_sql('policies', con=conn, if_exists='append', index=False)

    # 3.6 Claims
    claims_list = []
    claim_id = 1
    
    for idx, row in enumerate(df.itertuples()):
        claim_amt = float(row.claim_amount)
        if claim_amt > 0:
            p_num = row.policy_number
            policy_id = policy_lookup.get(p_num, idx + 1)
            
            c_status = row.claim_status if pd.notna(row.claim_status) else 'Approved'
            if c_status == 'No Claim':
                c_status = 'Approved'
                
            claims_list.append({
                'claim_id': claim_id,
                'policy_id': policy_id,
                'claim_number': f"CLM-{300000 + claim_id}",
                'registered_date': row.issue_date_str,
                'quote_approved_amount': claim_amt,
                'status': c_status
            })
            claim_id += 1
            
    df_claims = pd.DataFrame(claims_list)

    # 3.7 Commission rates
    rates_list = []
    rate_id = 1
    for cat in df['category'].dropna().unique():
        for sub in df[df['category'] == cat]['sub_category'].dropna().unique():
            rates_list.append({
                'rate_id': rate_id,
                'category': cat,
                'sub_category': sub,
                'base_rate_percent': 10.0
            })
            rate_id += 1
    df_rates = pd.DataFrame(rates_list)

    # 3.8 Sales commissions
    commissions_list = []
    comm_id = 1
    for idx, row in enumerate(df.itertuples()):
        p_num = row.policy_number
        policy_id = policy_lookup.get(p_num, idx + 1)
        comm_amt = float(row.commission_earned)
        
        commissions_list.append({
            'commission_id': comm_id,
            'policy_id': policy_id,
            'calculated_amount': comm_amt,
            'status': 'Received'
        })
        comm_id += 1
        
    df_comm = pd.DataFrame(commissions_list)

    with engine.connect() as conn:
        if not df_claims.empty:
            df_claims.to_sql('claims', con=conn, if_exists='append', index=False)
        if not df_rates.empty:
            df_rates.to_sql('commission_rates', con=conn, if_exists='append', index=False)
        if not df_comm.empty:
            df_comm.to_sql('sales_commissions', con=conn, if_exists='append', index=False)

    print(f"[loader] Successfully loaded {len(df_policies)} records from live Kaggle dataset into MySQL.")

    # Re-generate fallback CSV
    print("[loader] Generating flattened CSV (broker_master_data.csv) for dashboard fallback...")
    with engine.connect() as conn:
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
            JOIN clients c ON p.client_id = c.client_id
            JOIN products pr ON p.product_id = pr.product_id
            JOIN carriers ca ON pr.carrier_id = ca.carrier_id
            LEFT JOIN (SELECT policy_id, SUM(quote_approved_amount) as claim_amount, status FROM claims GROUP BY policy_id, status) cl ON p.policy_id = cl.policy_id
            LEFT JOIN sales_commissions sc ON p.policy_id = sc.policy_id
        """
        flattened_df = pd.read_sql(text(query), conn)
        csv_out_path = os.path.abspath(os.path.join(script_dir, "..", "data", "broker_master_data.csv"))
        flattened_df.to_csv(csv_out_path, index=False)
        print(f"[loader] Created {csv_out_path} successfully!")

if __name__ == "__main__":
    generate_mock_data()


