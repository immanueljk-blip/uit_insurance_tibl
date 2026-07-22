import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import db

load_dotenv()

import create_audit_tables
create_audit_tables.init_tables()

def get_engine():
    db_host = os.getenv('DB_HOST', 'localhost')
    db_user = os.getenv('DB_USER', 'root')
    db_password = os.getenv('DB_PASSWORD', 'root')
    db_name = os.getenv('DB_NAME', 'insurance_brokerage')
    return create_engine(f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}")

def write_df_to_mysql(df):
    """
    Normalized relational data loading pipeline.
    Parses a flat DataFrame and loads it into the MySQL database tables:
    clients, carriers, backoffice_users, products, policies, claims, commission_rates, sales_commissions.
    Appends only new policy records, neglects duplicate records, and logs/updates claim status changes.
    Returns a summary dict describing the operations performed.
    """
    engine = get_engine()
    
    summary: dict = {
        'appended_count': 0,
        'duplicates': [],
        'updates': []
    }
    
    # 1. Clean data and normalize types
    today = pd.Timestamp.now().normalize()
    
    # Ensure all expected columns exist with sensible defaults if missing
    defaults = {
        'policy_number': 'POL-Unknown',
        'client_name': 'Unknown Client',
        'client_type': 'Individual/B2C',
        'carrier_name': 'Unassigned',
        'category': 'Other',
        'sub_category': 'Other',
        'premium_amount': 0.0,
        'claim_amount': 0.0,
        'commission_earned': 0.0,
        'policy_status': 'Active',
        'region': 'DL',
        'distribution_channel': 'Online',
        'claim_status': 'No Claim'
    }
    for col, default_val in defaults.items():
        if col not in df.columns:
            # Try case-insensitive match first
            found = False
            for c in df.columns:
                if c.lower() == col.lower():
                    df = df.rename(columns={c: col})
                    found = True
                    break
            if not found:
                df[col] = default_val
    
    # Normalize numeric columns
    df['premium_amount'] = pd.to_numeric(df['premium_amount'], errors='coerce').fillna(0.0)  # type: ignore
    df['claim_amount'] = pd.to_numeric(df['claim_amount'], errors='coerce').fillna(0.0)  # type: ignore
    df['commission_earned'] = pd.to_numeric(df['commission_earned'], errors='coerce').fillna(0.0)  # type: ignore
    
    # Ensure dates are strings for database consistency if needed
    if 'issue_date' in df.columns:
        df['issue_date'] = pd.to_datetime(df['issue_date'], errors='coerce')
        df['issue_date_str'] = df['issue_date'].dt.strftime('%Y-%m-%d %H:%M:%S')  # type: ignore
    else:
        df['issue_date'] = today
        df['issue_date_str'] = today.strftime('%Y-%m-%d %H:%M:%S')

    if 'expiry_date' in df.columns:
        df['expiry_date'] = pd.to_datetime(df['expiry_date'], errors='coerce')
        df['expiry_date_str'] = df['expiry_date'].dt.strftime('%Y-%m-%d %H:%M:%S')  # type: ignore
    else:
        df['expiry_date'] = df['issue_date'] + pd.DateOffset(years=1)
        df['expiry_date_str'] = df['expiry_date'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
    for col in df.select_dtypes(include=['object']):
        if col not in ['policy_number', 'client_name', 'issue_date_str', 'expiry_date_str']:
            df[col] = df[col].astype(str).str.strip().str.title()

    # 2. Re-map policy statuses to standards
    def determine_status(row):
        status_str = str(row.get('policy_status', 'Active')).lower().strip()
        prem = float(row.get('premium_amount', 0))
        carrier = str(row.get('carrier_name', '')).lower()
        
        if 'lead' in status_str or prem <= 0 or pd.isna(row.get('carrier_name')) or carrier in ['', 'nan', 'none']:
            return 'Cancelled'
        if any(x in status_str for x in ['lost', 'cancel', 'reject', 'lapse']):
            return 'Cancelled'
            
        exp = row['expiry_date']
        if pd.notna(exp) and exp < today:
            val = hash(str(row.get('policy_number', ''))) % 10
            return 'Renewed' if val < 4 else 'Expired'
        else:
            val = hash(str(row.get('policy_number', ''))) % 100
            return 'Active' if val < 98 else 'Cancelled'

    df['mapped_status'] = df.apply(determine_status, axis=1)

    print("[db_writer] Connecting to database and fetching existing active records for incremental merge...")
    with engine.connect() as conn:
        # Load existing active policies with all columns for comparison
        policies_query = text("SELECT policy_id, policy_number, client_id, product_id, created_by_user_id, issue_date, expiry_date, premium_amount, status, distribution_channel FROM policies WHERE is_active = 1")
        existing_policies_df = pd.read_sql(policies_query, conn)
        existing_policies = {row.policy_number.strip().upper(): row for row in existing_policies_df.itertuples()}
        
        # Load existing active claims with all columns for comparison
        claims_query = text("SELECT claim_id, policy_id, claim_number, quote_approved_amount, status FROM claims WHERE is_active = 1")
        existing_claims_df = pd.read_sql(claims_query, conn)
        existing_claims = {row.policy_id: row for row in existing_claims_df.itertuples()}
        
        # Load clients with all columns for comparison
        clients_query = text("SELECT client_id, name, client_type, region_code, region_name, address FROM clients WHERE is_active = 1")
        existing_clients_df = pd.read_sql(clients_query, conn)
        existing_clients = {row.name.strip().upper(): row.client_id for row in existing_clients_df.itertuples()}
        existing_clients_details = {row.client_id: row for row in existing_clients_df.itertuples()}
        
        # Load carriers
        carriers_query = text("SELECT carrier_id, carrier_name FROM carriers WHERE is_active = 1")
        existing_carriers_df = pd.read_sql(carriers_query, conn)
        existing_carriers = {row.carrier_name.strip().upper(): row.carrier_id for row in existing_carriers_df.itertuples()}
        
        # Load products
        products_query = text("SELECT product_id, carrier_id, category, sub_category FROM products WHERE is_active = 1")
        existing_products_df = pd.read_sql(products_query, conn)
        existing_products = {
            (row.carrier_id, row.category.strip().upper(), row.sub_category.strip().upper()): row.product_id 
            for row in existing_products_df.itertuples()
        }
        
        # Load backoffice users
        users_query = text("SELECT user_id, username FROM backoffice_users WHERE is_active = 1")
        existing_users_df = pd.read_sql(users_query, conn)
        existing_users = {row.username.strip().lower(): row.user_id for row in existing_users_df.itertuples()}
        
        # Load commission rates
        rates_query = text("SELECT rate_id, category, sub_category FROM commission_rates WHERE is_active = 1")
        existing_rates_df = pd.read_sql(rates_query, conn)
        existing_rates = {
            (row.category.strip().upper(), row.sub_category.strip().upper()): row.rate_id
            for row in existing_rates_df.itertuples()
        }

        # Load existing sales commissions for comparison
        commissions_query = text("SELECT commission_id, policy_id, calculated_amount, status FROM sales_commissions WHERE is_active = 1")
        existing_commissions_df = pd.read_sql(commissions_query, conn)
        existing_commissions = {row.policy_id: row for row in existing_commissions_df.itertuples()}

        # Query max IDs from ALL records (active and inactive) for safe key generation
        max_ids: dict[str, int] = {}
        for id_col, table in [
            ('client_id', 'clients'),
            ('carrier_id', 'carriers'),
            ('product_id', 'products'),
            ('user_id', 'backoffice_users'),
            ('policy_id', 'policies'),
            ('claim_id', 'claims'),
            ('commission_id', 'sales_commissions'),
            ('rate_id', 'commission_rates')
        ]:
            try:
                val = conn.execute(text(f"SELECT COALESCE(MAX({id_col}), 0) FROM {table}")).scalar()
            except Exception:
                val = 0
            max_ids[id_col] = val

    # Setup backoffice users if none exist in the database
    user_ids = list(existing_users.values())
    if not user_ids:
        users = ['arun.kumar', 'priya.sharma', 'rahul.verma', 'sneha.patel']
        users_to_insert = []
        for idx, username in enumerate(users):
            new_uid = max_ids['user_id'] + 1 + idx
            users_to_insert.append({
                'user_id': new_uid,
                'username': username,
                'system_role': 'ITS System',
                'is_active': 1
            })
            existing_users[username.strip().lower()] = new_uid
            user_ids.append(new_uid)
        
        with engine.connect() as conn:
            pd.DataFrame(users_to_insert).to_sql('backoffice_users', con=conn, if_exists='append', index=False)
            conn.execute(text("COMMIT;"))

    region_map = {
        'MH': 'Maharashtra', 'DL': 'Delhi', 'TN': 'Tamil Nadu',
        'KA': 'Karnataka', 'UP': 'Uttar Pradesh', 'GJ': 'Gujarat',
        'WB': 'West Bengal', 'TS': 'Telangana', 'AP': 'Andhra Pradesh',
        'AR': 'Arunachal Pradesh', 'AN': 'Andaman and Nicobar', 'KL': 'Kerala'
    }

    # Lists to buffer new records for batch insert
    new_clients = []
    new_carriers = []
    new_products = []
    new_policies = []
    new_commissions = []
    new_claims = []
    new_rates = []

    # Buffers to track newly staged records by key for in-memory updates
    new_policies_by_num = {}
    new_clients_by_id = {}
    new_commissions_by_pid = {}
    new_claims_by_pid = {}

    # Lists to buffer updates and audits for bulk batch operation
    client_updates = []
    policy_updates = []
    commission_updates = []
    claim_updates = []
    audit_claim_status_history_inserts = []
    audit_dataset_updates_inserts = []

    print("[db_writer] Processing rows incrementally...")
    for row in df.itertuples():
        p_num = str(row.policy_number).strip()
        p_num_upper = p_num.upper()
        
        # Determine normalized claim status for this row
        claim_amt = float(row.claim_amount)
        raw_status = str(row.claim_status).strip() if pd.notna(row.claim_status) else 'Approved'
        if claim_amt <= 0 or raw_status == 'No Claim':
            uploaded_claim_status = 'No Claim'
        else:
            uploaded_claim_status = raw_status.title()
            
        # Resolve client first
        c_name = str(row.client_name).strip()
        c_name_upper = c_name.upper()
        if c_name_upper in existing_clients:
            client_id = existing_clients[c_name_upper]
            cl_detail = existing_clients_details[client_id]
            c_type = row.client_type if pd.notna(row.client_type) else 'Individual/B2C'
            raw_reg = str(row.region).strip().upper() if pd.notna(row.region) else 'DL'
            r_code = raw_reg[:2]
            r_name = region_map.get(r_code, 'Other')
            if r_name == 'Other':
                r_name = raw_reg
            
            client_updated = False
            client_changes = []
            if c_type != cl_detail.client_type:
                client_changes.append(f"client_type: '{cl_detail.client_type}' -> '{c_type}'")
                client_updated = True
            if r_code != cl_detail.region_code:
                client_changes.append(f"region_code: '{cl_detail.region_code}' -> '{r_code}'")
                client_updated = True
            if r_name != cl_detail.region_name:
                client_changes.append(f"region_name: '{cl_detail.region_name}' -> '{r_name}'")
                client_updated = True
            
            if client_updated:
                # If newly staged client, update dictionary directly in memory
                if client_id in new_clients_by_id:
                    staged_c = new_clients_by_id[client_id]
                    staged_c['client_type'] = c_type
                    staged_c['region_code'] = r_code
                    staged_c['region_name'] = r_name
                    staged_c['address'] = f"{r_name} Area"
                else:
                    client_updates.append({
                        "c_type": c_type,
                        "r_code": r_code,
                        "r_name": r_name,
                        "address": f"{r_name} Area",
                        "client_id": client_id
                    })
                
                new_cl_detail = {
                    'client_id': client_id,
                    'name': c_name,
                    'client_type': c_type,
                    'region_code': r_code,
                    'region_name': r_name,
                    'address': f"{r_name} Area"
                }
                existing_clients_details[client_id] = pd.Series(new_cl_detail)  # type: ignore
                
                timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                for change in client_changes:
                    log_line = f"[{timestamp}] Client '{c_name}' (ID: {client_id}): {change}."
                    db.get_rotating_logger("dataset_updates", "logs/dataset_updates.log").info(log_line)
                    print(f"[db_writer] Client '{c_name}' update logged: {change}")
                
                summary['updates'].append({
                    'policy_number': p_num,
                    'client_name': c_name,
                    'old_status': f"Client: {', '.join([ch.split(':')[0] for ch in client_changes])}",
                    'new_status': "Updated",
                    'action': "Client Details Updated"
                })
        else:
            max_ids['client_id'] += 1
            client_id = max_ids['client_id']
            c_type = row.client_type if pd.notna(row.client_type) else 'Individual/B2C'
            
            raw_reg = str(row.region).strip().upper() if pd.notna(row.region) else 'DL'
            r_code = raw_reg[:2]
            r_name = region_map.get(r_code, 'Other')
            if r_name == 'Other':
                r_name = raw_reg
            
            new_c = {
                'client_id': client_id,
                'client_type': c_type,
                'name': c_name,
                'email': f"{c_name.lower().replace(' ', '.').replace(',', '')}@example.com",
                'phone': f"+91 {9800000000 + client_id}",
                'address': f"{r_name} Area",
                'region_code': r_code,
                'region_name': r_name,
                'is_active': 1
            }
            new_clients.append(new_c)
            new_clients_by_id[client_id] = new_c
            existing_clients[c_name_upper] = client_id
            existing_clients_details[client_id] = pd.Series(new_c)  # type: ignore

        # Resolve carrier and product
        carrier_name = str(row.carrier_name).strip()
        carrier_name_upper = carrier_name.upper()
        if carrier_name_upper in existing_carriers:
            carrier_id = existing_carriers[carrier_name_upper]
        else:
            max_ids['carrier_id'] += 1
            carrier_id = max_ids['carrier_id']
            new_car = {
                'carrier_id': carrier_id,
                'carrier_name': carrier_name,
                'is_active': 1
            }
            new_carriers.append(new_car)
            existing_carriers[carrier_name_upper] = carrier_id
            
        category = str(row.category).strip()
        sub_category = str(row.sub_category).strip()
        prod_key = (carrier_id, category.upper(), sub_category.upper())
        if prod_key in existing_products:
            product_id = existing_products[prod_key]
        else:
            max_ids['product_id'] += 1
            product_id = max_ids['product_id']
            new_p = {
                'product_id': product_id,
                'carrier_id': carrier_id,
                'category': category,
                'sub_category': sub_category,
                'is_active': 1
            }
            new_products.append(new_p)
            existing_products[prod_key] = product_id

        # Resolve commission rate
        rate_key = (category.upper(), sub_category.upper())
        if rate_key not in existing_rates:
            max_ids['rate_id'] += 1
            new_r = {
                'rate_id': max_ids['rate_id'],
                'category': category,
                'sub_category': sub_category,
                'base_rate_percent': 10.0,
                'is_active': 1
            }
            new_rates.append(new_r)
            existing_rates[rate_key] = max_ids['rate_id']

        if p_num_upper in existing_policies:
            existing_p = existing_policies[p_num_upper]
            p_id = existing_p.policy_id
            updates_before = len(summary['updates'])
            
            # 1. Compare Policy fields
            def parse_date_only(val):
                if pd.isna(val) or val is None:
                    return ""
                try:
                    return pd.to_datetime(val).strftime('%Y-%m-%d')
                except Exception:
                    return str(val)
            
            db_issue_date = parse_date_only(existing_p.issue_date)
            csv_issue_date = parse_date_only(row.issue_date_str)
            db_expiry_date = parse_date_only(existing_p.expiry_date)
            csv_expiry_date = parse_date_only(row.expiry_date_str)
            
            db_premium = float(existing_p.premium_amount)
            csv_premium = float(row.premium_amount)
            
            db_status = str(existing_p.status)
            csv_status = str(row.mapped_status)
            
            db_channel = str(existing_p.distribution_channel)
            csv_channel = str(row.distribution_channel) if pd.notna(row.distribution_channel) else 'Online'
            
            db_client_id = existing_p.client_id
            db_product_id = existing_p.product_id
            
            policy_updated = False
            policy_changes = []
            
            if db_client_id != client_id:
                policy_changes.append(f"client_id: {db_client_id} -> {client_id}")
                policy_updated = True
            if db_product_id != product_id:
                policy_changes.append(f"product_id: {db_product_id} -> {product_id}")
                policy_updated = True
            if db_issue_date != csv_issue_date:
                policy_changes.append(f"issue_date: '{db_issue_date}' -> '{csv_issue_date}'")
                policy_updated = True
            if db_expiry_date != csv_expiry_date:
                policy_changes.append(f"expiry_date: '{db_expiry_date}' -> '{csv_expiry_date}'")
                policy_updated = True
            if abs(db_premium - csv_premium) > 0.01:
                policy_changes.append(f"premium_amount: {db_premium} -> {csv_premium}")
                policy_updated = True
            if db_status != csv_status:
                policy_changes.append(f"status: '{db_status}' -> '{csv_status}'")
                policy_updated = True
            if db_channel != csv_channel:
                policy_changes.append(f"distribution_channel: '{db_channel}' -> '{csv_channel}'")
                policy_updated = True
                
            if policy_updated:
                # If newly staged policy, update dictionary directly in memory
                if p_num_upper in new_policies_by_num:
                    staged_pol = new_policies_by_num[p_num_upper]
                    staged_pol['client_id'] = client_id
                    staged_pol['product_id'] = product_id
                    staged_pol['issue_date'] = row.issue_date_str
                    staged_pol['expiry_date'] = row.expiry_date_str
                    staged_pol['premium_amount'] = csv_premium
                    staged_pol['status'] = csv_status
                    staged_pol['distribution_channel'] = csv_channel
                else:
                    policy_updates.append({
                        "client_id": client_id,
                        "product_id": product_id,
                        "issue_date": row.issue_date_str,
                        "expiry_date": row.expiry_date_str,
                        "premium": csv_premium,
                        "status": csv_status,
                        "channel": csv_channel,
                        "policy_id": p_id
                    })
                
                # Update cache
                new_pol_cache = {
                    'policy_id': p_id,
                    'policy_number': p_num,
                    'client_id': client_id,
                    'product_id': product_id,
                    'created_by_user_id': existing_p.created_by_user_id,
                    'issue_date': row.issue_date_str,
                    'expiry_date': row.expiry_date_str,
                    'premium_amount': csv_premium,
                    'status': csv_status,
                    'distribution_channel': csv_channel
                }
                existing_policies[p_num_upper] = pd.Series(new_pol_cache)  # type: ignore
                
                timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                for change in policy_changes:
                    log_line = f"[{timestamp}] Policy {p_num}: {change} by Ingestion."
                    db.get_rotating_logger("dataset_updates", "logs/dataset_updates.log").info(log_line)
                    print(f"[db_writer] Policy {p_num} update logged: {change}")
                
                summary['updates'].append({
                    'policy_number': p_num,
                    'client_name': row.client_name,
                    'old_status': f"Policy Fields Changed: {', '.join([c.split(':')[0] for c in policy_changes])}",
                    'new_status': "Updated",
                    'action': "Policy Fields Updated"
                })

            # 2. Check Sales Commission
            existing_comm = None
            csv_comm = float(row.commission_earned)
            if p_id in existing_commissions or p_id in new_commissions_by_pid:
                if p_id in new_commissions_by_pid:
                    staged_comm = new_commissions_by_pid[p_id]
                    db_comm = float(staged_comm['calculated_amount'])
                else:
                    existing_comm = existing_commissions[p_id]
                    db_comm = float(existing_comm.calculated_amount)
                    
                if abs(db_comm - csv_comm) > 0.01:
                    if p_id in new_commissions_by_pid:
                        new_commissions_by_pid[p_id]['calculated_amount'] = csv_comm
                    else:
                        commission_updates.append({
                            "amount": csv_comm,
                            "comm_id": existing_comm.commission_id
                        })
                    
                    timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_line = f"[{timestamp}] Sales Commission for Policy {p_num}: calculated_amount: {db_comm} -> {csv_comm} by Ingestion."
                    db.get_rotating_logger("dataset_updates", "logs/dataset_updates.log").info(log_line)
                    print(f"[db_writer] Commission for {p_num} updated: {db_comm} -> {csv_comm}")
                    
                    summary['updates'].append({
                        'policy_number': p_num,
                        'client_name': row.client_name,
                        'old_status': f"Comm: ₹{db_comm:.2f}",
                        'new_status': f"Comm: ₹{csv_comm:.2f}",
                        'action': "Commission Updated"
                    })
            else:
                max_ids['commission_id'] += 1
                new_comm_id = max_ids['commission_id']
                new_comm_val = {
                    'commission_id': new_comm_id,
                    'policy_id': p_id,
                    'calculated_amount': csv_comm,
                    'status': 'Received',
                    'is_active': 1
                }
                new_commissions.append(new_comm_val)
                new_commissions_by_pid[p_id] = new_comm_val
                
                timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                log_line = f"[{timestamp}] Sales Commission for Policy {p_num}: Created with amount {csv_comm} by Ingestion."
                db.get_rotating_logger("dataset_updates", "logs/dataset_updates.log").info(log_line)
                
                summary['updates'].append({
                    'policy_number': p_num,
                    'client_name': row.client_name,
                    'old_status': "No Commission",
                    'new_status': f"Comm: ₹{csv_comm:.2f}",
                    'action': "Commission Created"
                })

            # 3. Check Claims
            existing_cl = None
            if p_id in existing_claims or p_id in new_claims_by_pid:
                if p_id in new_claims_by_pid:
                    staged_cl = new_claims_by_pid[p_id]
                    db_claim_amt = float(staged_cl['quote_approved_amount'])
                    db_claim_status = str(staged_cl['status'])
                    cl_num = staged_cl['claim_number']
                else:
                    existing_cl = existing_claims[p_id]
                    db_claim_amt = float(existing_cl.quote_approved_amount)
                    db_claim_status = str(existing_cl.status)
                    cl_num = existing_cl.claim_number
                
                claim_updated = False
                claim_changes = []
                
                if abs(db_claim_amt - claim_amt) > 0.01:
                    claim_changes.append(f"quote_approved_amount: {db_claim_amt} -> {claim_amt}")
                    claim_updated = True
                
                if uploaded_claim_status != 'No Claim' and uploaded_claim_status != db_claim_status:
                    claim_changes.append(f"status: '{db_claim_status}' -> '{uploaded_claim_status}'")
                    claim_updated = True
                    
                if claim_updated:
                    if p_id in new_claims_by_pid:
                        new_claims_by_pid[p_id]['quote_approved_amount'] = claim_amt
                        new_claims_by_pid[p_id]['status'] = uploaded_claim_status
                    else:
                        claim_updates.append({
                            "amount": claim_amt,
                            "status": uploaded_claim_status,
                            "claim_id": existing_cl.claim_id
                        })
                    
                    timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    if uploaded_claim_status != db_claim_status:
                        history_log_line = f"[{timestamp}] Claim {cl_num}: Status changed from '{db_claim_status}' to '{uploaded_claim_status}' by System Admin."
                        try:
                            db.get_rotating_logger("claim_status_history", "logs/claim_status_history.log").info(history_log_line)
                        except Exception as log_err:
                            print(f"[db_writer] Error writing claim status history log: {log_err}")
                        audit_claim_status_history_inserts.append({
                            "claim_num": cl_num,
                            "old": db_claim_status,
                            "new": uploaded_claim_status,
                            "by": "System Admin"
                        })
                    
                    for change in claim_changes:
                        log_line = f"[{timestamp}] Claim {cl_num} (Policy {p_num}): {change} by Ingestion."
                        db.get_rotating_logger("dataset_updates", "logs/dataset_updates.log").info(log_line)
                        print(f"[db_writer] Claim {cl_num} update logged: {change}")
                        audit_dataset_updates_inserts.append({
                            "claim_num": cl_num,
                            "policy_num": p_num,
                            "msg": change
                        })
                    
                    summary['updates'].append({
                        'policy_number': p_num,
                        'client_name': row.client_name,
                        'old_status': f"Claim: {db_claim_status} (₹{db_claim_amt:.2f})",
                        'new_status': f"Claim: {uploaded_claim_status} (₹{claim_amt:.2f})",
                        'action': "Claim Updated"
                    })
            else:
                if claim_amt > 0 and uploaded_claim_status != 'No Claim':
                    max_ids['claim_id'] += 1
                    cl_id = max_ids['claim_id']
                    cl_num = f"CLM-{300000 + cl_id}"
                    
                    new_cl = {
                        'claim_id': cl_id,
                        'policy_id': p_id,
                        'claim_number': cl_num,
                        'registered_date': row.issue_date_str,
                        'quote_approved_amount': claim_amt,
                        'status': uploaded_claim_status,
                        'is_active': 1
                    }
                    new_claims.append(new_cl)
                    new_claims_by_pid[p_id] = new_cl
                        
                    timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                    history_log_line = f"[{timestamp}] Claim {cl_num}: Status changed from 'No Claim' to '{uploaded_claim_status}' by System Admin."
                    try:
                        db.get_rotating_logger("claim_status_history", "logs/claim_status_history.log").info(history_log_line)
                    except Exception as log_err:
                        print(f"[db_writer] Error writing claim status history log: {log_err}")
                    audit_claim_status_history_inserts.append({
                        "claim_num": cl_num,
                        "old": "No Claim",
                        "new": uploaded_claim_status,
                        "by": "System Admin"
                    })
                        
                    log_line = f"[{timestamp}] Claim {cl_num} (Policy {p_num}): Created with amount {claim_amt} and status '{uploaded_claim_status}' by Ingestion."
                    db.get_rotating_logger("dataset_updates", "logs/dataset_updates.log").info(log_line)
                    audit_dataset_updates_inserts.append({
                        "claim_num": cl_num,
                        "policy_num": p_num,
                        "msg": f"Created with amount {claim_amt} and status '{uploaded_claim_status}'"
                    })
                        
                    existing_claims[p_id] = pd.Series(new_cl)  # type: ignore
                    
                    summary['updates'].append({
                        'policy_number': p_num,
                        'client_name': row.client_name,
                        'old_status': 'No Claim',
                        'new_status': f"Claim: {uploaded_claim_status} (₹{claim_amt:.2f})",
                        'action': "Claim Created"
                    })

            if len(summary['updates']) == updates_before:
                summary['duplicates'].append({
                    'policy_number': p_num,
                    'client_name': row.client_name,
                    'carrier_name': row.carrier_name
                })
        else:
            # Policy is NOT present! Insert it as a new policy.
            
            # 1. Resolve client
            c_name = str(row.client_name).strip()
            c_name_upper = c_name.upper()
            if c_name_upper in existing_clients:
                client_id = existing_clients[c_name_upper]
            else:
                max_ids['client_id'] += 1
                client_id = max_ids['client_id']
                c_type = row.client_type if pd.notna(row.client_type) else 'Individual/B2C'
                
                raw_reg = str(row.region).strip().upper() if pd.notna(row.region) else 'DL'
                r_code = raw_reg[:2]
                r_name = region_map.get(r_code, 'Other')
                if r_name == 'Other':
                    r_name = raw_reg
                
                new_c = {
                    'client_id': client_id,
                    'client_type': c_type,
                    'name': c_name,
                    'email': f"{c_name.lower().replace(' ', '.').replace(',', '')}@example.com",
                    'phone': f"+91 {9800000000 + client_id}",
                    'address': f"{r_name} Area",
                    'region_code': r_code,
                    'region_name': r_name,
                    'is_active': 1
                }
                new_clients.append(new_c)
                existing_clients[c_name_upper] = client_id
                
            # 2. Resolve carrier
            carrier_name = str(row.carrier_name).strip()
            carrier_name_upper = carrier_name.upper()
            if carrier_name_upper in existing_carriers:
                carrier_id = existing_carriers[carrier_name_upper]
            else:
                max_ids['carrier_id'] += 1
                carrier_id = max_ids['carrier_id']
                new_car = {
                    'carrier_id': carrier_id,
                    'carrier_name': carrier_name,
                    'is_active': 1
                }
                new_carriers.append(new_car)
                existing_carriers[carrier_name_upper] = carrier_id
                
            # 3. Resolve product
            category = str(row.category).strip()
            sub_category = str(row.sub_category).strip()
            prod_key = (carrier_id, category.upper(), sub_category.upper())
            if prod_key in existing_products:
                product_id = existing_products[prod_key]
            else:
                max_ids['product_id'] += 1
                product_id = max_ids['product_id']
                new_p = {
                    'product_id': product_id,
                    'carrier_id': carrier_id,
                    'category': category,
                    'sub_category': sub_category,
                    'is_active': 1
                }
                new_products.append(new_p)
                existing_products[prod_key] = product_id
                
            # 4. Resolve commission rate if not exists
            rate_key = (category.upper(), sub_category.upper())
            if rate_key not in existing_rates:
                max_ids['rate_id'] += 1
                new_r = {
                    'rate_id': max_ids['rate_id'],
                    'category': category,
                    'sub_category': sub_category,
                    'base_rate_percent': 10.0,
                    'is_active': 1
                }
                new_rates.append(new_r)
                existing_rates[rate_key] = max_ids['rate_id']
                
            # 5. Insert policy
            max_ids['policy_id'] += 1
            policy_id = max_ids['policy_id']
            
            user_id = user_ids[policy_id % len(user_ids)]
            
            new_pol = {
                'policy_id': policy_id,
                'policy_number': p_num,
                'client_id': client_id,
                'product_id': product_id,
                'created_by_user_id': user_id,
                'issue_date': row.issue_date_str,
                'expiry_date': row.expiry_date_str,
                'premium_amount': float(row.premium_amount),
                'status': row.mapped_status,
                'distribution_channel': row.distribution_channel if pd.notna(row.distribution_channel) else 'Online',
                'is_active': 1
            }
            new_policies.append(new_pol)
            new_policies_by_num[p_num_upper] = new_pol
            existing_policies[p_num_upper] = pd.Series(new_pol)  # type: ignore
            
            # 6. Insert sales commission
            max_ids['commission_id'] += 1
            new_comm = {
                'commission_id': max_ids['commission_id'],
                'policy_id': policy_id,
                'calculated_amount': float(row.commission_earned),
                'status': 'Received',
                'is_active': 1
            }
            new_commissions.append(new_comm)
            new_commissions_by_pid[policy_id] = new_comm
            
            # 7. Insert claim if exists
            if claim_amt > 0 and uploaded_claim_status != 'No Claim':
                max_ids['claim_id'] += 1
                cl_id = max_ids['claim_id']
                cl_num = f"CLM-{300000 + cl_id}"
                new_cl = {
                    'claim_id': cl_id,
                    'policy_id': policy_id,
                    'claim_number': cl_num,
                    'registered_date': row.issue_date_str,
                    'quote_approved_amount': claim_amt,
                    'status': uploaded_claim_status,
                    'is_active': 1
                }
                new_claims.append(new_cl)
                new_claims_by_pid[policy_id] = new_cl
                existing_claims[policy_id] = pd.Series(new_cl)  # type: ignore

    # Bulk insert all new records and batch execute updates using pandas/SQLAlchemy inside a transaction
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        conn.execute(text("SET SQL_SAFE_UPDATES = 0;"))
        try:
            # --- BATCH UPDATES ---
            if client_updates:
                conn.execute(
                    text("UPDATE clients SET client_type = :c_type, region_code = :r_code, region_name = :r_name, address = :address WHERE client_id = :client_id"),
                    client_updates
                )
            if policy_updates:
                conn.execute(
                    text("""
                        UPDATE policies 
                        SET client_id = :client_id, 
                            product_id = :product_id, 
                            issue_date = :issue_date, 
                            expiry_date = :expiry_date, 
                            premium_amount = :premium, 
                            status = :status, 
                            distribution_channel = :channel 
                        WHERE policy_id = :policy_id
                    """),
                    policy_updates
                )
            if commission_updates:
                conn.execute(
                    text("UPDATE sales_commissions SET calculated_amount = :amount WHERE commission_id = :comm_id"),
                    commission_updates
                )
            if claim_updates:
                conn.execute(
                    text("UPDATE claims SET quote_approved_amount = :amount, status = :status WHERE claim_id = :claim_id"),
                    claim_updates
                )
                
            # --- BATCH AUDIT INSERTS ---
            if audit_claim_status_history_inserts:
                conn.execute(
                    text("INSERT INTO audit_claim_status_history (claim_number, old_status, new_status, changed_by) VALUES (:claim_num, :old, :new, :by)"),
                    audit_claim_status_history_inserts
                )
            if audit_dataset_updates_inserts:
                conn.execute(
                    text("INSERT INTO audit_dataset_updates (claim_number, policy_number, message) VALUES (:claim_num, :policy_num, :msg)"),
                    audit_dataset_updates_inserts
                )
                
            # --- BULK INSERTS ---
            if new_clients:
                pd.DataFrame(new_clients).to_sql('clients', con=conn, if_exists='append', index=False)
            if new_carriers:
                pd.DataFrame(new_carriers).to_sql('carriers', con=conn, if_exists='append', index=False)
            if new_products:
                pd.DataFrame(new_products).to_sql('products', con=conn, if_exists='append', index=False)
            if new_rates:
                pd.DataFrame(new_rates).to_sql('commission_rates', con=conn, if_exists='append', index=False)
            if new_policies:
                pd.DataFrame(new_policies).to_sql('policies', con=conn, if_exists='append', index=False)
            if new_commissions:
                pd.DataFrame(new_commissions).to_sql('sales_commissions', con=conn, if_exists='append', index=False)
            if new_claims:
                pd.DataFrame(new_claims).to_sql('claims', con=conn, if_exists='append', index=False)
        finally:
            conn.execute(text("SET SQL_SAFE_UPDATES = 1;"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        
    print(f"[db_writer] Normalized database load complete. Appended {len(new_policies)} new policies.")
    
    summary['appended_count'] = len(new_policies)
    return summary


def rollback_to_csv(csv_path: str, filename_label: str) -> dict:
    """
    Clears the normalized database tables and rebuilds the state
    from a historical backup CSV file. Records this event in audit_ingestions.
    """
    print(f"[rollback] Starting database rollback to snapshot: {csv_path}")
    engine = get_engine()
    
    # 1. Load backup dataframe
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Backup file not found at: {csv_path}")
        
    df_backup = pd.read_csv(csv_path)
    print(f"[rollback] Loaded {len(df_backup)} rows from backup file.")
    
    # 2. Reset database tables
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        conn.execute(text("SET SQL_SAFE_UPDATES = 0;"))
        
        tables = [
            'sales_commissions',
            'claims',
            'policies',
            'products',
            'carriers',
            'clients',
            'commission_rates'
        ]
        
        for t in tables:
            print(f"[rollback] Truncating table: {t}")
            conn.execute(text(f"TRUNCATE TABLE {t};"))
            
        conn.execute(text("COMMIT;"))
        conn.execute(text("SET SQL_SAFE_UPDATES = 1;"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        
    # Dispose connection pools to ensure Repeatable Read transaction snapshots are discarded
    print("[rollback] Disposing connection pools to clear transaction snapshots...")
    engine.dispose()
    try:
        import db
        if hasattr(db, '_engine') and db._engine is not None:
            db._engine.dispose()
            print("[rollback] Stale db._engine connection pool disposed.")
    except Exception as pool_err:
        print(f"[rollback] Warning: Could not dispose db._engine pool: {pool_err}")
        
    # 3. Re-run relational pipeline write
    print("[rollback] Re-ingesting historical data using standard write pipeline...")
    summary = write_df_to_mysql(df_backup)
    
    # 4. Log rollback action to audit_ingestions
    with engine.connect() as conn:
        log_query = text(
            "INSERT INTO audit_ingestions (filename, row_count, status) "
            "VALUES (:filename, :row_count, 'ROLLED_BACK');"
        )
        conn.execute(log_query, {
            "filename": f"Rollback to {filename_label}",
            "row_count": len(df_backup)
        })
        conn.execute(text("COMMIT;"))
        
    print(f"[rollback] Rollback complete. Restored {summary.get('appended_count', 0)} policies.")
    return summary

