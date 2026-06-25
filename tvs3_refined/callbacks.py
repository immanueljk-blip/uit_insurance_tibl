import dash
from dash import Input, Output, State, html, ALL, ctx, dcc
import dash_bootstrap_components as dbc
import difflib
from dash_app import app, cache
import db
import pandas as pd
import io
import base64
from charts import (tab1, tab2, tab2b, tab3, tab3b, tab4b, tab5, tab5b,
                    tab6, tab6b, build_tab6b_content, tab7, tab8, tab9, tab10, tab11, tab12, tab13, tab14,
                    _cfg, _ax, chart_box, kpi_card, format_currency, section_title,
                    build_lead_pivot, build_nonconversion_table, build_followup_table,
                    _lt_kpi_bar, _lt_kpi_and_funnel_panel, _map_stages, STAGE_ORDER)
import plotly.express as px
from dash import dash_table
import traceback
import json
from layouts import TAB_GROUPS

TVS_BLUE   = "#1B3B8B"
TVS_ORANGE = "#E55B13"

def adjust_simulation_dates(df):
    """
    If the dataset's expiry dates are entirely in the past compared to today's year,
    shift all dates forward so the dataset remains active and renewals show up.
    """
    if 'issue_date' not in df.columns or 'expiry_date' not in df.columns:
        return df
        
    issue_dt = pd.to_datetime(df['issue_date'], errors='coerce')
    expiry_dt = pd.to_datetime(df['expiry_date'], errors='coerce')
    
    valid_expiry = expiry_dt.dropna()
    if valid_expiry.empty:
        return df
        
    max_expiry = valid_expiry.max()
    today = pd.Timestamp.now().normalize()
    
    if max_expiry < today:
        # Calculate offset so that the maximum expiry date aligns with today + 30 days
        offset = (today + pd.Timedelta(days=30)) - max_expiry
        
        # Shift dates and convert back to strings, preserving NaT as None
        shifted_issue = issue_dt + offset
        shifted_expiry = expiry_dt + offset
        
        df['issue_date'] = shifted_issue.apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if not pd.isna(x) else None)
        df['expiry_date'] = shifted_expiry.apply(lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if not pd.isna(x) else None)
        print(f"Shifted custom simulation dates forward by {offset.days} days to align with today's date.")
        
    return df


def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        if 'csv' in filename:
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        elif 'xls' in filename:
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            return None
            
        # --- Clean uploaded data ---
        numeric_cols = ['premium_amount', 'claim_amount', 'commission_earned']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
        # --- Normalize Categorical Strings ---
        # Prevent math/grouping failures caused by case sensitivity or trailing spaces
        for col in df.select_dtypes(include=['object']):
            if col not in ['policy_number', 'client_name', 'issue_date', 'expiry_date']:
                df[col] = df[col].astype(str).str.strip().str.title()
                
        return df
    except Exception as e:
        print(f"Upload error: {e}")
        return None


def get_current_df(stored_data):
    if stored_data is not None:
        df = pd.DataFrame(stored_data)
        if 'issue_date' in df.columns:
            df['issue_date'] = pd.to_datetime(df['issue_date'], errors='coerce')
        if 'expiry_date' in df.columns:
            df['expiry_date'] = pd.to_datetime(df['expiry_date'], errors='coerce')
        return df
    return db.df_global.copy()


# ── Upload / Clear & Validation Engine ──────────────────────────────────────────

def suggest_mappings(df_columns):
    """
    Given a list of uploaded dataframe columns, find which required columns are missing,
    and suggest matches from the unrecognized uploaded columns using standard aliases
    and difflib similarity.
    """
    required_cols = [
        "policy_number", "client_name", "client_type", "carrier_name",
        "category", "sub_category", "premium_amount", "claim_amount",
        "commission_earned", "policy_status", "issue_date", "expiry_date"
    ]
    
    columns_lower = [str(c).lower().strip() for c in df_columns]
    missing_cols = [col for col in required_cols if col.lower() not in columns_lower]
    if not missing_cols:
        return {}
        
    unrecognized_cols = [col for col in df_columns if col.lower().strip() not in required_cols]
    suggestions = {}
    
    common_aliases = {
        "policy_number": ["policy_no", "pol_no", "pol_num", "policy_num", "policyid", "policyno", "policy number", "pol number"],
        "client_name": ["client", "customer", "cust_name", "customer_name", "clientname", "client_nam", "customername", "name"],
        "client_type": ["type", "clienttype", "type_of_client", "segment"],
        "carrier_name": ["carrier", "underwriter", "insurance_company", "carriername", "carrier_nam", "company"],
        "category": ["lob", "line_of_business", "class", "product_category", "category_name"],
        "sub_category": ["subcategory", "sub_product", "sub_class", "sub_category_name", "subcat"],
        "premium_amount": ["premium", "prem", "premium_amt", "gwp", "premiumamount", "premium_amt"],
        "claim_amount": ["claim", "claims", "claim_amt", "incurred_claims", "claimamount", "claim_amt"],
        "commission_earned": ["commission", "comm", "commission_amt", "comm_earned", "commissionearned", "commission_earned"],
        "policy_status": ["status", "pol_status", "state", "policystatus"],
        "issue_date": ["issue", "start_date", "inception_date", "issuedate", "issue_dt"],
        "expiry_date": ["expiry", "end_date", "expiration_date", "expirydate", "expiry_dt"]
    }
    
    used_unrecognized = set()
    for m_col in missing_cols:
        m_clean = m_col.lower().replace("_", "").replace(" ", "")
        best_match = None
        best_ratio = 0.0
        
        for u_col in unrecognized_cols:
            if u_col in used_unrecognized:
                continue
            u_clean = str(u_col).lower().replace("_", "").replace(" ", "")
            
            # 1. Exact/Substring match in alias list
            if m_col in common_aliases:
                aliases = common_aliases[m_col]
                if any(alias == u_clean or alias in u_clean or u_clean in alias for alias in aliases):
                    best_match = u_col
                    best_ratio = 0.95
                    break
            
            # 2. SequenceMatcher similarity
            ratio = difflib.SequenceMatcher(None, m_clean, u_clean).ratio()
            if ratio > 0.55 and ratio > best_ratio:
                best_match = u_col
                best_ratio = ratio
                
        if best_match:
            suggestions[m_col] = best_match
            used_unrecognized.add(best_match)
        else:
            suggestions[m_col] = None
            
    return suggestions


def validate_dataframe(df):
    # Check schema compliance case-insensitively (excluding region which is optional)
    required_cols = [
        "policy_number", "client_name", "client_type", "carrier_name",
        "category", "sub_category", "premium_amount", "claim_amount",
        "commission_earned", "policy_status", "issue_date", "expiry_date"
    ]
    columns_lower = [c.lower() for c in df.columns]
    missing_cols = [col for col in required_cols if col.lower() not in columns_lower]
    
    if missing_cols:
        return missing_cols, [], []
        
    # Map from standard lowercase name back to original column name in df
    orig_col_map = {}
    for col in df.columns:
        orig_col_map[col.lower().strip()] = col

    # Rename columns to standard casing
    mapped_df = df.copy()
    rename_map = {}
    for col in df.columns:
        for exp in required_cols + ["region"]:
            if col.lower() == exp.lower():
                rename_map[col] = exp
    mapped_df = mapped_df.rename(columns=rename_map)
    
    # Auto-initialize optional region if missing
    if "region" not in mapped_df.columns:
        mapped_df["region"] = "DL"
    
    errors = []
    cell_errors = []
    valid_client_types = {'individual/b2c', 'corporate/b2b'}
    valid_categories = {'motor', 'health', 'home', 'travel', 'other'}
    valid_policy_statuses = {'active', 'cancelled', 'expired', 'renewed', 'docs and inspection pending', 'caselogin', 'soft copy received', 'policy issued', 'booked', 'lead', 'lapse', 'lost', 'reject'}
    valid_claim_statuses = {'registered', 'survey completed', 'approved', 'settled', 'rejected', 'under review', 'no claim'}
    
    for idx, row in mapped_df.iterrows():
        row_num = idx + 1
        
        # Helper to safely log cell error using original column name
        def add_cell_error(field):
            orig_col = orig_col_map.get(field.lower().strip(), field)
            cell_errors.append({"row_idx": idx, "col": orig_col})
        
        # 1. Null / Empty checks
        for field in ['policy_number', 'client_name', 'category', 'sub_category', 'region']:
            val = row[field]
            if pd.isna(val) or str(val).strip() == "":
                errors.append(f"Row {row_num}: Column '{field}' is required and cannot be empty.")
                add_cell_error(field)
                
        # 2. Client Type Check
        c_type = str(row['client_type']).strip().lower()
        if pd.isna(row['client_type']) or c_type not in valid_client_types:
            errors.append(f"Row {row_num}: Invalid Client Type '{row['client_type']}'. Expected 'Individual/B2C' or 'Corporate/B2B'.")
            add_cell_error('client_type')
            
        # 3. Category Check
        cat = str(row['category']).strip().lower()
        if pd.isna(row['category']) or cat not in valid_categories:
            errors.append(f"Row {row_num}: Invalid Category '{row['category']}'. Expected Motor, Health, Home, Travel, or Other.")
            add_cell_error('category')
            
        # 4. Numerics Checks
        for field in ['premium_amount', 'claim_amount', 'commission_earned']:
            val = row[field]
            try:
                num = float(val)
                if num < 0:
                    errors.append(f"Row {row_num}: Numeric field '{field}' cannot be negative (found {val}).")
                    add_cell_error(field)
            except (ValueError, TypeError):
                errors.append(f"Row {row_num}: Field '{field}' must be a valid number (found '{val}').")
                add_cell_error(field)
                
        # 5. Date Parsing and sequence check
        issue_date_parsed = pd.to_datetime(row['issue_date'], errors='coerce')
        expiry_date_parsed = pd.to_datetime(row['expiry_date'], errors='coerce')
        
        if pd.isna(issue_date_parsed):
            errors.append(f"Row {row_num}: 'issue_date' has an invalid date format (found '{row['issue_date']}').")
            add_cell_error('issue_date')
        if pd.isna(expiry_date_parsed):
            errors.append(f"Row {row_num}: 'expiry_date' has an invalid date format (found '{row['expiry_date']}').")
            add_cell_error('expiry_date')
            
        if not pd.isna(issue_date_parsed) and not pd.isna(expiry_date_parsed):
            if expiry_date_parsed < issue_date_parsed:
                errors.append(f"Row {row_num}: 'expiry_date' ({row['expiry_date']}) cannot be earlier than 'issue_date' ({row['issue_date']}).")
                add_cell_error('issue_date')
                add_cell_error('expiry_date')
                
        # 6. Policy Status Check
        p_status = str(row['policy_status']).strip().lower()
        if pd.isna(row['policy_status']) or p_status not in valid_policy_statuses:
            errors.append(f"Row {row_num}: Invalid Policy Status '{row['policy_status']}'.")
            add_cell_error('policy_status')
            
        # 7. Claim Status Check
        if 'claim_status' in mapped_df.columns:
            cl_status = str(row['claim_status']).strip().lower()
            if pd.notna(row['claim_status']) and cl_status not in valid_claim_statuses:
                errors.append(f"Row {row_num}: Invalid Claim Status '{row['claim_status']}'.")
                add_cell_error('claim_status')

    return None, errors, cell_errors


