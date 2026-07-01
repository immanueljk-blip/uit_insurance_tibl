import os
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def main():
    print("Generating 80,000 policy records...")
    
    # Pre-defined lists for fast generation
    client_types = ['Individual/B2C', 'Corporate/B2B']
    carriers = ['TATA AIG', 'ICICI Lombard', 'United India', 'New India Assurance', 'HDFC ERGO', 'Bajaj Allianz']
    categories = ['Motor', 'Health', 'Home', 'Travel']
    sub_categories = {
        'Motor': ['2W', '4W', 'CV'],
        'Health': ['Individual', 'Group Medi'],
        'Home': ['Theft', 'Damage'],
        'Travel': ['Flight', 'Overseas']
    }
    policy_statuses = ['Active', 'Expired', 'Renewed', 'Cancelled']
    channels = ['Direct', 'Broker', 'Agency', 'Online']
    regions = ['Maharashtra', 'Delhi', 'Tamil Nadu', 'Karnataka', 'Uttar Pradesh', 'Gujarat', 'West Bengal']
    claim_statuses = ['Registered', 'Under Review', 'Approved', 'Rejected', 'Settled']

    # Generate dates efficiently
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2026, 6, 30)
    delta_days = (end_date - start_date).days

    rows = []
    for i in range(80000):
        # Determine Client Type & Name
        c_type = client_types[i % 2]
        c_name = f"Client Corp {i//2 + 1} Ltd" if c_type == 'Corporate/B2B' else f"Policyholder Ind {i//2 + 1}"
        
        # Category & Subcategory
        cat = categories[i % 4]
        sub = random.choice(sub_categories[cat])
        
        # Dates
        rand_days = random.randint(0, delta_days)
        issue_dt = start_date + timedelta(days=rand_days)
        expiry_dt = issue_dt + timedelta(days=365)
        
        # Financials
        prem = round(random.uniform(4000.0, 65000.0), 2)
        comm = round(prem * random.uniform(0.08, 0.18), 2)
        
        # Claims logic
        has_claim = random.random() < 0.18  # 18% claim rate
        if has_claim:
            clm_status = random.choice(claim_statuses)
            clm_amount = round(random.uniform(500.0, prem * 0.8), 2)
        else:
            clm_status = 'No Claim'
            clm_amount = 0.0

        rows.append({
            'policy_number': f"POL-{10000000 + i}",
            'client_name': c_name,
            'client_type': c_type,
            'carrier_name': random.choice(carriers),
            'category': cat,
            'sub_category': sub,
            'issue_date': issue_dt.strftime('%Y-%m-%d'),
            'expiry_date': expiry_dt.strftime('%Y-%m-%d'),
            'premium_amount': prem,
            'policy_status': random.choice(policy_statuses),
            'distribution_channel': random.choice(channels),
            'region': random.choice(regions),
            'claim_amount': clm_amount,
            'claim_status': clm_status,
            'commission_earned': comm
        })

    df = pd.DataFrame(rows)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.abspath(os.path.join(script_dir, "..", "data", "broker_master_80k.csv"))
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Successfully generated 80,000 policy records and saved to: {out_path}")

if __name__ == '__main__':
    main()
