import os
import re
import time
import pandas as pd
import requests
import json
from sql_templates import match_template
from threading import Lock
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv
import google.generativeai as genai

# Load .env from package directory
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(base_dir, ".env"))

# Configure Gemini API client
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    print("[chat_helper] Warning: GEMINI_API_KEY not found in environment.")


# ── Persistent DB engine with connection pool ──────────────────────────────────
# Created once at module load; reused for every SQL execution.
_db_engine = None

def _get_engine():
    global _db_engine
    if _db_engine is None:
        db_host     = os.getenv('DB_HOST', '127.0.0.1')
        db_user     = os.getenv('DB_USER', 'root')
        db_password = os.getenv('DB_PASSWORD', 'root')
        db_name     = os.getenv('DB_NAME', 'insurance_brokerage')
        _db_engine = create_engine(
            f"mysql+mysqldb://{db_user}:{db_password}@{db_host}/{db_name}",
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _db_engine


# ── Ollama probe cache ─────────────────────────────────────────────────────────
# Checking Ollama liveness on every query added 1-2 s per call.
# Cache the result for 60 s so the probe only fires once per minute.
_ollama_cache: dict = {"model": None, "ts": 0.0}
_OLLAMA_CACHE_TTL = 60  # seconds

# ── SQL Query Cache ────────────────────────────────────────────────────────────
_sql_cache: dict = {}
_sql_cache_lock = Lock()

def get_local_ollama_model() -> str | None:
    """Return the best available Ollama model name, or None if Ollama is offline.
    Result is cached for 60 seconds to avoid a live HTTP probe on every query.
    """
    now = time.monotonic()
    if now - _ollama_cache["ts"] < _OLLAMA_CACHE_TTL:
        return _ollama_cache["model"]

    model = None
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=1.5)
        if response.status_code == 200:
            models_data = response.json()
            models = [m['name'] for m in models_data.get('models', [])]
            for m in models:
                if "qwen2.5-coder" in m:
                    model = m
                    break
            if model is None and models:
                model = models[0]
    except Exception:
        pass

    _ollama_cache["model"] = model
    _ollama_cache["ts"] = now
    return model