@app.callback(
    [Output('uploaded-raw-data-store', 'data'),
     Output('uploaded-filename-store', 'data'),
     Output('upload-status', 'children'),
     Output('uploaded-data-store', 'data', allow_duplicate=True),
     Output('schema-error-modal', 'is_open'),
     Output('schema-error-modal-body', 'children'),
     Output('uploaded-schema-mapping-store', 'data')],
    [Input('upload-data', 'contents'),
     Input('btn-clear-upload', 'n_clicks')],
    [State('upload-data', 'filename')],
    prevent_initial_call=True
)
def handle_upload(contents, clear_clicks, filename):
    trigger = ctx.triggered_id
    if trigger == 'btn-clear-upload':
        return None, None, "Live DB", None, False, None, None
    if contents is not None:
        df = parse_contents(contents, filename)
        if df is not None:
            short = filename[:18] + "…" if len(filename) > 20 else filename
            
            # Extract missing columns
            required_cols = [
                "policy_number", "client_name", "client_type", "carrier_name",
                "category", "sub_category", "premium_amount", "claim_amount",
                "commission_earned", "policy_status", "issue_date", "expiry_date"
            ]
            columns_lower = [str(c).lower().strip() for c in df.columns]
            missing_cols = [col for col in required_cols if col.lower() not in columns_lower]
            
            if missing_cols:
                suggestions = suggest_mappings(df.columns)
                if len(suggestions) == len(missing_cols):
                    # We can suggest mapping for all missing columns!
                    # Do not show modal, store suggestions and stage raw data
                    return df.to_dict('records'), filename, f"Mapping Required · {short}", None, False, None, suggestions
                else:
                    # Some missing columns have no suggestion, show modal
                    unmapped_cols = [c for c in missing_cols if c not in suggestions]
                    err_body = html.Div([
                        html.P("The uploaded file is missing required columns and could not be mapped.", style={"fontWeight": "bold", "color": "#EF4444"}),
                        html.P("Please ensure the following columns are present in your sheet:", style={"color": "#4B5563"}),
                        html.Div([
                            html.Div([
                                html.Span(col, style={
                                    "background": "white", "border": "1.5px solid #FCA5A5", "color": "#B91C1C",
                                    "padding": "4px 10px", "borderRadius": "20px", "fontSize": "11px", "fontWeight": "700",
                                    "fontFamily": "monospace", "display": "inline-block", "margin": "4px",
                                    "boxShadow": "0 2px 4px rgba(239,68,68,0.03)"
                                }) for col in unmapped_cols
                            ], style={"display": "flex", "flexWrap": "wrap", "gap": "4px", "marginTop": "8px"})
                        ], style={"background": "#FFF5F5", "border": "1.5px solid #FCA5A5", "padding": "12px", "borderRadius": "8px", "marginTop": "12px"})
                    ])
                    return df.to_dict('records'), filename, f"Schema Error · {short}", None, True, err_body, None
            
            # If no missing columns, perform normal validation
            missing_cols, field_errors, cell_errors = validate_dataframe(df)
            if field_errors:
                err_body = html.Div([
                    html.P("The uploaded dataset contains invalid field data and has been rejected.", style={"fontWeight": "bold", "color": "#EF4444"}),
                    html.P("Please correct the following validation errors before re-uploading:", style={"color": "#4B5563"}),
                    html.Div([
                        html.Ul([
                            html.Li(err, style={"fontSize": "11px", "color": "#B91C1C", "fontFamily": "monospace", "marginBottom": "4px"}) 
                            for err in field_errors[:25]
                        ] + ([html.Li(f"...and {len(field_errors) - 25} more errors.", style={"fontWeight": "bold", "fontSize": "11px", "color": "#B91C1C", "marginTop": "8px"})] if len(field_errors) > 25 else [])),
                    ], style={
                        "background": "#FFF5F5", "border": "1.5px solid #FCA5A5", "padding": "16px",
                        "borderRadius": "8px", "marginTop": "12px", "maxHeight": "300px", "overflowY": "auto"
                    })
                ])
                return df.to_dict('records'), filename, f"Validation Error · {short}", None, True, err_body, None
            
            # Standard rename mapping for standard casing
            expected_cols = [
                "policy_number", "client_name", "client_type", "carrier_name",
                "category", "sub_category", "premium_amount", "claim_amount",
                "commission_earned", "policy_status", "issue_date", "expiry_date", "region"
            ]
            mapped_df = df.copy()
            rename_map = {}
            for col in df.columns:
                for exp in expected_cols:
                    if col.lower() == exp.lower():
                        rename_map[col] = exp
            mapped_df = mapped_df.rename(columns=rename_map)
            
            if "region" not in mapped_df.columns:
                mapped_df["region"] = "DL"
            
            mapped_df = adjust_simulation_dates(mapped_df)
            
            numeric_cols = ['premium_amount', 'claim_amount', 'commission_earned']
            for col in numeric_cols:
                if col in mapped_df.columns:
                    mapped_df[col] = pd.to_numeric(mapped_df[col], errors='coerce').fillna(0)
            for col in mapped_df.select_dtypes(include=['object']):
                if col not in ['policy_number', 'client_name', 'issue_date', 'expiry_date']:
                    mapped_df[col] = mapped_df[col].astype(str).str.strip().str.title()
            
            return mapped_df.to_dict('records'), filename, f"Staged · {short}", mapped_df.to_dict('records'), False, None, None
            
        parse_err_body = html.Div([
            html.P("The uploaded file could not be parsed.", style={"fontWeight": "bold", "color": "#EF4444"}),
            html.P("Please check that the file is a valid Excel (.xlsx/.xls) or CSV (.csv) format and try again.", style={"color": "#4B5563"})
        ])
        return None, None, "Parse error", None, True, parse_err_body, None
    return None, None, "Live DB", None, False, None, None


@app.callback(
    [Output('uploaded-data-store', 'data'),
     Output('uploaded-schema-mapping-store', 'data', allow_duplicate=True),
     Output('schema-error-modal', 'is_open', allow_duplicate=True),
     Output('schema-error-modal-body', 'children', allow_duplicate=True),
     Output('upload-status', 'children', allow_duplicate=True)],
    Input('btn-apply-schema-mapping', 'n_clicks'),
    [State('uploaded-raw-data-store', 'data'),
     State('uploaded-filename-store', 'data'),
     State({'type': 'column-map-dropdown', 'index': ALL}, 'value'),
     State({'type': 'column-map-dropdown', 'index': ALL}, 'id')],
    prevent_initial_call=True
)
def apply_column_mapping(n_clicks, raw_data, filename, dropdown_values, dropdown_ids):
    if not n_clicks or not raw_data:
        raise dash.exceptions.PreventUpdate
        
    df = pd.DataFrame(raw_data)
    short = filename[:18] + "…" if len(filename) > 20 else filename
    
    # Construct renaming dictionary
    rename_map = {}
    for val, id_dict in zip(dropdown_values, dropdown_ids):
        uploaded_col = id_dict['index']
        if val:
            rename_map[uploaded_col] = val
            
    mapped_df = df.rename(columns=rename_map)
    
    # Run validation on mapped DataFrame
    missing_cols, field_errors, cell_errors = validate_dataframe(mapped_df)
    
    if missing_cols or field_errors:
        err_body = []
        if missing_cols:
            err_body.append(html.Div([
                html.Strong("⚠️ Missing Required Columns: "),
                "Even after mapping, some columns are missing: " + ", ".join(missing_cols)
            ], style={"color": "#B91C1C", "marginBottom": "6px"}))
        if field_errors:
            err_body.append(html.Div([
                html.Strong("⚠️ Cell Validation Errors: "),
                html.Ul([html.Li(err, style={"fontSize": "10px"}) for err in field_errors[:15]])
            ], style={"color": "#B91C1C"}))
            
        modal_content = html.Div(err_body)
        return dash.no_update, dash.no_update, True, modal_content, f"Mapping Error · {short}"
        
    # Success, normalize mapped data
    expected_cols = [
        "policy_number", "client_name", "client_type", "carrier_name",
        "category", "sub_category", "premium_amount", "claim_amount",
        "commission_earned", "policy_status", "issue_date", "expiry_date", "region"
    ]
    for col in mapped_df.columns:
        for exp in expected_cols:
            if col.lower() == exp.lower():
                rename_map[col] = exp
    mapped_df = mapped_df.rename(columns=rename_map)
    
    if "region" not in mapped_df.columns:
        mapped_df["region"] = "DL"
        
    mapped_df = adjust_simulation_dates(mapped_df)
    
    numeric_cols = ['premium_amount', 'claim_amount', 'commission_earned']
    for col in numeric_cols:
        if col in mapped_df.columns:
            mapped_df[col] = pd.to_numeric(mapped_df[col], errors='coerce').fillna(0)
    for col in mapped_df.select_dtypes(include=['object']):
        if col not in ['policy_number', 'client_name', 'issue_date', 'expiry_date']:
            mapped_df[col] = mapped_df[col].astype(str).str.strip().str.title()
            
    # Stage the verified data, clear suggestions, close modal
    return mapped_df.to_dict('records'), None, False, None, f"Staged · {short}"


