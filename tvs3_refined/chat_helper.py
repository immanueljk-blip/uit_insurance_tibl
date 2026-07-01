import os
import re
import time
import pandas as pd
import requests
import json
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
            f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}",
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

6. **sales_commissions**:
   - `commission_id` (INT, Primary Key)
   - `policy_id` (INT, Foreign Key to policies)
   - `calculated_amount` (DECIMAL, Brokerage/commission earned by the broker)
   - `status` (VARCHAR)
   - `is_active` (TINYINT, 1=active, 0=inactive)

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
- Standard JOIN keys (IMPORTANT: The policies table does NOT have a carrier_id column — you MUST always join policies → products → carriers via product_id then carrier_id):
  - Join policies with clients:          `p.client_id = cli.client_id`
  - Join policies with products:         `p.product_id = pr.product_id`
  - Join products with carriers:         `pr.carrier_id = car.carrier_id`
  - Join claims with policies:           `cl.policy_id = p.policy_id`
  - Join sales_commissions with policies:`sc.policy_id = p.policy_id`
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
- Metrics:
  - Written Premium: SUM(p.premium_amount)
  - Claims/Losses: SUM(cl.quote_approved_amount)
  - Commission/Brokerage Earned: SUM(sc.calculated_amount)
  - Loss Ratio: (SUM(cl.quote_approved_amount) / SUM(p.premium_amount)) * 100
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
    def replace_plain_number(match):
        """Handle bare large numbers not already prefixed with ₹"""
        raw = match.group(0).replace(",", "")
        try:
            val = float(raw)
            if val < 10000:
                return match.group(0)
            if 1900 <= val <= 2099 and '.' not in raw:
                return match.group(0)
            return to_indian_rupee(val)
        except (ValueError, TypeError):
            return match.group(0)

    text = re.sub(r'(?<![₹\d.,])\b(\d{5,}(?:,\d+)*(?:\.\d+)?|\d{4,}(?:,\d+)+(?:\.\d+)?)\b(?!\s*%)', replace_plain_number, text)

    return text


# Legacy alias kept for any code that still calls get_db_connection()
def get_db_connection():
    return _get_engine()


def clean_and_validate_sql(sql_text: str) -> str | None:
    """
    Cleans the SQL code returned by Gemini and applies guardrails to ensure it's a read-only SELECT.
    """
    if not sql_text:
        return None
        
    # Strip markdown formatting
    cleaned = sql_text.strip()
    match = re.search(r'```sql\s*(.*?)\s*```', cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    else:
        # Fallback to removing backticks if they are there
        cleaned = cleaned.replace('```sql', '').replace('```', '').strip()
        
    # Standardize spaces and remove leading comments
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL) # remove block comments
    cleaned = re.sub(r'--.*$', '', cleaned, flags=re.MULTILINE)   # remove line comments
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
        # Check for word boundary to prevent matching things like "category" (which contains "cat")
        if re.search(r'\b' + re.escape(word) + r'\b', cleaned_check):
            return None
            
    return cleaned


def generate_sql(user_query: str) -> str | None:
    """
    Tries to generate a safe SQL query using a local Ollama model first,
    falling back to Gemini if Ollama is unreachable or fails.
    """
    model_name = get_local_ollama_model()  # uses cache — no live HTTP on repeat calls
    if model_name:
        print(f"[chat_helper] Local Ollama detected: using model '{model_name}'...")
        try:
            url = "http://localhost:11434/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": DB_SCHEMA_PROMPT},
                    {"role": "user", "content": f"Generate a MySQL SELECT query for this request: {user_query}"}
                ],
                "temperature": 0.0
            }
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                sql_text = result['choices'][0]['message']['content']
                validated_sql = clean_and_validate_sql(sql_text)
                if validated_sql:
                    print("[chat_helper] Successfully generated SQL query using local Ollama.")
                    return validated_sql
                else:
                    print("[chat_helper] Local Ollama generated unsafe/invalid SQL. Falling back to Gemini...")
            else:
                print(f"[chat_helper] Ollama API returned status code {response.status_code}. Falling back to Gemini...")
        except Exception as e:
            print(f"[chat_helper] Local Ollama connection/inference error: {e}. Falling back to Gemini...")
            
    # Fallback to Gemini
    print("[chat_helper] Querying Gemini cloud API...")
    if not api_key:
        return None
        
    try:
        model = genai.GenerativeModel(
            model_name="gemini-flash-lite-latest",
            system_instruction=DB_SCHEMA_PROMPT
        )
        response = model.generate_content(
            f"Generate a MySQL SELECT query for this request: {user_query}"
        )
        
        # Safely extract text to avoid exception on empty or blocked candidate parts
        sql_text = ""
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts and len(candidate.content.parts) > 0:
                sql_text = candidate.content.parts[0].text
                
        if not sql_text or not sql_text.strip():
            return None
            
        return clean_and_validate_sql(sql_text)
    except Exception as e:
        print(f"[chat_helper] Gemini SQL generation error: {e}")
        return None


def execute_sql(sql: str) -> tuple[pd.DataFrame | None, str | None]:
    """
    Executes a SELECT query on MySQL using the persistent connection pool.
    """
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            df = pd.read_sql(text(sql), conn)
            return df, None
    except Exception as e:
        print(f"[chat_helper] Database execution error: {e}")
        return None, str(e)


def generate_summary(user_query: str, sql: str, df: pd.DataFrame) -> str:
    """
    Sends the user query, SQL, and query result to local Ollama first,
    falling back to Gemini for human-readable summary.
    """
    if df.empty:
        return "The query executed successfully but returned 0 results matching your search criteria."
        
    data_context = df.head(15).to_string(index=False)
    row_count = len(df)
    
    prompt = f"""
You are the AI Insurance Assistant. Summarize the results of the database query to answer the user's business question.

User Question: {user_query}
Executed SQL:
```sql
{sql}
```

Query Results ({row_count} total rows, showing top 15):
{data_context}

Provide a concise, professional summary of these results. Point out the key findings, metrics, and trends that answer the user's question directly. Use formatting (like bullet points or bold text) to highlight figures.
"""
    model_name = get_local_ollama_model()  # uses cache — no extra HTTP probe
    if model_name:
        print(f"[chat_helper] Summarizing using local Ollama model '{model_name}'...")
        try:
            url = "http://localhost:11434/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                raw_summary = result['choices'][0]['message']['content'].strip()
                return post_process_summary(raw_summary)
            else:
                print(f"[chat_helper] Ollama summary API returned status code {response.status_code}. Falling back to Gemini...")
        except Exception as e:
            print(f"[chat_helper] Local Ollama summary error: {e}. Falling back to Gemini...")
            
    # Fallback to Gemini
    print("[chat_helper] Summarizing via Gemini cloud API...")
    if not api_key:
        return "Gemini API key is not configured, so I can only show you the raw query results."
        
    try:
        model = genai.GenerativeModel("gemini-flash-lite-latest")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[chat_helper] Summary generation error: {e}")
        return "I retrieved the data successfully but encountered an error generating the final summary explanation."


def ask_assistant(user_query: str) -> dict:
    """
    Full pipeline to receive query, translate to SQL, execute, and summarize.
    """
    if not api_key:
        return {
            "success": False,
            "error": "Gemini API Key is not configured. Please add GEMINI_API_KEY to your .env file.",
            "sql": None,
            "data": None,
            "answer": None
        }
        
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
        
    answer = generate_summary(user_query, sql, df)
    
    return {
        "success": True,
        "error": None,
        "sql": sql,
        "data": df.to_dict('records') if df is not None else None,
        "answer": answer
    }