DB_SCHEMA_PROMPT = """
You are an expert MySQL Database assistant for an Insurance Brokerage company.
Your job is to translate natural language questions into executable MySQL SELECT queries based on the following database schema.

### Database Schema Guidelines:
1. **clients**:
   - `client_id` (INT, Primary Key)
   - `name` (VARCHAR, Client's name)
   - `client_type` (VARCHAR, e.g., 'Individual/B2C', 'Corporate/B2B')
   - `region_code` (VARCHAR, 2-letter state code like 'MH', 'DL', 'TN', 'KA', 'UP', 'GJ')
   - `region_name` (VARCHAR, full state name like 'Maharashtra', 'Delhi', 'Tamil Nadu', 'Karnataka', 'Uttar Pradesh', 'Gujarat')
   - `address` (VARCHAR)
   - `is_active` (TINYINT, 1=active, 0=inactive)
   ⚠️ CRITICAL: There is NO separate `regions` table. Region data (region_code, region_name) is stored DIRECTLY inside the `clients` table. NEVER join or reference a `regions` table — it does not exist.

2. **carriers**:
   - `carrier_id` (INT, Primary Key)
   - `carrier_name` (VARCHAR, e.g., 'Tata AIG', 'HDFC Ergo', 'ICICI Lombard')
   - `is_active` (TINYINT, 1=active, 0=inactive)

3. **products**:
   - `product_id` (INT, Primary Key)
   - `carrier_id` (INT, Foreign Key to carriers)
   - `category` (VARCHAR, e.g., 'Motor', 'Health', 'Travel', 'Fire')
   - `sub_category` (VARCHAR, e.g., 'Two Wheeler', 'Private Car', 'Family Floater', 'Individual Health')
   - `is_active` (TINYINT, 1=active, 0=inactive)

4. **policies**:
   - `policy_id` (INT, Primary Key)
   - `policy_number` (VARCHAR)
   - `client_id` (INT, Foreign Key to clients)
   - `product_id` (INT, Foreign Key to products)
   - `created_by_user_id` (INT, Foreign Key to backoffice_users)
   - `issue_date` (DATETIME)
   - `expiry_date` (DATETIME)
   - `premium_amount` (DECIMAL, Total premium paid)
   - `status` (VARCHAR, e.g., 'Active', 'Expired', 'Renewed', 'Cancelled')
   - `distribution_channel` (VARCHAR, e.g., 'Online', 'Offline', 'Direct')
   - `is_active` (TINYINT, 1=active, 0=inactive)

5. **claims**:
   - `claim_id` (INT, Primary Key)
   - `policy_id` (INT, Foreign Key to policies)
   - `claim_number` (VARCHAR)
   - `quote_approved_amount` (DECIMAL, Approved claim payout amount)
   - `status` (VARCHAR, e.g., 'No Claim', 'Pending', 'Approved', 'Rejected')
   - `is_active` (TINYINT, 1=active, 0=inactive)
   ⚠️ CRITICAL: There is NO claim_date column. Never query or filter by claim_date. Always join to policies and use p.issue_date.

6. **sales_commissions**:
   - `commission_id` (INT, Primary Key)
   - `policy_id` (INT, Foreign Key to policies)
   - `calculated_amount` (DECIMAL, Brokerage/commission earned by the broker)
   - `status` (VARCHAR)
   - `is_active` (TINYINT, 1=active, 0=inactive)
   ⚠️ CRITICAL: There is NO claim_number column in this table. NEVER join sales_commissions directly to claims. You MUST join sales_commissions to policies using policy_id.

7. **backoffice_users**:
   - `user_id` (INT, Primary Key)
   - `username` (VARCHAR, e.g., 'arun.kumar')
   - `system_role` (VARCHAR)
   - `is_active` (TINYINT)

### MANDATORY Table Aliases (you MUST use these exact aliases for every table — NEVER use 'c' for carriers):
- `clients`           → alias `cli`
- `carriers`          → alias `car`
- `products`          → alias `pr`
- `policies`          → alias `p`
- `claims`            → alias `cl`
- `sales_commissions` → alias `sc`
- `backoffice_users`  → alias `bu`

### Rules & Instructions:
- Generate ONLY a MySQL SELECT query. Do not return any updates, deletions, modifications or insertions.
- Return ONLY the raw SQL code wrapped in a markdown code block: ```sql ... ```. No other conversational text.
- ALWAYS use the MANDATORY table aliases listed above. Never deviate.
- Filter out inactive records by checking `is_active = 1` for all queried tables unless the user asks specifically for deleted/inactive records.
- Standard JOIN keys:
  - Join policies with clients:          `p.client_id = cli.client_id`
  - Join policies with products:         `p.product_id = pr.product_id`
  - Join products with carriers:         `pr.carrier_id = car.carrier_id`
  - Join claims with policies:           `cl.policy_id = p.policy_id`
  - Join sales_commissions with policies:`sc.policy_id = p.policy_id`
  ⚠️ CRITICAL JOIN RULE: There is NO direct relationship or foreign key between clients (`clients / cli`) and products (`products / pr`). NEVER write `cli.client_id = pr.client_id` or similar direct joins. To relate clients to products or carriers, you MUST always join through the `policies` table (i.e. `clients cli JOIN policies p ON cli.client_id = p.client_id JOIN products pr ON p.product_id = pr.product_id`).
  ⚠️ CRITICAL JOIN RULE 2: There is NO direct relationship or foreign key between claims (`claims / cl`) and sales_commissions (`sales_commissions / sc`). NEVER join them directly on columns like `claim_number` or `policy_id`. To query both claims and commissions, you MUST join both of them separately to the `policies` table `p` (i.e., `FROM policies p JOIN claims cl ON cl.policy_id = p.policy_id JOIN sales_commissions sc ON sc.policy_id = p.policy_id`).
  ⚠️ CRITICAL JOIN ORDER RULE: You must introduce each table with its own `JOIN` clause before referencing its columns or alias. Never write a join condition referencing an alias that has not been joined yet (for example, do not reference `car.carrier_id` inside `JOIN products pr` unless `carriers car` is already joined). Always write them as separate, sequential joins in logical order (e.g. `JOIN products pr ON p.product_id = pr.product_id JOIN carriers car ON pr.carrier_id = car.carrier_id`).
- Example correct query for carrier performance:
  ```sql
  SELECT car.carrier_name, SUM(p.premium_amount) AS total_premium
  FROM policies p
  JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
  JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
  WHERE p.is_active = 1
  GROUP BY car.carrier_id, car.carrier_name
  ORDER BY total_premium DESC LIMIT 3;
  ```
- Example correct query for region analysis (NOTE: use cli.region_name directly — NO regions table):
  ```sql
  SELECT cli.region_name, SUM(cl.quote_approved_amount) AS total_claims
  FROM claims cl
  JOIN policies p ON cl.policy_id = p.policy_id AND p.is_active = 1
  JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
  WHERE cl.is_active = 1
  GROUP BY cli.region_name
  ORDER BY total_claims DESC LIMIT 1;
  ```
- Example correct query for clients residing in a state and using a specific carrier:
  ```sql
  SELECT DISTINCT cli.name, cli.address
  FROM clients cli
  JOIN policies p ON cli.client_id = p.client_id AND p.is_active = 1
  JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
  JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
  WHERE cli.region_name = 'Tamil Nadu' AND car.carrier_name = 'TATA AIG' AND cli.is_active = 1;
  ```
- Example correct query for distinct categories and carriers (using exact table aliases 'pr' and 'car'):
  ```sql
  SELECT DISTINCT pr.category, car.carrier_name
  FROM products pr
  JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
  WHERE pr.is_active = 1;
  ```
- Example correct query for claims/losses within a specific time period (e.g., last 3 months):
  ```sql
  SELECT cl.claim_number, cl.quote_approved_amount
  FROM claims cl
  JOIN policies p ON cl.policy_id = p.policy_id AND p.is_active = 1
  WHERE cl.is_active = 1 AND p.issue_date >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH);
  ```
- WARNING FOR SMALL LLMS (CRITICAL): Never use table alias 'p' or 'prod' for products (always use 'pr'). Never use 'c' or 'corr' for carriers (always use 'car'). The products table column is 'category' (NOT 'category_name').
- WARNING ON DATES (CRITICAL): The `claims` table does NOT contain a `claim_date`, `created_at`, or any other date column. If asked for claims/losses in a time period (like "last 3 months"), you MUST join `policies` (`p`) and filter on `p.issue_date`.
- Handling unavailable/non-existent columns (e.g., gender):
  ⚠️ CRITICAL: The `clients` table does NOT contain a `gender` column. If the user asks for "female clients" or "male clients", do NOT use a `gender` column in the WHERE clause (doing so will crash). Instead, query the clients without filtering by gender, as we do not store this data.
- Metrics:
  - Written Premium: SUM(p.premium_amount)
  - Claims/Losses: SUM(cl.quote_approved_amount)
  - Commission/Brokerage Earned: SUM(sc.calculated_amount)
  - Loss Ratio / Incurred Claim Ratio (ICR): (SUM(cl.quote_approved_amount) / SUM(p.premium_amount)) * 100
- WARNING ON ICR (CRITICAL): There is NO column named 'icr' or 'incurred_claim_ratio' in any table. If the user asks for 'ICR' or 'Incurred Claim Ratio', you MUST calculate it using the formula: (SUM(cl.quote_approved_amount) / SUM(p.premium_amount)) * 100. This requires joining both 'claims' (cl) and 'policies' (p).
- Be extremely precise with joins and aggregate functions.
- **Avoid MySQL GROUP BY Errors:** Include ALL selected non-aggregated columns in the GROUP BY clause (e.g. `GROUP BY car.carrier_id, car.carrier_name` not just `GROUP BY car.carrier_id`).
- **Currency & Formatting (IMPORTANT):** All financial values represent Indian Rupees (INR). Use ₹ symbol (not $) and format nicely (e.g., ₹2,80,51,677.88 or ₹2.8 Crore) in your text explanations.
- **Handling Analytical & Diagnostic Questions (IMPORTANT):** For open-ended business questions (e.g., "why are we losing money?", "which areas have high losses?"), generate a diagnostic SQL query joining policies, products, claims grouped by category/carrier/region with loss ratios sorted descending. Never return an empty string for analytical requests.
- If the question is completely unrelated to insurance analytics and cannot be mapped to any SQL query, only then return an empty string.
"""