# ── Close Schema Validation Modal ─────────────────────────────────────────────

@app.callback(
    Output('schema-error-modal', 'is_open', allow_duplicate=True),
    Input('btn-close-schema-error', 'n_clicks'),
    prevent_initial_call=True
)
def close_schema_error_modal(n_clicks):
    if n_clicks and n_clicks > 0:
        return False
    return dash.no_update


# ── Header KPI ─────────────────────────────────────────────────────────────────

@app.callback(
    Output('header-record-count', 'children'),
    [Input('uploaded-data-store', 'data'),
     Input('refresh-trigger', 'data')]
)
def update_record_count(stored_data, refresh_data):
    df = get_current_df(stored_data)
    source = "Uploaded" if stored_data else "Live DB"
    return f"{source} · {len(df):,} records"


@app.callback(
    Output('header-icr-kpi', 'children'),
    [Input('uploaded-data-store', 'data'),
     Input('refresh-trigger', 'data')]
)
def update_header_icr(stored_data, refresh_data):
    df = get_current_df(stored_data)
    if df is None or df.empty:
        return "ICR —"
    claim_col = 'claim_amount' if 'claim_amount' in df.columns else None
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    if not claim_col or not premium_col:
        return "ICR —"
    total_claim = df[claim_col].sum()
    total_prem = df[premium_col].sum()
    if total_prem <= 0:
        return "ICR —"
    icr = total_claim / total_prem * 100
    return f"ICR {icr:.1f}%"


# ── Group navigation → sub-tab update ─────────────────────────────────────────
# When a group button is clicked, update the active-group-store.

@app.callback(
    [Output("active-group-store", "data"),
     Output("tab-selector", "value")],
    [Input(f"nav-group-btn-{i}", "n_clicks") for i in range(len(TAB_GROUPS))],
    State("tab-selector", "value"),
    prevent_initial_call=True,
)
def switch_group(*args):
    current_tab = args[-1]
    # Determine which button was clicked
    triggered = ctx.triggered_id
    if triggered is None:
        return dash.no_update, dash.no_update
    # Extract group index from id pattern "nav-group-btn-{i}"
    try:
        group_idx = int(str(triggered).replace("nav-group-btn-", ""))
    except (ValueError, AttributeError):
        return dash.no_update, dash.no_update

    group = TAB_GROUPS[group_idx]
    # Select first tab of the group
    new_tab = group["tabs"][0]["value"]
    return group_idx, new_tab


@app.callback(
    [Output(f"nav-group-btn-{i}", "className") for i in range(len(TAB_GROUPS))],
    Input("active-group-store", "data"),
)
def highlight_active_group(active_idx):
    if active_idx is None:
        active_idx = 0
    return [
        "nav-group-btn nav-group-btn--active" if i == active_idx else "nav-group-btn"
        for i in range(len(TAB_GROUPS))
    ]


@app.callback(
    Output("tab-selector", "options"),
    Input("active-group-store", "data"),
)
def filter_sub_tabs(active_idx):
    if active_idx is None:
        active_idx = 0
    return TAB_GROUPS[active_idx]["tabs"]


@app.callback(
    Output("sub-tab-strip", "className"),
    Input("active-group-store", "data"),
)
def toggle_sub_tab_strip(active_idx):
    if active_idx is None:
        active_idx = 0
    n_tabs = len(TAB_GROUPS[active_idx]["tabs"])
    return "sub-tab-strip--single" if n_tabs <= 1 else ""


@app.callback(
    Output("sub-tab-context", "children"),
    [Input("active-group-store", "data"),
     Input("tab-selector", "value")]
)
def update_sub_tab_context(active_idx, tab_value):
    if active_idx is None:
        active_idx = 0
    group_label = TAB_GROUPS[active_idx]["label"]
    tab_label = next(
        (t["label"] for t in TAB_GROUPS[active_idx]["tabs"] if t["value"] == tab_value),
        "",
    )
    if tab_label and tab_label != group_label:
        return f"{group_label} · {tab_label}"
    return group_label


@app.callback(
    Output("active-group-store", "data", allow_duplicate=True),
    Input("tab-selector", "value"),
    prevent_initial_call=True,
)
def sync_group_from_tab(tab_value):
    for i, group in enumerate(TAB_GROUPS):
        if any(t["value"] == tab_value for t in group["tabs"]):
            return i
    return 0


# ── Tab content renderer ────────────────────────────────────────────────────────

@app.callback(
    Output("tab-content", "children"),
    [Input("tab-selector", "value"),
     Input('uploaded-data-store', 'data'),
     Input('refresh-trigger', 'data')],
    [State('uploaded-filename-store', 'data'),
     State('uploaded-raw-data-store', 'data'),
     State('uploaded-schema-mapping-store', 'data')]
)
def render_tab(tab, stored_data, refresh_data, filename, raw_data, mapping_store):
    if not tab:
        tab = "tab-1"
        
    # Write to access audit log
    os.makedirs('logs', exist_ok=True)
    timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] User accessed tab: {tab}\n"
    try:
        with open(os.path.join('logs', 'audit_access.log'), 'a') as f:
            f.write(log_line)
    except Exception as e:
        print(f"[audit] Error writing tab access log: {e}")
        
    try:
        dff = get_current_df(stored_data)
        if dff is None or dff.empty:
            return html.Div("No data available.", style={
                "padding": "40px", "color": "#D97706", "fontWeight": "600", "fontSize": "16px"
            })
        tab_map = {
            "tab-1": tab1, "tab-2": tab2, "tab-2b": tab2b, "tab-3": tab3, "tab-3b": tab3b,
            "tab-4b": tab4b, "tab-5": tab5, "tab-5b": tab5b,
            "tab-6": tab6, "tab-6b": tab6b, "tab-7": tab7, "tab-8": tab8,
            "tab-9": tab9, "tab-10": tab10, "tab-11": tab11, "tab-12": tab12,
            "tab-13": tab13, "tab-14": tab14,
        }
        fn = tab_map.get(tab)
        if fn:
            if tab == "tab-13":
                # Render using the validated/mapped data if it exists, otherwise fall back to raw uploaded data or Live DB
                if stored_data is not None:
                    df_to_use = dff
                elif raw_data is not None:
                    df_to_use = pd.DataFrame(raw_data)
                else:
                    df_to_use = dff
                
                if (stored_data is not None) or (raw_data is not None):
                    if 'issue_date' in df_to_use.columns:
                        df_to_use['issue_date'] = pd.to_datetime(df_to_use['issue_date'], errors='coerce')
                    if 'expiry_date' in df_to_use.columns:
                        df_to_use['expiry_date'] = pd.to_datetime(df_to_use['expiry_date'], errors='coerce')
                
                is_mapped = stored_data is not None
                is_schema_valid = True
                validation_errors = None
                
                # Only validate if we have raw data that has not been mapped/validated yet
                if stored_data is None and raw_data is not None:
                    missing_cols, field_errors, cell_errors = validate_dataframe(df_to_use)
                    if missing_cols or field_errors:
                        is_schema_valid = False
                        validation_errors = {
                            "missing_cols": missing_cols or [],
                            "field_errors": field_errors or [],
                            "cell_errors": cell_errors or []
                        }
                return fn(df_to_use, filename, is_mapped, is_schema_valid, validation_errors, mapping_suggestions=mapping_store)
            return fn(dff)
    except Exception:
        return html.Div([
            html.Strong("Render error:"),
            html.Pre(traceback.format_exc(), style={
                "fontSize": "11px", "background": "#FEF2F2", "padding": "12px"
            })
        ], style={"padding": "20px"})
    return html.Div()


# ── Renewal input control ───────────────────────────────────────────────────────