def post_process_summary(text: str) -> str:
    """
    Post-processes AI-generated summaries to fix currency symbols,
    replace Western units (million/billion) with Indian units (Lakh/Crore),
    and format large numeric values into proper Indian Rupee notation.
    Works on output from both local Qwen and cloud Gemini.
    """

    def to_indian_rupee(val: float) -> str:
        """Converts a float into Indian Rupee formatted string like ₹55,79,703.07"""
        if val < 1000:
            return f"₹{val:.2f}"
        integer_part = str(int(val))
        decimal_part = f"{val:.2f}".split(".")[1]
        if len(integer_part) <= 3:
            return f"₹{integer_part}.{decimal_part}"
        last3 = integer_part[-3:]
        rest = integer_part[:-3]
        groups = []
        while rest:
            groups.append(rest[-2:])
            rest = rest[:-2]
        groups.reverse()
        formatted = ",".join(g for g in groups if g) + "," + last3
        return f"₹{formatted}.{decimal_part}"

    # Step 0: Replace million/billion with Indian Lakh/Crore
    def replace_western_unit(match):
        prefix = match.group(1) or ""   # e.g. "$", "₹", "Rs.", "INR" or ""
        val_str = match.group(2).replace(",", "")
        unit    = match.group(3).lower()
        try:
            val = float(val_str)
            if unit == "million":
                lakh_val = val * 10
                if lakh_val >= 100:
                    crore_val = lakh_val / 100
                    return f" ₹{crore_val:,.2f} Crore"
                return f" ₹{lakh_val:,.2f} Lakh"
            elif unit == "billion":
                crore_val = val * 100
                return f" ₹{crore_val:,.2f} Crore"
        except (ValueError, TypeError):
            pass
        return match.group(0)

    text = re.sub(
        r'(Rs\.?|INR|₹|\$)?\s*(\d+(?:\.\d+)?)\s*(million|billion)',
        replace_western_unit,
        text,
        flags=re.IGNORECASE
    )

    def replace_dollar_number(match):
        """Handle $12345.67 patterns as a complete unit"""
        raw = match.group(1).replace(",", "")
        try:
            return to_indian_rupee(float(raw))
        except (ValueError, TypeError):
            return match.group(0)

    # Step 1: Handle $number patterns first (e.g. $3,987,234.50 → ₹39,87,234.50)
    text = re.sub(r'\$\s*([\d,]+(?:\.\d+)?)', replace_dollar_number, text)

    # Step 2: Replace any remaining bare $ signs
    text = text.replace("$", "₹")

    # Step 3: Format plain large numbers (>= 10,000) not already prefixed with ₹
    # Excludes: percentages (23.5%), years (2024, 1999), small counts (< 10000)
    # Only formats if surrounding context indicates a financial/currency value
    def replace_plain_number(match):
        """Handle bare large numbers not already prefixed with ₹ if context implies currency"""
        raw = match.group(0).replace(",", "")
        try:
            val = float(raw)
            if val < 10000:
                return match.group(0)
            if 1900 <= val <= 2099 and '.' not in raw:
                return match.group(0)
            
            # Check if surrounding text contains money-related keywords
            start_idx = max(0, match.start() - 40)
            end_idx = min(len(text), match.end() + 40)
            context = text[start_idx:end_idx].lower()
            
            money_keywords = ["premium", "claim", "commission", "brokerage", "payout", "amount", "loss", "revenue", "rupee", "rs.", "inr"]
            if any(kw in context for kw in money_keywords) and "client" not in context and "count" not in context:
                return to_indian_rupee(val)
            return match.group(0)
        except (ValueError, TypeError):
            return match.group(0)

    text = re.sub(r'(?<![₹\d.,])\b(\d{5,}(?:,\d+)*(?:\.\d+)?|\d{4,}(?:,\d+)+(?:\.\d+)?)\b(?!\s*%)', replace_plain_number, text)

    return text