@app.callback(
    [Output('renewal-stats-section', 'children'),
     Output('renewal-table-section', 'children')],
    [Input('renewal-input', 'value'),
     Input('uploaded-data-store', 'data'),
     Input('refresh-trigger', 'data')]
)
def update_renewal_section(days, stored_data, refresh_data):
    # Safe parsing of days value from the input field
    try:
        if days is None or str(days).strip() == "":
            days = 30
        else:
            days = int(float(days))
    except (ValueError, TypeError):
        days = 30

    df = get_current_df(stored_data)

    if 'expiry_date' not in df.columns or 'premium_amount' not in df.columns:
        return html.Div("Renewal Data N/A"), html.Div("No Data")

    df['expiry_date'] = pd.to_datetime(df['expiry_date'], errors='coerce')
    now = pd.Timestamp.today().normalize()
    df['days_to_expiry'] = (df['expiry_date'] - now).dt.days

    b0   = df[(df['days_to_expiry'] >= 0) & (df['days_to_expiry'] <= min(30, days))] if days >= 0 else pd.DataFrame()
    b31  = df[(df['days_to_expiry'] > 30) & (df['days_to_expiry'] <= min(60, days))] if days > 30 else pd.DataFrame()
    b61  = df[(df['days_to_expiry'] > 60) & (df['days_to_expiry'] <= min(90, days))] if days > 60 else pd.DataFrame()
    b91  = df[(df['days_to_expiry'] > 90) & (df['days_to_expiry'] <= days)] if days > 90 else pd.DataFrame()

    def stat_chip(label, val, sub, color):
        return html.Div([
            html.Div(label, style={"fontSize": "9px", "fontWeight": "700", "color": "#9CA3AF",
                                   "textTransform": "uppercase", "letterSpacing": "0.6px"}),
            html.Div(val,   style={"fontSize": "15px", "fontWeight": "800", "color": color, "lineHeight": "1.1"}),
            html.Div(sub,   style={"fontSize": "9px", "color": "#6B7280"}),
        ], style={"flex": "1", "background": "white", "borderRadius": "8px",
                  "border": f"1px solid {color}40", "borderTop": f"3px solid {color}",
            "borderRadius": "8px", "padding": "16px", "background": "white",
            "boxShadow": "0 4px 12px rgba(0,0,0,0.04)",
            "display": "flex", "flexDirection": "column", "alignItems": "center", "textAlign": "center"
        })

    stats = html.Div([
        stat_chip("0–30 Days", format_currency(b0['premium_amount'].sum()) if not b0.empty else "₹0",   f"{len(b0)} policies", "#EF4444"),
        stat_chip("31–60 Days", format_currency(b31['premium_amount'].sum()) if not b31.empty else "₹0", f"{len(b31)} policies", "#F59E0B"),
        stat_chip("61–90 Days", format_currency(b61['premium_amount'].sum()) if not b61.empty else "₹0", f"{len(b61)} policies", "#8B5CF6"),
        stat_chip("91+ Days", format_currency(b91['premium_amount'].sum()) if not b91.empty else "₹0", f"{len(b91)} policies", "#10B981"),
    ], style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(180px, 1fr))", "gap": "16px", "marginBottom": "24px", "maxWidth": "1200px", "margin": "0 auto"})

    target_df = df[(df['days_to_expiry'] >= 0) & (df['days_to_expiry'] <= days)].copy()

    if target_df.empty:
        return stats, html.Div(
            f"No policies expiring in next {days} days.",
            style={"color": "#6B7280", "fontSize": "11px", "fontStyle": "italic"}
        )

    table_cols = [c for c in ['client_name', 'carrier_name', 'premium_amount', 'days_to_expiry']
                  if c in target_df.columns]
    export_df = target_df[table_cols].head(20).sort_values('days_to_expiry')
    
    # Format premium for display in table
    if 'premium_amount' in export_df.columns:
        export_df['premium_amount'] = export_df['premium_amount'].apply(lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "₹0.00")

    table = dash_table.DataTable(
        data=export_df.to_dict('records'),
        columns=[{"name": str(i).replace('_', ' ').title(), "id": str(i)} for i in export_df.columns],
        page_size=8, sort_action='native',
        style_table={"overflowX": "auto"},
        style_cell={
            "padding": "6px 12px",
            "fontFamily": "Plus Jakarta Sans, Inter, sans-serif",
            "fontSize": "11px",
            "border": "1px solid #E5E7EB",
            "height": "auto"
        },
        style_header={
            "backgroundColor": TVS_BLUE,
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "11px",
            "padding": "8px 12px",
            "height": "auto"
        },
        style_cell_conditional=[
            {"if": {"column_id": "client_name"}, "textAlign": "left"},
            {"if": {"column_id": "carrier_name"}, "textAlign": "left"},
            {"if": {"column_id": "premium_amount"}, "textAlign": "right"},
            {"if": {"column_id": "days_to_expiry"}, "textAlign": "right"},
        ],
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#F9FAFB"},
            {"if": {"filter_query": "{days_to_expiry} <= 30", "column_id": "days_to_expiry"},
             "color": "#EF4444", "fontWeight": "bold"},
        ],
        export_format='csv',
    )
    return stats, table


# ── Pivot Explorer ─────────────────────────────────────────────────────────────

@app.callback(
    Output("pivot-results-container", "children"),
    [Input("pivot-row",    "value"),
     Input("pivot-col",    "value"),
     Input("pivot-metric", "value"),
     Input("pivot-agg",    "value"),
     Input('uploaded-data-store', 'data'),
     Input('refresh-trigger', 'data')]
)
def update_dynamic_pivot(row, col, metric, agg, stored_data, refresh_data):
    dff = get_current_df(stored_data)
    if not row or not col or not metric or dff is None or dff.empty:
        return html.Div("No data available.", style={"padding": "20px"})
    try:
        dff[metric] = pd.to_numeric(dff[metric], errors='coerce').fillna(0)
        pv = pd.pivot_table(dff, values=metric, index=row, columns=col, aggfunc=agg).round(2)

        fig = px.imshow(pv, text_auto=True, color_continuous_scale="Blues", aspect="auto", origin="lower",
                        labels=dict(x=str(col).replace('_', ' '),
                                    y=str(row).replace('_', ' '),
                                    color=str(metric).replace('_', ' ')),
                        title=f"{agg.capitalize()} of {str(metric).replace('_', ' ')} "
                              f"by {str(row).replace('_', ' ')} & {str(col).replace('_', ' ')}")
        _ax(fig.update_layout(**_cfg()))

        pv_reset = pv.reset_index().fillna(0)
        table = dash_table.DataTable(
            id='dynamic-pivot-table',
            data=pv_reset.to_dict('records'),
            columns=[{"name": str(i).replace('_', ' '), "id": str(i)} for i in pv_reset.columns],
            style_table={'overflowX': 'auto', 'borderRadius': '8px', 'border': '1px solid #E5E7EB'},
            style_cell={
                'textAlign': 'left',
                'padding': '6px 12px',
                'fontFamily': 'Plus Jakarta Sans, Inter, sans-serif',
                'fontSize': '11px',
                'height': 'auto'
            },
            style_header={
                'backgroundColor': TVS_BLUE,
                'color': 'white',
                'fontWeight': 'bold',
                'padding': '8px 12px',
                'fontSize': '11px',
                'height': 'auto'
            },
            style_data_conditional=[
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#F9FAFB'}
            ],
            export_format='csv'
        )

        return html.Div([
            html.Div(chart_box(fig, "pivot-heatmap"), className="pivot-chart-row"),
            html.Div([
                html.Div("Pivot Summary Grid", style={
                    "fontSize": "11px", "fontWeight": "800", "color": TVS_BLUE,
                    "marginBottom": "6px",
                }),
                table,
            ], className="pivot-table-row"),
        ])
    except Exception as e:
        return html.Div(f"Error generating pivot: {e}", style={"color": "red", "padding": "20px"})


# ── Refresh data ───────────────────────────────────────────────────────────────

@app.callback(
    Output('refresh-trigger', 'data'),
    Input('btn-refresh-data', 'n_clicks')
)
def refresh_data(n_clicks):
    if n_clicks and n_clicks > 0:
        db.df_global = db.get_data()
        return n_clicks
    return dash.no_update


# ── Universal drilldown modal ──────────────────────────────────────────────────

@app.callback(
    [Output("drilldown-modal", "is_open"),
     Output("drilldown-modal-title", "children"),
     Output("drilldown-modal-body", "children")],
    [Input({"type": "dynamic-chart", "index": ALL}, "clickData"),
     Input({"type": "kpi-card", "index": ALL}, "n_clicks"),
     Input("btn-close-drilldown", "n_clicks")],
    [State("uploaded-data-store", "data")],
    prevent_initial_call=True
)
def handle_universal_click(clickData_list, kpi_clicks_list, close_clicks, stored_data):
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update

    trigger_id = ctx.triggered_id

    # Handle close button
    if trigger_id == "btn-close-drilldown":
        if not close_clicks or close_clicks == 0:
            return dash.no_update, dash.no_update, dash.no_update
        return False, dash.no_update, dash.no_update

    df = get_current_df(stored_data)
    if df.empty:
        return dash.no_update, dash.no_update, dash.no_update

    # Handle pattern matching triggers (KPI cards and dynamic charts)
    if isinstance(trigger_id, dict):
        trigger_type = trigger_id.get("type")
        trigger_index = trigger_id.get("index")

        if trigger_type == "kpi-card":
            clicks = ctx.triggered[0]['value']
            if not clicks or clicks == 0:
                return dash.no_update, dash.no_update, dash.no_update

            if trigger_index == "claims-filed":
                title = "Claims Filed Details"
                filtered_df = df[df['claim_amount'] > 0].copy()
            elif trigger_index == "open-exposure":
                title = "Open Exposure Details"
                open_statuses = ['Registered', 'Survey Completed']
                filtered_df = df[df['claim_status'].isin(open_statuses)].copy()
            elif trigger_index == "claims-approved":
                title = "Approved Claims Details"
                filtered_df = df[df['claim_status'] == 'Approved'].copy()
            elif trigger_index == "claims-settled":
                title = "Settled Claims Details"
                filtered_df = df[df['claim_status'] == 'Settled'].copy()
            else:
                filtered_df = pd.DataFrame()
                title = "Details"

            if filtered_df.empty:
                return True, title, html.Div("No records found.", style={"padding": "20px", "textAlign": "center", "color": "#6B7280"})

            # Summary Metrics
            total_val = filtered_df['claim_amount'].sum()
            avg_val = filtered_df['claim_amount'].mean() if len(filtered_df) > 0 else 0
            
            summary_html = html.Div([
                html.Div([
                    html.Div("Total Claims", style={"fontSize": "11px", "color": "#6B7280", "fontWeight": "bold", "textTransform": "uppercase"}),
                    html.Div(f"{len(filtered_df):,}", style={"fontSize": "20px", "fontWeight": "800", "color": TVS_BLUE}),
                ], style={"flex": 1, "background": "#F3F4F6", "padding": "12px", "borderRadius": "8px", "marginRight": "12px"}),
                html.Div([
                    html.Div("Total Claim Value", style={"fontSize": "11px", "color": "#6B7280", "fontWeight": "bold", "textTransform": "uppercase"}),
                    html.Div(format_currency(total_val), style={"fontSize": "20px", "fontWeight": "800", "color": TVS_BLUE}),
                ], style={"flex": 1, "background": "#F3F4F6", "padding": "12px", "borderRadius": "8px", "marginRight": "12px"}),
                html.Div([
                    html.Div("Average Claim", style={"fontSize": "11px", "color": "#6B7280", "fontWeight": "bold", "textTransform": "uppercase"}),
                    html.Div(format_currency(avg_val), style={"fontSize": "20px", "fontWeight": "800", "color": TVS_BLUE}),
                ], style={"flex": 1, "background": "#F3F4F6", "padding": "12px", "borderRadius": "8px"}),
            ], style={"display": "flex", "marginBottom": "16px"})

            display_cols = ['policy_number', 'client_name', 'carrier_name', 'category', 'claim_status', 'claim_amount']
            display_cols = [c for c in display_cols if c in filtered_df.columns]

            df_disp = filtered_df.copy()
            if 'claim_amount' in df_disp.columns:
                df_disp['claim_amount'] = df_disp['claim_amount'].apply(format_currency)

            table = dash_table.DataTable(
                id='drilldown-data-table',
                data=df_disp[display_cols].to_dict('records'),
                columns=[{"name": i.replace("_", " ").title(), "id": i} for i in display_cols],
                page_size=10,
                style_table={'overflowX': 'auto'},
                style_cell={
                    'padding': '6px 12px',
                    'fontFamily': 'Plus Jakarta Sans, Inter, sans-serif',
                    'fontSize': '11px',
                    'border': '1px solid #E5E7EB',
                    'height': 'auto'
                },
                style_header={
                    'backgroundColor': TVS_BLUE,
                    'color': 'white',
                    'fontWeight': 'bold',
                    'padding': '8px 12px',
                    'fontSize': '11px',
                    'height': 'auto'
                },
                style_cell_conditional=[
                    {'if': {'column_id': 'policy_number'}, 'textAlign': 'left'},
                    {'if': {'column_id': 'client_name'}, 'textAlign': 'left'},
                    {'if': {'column_id': 'carrier_name'}, 'textAlign': 'left'},
                    {'if': {'column_id': 'category'}, 'textAlign': 'left'},
                    {'if': {'column_id': 'claim_status'}, 'textAlign': 'left'},
                    {'if': {'column_id': 'claim_amount'}, 'textAlign': 'right'},
                ],
                style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#f9fafb'}],
                export_format='csv'
            )

            # Hide claim status editor form (disabled in UI, preserved in DOM for callbacks)
            quick_update_form = html.Div([
                dcc.Dropdown(id='dd-update-claim-policy', style={"display": "none"}),
                dcc.Dropdown(id='dd-update-claim-status', style={"display": "none"}),
                html.Button(id="btn-update-claim-status", n_clicks=0, style={"display": "none"}),
                html.Div(id='claim-update-status', style={"display": "none"})
            ], style={"display": "none"})

            modal_content = html.Div([
                summary_html,
                quick_update_form,
                table
            ])
            
            return True, title, modal_content

        elif trigger_type == "dynamic-chart":
            # Handle chart clicks (existing logic)
            prop_id = ctx.triggered[0]['prop_id']
            clickData = ctx.triggered[0]['value']

            if not clickData:
                return dash.no_update, dash.no_update, dash.no_update

            point = clickData["points"][0]
            filtered_df = df.copy()
            title = "Drill-down Details"

            filter_map = {
                "status-chart":      ("policy_status",        point.get("y", "")),
                "status":            ("policy_status",        point.get("y", "")), # Tab 3
                "cat-chart":         ("category",             point.get("y", "")),
                "carrier-vs-chart":  ("carrier_name",         point.get("x", "")),
                "channel-chart":     ("distribution_channel", point.get("x", "")),
                "top-client-chart":  ("client_name",          point.get("y", "")),
                "client-type-chart": ("client_type",          point.get("y", "")),
                "margin-cat-chart":  ("category",             point.get("x", "")),
                "nr-chart":          ("carrier_name",         point.get("y", "")),
                "comm-chart":        ("carrier_name",         point.get("x", "")),
                "icr-chart":         ("carrier_name",         point.get("x", "")),
                "sub-cat":           ("sub_category",         point.get("x", "")),
                "motor-chart":       ("carrier_name",         point.get("y", "")), # Stacked
                "cancel-carrier":    ("carrier_name",         point.get("x", "")),
                "cancel-cat":        ("category",             point.get("x", "")),
                "region-bar-chart":  ("region",               point.get("x", "")),
                "region-dist-chart": ("region",               point.get("y", "")),
            }

            if trigger_index in ["monthly-chart", "margin-trend-chart", "renewal-heatmap", "vintage-chart", "growth-chart"]:
                month = point.get("x", "")
                if trigger_index == "renewal-heatmap" and 'expiry_date' in filtered_df.columns:
                    filtered_df['exp_month'] = pd.to_datetime(filtered_df['expiry_date']).dt.to_period('M').astype(str)
                    filtered_df = filtered_df[filtered_df['exp_month'] == month]
                    title = f"Expiring Details for Month: {month}"
                elif trigger_index == "vintage-chart" and 'issue_date' in filtered_df.columns:
                    filtered_df['issue_quarter'] = pd.to_datetime(filtered_df['issue_date']).dt.to_period('Q').astype(str)
                    filtered_df = filtered_df[filtered_df['issue_quarter'] == month]
                    title = f"Vintage Cohort: {month}"
                elif 'issue_date' in filtered_df.columns:
                    filtered_df['issue_month'] = pd.to_datetime(filtered_df['issue_date']).dt.to_period('M').astype(str)
                    filtered_df = filtered_df[filtered_df['issue_month'] == month]
                    title = f"Details for Month: {month}"
            elif trigger_index == "seg-chart":
                pass
            elif trigger_index == "treemap-chart":
                clicked_label = point.get("label", "")
                if clicked_label and clicked_label != "All Channels":
                    mask = (
                        (filtered_df.get('distribution_channel', '') == clicked_label) |
                        (filtered_df.get('category', '') == clicked_label) |
                        (filtered_df.get('sub_category', '') == clicked_label)
                    )
                    filtered_df = filtered_df[mask]
                title = f"Details — {clicked_label}"
            elif trigger_index in filter_map and filter_map[trigger_index]:
                col, val = filter_map[trigger_index]
                if col in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df[col] == val]
                title = f"Details — {val}"

            if filtered_df.empty:
                return True, "No Data Found", html.Div("No records match this selection.")

            display_cols = ['policy_number', 'client_name', 'client_type',
                            'premium_amount', 'policy_status', 'issue_date']
            display_cols = [c for c in display_cols if c in filtered_df.columns]

            df_disp = filtered_df.copy()
            if 'premium_amount' in df_disp.columns:
                df_disp['premium_amount'] = df_disp['premium_amount'].apply(format_currency)
            if 'issue_date' in df_disp.columns:
                df_disp['issue_date'] = df_disp['issue_date'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else "")

            table = dash_table.DataTable(
                data=df_disp[display_cols].to_dict('records'),
                columns=[{"name": i.replace("_", " ").title(), "id": i} for i in display_cols],
                page_size=10,
                style_table={'overflowX': 'auto'},
                style_cell={
                    'padding': '6px 12px',
                    'fontFamily': 'Plus Jakarta Sans, Inter, sans-serif',
                    'fontSize': '11px',
                    'border': '1px solid #E5E7EB',
                    'height': 'auto'
                },
                style_header={
                    'backgroundColor': TVS_BLUE,
                    'color': 'white',
                    'fontWeight': 'bold',
                    'padding': '8px 12px',
                    'fontSize': '11px',
                    'height': 'auto'
                },
                style_cell_conditional=[
                    {'if': {'column_id': 'policy_number'}, 'textAlign': 'left'},
                    {'if': {'column_id': 'client_name'}, 'textAlign': 'left'},
                    {'if': {'column_id': 'client_type'}, 'textAlign': 'left'},
                    {'if': {'column_id': 'policy_status'}, 'textAlign': 'left'},
                    {'if': {'column_id': 'issue_date'}, 'textAlign': 'left'},
                    {'if': {'column_id': 'premium_amount'}, 'textAlign': 'right'},
                ],
                style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#f9fafb'}]
            )

            return True, title, table

    return dash.no_update, dash.no_update, dash.no_update