# Legacy alias kept for any code that still calls get_db_connection()
def get_db_connection():
    return _get_engine()


# ── Known schema for structural SQL validation ────────────────────────────────
_VALID_COLUMNS: dict[str, set[str]] = {
    "cli": {"client_id", "name", "client_type", "region_code", "region_name", "address", "is_active"},
    "car": {"carrier_id", "carrier_name", "is_active"},
    "pr":  {"product_id", "carrier_id", "category", "sub_category", "is_active"},
    "p":   {"policy_id", "policy_number", "client_id", "product_id", "created_by_user_id",
            "issue_date", "expiry_date", "premium_amount", "status", "distribution_channel", "is_active"},
    "cl":  {"claim_id", "policy_id", "claim_number", "quote_approved_amount", "status", "is_active"},
    "sc":  {"commission_id", "policy_id", "calculated_amount", "status", "is_active"},
    "bu":  {"user_id", "username", "system_role", "is_active"},
}

# Map full table names to their mandatory aliases
_TABLE_ALIAS_MAP: dict[str, str] = {
    "clients": "cli", "carriers": "car", "products": "pr",
    "policies": "p", "claims": "cl", "sales_commissions": "sc",
    "backoffice_users": "bu",
}


def clean_and_validate_sql(sql_text: str) -> str | None:
    """
    Cleans the SQL code returned by the LLM and applies guardrails:
    1. Read-only SELECT check.
    2. Structural validation: every alias.column reference must match the known schema.
    """
    if not sql_text:
        return None
        
    # Strip markdown formatting
    cleaned = sql_text.strip()
    match = re.search(r'```sql\s*(.*?)\s*```', cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    else:
        cleaned = cleaned.replace('```sql', '').replace('```', '').strip()
        
    # Standardize spaces and remove comments
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'--.*$', '', cleaned, flags=re.MULTILINE)
    cleaned_check = cleaned.strip().lower()
    
    # Must start with SELECT
    if not cleaned_check.startswith("select"):
        return None
        
    # Forbidden keywords to prevent DDL/DML injection
    forbidden = [
        "insert", "update", "delete", "drop", "truncate", "alter", 
        "create", "replace", "grant", "revoke", "load_file", "into outfile"
    ]
    for word in forbidden:
        if re.search(r'\b' + re.escape(word) + r'\b', cleaned_check):
            return None

    # Block SELECT *
    if re.search(r'\bselect\s+\*', cleaned_check):
        print("[chat_helper] SQL VALIDATION FAILED: SELECT * is not allowed.")
        return None

    # ── Structural validation ──────────────────────────────────────────────
    # 1. Verify all table names referenced actually exist in our schema
    tables_referenced = re.findall(r'\b(?:from|join)\s+(\w+)', cleaned_check)
    valid_tables = set(_TABLE_ALIAS_MAP.keys())
    for t in tables_referenced:
        t_l = t.lower()
        if t_l in ("select", "on", "where", "join", "inner", "left", "right", "outer", "cross", "group", "order", "limit", "and", "or", "as", "using", "set", "having"):
            continue
        if t_l not in valid_tables:
            print(f"[chat_helper] SQL VALIDATION FAILED: Table '{t}' does not exist in our schema.")
            return None

    # 2. Find all declared table aliases from FROM / JOIN clauses
    declared_aliases: set[str] = set()
    # Match patterns: FROM table alias, FROM table AS alias, JOIN table alias ON, JOIN table AS alias ON
    for m in re.finditer(r'(?:from|join)\s+(\w+)\s+(?:as\s+)?(\w+)', cleaned_check):
        table_name, alias = m.group(1), m.group(2)
        if alias.lower() not in ("on", "where", "join", "inner", "left", "right", "outer", "cross", "group", "order", "limit", "and", "or", "as", "using", "set", "having"):
            declared_aliases.add(alias.lower())

    # 3. Find all alias.column references in the query
    col_refs = re.findall(r'\b(\w+)\.(\w+)\b', cleaned_check)
    
    for alias, col in col_refs:
        alias_l = alias.lower()
        col_l = col.lower()
        
        # Skip function-like patterns or subquery aliases we can't validate
        if alias_l in ("date_sub", "curdate", "now", "count", "sum", "avg", "min", "max", "ifnull", "coalesce"):
            continue
            
        # Check 1: Is the alias declared in FROM/JOIN?
        if alias_l not in declared_aliases:
            print(f"[chat_helper] SQL VALIDATION FAILED: alias '{alias}' used but never declared in FROM/JOIN.")
            return None
            
        # Check 2: Is the column valid for this alias?
        if alias_l in _VALID_COLUMNS:
            if col_l not in _VALID_COLUMNS[alias_l]:
                print(f"[chat_helper] SQL VALIDATION FAILED: column '{alias}.{col}' does not exist. Valid columns for '{alias}': {_VALID_COLUMNS[alias_l]}")
                return None
            
    return cleaned