# ── Verify & Commit Staged Data to MySQL ───────────────────────────────────────

import os
from datetime import datetime
import db_writer

@app.callback(
    [Output('uploaded-raw-data-store', 'data', allow_duplicate=True),
     Output('uploaded-filename-store', 'data', allow_duplicate=True),
     Output('upload-status', 'children', allow_duplicate=True),
     Output('uploaded-data-store', 'data', allow_duplicate=True),
     Output('refresh-trigger', 'data', allow_duplicate=True),
     Output('ingestion-result-modal', 'is_open'),
     Output('ingestion-result-modal-body', 'children')],
    Input('btn-verify-commit', 'n_clicks'),
    [State('uploaded-data-store', 'data'),
     State('uploaded-filename-store', 'data')],
    prevent_initial_call=True
)
def verify_and_commit_data(n_clicks, mapped_data, filename):
    if not n_clicks or mapped_data is None:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        
    try:
        df = pd.DataFrame(mapped_data)
        
        # 1. Ingest to MySQL DB via relational pipeline
        summary = db_writer.write_df_to_mysql(df)
        
        # Write to ingestion audit log on success
        os.makedirs('logs', exist_ok=True)
        timestamp_log = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp_log}] User loaded data. File: {filename}, Rows: {len(df)}, Status: Ingested to Database successfully.\n"
        try:
            with open(os.path.join('logs', 'audit_ingestion.log'), 'a') as f:
                f.write(log_line)
        except Exception as log_err:
            print(f"[audit] Error writing audit ingestion log: {log_err}")
        
        # 2. Force reload memory master data
        db.df_global = db.get_data()
        
        # 3. Save full backup of the entire live dataset to revisions/
        os.makedirs('revisions', exist_ok=True)
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        archive_path = os.path.join('revisions', f"dataset_rev_{timestamp}.csv")
        db.df_global.to_csv(archive_path, index=False)
        print(f"[commit] Archived full database backup to {archive_path}")
        
        # Build modal content
        appended_cnt = summary.get('appended_count', 0)
        duplicates = summary.get('duplicates', [])
        updates = summary.get('updates', [])
        
        modal_body = html.Div([
            # Success summary banner
            html.Div([
                html.H4("Data Ingested Successfully", style={"color": "#047857", "fontWeight": "800", "margin": 0}),
                html.P(f"Processed file '{filename}' with the following database operations:", style={"margin": "4px 0 0", "color": "#065F46", "fontSize": "12px"})
            ], style={"background": "#D1FAE5", "border": "1px solid #A7F3D0", "padding": "14px", "borderRadius": "8px", "marginBottom": "16px"}),
            
            # KPI stats row
            html.Div([
                html.Div([
                    html.Div("New Records Appended", style={"fontSize": "10px", "color": "#6B7280", "fontWeight": "bold", "textTransform": "uppercase"}),
                    html.Div(f"{appended_cnt}", style={"fontSize": "22px", "fontWeight": "800", "color": "#10B981"}),
                ], style={"flex": 1, "background": "#F9FAFB", "border": "1px solid #E5E7EB", "padding": "10px", "borderRadius": "6px", "textAlign": "center"}),
                
                html.Div([
                    html.Div("Duplicates Ignored", style={"fontSize": "10px", "color": "#6B7280", "fontWeight": "bold", "textTransform": "uppercase"}),
                    html.Div(f"{len(duplicates) + len(updates)}", style={"fontSize": "22px", "fontWeight": "800", "color": "#EF4444" if (len(duplicates) + len(updates)) > 0 else "#6B7280"}),
                ], style={"flex": 1, "background": "#F9FAFB", "border": "1px solid #E5E7EB", "padding": "10px", "borderRadius": "6px", "textAlign": "center", "marginLeft": "10px"}),
                
                html.Div([
                    html.Div("Claim Updates Processed", style={"fontSize": "10px", "color": "#6B7280", "fontWeight": "bold", "textTransform": "uppercase"}),
                    html.Div(f"{len(updates)}", style={"fontSize": "22px", "fontWeight": "800", "color": "#3B82F6" if len(updates) > 0 else "#6B7280"}),
                ], style={"flex": 1, "background": "#F9FAFB", "border": "1px solid #E5E7EB", "padding": "10px", "borderRadius": "6px", "textAlign": "center", "marginLeft": "10px"}),
            ], style={"display": "flex", "marginBottom": "16px"}),
        ])
        
        if duplicates:
            dup_rows = []
            for item in duplicates[:50]:
                dup_rows.append(html.Tr([
                    html.Td(item['policy_number'], style={"fontFamily": "monospace", "fontWeight": "600", "padding": "6px 10px", "borderBottom": "1px solid #E5E7EB"}),
                    html.Td(item['client_name'], style={"padding": "6px 10px", "borderBottom": "1px solid #E5E7EB"}),
                    html.Td(item['carrier_name'], style={"padding": "6px 10px", "borderBottom": "1px solid #E5E7EB"}),
                    html.Td("Already exists (Neglected)", style={"color": "#B91C1C", "fontWeight": "600", "padding": "6px 10px", "borderBottom": "1px solid #E5E7EB"})
                ]))
            
            duplicates_section = html.Div([
                html.H5("Ignored Duplicate Records", style={"fontSize": "13px", "fontWeight": "800", "color": "#B91C1C", "marginTop": "14px", "marginBottom": "6px"}),
                html.P("The following policies already exist in the database and were neglected to prevent duplication:", style={"fontSize": "11px", "color": "#6B7280", "margin": "0 0 6px"}),
                html.Div(
                    html.Table([
                        html.Thead(html.Tr([
                            html.Th("Policy Number", style={"backgroundColor": "#FEE2E2", "color": "#991B1B", "padding": "6px 10px", "textAlign": "left"}),
                            html.Th("Client Name", style={"backgroundColor": "#FEE2E2", "color": "#991B1B", "padding": "6px 10px", "textAlign": "left"}),
                            html.Th("Carrier Name", style={"backgroundColor": "#FEE2E2", "color": "#991B1B", "padding": "6px 10px", "textAlign": "left"}),
                            html.Th("Action", style={"backgroundColor": "#FEE2E2", "color": "#991B1B", "padding": "6px 10px", "textAlign": "left"})
                        ])),
                        html.Tbody(dup_rows)
                    ], style={"width": "100%", "borderCollapse": "collapse", "fontSize": "11px"}),
                    style={"maxHeight": "180px", "overflowY": "auto", "border": "1px solid #FCA5A5", "borderRadius": "6px", "marginBottom": "14px"}
                )
            ])
            modal_body.children.append(duplicates_section)
            
        if updates:
            up_rows = []
            for item in updates[:50]:
                up_rows.append(html.Tr([
                    html.Td(item['policy_number'], style={"fontFamily": "monospace", "fontWeight": "600", "padding": "6px 10px", "borderBottom": "1px solid #E5E7EB"}),
                    html.Td(item['client_name'], style={"padding": "6px 10px", "borderBottom": "1px solid #E5E7EB"}),
                    html.Td(item['old_status'], style={"color": "#6B7280", "padding": "6px 10px", "borderBottom": "1px solid #E5E7EB"}),
                    html.Td("→", style={"fontWeight": "bold", "textAlign": "center", "padding": "6px 10px", "borderBottom": "1px solid #E5E7EB"}),
                    html.Td(item['new_status'], style={"color": "#2563EB", "fontWeight": "600", "padding": "6px 10px", "borderBottom": "1px solid #E5E7EB"}),
                    html.Td(item.get('action', 'Updated & Logged'), style={"color": "#1E40AF", "fontWeight": "600", "padding": "6px 10px", "borderBottom": "1px solid #E5E7EB"})
                ]))
                
            updates_section = html.Div([
                html.H5("Existing Records Updated & Logged", style={"fontSize": "13px", "fontWeight": "800", "color": "#1E3A8A", "marginTop": "14px", "marginBottom": "6px"}),
                html.P("The following existing policies/clients had updated fields which were saved to the database and logged to dataset_updates.log:", style={"fontSize": "11px", "color": "#6B7280", "margin": "0 0 6px"}),
                html.Div(
                    html.Table([
                        html.Thead(html.Tr([
                            html.Th("Policy Number", style={"backgroundColor": "#DBEAFE", "color": "#1E40AF", "padding": "6px 10px", "textAlign": "left"}),
                            html.Th("Client Name", style={"backgroundColor": "#DBEAFE", "color": "#1E40AF", "padding": "6px 10px", "textAlign": "left"}),
                            html.Th("Old Value", style={"backgroundColor": "#DBEAFE", "color": "#1E40AF", "padding": "6px 10px", "textAlign": "left"}),
                            html.Th("", style={"backgroundColor": "#DBEAFE", "color": "#1E40AF", "padding": "6px 10px", "textAlign": "center"}),
                            html.Th("New Value", style={"backgroundColor": "#DBEAFE", "color": "#1E40AF", "padding": "6px 10px", "textAlign": "left"}),
                            html.Th("Details", style={"backgroundColor": "#DBEAFE", "color": "#1E40AF", "padding": "6px 10px", "textAlign": "left"})
                        ])),
                        html.Tbody(up_rows)
                    ], style={"width": "100%", "borderCollapse": "collapse", "fontSize": "11px"}),
                    style={"maxHeight": "180px", "overflowY": "auto", "border": "1px solid #BFDBFE", "borderRadius": "6px"}
                )
            ])
            modal_body.children.append(updates_section)
        
        # 4. Reset UI state & trigger full dashboard updates
        return None, None, "Live DB", None, n_clicks, True, modal_body
        
    except Exception as e:
        print(f"[commit] Error during commit: {e}")
        # Write to ingestion audit log on failure
        os.makedirs('logs', exist_ok=True)
        timestamp_log = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp_log}] User loaded data. File: {filename}, Status: Ingestion Failed with error: {e}.\n"
        try:
            with open(os.path.join('logs', 'audit_ingestion.log'), 'a') as f:
                f.write(log_line)
        except Exception as log_err:
            print(f"[audit] Error writing audit ingestion log: {log_err}")
        
        err_msg = html.Div(f"⚠ Commit Error: {e}", style={"color": "#EF4444", "fontWeight": "bold"})
        return dash.no_update, dash.no_update, f"⚠ Commit Error: {e}", dash.no_update, dash.no_update, True, err_msg


@app.callback(
    Output('ingestion-result-modal', 'is_open', allow_duplicate=True),
    Input('btn-close-ingestion-result', 'n_clicks'),
    prevent_initial_call=True
)
def close_ingestion_result_modal(n_clicks):
    if n_clicks and n_clicks > 0:
        return False
    return dash.no_update


# ── Update Claim Status (with audit logging) ───────────────────────────────────

from sqlalchemy import text

@app.callback(
    [Output('claim-update-status', 'children'),
     Output('drilldown-data-table', 'data'),
     Output('refresh-trigger', 'data', allow_duplicate=True)],
    Input('btn-update-claim-status', 'n_clicks'),
    [State('dd-update-claim-policy', 'value'),
     State('dd-update-claim-status', 'value'),
     State('drilldown-data-table', 'data')],
    prevent_initial_call=True
)
def update_claim_status(n_clicks, policy_number, new_status, current_data):
    if not n_clicks or not policy_number or not new_status:
        return dash.no_update, dash.no_update, dash.no_update

    try:
        engine = db_writer.get_engine()
        claim_number = None
        old_status = None
        
        with engine.connect() as conn:
            # 1. Fetch current claim details
            query = text("""
                SELECT c.claim_id, c.claim_number, c.status
                FROM claims c
                JOIN policies p ON c.policy_id = p.policy_id
                WHERE p.policy_number = :policy_number
            """)
            result = conn.execute(query, {"policy_number": policy_number}).fetchone()
            
            if result is None:
                err_msg = html.Div(f"No claim record found for policy {policy_number}.", style={"color": "#EF4444", "fontSize": "11px", "fontWeight": "bold", "marginTop": "8px"})
                return err_msg, dash.no_update, dash.no_update
                
            claim_id, claim_number, old_status = result
            
            # 2. Update status in database
            update_query = text("""
                UPDATE claims SET status = :new_status WHERE claim_id = :claim_id
            """)
            conn.execute(update_query, {"new_status": new_status, "claim_id": claim_id})
            try:
                conn.commit()
            except:
                pass
                
        # 3. Log the status change history
        os.makedirs('logs', exist_ok=True)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] Claim {claim_number}: Status changed from '{old_status}' to '{new_status}' by System Admin.\n"
        with open(os.path.join('logs', 'claim_status_history.log'), 'a') as f:
            f.write(log_line)
            
        # 4. Force reload memory master data
        db.df_global = db.get_data()
        
        # 5. Update the local datatable data inline
        updated_data = []
        for row in current_data:
            if row.get('policy_number') == policy_number:
                row['claim_status'] = new_status
            updated_data.append(row)
            
        success_msg = html.Div(
            f"Successfully updated claim status to '{new_status}' and logged the transaction.",
            style={
                "color": "#10B981", "fontSize": "11px", "fontWeight": "bold", "marginTop": "8px",
                "background": "#ECFDF5", "border": "1px solid #A7F3D0", "padding": "8px 12px", "borderRadius": "4px"
            }
        )
        
        return success_msg, updated_data, n_clicks
        
    except Exception as e:
        print(f"[status-update] Error updating claim status: {e}")
        err_msg = html.Div(f"Database error: {e}", style={"color": "#EF4444", "fontSize": "11px", "fontWeight": "bold", "marginTop": "8px"})
        return err_msg, dash.no_update, dash.no_update


# ── Toggle Ingest Button based on Header Verification Checklist ────────────────

@app.callback(
    [Output('btn-verify-commit', 'disabled'),
     Output('btn-verify-commit', 'className'),
     Output('btn-verify-commit', 'title'),
     Output('checklist-counter-badge', 'children'),
     Output('checklist-counter-badge', 'className')],
    [Input('uploaded-filename-store', 'data'),
     Input('uploaded-data-store', 'data')]
)
def toggle_verify_button(filename, mapped_data):
    print(f"[toggle_verify_button] Triggered. filename: {filename}, mapped_data is None: {mapped_data is None}")
    if filename and mapped_data:
        res = (False, "hdr-btn hdr-btn--green", "Click to Ingest to Database", "Verified", "checklist-counter checklist-counter--complete")
        print(f"[toggle_verify_button] Enabling commit button: {res}")
        return res
    else:
        res = (True, "hdr-btn hdr-btn--outline", "No file loaded or mapping incomplete", "0 / 13 Checked", "checklist-counter")
        print(f"[toggle_verify_button] Disabling commit button: {res}")
        return res


# ── Lead Tracker — Filter & Sub-Tab Callback ──────────────────────────────────

@app.callback(
    [Output('lt-table-container', 'children'),
     Output('lt-kpi-container',   'children'),
     Output('lt-table-title',     'children'),
     Output('lt-date-from',       'date'),
     Output('lt-date-to',         'date'),
     Output('lt-product',         'value'),
     Output('lt-source',          'value'),
     Output('lt-carrier',         'value'),
     Output('lt-client-type',     'value'),
     Output('lt-preset',          'value'),
     Output('lt-toggle-container', 'style'),
     Output('lt-product-detailed', 'value')],
    [Input('lt-date-from',    'date'),
     Input('lt-date-to',      'date'),
     Input('lt-product',      'value'),
     Input('lt-source',       'value'),
     Input('lt-carrier',      'value'),
     Input('lt-client-type',  'value'),
     Input('lt-subtab',       'value'),
     Input('lt-clear',        'n_clicks'),
     Input('uploaded-data-store', 'data'),
     Input('refresh-trigger', 'data'),
     Input('lt-product-detailed', 'value')],
    prevent_initial_call=True,
)
def update_lead_tracker(date_from, date_to, product, source, carrier,
                        client_type, subtab, clear_n, stored_data, refresh_data,
                        product_detailed):
    """
    Filters the dataset and rebuilds the lead pipeline table
    based on the selected filters and active sub-tab.
    """
    triggered = ctx.triggered_id

    # Load full dataset
    dff = get_current_df(stored_data)
    if dff is None or dff.empty:
        empty_msg = html.Div("No data available.", style={"padding": "20px", "color": "#6B7280"})
        return empty_msg, dash.no_update, "Sales Pipeline", dash.no_update, dash.no_update, '__all__', '__all__', '__all__', '__all__', None, {"display": "none"}, dash.no_update

    # --- Handle Clear Filters ---
    if triggered == 'lt-clear':
        if 'issue_date' in dff.columns:
            dates = pd.to_datetime(dff['issue_date'], errors='coerce').dropna()
            min_d = dates.min().date().isoformat() if not dates.empty else None
            max_d = dates.max().date().isoformat() if not dates.empty else None
        else:
            min_d = max_d = None
        pivot = build_lead_pivot(dff, 'category', show_subcategories=False)
        kpis  = _lt_kpi_and_funnel_panel(dff)
        return pivot, kpis, "Sales Pipeline Summary — By Product", min_d, max_d, '__all__', '__all__', '__all__', '__all__', None, {"display": "block"}, []

    # --- Apply Date Filter ---
    if 'issue_date' in dff.columns:
        dff['issue_date'] = pd.to_datetime(dff['issue_date'], errors='coerce')
        if date_from:
            dff = dff[dff['issue_date'] >= pd.Timestamp(date_from)]
        if date_to:
            dff = dff[dff['issue_date'] <= pd.Timestamp(date_to) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]

    # --- Apply Dropdown Filters ---
    if product and product != '__all__' and 'category' in dff.columns:
        dff = dff[dff['category'] == product]
    if source and source != '__all__' and 'distribution_channel' in dff.columns:
        dff = dff[dff['distribution_channel'] == source]
    if carrier and carrier != '__all__' and 'carrier_name' in dff.columns:
        dff = dff[dff['carrier_name'] == carrier]
    if client_type and client_type != '__all__' and 'client_type' in dff.columns:
        dff = dff[dff['client_type'] == client_type]

    is_prod_tab = (subtab or 'product') == 'product'
    toggle_style = {"display": "block"} if is_prod_tab else {"display": "none"}

    if dff.empty:
        empty_msg = html.Div(
            "No records match the current filters. Try adjusting your selection.",
            style={"padding": "24px", "color": "#6B7280", "fontStyle": "italic", "textAlign": "center"}
        )
        return empty_msg, _lt_kpi_and_funnel_panel(dff), "No Results", dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, toggle_style, dash.no_update

    # --- Route to correct table based on sub-tab ---
    kpis = _lt_kpi_and_funnel_panel(dff)

    SUB_TAB_MAP = {
        'product':       ('category',             'Sales Pipeline Summary — By Product'),
        'source':        ('distribution_channel', 'Sales Pipeline Summary — By Source / Channel'),
        'carrier':       ('carrier_name',         'Sales Pipeline Summary — By Carrier / Insurer'),
    }

    show_sub = ('show' in (product_detailed or [])) if is_prod_tab else False

    if subtab == 'nonconversion':
        table = build_nonconversion_table(dff)
        title = "Non-Conversion Analysis — Lost & Lapsed Leads"
    elif subtab == 'followup':
        table = build_followup_table(dff)
        title = "Follow-Up Pipeline — Pending Lead Actions"
    elif subtab is None:
        table = build_nonconversion_table(dff)
        title = "Non-Conversion Analysis — Lost & Lapsed Leads"
        toggle_style = {"display": "none"}
    else:
        group_col, title = SUB_TAB_MAP.get(subtab or 'product', ('category', 'Sales Pipeline Summary — By Product'))
        if group_col not in dff.columns:
            group_col = 'category'
        table = build_lead_pivot(dff, group_col, show_subcategories=show_sub)

    return table, kpis, title, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, toggle_style, dash.no_update