def query_groq(system_prompt: str, user_prompt: str, temperature: float = 0.0, max_tokens: int = 250) -> str | None:
    """Helper to query Groq Cloud REST completions endpoint directly using requests."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
        
    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it", "mixtral-8x22b-32768"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    for model in models:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        try:
            print(f"[chat_helper] Attempting Groq inference with model '{model}'...")
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=15
            )
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                if content:
                    return content
            else:
                print(f"[chat_helper] Groq model '{model}' failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"[chat_helper] Groq error for model '{model}': {e}")
            
    return None


def generate_sql(user_query: str, conversation_context: list | None = None) -> str | None:
    """
    Generates a safe SQL query.  Resolution order:
      1. In-memory cache  (instant – repeat queries)
      2. Template cache   (instant – ~85 pre-built patterns)
      3. Groq Cloud LLM   (fast – primary if API key exists)
      4. Local Ollama LLM (slow – fallback/offline, retries up to 3×)
    
    Args:
        user_query: The natural language question from the user.
        conversation_context: Optional list of prior Q&A dicts for multi-turn memory.
            Each dict has keys: 'question', 'sql', 'summary' (all strings).
    """
    # ── 1. In-memory cache ────────────────────────────────────────────────
    norm_query = " ".join(user_query.strip().lower().split())
    with _sql_cache_lock:
        if norm_query in _sql_cache:
            print(f"[chat_helper] SQL Cache hit for user query: '{user_query}'")
            return _sql_cache[norm_query]

    # ── 2. Template cache (keyword-scored, instant) ───────────────────────
    template_sql, template_id = match_template(user_query)
    if template_sql:
        print(f"[chat_helper] Template match: '{template_id}' for query: '{user_query}'")
        with _sql_cache_lock:
            _sql_cache[norm_query] = template_sql
        return template_sql

    # ── Build conversation context string for LLM prompts ─────────────────
    context_str = ""
    if conversation_context:
        recent = conversation_context[-3:]  # last 3 turns max
        lines = []
        for turn in recent:
            lines.append(f"Q: {turn.get('question', '')}")
            lines.append(f"SQL: {turn.get('sql', 'N/A')}")
        context_str = "\n\nPrevious conversation (use this for context on follow-up questions):\n" + "\n".join(lines)

    # ── 3. Groq Cloud LLM (Primary) ───────────────────────────────────────
    if os.getenv("GROQ_API_KEY"):
        print("[chat_helper] Generating SQL using Groq...")
        sql_text = query_groq(
            system_prompt=DB_SCHEMA_PROMPT + context_str,
            user_prompt=f"Generate a MySQL SELECT query for this request: {user_query}",
            temperature=0.0,
            max_tokens=250
        )
        if sql_text:
            validated_sql = clean_and_validate_sql(sql_text)
            if validated_sql:
                print("[chat_helper] SQL generated by Groq validated successfully.")
                return validated_sql
            else:
                print("[chat_helper] SQL generated by Groq failed structural validation.")

    # ── 4. Local Ollama LLM fallback (for truly novel queries) ─────────────
    model_name = get_local_ollama_model()
    if not model_name:
        print("[chat_helper] No local Ollama model available.")
        return None

    MAX_RETRIES = 3
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[chat_helper] Ollama SQL generation attempt {attempt}/{MAX_RETRIES} using '{model_name}'...")
        try:
            url = "http://localhost:11434/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            temp = 0.0 if attempt == 1 else 0.1 * attempt
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": DB_SCHEMA_PROMPT},
                    {"role": "user", "content": f"Generate a MySQL SELECT query for this request: {user_query}"}
                ],
                "temperature": temp,
                "options": {
                    "num_predict": 150,
                    "stop": ["\n\n", "```\n"]
                }
            }
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                sql_text = result['choices'][0]['message']['content']
                validated_sql = clean_and_validate_sql(sql_text)
                if validated_sql:
                    print(f"[chat_helper] SQL validated successfully on attempt {attempt}.")
                    return validated_sql
                else:
                    print(f"[chat_helper] Attempt {attempt}: SQL failed structural validation. {'Retrying...' if attempt < MAX_RETRIES else 'All retries exhausted.'}")
            else:
                print(f"[chat_helper] Ollama API returned status code {response.status_code}.")
                break
        except Exception as e:
            print(f"[chat_helper] Ollama connection/inference error: {e}")
            break

    print("[chat_helper] All SQL generation attempts failed validation.")
    return None


def execute_sql(sql: str) -> tuple[pd.DataFrame | None, str | None]:
    """
    Executes a SELECT query on MySQL using the persistent connection pool.
    """
    # SQL Injection / Safety Guardrails:
    # 1. Clean the SQL query (remove comments and whitespace)
    cleaned_sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    cleaned_sql = re.sub(r'/\*.*?\*/', '', cleaned_sql, flags=re.DOTALL)
    cleaned_sql = cleaned_sql.strip()
    
    # 2. Strict SELECT checking
    if not cleaned_sql.upper().startswith("SELECT"):
        return None, "Security Error: Only SELECT queries are permitted."
        
    # 3. Forbidden keywords check
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "REPLACE", "GRANT", "REVOKE"]
    for kw in forbidden:
        if re.search(r'\b' + kw + r'\b', cleaned_sql.upper()):
            return None, f"Security Error: Unauthorized SQL operation containing '{kw}'."

    try:
        engine = _get_engine()
        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn)
            return df, None
    except Exception as e:
        print(f"[chat_helper] Database execution error: {e}")
        return None, str(e)


SUMMARY_SYSTEM_PROMPT = """You are the AI Insurance Assistant. Summarize the database query results to answer the user's business question.
CRITICAL FOR SPEED: Keep your summary extremely brief and direct. Write a maximum of 2-3 concise sentences or 3 short bullet points. Do not include greetings, introductions, or closing remarks. Focus strictly on key metrics (like Written Premium, Claims, Loss Ratio) using Indian formatting (₹ Lakh/Crore)."""

def generate_summary(user_query: str, sql: str, df: pd.DataFrame) -> str:
    """
    Sends the user query, SQL, and query result to local Ollama first,
    falling back to Gemini for human-readable summary.
    """
    if df.empty:
        return "The query executed successfully but returned 0 results matching your search criteria."
        
    data_context = df.head(15).to_string(index=False)
    row_count = len(df)
    
    user_prompt = f"User Question: {user_query}\nExecuted SQL:\n```sql\n{sql}\n```\n\nQuery Results ({row_count} total rows, showing top 15):\n{data_context}"
    
    model_name = get_local_ollama_model()  # uses cache — no extra HTTP probe
    if model_name:
        print(f"[chat_helper] Summarizing using local Ollama model '{model_name}'...")
        try:
            url = "http://localhost:11434/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "options": {
                    "num_predict": 120,
                    "temperature": 0.0
                }
            }
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                raw_summary = result['choices'][0]['message']['content'].strip()
                return post_process_summary(raw_summary)
            else:
                print(f"[chat_helper] Ollama summary API returned status code {response.status_code}.")
        except Exception as e:
            print(f"[chat_helper] Local Ollama summary error: {e}")
            
    return "I retrieved the data successfully but encountered an error generating the summary. Please review the data table below."


def ask_assistant(user_query: str) -> dict:
    """
    Full pipeline to receive query, translate to SQL, execute, and summarize.
    Uses local Ollama model only — no cloud fallback.
    """
    sql = generate_sql(user_query)
    if not sql:
        return {
            "success": False,
            "error": "I couldn't generate a valid, safe SQL query for that question. Please try rephrasing it.",
            "sql": None,
            "data": None,
            "answer": None
        }
        
    df, err = execute_sql(sql)
    if err:
        return {
            "success": False,
            "error": f"Database execution failed: {err}",
            "sql": sql,
            "data": None,
            "answer": None
        }
        
    # Query executed successfully! Safe to cache this SQL query.
    norm_query = " ".join(user_query.strip().lower().split())
    with _sql_cache_lock:
        _sql_cache[norm_query] = sql
        
    answer = generate_summary(user_query, sql, df)
    
    return {
        "success": True,
        "error": None,
        "sql": sql,
        "data": df.to_dict('records') if df is not None else None,
        "answer": answer
    }


# ── Compare Mode ──────────────────────────────────────────────────────────────

_COMPARE_PATTERN = re.compile(
    r'(?:compare|vs\.?|versus|\bvs\b)\s+',
    re.IGNORECASE
)

_COMPARE_SPLIT = re.compile(
    r'\s+(?:vs\.?|versus|\bvs\b|and|&|compared\s+to|against)\s+',
    re.IGNORECASE
)


def detect_comparison(user_query: str) -> tuple | None:
    """
    Detects if the user wants a comparison between two entities.
    Returns (entity_a, entity_b) if found, else None.
    
    Patterns matched:
      - "Compare Tata AIG vs HDFC Ergo"
      - "Tata AIG versus HDFC Ergo premium"
      - "Compare motor vs health"
    """
    if not _COMPARE_PATTERN.search(user_query):
        return None
    
    # Remove leading "compare" keyword
    cleaned = re.sub(r'^\s*compare\s+', '', user_query, flags=re.IGNORECASE).strip()
    
    # Split on vs/versus/and/against
    parts = _COMPARE_SPLIT.split(cleaned, maxsplit=1)
    if len(parts) != 2:
        return None
    
    entity_a = parts[0].strip().rstrip('.,!?')
    entity_b = parts[1].strip().rstrip('.,!?')
    
    if not entity_a or not entity_b:
        return None
    
    print(f"[chat_helper] Comparison detected: '{entity_a}' vs '{entity_b}'")
    return (entity_a, entity_b)


def run_comparison(entity_a: str, entity_b: str) -> dict:
    """
    Runs two separate SQL queries to compare two entities across
    standard KPIs: premium, claims, commission, policy count, loss ratio.
    Returns a dict with comparison data.
    """
    comparison_sql = """
        SELECT
            car.carrier_name,
            COUNT(DISTINCT p.policy_id) AS policy_count,
            SUM(p.premium_amount) AS total_premium,
            SUM(COALESCE(cl.quote_approved_amount, 0)) AS total_claims,
            SUM(COALESCE(comm.calculated_amount, 0)) AS total_commission,
            CASE WHEN SUM(p.premium_amount) > 0
                 THEN ROUND(SUM(COALESCE(cl.quote_approved_amount, 0)) / SUM(p.premium_amount) * 100, 2)
                 ELSE 0 END AS loss_ratio
        FROM policies p
        JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
        JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
        LEFT JOIN claims cl ON p.policy_id = cl.policy_id AND cl.is_active = 1 AND cl.status = 'Approved'
        LEFT JOIN sales_commissions comm ON p.policy_id = comm.policy_id AND comm.is_active = 1
        WHERE p.is_active = 1
          AND (LOWER(car.carrier_name) LIKE :entity_a OR LOWER(car.carrier_name) LIKE :entity_b
               OR LOWER(pr.category) LIKE :entity_a OR LOWER(pr.category) LIKE :entity_b
               OR LOWER(pr.sub_category) LIKE :entity_a OR LOWER(pr.sub_category) LIKE :entity_b)
        GROUP BY car.carrier_name
        ORDER BY total_premium DESC
    """
    
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            df = pd.read_sql(
                text(comparison_sql),
                conn,
                params={
                    'entity_a': f'%{entity_a.lower()}%',
                    'entity_b': f'%{entity_b.lower()}%'
                }
            )
        
        if df.empty:
            return {
                "success": False,
                "error": f"No data found for '{entity_a}' or '{entity_b}'. Please check the entity names.",
                "data": None,
                "is_comparison": True
            }
        
        return {
            "success": True,
            "error": None,
            "sql": comparison_sql.strip(),
            "data": df.to_dict('records'),
            "answer": _format_comparison_summary(entity_a, entity_b, df),
            "is_comparison": True,
            "entity_a": entity_a,
            "entity_b": entity_b
        }
    except Exception as e:
        print(f"[chat_helper] Comparison query error: {e}")
        return {
            "success": False,
            "error": f"Comparison query failed: {str(e)}",
            "data": None,
            "is_comparison": True
        }


def _format_comparison_summary(entity_a: str, entity_b: str, df: pd.DataFrame) -> str:
    """Formats a plain-text comparison summary from the comparison DataFrame."""
    if len(df) == 0:
        return f"No data found for comparison between {entity_a} and {entity_b}."
    
    lines = [f"**Comparison: {entity_a.title()} vs {entity_b.title()}**\n"]
    
    for _, row in df.iterrows():
        name = row.get('carrier_name', 'Unknown')
        premium = row.get('total_premium', 0)
        claims = row.get('total_claims', 0)
        policies = row.get('policy_count', 0)
        commission = row.get('total_commission', 0)
        loss_ratio = row.get('loss_ratio', 0)
        
        # Format in Crore
        prem_cr = premium / 1e7 if premium else 0
        claims_cr = claims / 1e7 if claims else 0
        comm_cr = commission / 1e7 if commission else 0
        
        lines.append(f"**{name}**: {policies:,} policies | "
                     f"Premium: ₹{prem_cr:,.2f} Cr | "
                     f"Claims: ₹{claims_cr:,.2f} Cr | "
                     f"Commission: ₹{comm_cr:,.2f} Cr | "
                     f"Loss Ratio: {loss_ratio:.1f}%")
    
    return "\n".join(lines)