# ── Lead Tracker — Date Preset Callback ────────────────────────────────────────

@app.callback(
    [Output('lt-date-from', 'date', allow_duplicate=True),
     Output('lt-date-to', 'date', allow_duplicate=True)],
    [Input('lt-go', 'n_clicks')],
    [State('lt-preset', 'value')],
    prevent_initial_call=True
)
def update_lead_date_preset(go_clicks, preset):
    if not preset:
        raise dash.exceptions.PreventUpdate
        
    today = pd.Timestamp.now().normalize()
    
    start_date = None
    end_date = None
    
    if preset == 'today':
        start_date = today
        end_date = today
    elif preset == 'yesterday':
        start_date = today - pd.Timedelta(days=1)
        end_date = today - pd.Timedelta(days=1)
    elif preset == 'this_week':
        start_date = today - pd.Timedelta(days=today.weekday())
        end_date = today
    elif preset == 'last_week':
        start_of_this_week = today - pd.Timedelta(days=today.weekday())
        start_date = start_of_this_week - pd.Timedelta(days=7)
        end_date = start_of_this_week - pd.Timedelta(days=1)
    elif preset == 'this_month':
        start_date = today.replace(day=1)
        end_date = today
    elif preset == 'last_month':
        first_of_this_month = today.replace(day=1)
        end_date = first_of_this_month - pd.Timedelta(days=1)
        start_date = end_date.replace(day=1)
    elif preset == 'last_30_days':
        start_date = today - pd.Timedelta(days=30)
        end_date = today
    elif preset == 'last_90_days':
        start_date = today - pd.Timedelta(days=90)
        end_date = today
        
    if start_date and end_date:
        return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
        
    raise dash.exceptions.PreventUpdate


# ── Lead Tracker — Drilldown Modal Callback ───────────────────────────────────

@app.callback(
    [Output('lt-drilldown-modal', 'is_open'),
     Output('lt-drilldown-modal-title', 'children'),
     Output('lt-drilldown-modal-body', 'children')],
    [Input('lt-pivot-table', 'active_cell'),
     Input('lt-drilldown-modal-close', 'n_clicks')],
    [State('lt-pivot-table', 'data'),
     State('lt-date-from', 'date'),
     State('lt-date-to', 'date'),
     State('lt-product', 'value'),
     State('lt-source', 'value'),
     State('lt-carrier', 'value'),
     State('lt-client-type', 'value'),
     State('lt-subtab', 'value'),
     State('uploaded-data-store', 'data'),
     State('lt-drilldown-modal', 'is_open')],
    prevent_initial_call=True
)
def display_drilldown(active_cell, close_clicks, table_data, date_from, date_to,
                      product, source, carrier, client_type, subtab, stored_data, is_open):
    triggered = ctx.triggered_id
    
    if triggered == 'lt-drilldown-modal-close':
        return False, dash.no_update, dash.no_update
        
    if not active_cell or not table_data:
        return is_open, dash.no_update, dash.no_update
        
    # Get clicked cell details
    row_idx = active_cell['row']
    col_id = active_cell['column_id']
    
    if row_idx >= len(table_data):
        return is_open, dash.no_update, dash.no_update
        
    row_data = table_data[row_idx]
    
    # Load and apply same filters to raw data
    dff = get_current_df(stored_data)
    if dff is None or dff.empty:
        return is_open, "No Data", "No data available."
        
    # Apply Date filters
    if 'issue_date' in dff.columns:
        dff['issue_date'] = pd.to_datetime(dff['issue_date'], errors='coerce')
        if date_from:
            dff = dff[dff['issue_date'] >= pd.Timestamp(date_from)]
        if date_to:
            dff = dff[dff['issue_date'] <= pd.Timestamp(date_to) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)]

    # Apply Dropdown filters
    if product and product != '__all__' and 'category' in dff.columns:
        dff = dff[dff['category'] == product]
    if source and source != '__all__' and 'distribution_channel' in dff.columns:
        dff = dff[dff['distribution_channel'] == source]
    if carrier and carrier != '__all__' and 'carrier_name' in dff.columns:
        dff = dff[dff['carrier_name'] == carrier]
    if client_type and client_type != '__all__' and 'client_type' in dff.columns:
        dff = dff[dff['client_type'] == client_type]
        
    # Map stage column
    dff = _map_stages(dff)
    
    # Drill down based on active tab and clicked row
    current_subtab = subtab or 'product'
    title = "Lead Details"
    
    if current_subtab == 'product':
        cat_val = row_data.get('category')
        sub_val = row_data.get('sub_category')
        
        if cat_val is None:
            cat_val = row_data.get('label')
            
        if cat_val and cat_val != "Grand Total":
            dff = dff[dff['category'] == cat_val]
            title = f"Leads — Category: {cat_val}"
            
            if sub_val and sub_val != "Unknown" and sub_val != "":
                dff = dff[dff['sub_category'] == sub_val]
                title += f" ({sub_val})"
        else:
            title = "Leads — All Products"
    else:
        label_val = row_data.get('label')
        if label_val and label_val != "Grand Total":
            if current_subtab == 'source':
                dff = dff[dff['distribution_channel'] == label_val]
                title = f"Leads — Channel: {label_val}"
            elif current_subtab == 'carrier':
                dff = dff[dff['carrier_name'] == label_val]
                title = f"Leads — Carrier: {label_val}"
        else:
            title = f"Leads — All {current_subtab.title()}s"
            
    # Filter by stage (col_id) if it's one of the lead stages
    if col_id in STAGE_ORDER:
        dff = dff[dff['lead_stage'] == col_id]
        title += f" [Stage: {col_id}]"
    elif col_id == 'Total':
        title += " [All Stages]"
    else:
        title += " [All Stages]"
        
    # Now build a clean detailed DataTable inside the Modal
    if dff.empty:
        modal_content = html.Div("No records found matching this drill-down cell.", style={"padding": "20px", "textAlign": "center", "color": "#6B7280"})
    else:
        # Select columns to display
        cols_to_show = ['policy_number', 'client_name', 'category', 'sub_category', 'carrier_name', 'premium_amount', 'policy_status', 'issue_date']
        display_df = dff[cols_to_show].copy()
        
        # Add Serial Numbers
        display_df.insert(0, 's_no', range(1, len(display_df) + 1))
        
        # Format premium amount and dates
        display_df['premium_amount'] = display_df['premium_amount'].apply(lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "₹0.00")
        display_df['issue_date'] = display_df['issue_date'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else "N/A")
        
        dt_columns = []
        for c in ['s_no'] + cols_to_show:
            if c == 's_no':
                dt_columns.append({"name": "S.No.", "id": c})
            else:
                dt_columns.append({"name": c.replace('_', ' ').title(), "id": c})
        
        modal_content = dash_table.DataTable(
            data=display_df.to_dict('records'),
            columns=dt_columns,
            page_size=10,
            style_cell={
                'fontFamily': 'Plus Jakarta Sans, Inter, sans-serif',
                'fontSize': '11px',
                'padding': '8px 12px',
                'border': '1px solid #E5E7EB',
            },
            style_header={
                'backgroundColor': TVS_BLUE,
                'color': 'white',
                'fontWeight': 'bold',
                'textAlign': 'left',
                'padding': '10px 12px',
            },
            style_cell_conditional=[
                {'if': {'column_id': 's_no'}, 'textAlign': 'left'},
                {'if': {'column_id': 'policy_number'}, 'textAlign': 'left'},
                {'if': {'column_id': 'client_name'}, 'textAlign': 'left'},
                {'if': {'column_id': 'category'}, 'textAlign': 'left'},
                {'if': {'column_id': 'sub_category'}, 'textAlign': 'left'},
                {'if': {'column_id': 'carrier_name'}, 'textAlign': 'left'},
                {'if': {'column_id': 'policy_status'}, 'textAlign': 'left'},
                {'if': {'column_id': 'issue_date'}, 'textAlign': 'left'},
                {'if': {'column_id': 'premium_amount'}, 'textAlign': 'right'},
            ],
            style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#f9fafb'}],
            style_table={
                'width': '100%',
            }
        )
        
    return True, title, modal_content


# ── tab6b (Channel Mix) Filter Callback ────────────────────────────────────────

@app.callback(
    Output("tab6b-content-container", "children"),
    [Input('uploaded-data-store', 'data'),
     Input('refresh-trigger', 'data')],
    prevent_initial_call=True
)
def update_tab6b_content(stored_data, refresh_data):
    dff = get_current_df(stored_data)
    if dff is None or dff.empty:
        return html.Div("No data available.", style={"padding": "20px", "color": "#6B7280"})
    
    return build_tab6b_content(dff, "all", dff)
