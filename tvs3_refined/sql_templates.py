"""
SQL Template Cache for the Insurance Brokerage AI Assistant.

Provides instant, pre-validated SQL responses for ~85 common business
questions, eliminating the need for LLM inference in the majority of
cases.  Each template uses keyword-group scoring so natural language
variations like "show premium by carrier" and "carrier wise premium"
both resolve correctly.

Architecture
────────────
    User query
        │
        ▼
    match_template()  ──► SQL (instant)   ← ~80 % of queries
        │ (no match)
        ▼
    Ollama LLM        ──► SQL (5-30 sec)  ← novel / complex queries
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════════════════
#  Data structures
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SQLTemplate:
    """One pre-built SQL template with keyword matching metadata."""
    id: str                                          # unique short id
    description: str                                 # human-readable label
    sql: str                                         # the SQL query
    required: list[list[str]]                        # keyword groups – ≥1 from EACH group must match
    boost: list[list[str]] = field(default_factory=list)   # optional groups that increase score
    exclude: list[str] = field(default_factory=list)       # keywords that disqualify this template


# ═══════════════════════════════════════════════════════════════════════════════
#  Template definitions  (~85 templates covering every business angle)
# ═══════════════════════════════════════════════════════════════════════════════

TEMPLATES: list[SQLTemplate] = [

    # ─── POLICY COUNT METRICS ──────────────────────────────────────────────

    SQLTemplate(
        id="policy_count_total",
        description="Total number of active policies",
        required=[["policy", "policies"], ["count", "total", "how many", "number"]],
        exclude=["premium", "claim", "commission", "carrier", "product", "region", "channel", "user", "status", "month", "year", "trend"],
        sql="""
SELECT COUNT(*) AS total_policies
FROM policies p
WHERE p.is_active = 1
""",
    ),

    SQLTemplate(
        id="policy_count_by_status",
        description="Policy count broken down by status",
        required=[["policy", "policies"], ["status", "breakdown"]],
        exclude=["premium", "claim", "commission", "carrier", "product", "region", "channel"],
        sql="""
SELECT p.status, COUNT(*) AS policy_count
FROM policies p
WHERE p.is_active = 1
GROUP BY p.status
ORDER BY policy_count DESC
""",
    ),

    SQLTemplate(
        id="policy_count_by_carrier",
        description="Policy count by carrier/insurer",
        required=[["policy", "policies"], ["carrier", "insurer", "insurance company"]],
        exclude=["premium", "claim", "commission", "loss ratio", "region", "product"],
        boost=[["count", "total", "how many", "number"]],
        sql="""
SELECT car.carrier_name, COUNT(*) AS policy_count
FROM policies p
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE p.is_active = 1
GROUP BY car.carrier_name
ORDER BY policy_count DESC
""",
    ),

    SQLTemplate(
        id="policy_count_by_product",
        description="Policy count by product category",
        required=[["policy", "policies"], ["product", "category", "categories"]],
        exclude=["premium", "claim", "commission", "carrier", "region", "sub"],
        boost=[["count", "total", "how many"]],
        sql="""
SELECT pr.category, COUNT(*) AS policy_count
FROM policies p
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
WHERE p.is_active = 1
GROUP BY pr.category
ORDER BY policy_count DESC
""",
    ),

    SQLTemplate(
        id="policy_count_by_subcategory",
        description="Policy count by product sub-category",
        required=[["policy", "policies"], ["sub_category", "sub category", "subcategory", "sub-category"]],
        exclude=["premium", "claim", "commission"],
        sql="""
SELECT pr.category, pr.sub_category, COUNT(*) AS policy_count
FROM policies p
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
WHERE p.is_active = 1
GROUP BY pr.category, pr.sub_category
ORDER BY policy_count DESC
""",
    ),

    SQLTemplate(
        id="policy_count_by_region",
        description="Policy count by region/state",
        required=[["policy", "policies"], ["region", "state", "statewise", "regionwise", "location", "geography"]],
        exclude=["premium", "claim", "commission", "carrier", "product"],
        boost=[["count", "total", "how many"]],
        sql="""
SELECT cli.region_name, COUNT(*) AS policy_count
FROM policies p
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
WHERE p.is_active = 1
GROUP BY cli.region_name
ORDER BY policy_count DESC
""",
    ),

    SQLTemplate(
        id="policy_count_by_channel",
        description="Policy count by distribution channel",
        required=[["policy", "policies"], ["channel", "distribution", "online", "offline", "direct"]],
        exclude=["premium", "claim", "commission"],
        boost=[["count", "total", "how many"]],
        sql="""
SELECT p.distribution_channel, COUNT(*) AS policy_count
FROM policies p
WHERE p.is_active = 1
GROUP BY p.distribution_channel
ORDER BY policy_count DESC
""",
    ),

    SQLTemplate(
        id="policy_count_by_user",
        description="Policy count by backoffice user",
        required=[["policy", "policies"], ["user", "agent", "executive", "created by", "issued by"]],
        exclude=["premium", "claim", "commission"],
        boost=[["count", "total", "how many"]],
        sql="""
SELECT bu.username, COUNT(*) AS policy_count
FROM policies p
JOIN backoffice_users bu ON p.created_by_user_id = bu.user_id AND bu.is_active = 1
WHERE p.is_active = 1
GROUP BY bu.username
ORDER BY policy_count DESC
""",
    ),

    SQLTemplate(
        id="policy_monthly_trend",
        description="Monthly policy issuance trend",
        required=[["policy", "policies"], ["month", "monthly", "trend", "over time"]],
        exclude=["premium", "claim", "commission", "year"],
        sql="""
SELECT DATE_FORMAT(p.issue_date, '%Y-%m') AS month, COUNT(*) AS policies_issued
FROM policies p
WHERE p.is_active = 1
GROUP BY DATE_FORMAT(p.issue_date, '%Y-%m')
ORDER BY month DESC
LIMIT 24
""",
    ),

    SQLTemplate(
        id="policy_yearly_trend",
        description="Yearly policy issuance trend",
        required=[["policy", "policies"], ["year", "yearly", "annual"]],
        exclude=["premium", "claim", "commission", "month"],
        boost=[["trend", "count", "total"]],
        sql="""
SELECT YEAR(p.issue_date) AS year, COUNT(*) AS policies_issued
FROM policies p
WHERE p.is_active = 1
GROUP BY YEAR(p.issue_date)
ORDER BY year DESC
""",
    ),

    SQLTemplate(
        id="policies_expiring_soon",
        description="Policies expiring in the next 30 days",
        required=[["expir", "renew", "upcoming", "due"]],
        boost=[["policy", "policies", "soon", "next", "30"]],
        exclude=["expired", "lapsed"],
        sql="""
SELECT p.policy_number, cli.name AS client_name, pr.category, car.carrier_name,
       p.premium_amount, p.expiry_date
FROM policies p
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE p.is_active = 1
  AND p.expiry_date BETWEEN CURDATE() AND DATE_ADD(CURDATE(), INTERVAL 30 DAY)
ORDER BY p.expiry_date ASC
LIMIT 50
""",
    ),

    SQLTemplate(
        id="recently_issued_policies",
        description="Recently issued policies (last 30 days)",
        required=[["recent", "new", "latest", "last"]],
        boost=[["policy", "policies", "issued"]],
        exclude=["claim", "client", "commission"],
        sql="""
SELECT p.policy_number, cli.name AS client_name, pr.category, car.carrier_name,
       p.premium_amount, p.issue_date
FROM policies p
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE p.is_active = 1
  AND p.issue_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
ORDER BY p.issue_date DESC
LIMIT 50
""",
    ),

    # ─── PREMIUM METRICS ──────────────────────────────────────────────────

    SQLTemplate(
        id="premium_total",
        description="Total premium amount (GWP)",
        required=[["premium", "gwp", "written premium"], ["total", "sum", "overall", "aggregate", "what", "show", "our"]],
        exclude=["carrier", "product", "region", "channel", "client", "user", "month", "year", "category", "trend", "average", "top"],
        sql="""
SELECT SUM(p.premium_amount) AS total_premium
FROM policies p
WHERE p.is_active = 1
""",
    ),

    SQLTemplate(
        id="premium_by_carrier",
        description="Total premium by carrier/insurer",
        required=[["premium", "gwp", "written premium"], ["carrier", "insurer", "insurance company"]],
        exclude=["claim", "loss ratio", "commission", "region", "product", "client", "channel", "user", "average"],
        sql="""
SELECT car.carrier_name, SUM(p.premium_amount) AS total_premium
FROM policies p
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE p.is_active = 1
GROUP BY car.carrier_name
ORDER BY total_premium DESC
""",
    ),

    SQLTemplate(
        id="premium_by_product",
        description="Total premium by product category",
        required=[["premium", "gwp", "written premium"], ["product", "category", "categories"]],
        exclude=["claim", "loss ratio", "commission", "carrier", "region", "client", "channel", "sub"],
        sql="""
SELECT pr.category, SUM(p.premium_amount) AS total_premium
FROM policies p
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
WHERE p.is_active = 1
GROUP BY pr.category
ORDER BY total_premium DESC
""",
    ),

    SQLTemplate(
        id="premium_by_subcategory",
        description="Total premium by product sub-category",
        required=[["premium", "gwp"], ["sub_category", "sub category", "subcategory", "sub-category"]],
        sql="""
SELECT pr.category, pr.sub_category, SUM(p.premium_amount) AS total_premium
FROM policies p
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
WHERE p.is_active = 1
GROUP BY pr.category, pr.sub_category
ORDER BY total_premium DESC
""",
    ),

    SQLTemplate(
        id="premium_by_region",
        description="Total premium by region/state",
        required=[["premium", "gwp", "written premium"], ["region", "state", "statewise", "regionwise", "geography"]],
        exclude=["claim", "loss ratio", "commission", "carrier", "product"],
        sql="""
SELECT cli.region_name, SUM(p.premium_amount) AS total_premium
FROM policies p
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
WHERE p.is_active = 1
GROUP BY cli.region_name
ORDER BY total_premium DESC
""",
    ),

    SQLTemplate(
        id="premium_by_channel",
        description="Total premium by distribution channel",
        required=[["premium", "gwp", "written premium"], ["channel", "distribution", "online", "offline"]],
        exclude=["claim", "loss ratio", "commission"],
        sql="""
SELECT p.distribution_channel, SUM(p.premium_amount) AS total_premium
FROM policies p
WHERE p.is_active = 1
GROUP BY p.distribution_channel
ORDER BY total_premium DESC
""",
    ),

    SQLTemplate(
        id="premium_by_client_type",
        description="Total premium by client type (B2B/B2C)",
        required=[["premium", "gwp"], ["client type", "individual", "corporate", "b2b", "b2c"]],
        sql="""
SELECT cli.client_type, SUM(p.premium_amount) AS total_premium, COUNT(*) AS policy_count
FROM policies p
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
WHERE p.is_active = 1
GROUP BY cli.client_type
ORDER BY total_premium DESC
""",
    ),

    SQLTemplate(
        id="premium_by_user",
        description="Total premium by backoffice user",
        required=[["premium", "gwp"], ["user", "agent", "executive", "salesperson"]],
        exclude=["claim", "commission", "client"],
        sql="""
SELECT bu.username, SUM(p.premium_amount) AS total_premium, COUNT(*) AS policy_count
FROM policies p
JOIN backoffice_users bu ON p.created_by_user_id = bu.user_id AND bu.is_active = 1
WHERE p.is_active = 1
GROUP BY bu.username
ORDER BY total_premium DESC
""",
    ),

    SQLTemplate(
        id="premium_average",
        description="Average premium amount overall",
        required=[["average", "avg", "mean"], ["premium"]],
        exclude=["carrier", "product", "region", "claim"],
        sql="""
SELECT ROUND(AVG(p.premium_amount), 2) AS average_premium
FROM policies p
WHERE p.is_active = 1
""",
    ),

    SQLTemplate(
        id="premium_avg_by_carrier",
        description="Average premium by carrier",
        required=[["average", "avg", "mean"], ["premium"], ["carrier", "insurer"]],
        sql="""
SELECT car.carrier_name, ROUND(AVG(p.premium_amount), 2) AS avg_premium, COUNT(*) AS policy_count
FROM policies p
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE p.is_active = 1
GROUP BY car.carrier_name
ORDER BY avg_premium DESC
""",
    ),

    SQLTemplate(
        id="premium_monthly_trend",
        description="Monthly premium trend",
        required=[["premium", "gwp"], ["month", "monthly", "trend"]],
        exclude=["year", "yearly", "claim", "this", "current", "last", "previous"],
        sql="""
SELECT DATE_FORMAT(p.issue_date, '%Y-%m') AS month,
       SUM(p.premium_amount) AS total_premium,
       COUNT(*) AS policy_count
FROM policies p
WHERE p.is_active = 1
GROUP BY DATE_FORMAT(p.issue_date, '%Y-%m')
ORDER BY month DESC
LIMIT 24
""",
    ),

    SQLTemplate(
        id="premium_yearly_trend",
        description="Yearly premium trend",
        required=[["premium", "gwp"], ["year", "yearly", "annual"]],
        exclude=["month", "monthly", "claim", "this", "current", "last", "previous"],
        sql="""
SELECT YEAR(p.issue_date) AS year,
       SUM(p.premium_amount) AS total_premium,
       COUNT(*) AS policy_count
FROM policies p
WHERE p.is_active = 1
GROUP BY YEAR(p.issue_date)
ORDER BY year DESC
""",
    ),

    SQLTemplate(
        id="top_clients_by_premium",
        description="Top clients by premium amount",
        required=[["top", "largest", "biggest", "highest", "best"], ["client", "customer"], ["premium"]],
        sql="""
SELECT cli.name AS client_name, cli.client_type, cli.region_name,
       SUM(p.premium_amount) AS total_premium, COUNT(*) AS policy_count
FROM policies p
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
WHERE p.is_active = 1
GROUP BY cli.client_id, cli.name, cli.client_type, cli.region_name
ORDER BY total_premium DESC
LIMIT 10
""",
    ),

    # ─── CLAIM METRICS ────────────────────────────────────────────────────

    SQLTemplate(
        id="claims_total_count",
        description="Total number of claims",
        required=[["claim", "claims"], ["count", "total", "how many", "number"]],
        exclude=["premium", "commission", "carrier", "product", "region", "status", "amount", "loss", "pending", "approved", "rejected"],
        sql="""
SELECT COUNT(*) AS total_claims
FROM claims cl
WHERE cl.is_active = 1
""",
    ),

    SQLTemplate(
        id="claims_total_amount",
        description="Total claim payout amount",
        required=[["claim", "claims"], ["amount", "payout", "sum", "total"]],
        exclude=["premium", "commission", "carrier", "product", "region", "status", "count", "loss", "average", "avg", "mean"],
        sql="""
SELECT SUM(cl.quote_approved_amount) AS total_claim_amount
FROM claims cl
WHERE cl.is_active = 1
""",
    ),

    SQLTemplate(
        id="claims_by_status",
        description="Claims breakdown by status",
        required=[["claim", "claims"], ["status", "pending", "approved", "rejected", "breakdown"]],
        exclude=["premium", "commission", "carrier", "product", "region"],
        sql="""
SELECT cl.status, COUNT(*) AS claim_count, SUM(cl.quote_approved_amount) AS total_amount
FROM claims cl
WHERE cl.is_active = 1
GROUP BY cl.status
ORDER BY claim_count DESC
""",
    ),

    SQLTemplate(
        id="claims_by_carrier",
        description="Claims by carrier/insurer",
        required=[["claim", "claims"], ["carrier", "insurer", "insurance company"]],
        exclude=["premium", "commission", "region", "product", "loss"],
        boost=[["count", "total", "amount"]],
        sql="""
SELECT car.carrier_name,
       COUNT(*) AS claim_count,
       SUM(cl.quote_approved_amount) AS total_claim_amount
FROM claims cl
JOIN policies p ON cl.policy_id = p.policy_id AND p.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE cl.is_active = 1
GROUP BY car.carrier_name
ORDER BY total_claim_amount DESC
""",
    ),

    SQLTemplate(
        id="claims_by_product",
        description="Claims by product category",
        required=[["claim", "claims"], ["product", "category", "categories"]],
        exclude=["premium", "commission", "carrier", "region", "loss", "sub"],
        sql="""
SELECT pr.category,
       COUNT(*) AS claim_count,
       SUM(cl.quote_approved_amount) AS total_claim_amount
FROM claims cl
JOIN policies p ON cl.policy_id = p.policy_id AND p.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
WHERE cl.is_active = 1
GROUP BY pr.category
ORDER BY total_claim_amount DESC
""",
    ),

    SQLTemplate(
        id="claims_by_region",
        description="Claims by region/state",
        required=[["claim", "claims"], ["region", "state", "statewise", "regionwise"]],
        exclude=["premium", "commission", "carrier", "product", "loss"],
        sql="""
SELECT cli.region_name,
       COUNT(*) AS claim_count,
       SUM(cl.quote_approved_amount) AS total_claim_amount
FROM claims cl
JOIN policies p ON cl.policy_id = p.policy_id AND p.is_active = 1
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
WHERE cl.is_active = 1
GROUP BY cli.region_name
ORDER BY total_claim_amount DESC
""",
    ),

    SQLTemplate(
        id="claims_average",
        description="Average claim amount",
        required=[["average", "avg", "mean"], ["claim"]],
        exclude=["premium", "commission"],
        sql="""
SELECT ROUND(AVG(cl.quote_approved_amount), 2) AS average_claim_amount
FROM claims cl
WHERE cl.is_active = 1
""",
    ),

    SQLTemplate(
        id="claims_largest",
        description="Largest/highest individual claims",
        required=[["largest", "biggest", "highest", "top", "maximum"], ["claim", "claims"]],
        exclude=["premium", "commission", "loss"],
        sql="""
SELECT cl.claim_number, cli.name AS client_name, pr.category, car.carrier_name,
       cl.quote_approved_amount, cl.status
FROM claims cl
JOIN policies p ON cl.policy_id = p.policy_id AND p.is_active = 1
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE cl.is_active = 1
ORDER BY cl.quote_approved_amount DESC
LIMIT 10
""",
    ),

    SQLTemplate(
        id="claims_monthly_trend",
        description="Monthly claims trend",
        required=[["claim", "claims"], ["month", "monthly", "trend"]],
        exclude=["premium", "commission", "year"],
        sql="""
SELECT DATE_FORMAT(p.issue_date, '%Y-%m') AS month,
       COUNT(*) AS claim_count,
       SUM(cl.quote_approved_amount) AS total_claim_amount
FROM claims cl
JOIN policies p ON cl.policy_id = p.policy_id AND p.is_active = 1
WHERE cl.is_active = 1
GROUP BY DATE_FORMAT(p.issue_date, '%Y-%m')
ORDER BY month DESC
LIMIT 24
""",
    ),

    SQLTemplate(
        id="pending_claims",
        description="List of pending claims",
        required=[["pending"], ["claim", "claims"]],
        boost=[["list", "show", "how many", "count"]],
        sql="""
SELECT cl.claim_number, cli.name AS client_name, pr.category, car.carrier_name,
       cl.quote_approved_amount, p.policy_number
FROM claims cl
JOIN policies p ON cl.policy_id = p.policy_id AND p.is_active = 1
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE cl.is_active = 1 AND cl.status = 'Pending'
ORDER BY cl.quote_approved_amount DESC
""",
    ),

    # ─── LOSS RATIO METRICS ───────────────────────────────────────────────

    SQLTemplate(
        id="loss_ratio_overall",
        description="Overall loss ratio (claims/premium)",
        required=[["loss ratio", "claim ratio", "incurred ratio"]],
        exclude=["carrier", "product", "region", "client", "category", "top", "worst", "best", "highest", "lowest"],
        sql="""
SELECT ROUND(SUM(cl.quote_approved_amount) / NULLIF(SUM(p.premium_amount), 0) * 100, 2) AS loss_ratio_pct,
       SUM(cl.quote_approved_amount) AS total_claims,
       SUM(p.premium_amount) AS total_premium
FROM policies p
JOIN claims cl ON cl.policy_id = p.policy_id AND cl.is_active = 1
WHERE p.is_active = 1
""",
    ),

    SQLTemplate(
        id="loss_ratio_by_carrier",
        description="Loss ratio by carrier",
        required=[["loss ratio", "claim ratio"], ["carrier", "insurer", "insurance company"]],
        exclude=["product", "region", "client", "top", "worst", "best"],
        sql="""
SELECT car.carrier_name,
       SUM(p.premium_amount) AS total_premium,
       SUM(cl.quote_approved_amount) AS total_claims,
       ROUND(SUM(cl.quote_approved_amount) / NULLIF(SUM(p.premium_amount), 0) * 100, 2) AS loss_ratio_pct
FROM policies p
JOIN claims cl ON cl.policy_id = p.policy_id AND cl.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE p.is_active = 1
GROUP BY car.carrier_name
ORDER BY loss_ratio_pct DESC
""",
    ),

    SQLTemplate(
        id="loss_ratio_by_product",
        description="Loss ratio by product category",
        required=[["loss ratio", "claim ratio"], ["product", "category"]],
        exclude=["carrier", "region", "client", "top", "worst", "best"],
        sql="""
SELECT pr.category,
       SUM(p.premium_amount) AS total_premium,
       SUM(cl.quote_approved_amount) AS total_claims,
       ROUND(SUM(cl.quote_approved_amount) / NULLIF(SUM(p.premium_amount), 0) * 100, 2) AS loss_ratio_pct
FROM policies p
JOIN claims cl ON cl.policy_id = p.policy_id AND cl.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
WHERE p.is_active = 1
GROUP BY pr.category
ORDER BY loss_ratio_pct DESC
""",
    ),

    SQLTemplate(
        id="loss_ratio_by_region",
        description="Loss ratio by region/state",
        required=[["loss ratio", "claim ratio"], ["region", "state", "statewise"]],
        exclude=["carrier", "product", "client", "top", "worst", "best"],
        sql="""
SELECT cli.region_name,
       SUM(p.premium_amount) AS total_premium,
       SUM(cl.quote_approved_amount) AS total_claims,
       ROUND(SUM(cl.quote_approved_amount) / NULLIF(SUM(p.premium_amount), 0) * 100, 2) AS loss_ratio_pct
FROM policies p
JOIN claims cl ON cl.policy_id = p.policy_id AND cl.is_active = 1
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
WHERE p.is_active = 1
GROUP BY cli.region_name
ORDER BY loss_ratio_pct DESC
""",
    ),

    SQLTemplate(
        id="loss_ratio_by_client",
        description="Loss ratio by client",
        required=[["loss ratio", "claim ratio"], ["client", "customer"]],
        exclude=["carrier", "product", "region", "top", "worst", "best"],
        sql="""
SELECT cli.name AS client_name, cli.client_type,
       SUM(p.premium_amount) AS total_premium,
       SUM(cl.quote_approved_amount) AS total_claims,
       ROUND(SUM(cl.quote_approved_amount) / NULLIF(SUM(p.premium_amount), 0) * 100, 2) AS loss_ratio_pct
FROM policies p
JOIN claims cl ON cl.policy_id = p.policy_id AND cl.is_active = 1
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
WHERE p.is_active = 1
GROUP BY cli.client_id, cli.name, cli.client_type
ORDER BY loss_ratio_pct DESC
LIMIT 20
""",
    ),

    SQLTemplate(
        id="loss_ratio_worst",
        description="Worst/highest loss ratios",
        required=[["loss ratio", "claim ratio"], ["worst", "highest", "top", "maximum", "most"]],
        sql="""
SELECT car.carrier_name, pr.category, cli.region_name,
       SUM(p.premium_amount) AS total_premium,
       SUM(cl.quote_approved_amount) AS total_claims,
       ROUND(SUM(cl.quote_approved_amount) / NULLIF(SUM(p.premium_amount), 0) * 100, 2) AS loss_ratio_pct
FROM policies p
JOIN claims cl ON cl.policy_id = p.policy_id AND cl.is_active = 1
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE p.is_active = 1
GROUP BY car.carrier_name, pr.category, cli.region_name
HAVING SUM(p.premium_amount) > 0
ORDER BY loss_ratio_pct DESC
LIMIT 10
""",
    ),

    SQLTemplate(
        id="loss_ratio_best",
        description="Best/lowest loss ratios",
        required=[["loss ratio", "claim ratio"], ["best", "lowest", "minimum", "least"]],
        sql="""
SELECT car.carrier_name, pr.category,
       SUM(p.premium_amount) AS total_premium,
       SUM(cl.quote_approved_amount) AS total_claims,
       ROUND(SUM(cl.quote_approved_amount) / NULLIF(SUM(p.premium_amount), 0) * 100, 2) AS loss_ratio_pct
FROM policies p
JOIN claims cl ON cl.policy_id = p.policy_id AND cl.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE p.is_active = 1
GROUP BY car.carrier_name, pr.category
HAVING SUM(p.premium_amount) > 0
ORDER BY loss_ratio_pct ASC
LIMIT 10
""",
    ),

    # ─── CLIENT METRICS ───────────────────────────────────────────────────

    SQLTemplate(
        id="clients_total",
        description="Total number of active clients",
        required=[["client", "clients", "customer", "customers"], ["count", "total", "how many", "number", "list"]],
        exclude=["premium", "claim", "commission", "policy", "carrier", "product", "region", "type", "top"],
        sql="""
SELECT COUNT(*) AS total_clients
FROM clients cli
WHERE cli.is_active = 1
""",
    ),

    SQLTemplate(
        id="clients_by_type",
        description="Client count by type (Individual/Corporate)",
        required=[["client", "clients", "customer"], ["type", "individual", "corporate", "b2b", "b2c", "segment"]],
        exclude=["premium", "claim", "commission", "policy", "top"],
        sql="""
SELECT cli.client_type, COUNT(*) AS client_count
FROM clients cli
WHERE cli.is_active = 1
GROUP BY cli.client_type
ORDER BY client_count DESC
""",
    ),

    SQLTemplate(
        id="clients_by_region",
        description="Client count by region/state",
        required=[["client", "clients", "customer"], ["region", "state", "statewise", "geography"]],
        exclude=["premium", "claim", "commission", "policy", "top"],
        sql="""
SELECT cli.region_name, COUNT(*) AS client_count
FROM clients cli
WHERE cli.is_active = 1
GROUP BY cli.region_name
ORDER BY client_count DESC
""",
    ),

    SQLTemplate(
        id="clients_top_by_premium",
        description="Top clients ranked by premium",
        required=[["client", "clients", "customer"], ["top", "largest", "biggest", "highest", "best"]],
        boost=[["premium"]],
        exclude=["claim", "commission", "loss"],
        sql="""
SELECT cli.name AS client_name, cli.client_type, cli.region_name,
       SUM(p.premium_amount) AS total_premium, COUNT(*) AS policy_count
FROM policies p
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
WHERE p.is_active = 1
GROUP BY cli.client_id, cli.name, cli.client_type, cli.region_name
ORDER BY total_premium DESC
LIMIT 10
""",
    ),

    SQLTemplate(
        id="clients_top_by_claims",
        description="Top clients by claim amount",
        required=[["client", "clients", "customer"], ["top", "largest", "biggest", "highest", "most"], ["claim"]],
        sql="""
SELECT cli.name AS client_name, cli.client_type, cli.region_name,
       SUM(cl.quote_approved_amount) AS total_claims, COUNT(*) AS claim_count
FROM claims cl
JOIN policies p ON cl.policy_id = p.policy_id AND p.is_active = 1
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
WHERE cl.is_active = 1
GROUP BY cli.client_id, cli.name, cli.client_type, cli.region_name
ORDER BY total_claims DESC
LIMIT 10
""",
    ),

    SQLTemplate(
        id="clients_most_policies",
        description="Clients with most policies",
        required=[["client", "clients", "customer"], ["most", "maximum", "highest"], ["policy", "policies"]],
        sql="""
SELECT cli.name AS client_name, cli.client_type, cli.region_name,
       COUNT(*) AS policy_count, SUM(p.premium_amount) AS total_premium
FROM policies p
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
WHERE p.is_active = 1
GROUP BY cli.client_id, cli.name, cli.client_type, cli.region_name
ORDER BY policy_count DESC
LIMIT 10
""",
    ),

    SQLTemplate(
        id="inactive_clients",
        description="List of inactive clients",
        required=[["inactive", "deactivated", "deleted"], ["client", "clients", "customer"]],
        sql="""
SELECT cli.name AS client_name, cli.client_type, cli.region_name, cli.address
FROM clients cli
WHERE cli.is_active = 0
ORDER BY cli.name
""",
    ),

    # ─── CARRIER METRICS ──────────────────────────────────────────────────

    SQLTemplate(
        id="carriers_list",
        description="List all active carriers/insurers",
        required=[["carrier", "carriers", "insurer", "insurers", "insurance company", "insurance companies"]],
        boost=[["list", "show", "all", "active", "our", "what"]],
        exclude=["premium", "claim", "commission", "policy", "loss", "performance", "top", "best"],
        sql="""
SELECT car.carrier_id, car.carrier_name, car.is_active
FROM carriers car
WHERE car.is_active = 1
ORDER BY car.carrier_name
""",
    ),

    SQLTemplate(
        id="carrier_products",
        description="Products offered per carrier",
        required=[["carrier", "insurer"], ["product", "products", "category", "offer"]],
        exclude=["premium", "claim", "commission", "loss"],
        sql="""
SELECT car.carrier_name, pr.category, pr.sub_category
FROM products pr
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE pr.is_active = 1
ORDER BY car.carrier_name, pr.category, pr.sub_category
""",
    ),

    SQLTemplate(
        id="carrier_performance",
        description="Carrier performance overview (premium, claims, loss ratio)",
        required=[["carrier", "insurer"], ["performance", "overview", "comparison", "compare", "summary"]],
        sql="""
SELECT car.carrier_name,
       COUNT(DISTINCT p.policy_id) AS policy_count,
       SUM(p.premium_amount) AS total_premium,
       SUM(cl.quote_approved_amount) AS total_claims,
       ROUND(SUM(cl.quote_approved_amount) / NULLIF(SUM(p.premium_amount), 0) * 100, 2) AS loss_ratio_pct
FROM policies p
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
LEFT JOIN claims cl ON cl.policy_id = p.policy_id AND cl.is_active = 1
WHERE p.is_active = 1
GROUP BY car.carrier_name
ORDER BY total_premium DESC
""",
    ),

    SQLTemplate(
        id="carrier_best_performing",
        description="Best performing carriers",
        required=[["best", "top"], ["carrier", "insurer"], ["perform", "performing"]],
        sql="""
SELECT car.carrier_name,
       SUM(p.premium_amount) AS total_premium,
       SUM(cl.quote_approved_amount) AS total_claims,
       ROUND(SUM(cl.quote_approved_amount) / NULLIF(SUM(p.premium_amount), 0) * 100, 2) AS loss_ratio_pct
FROM policies p
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
LEFT JOIN claims cl ON cl.policy_id = p.policy_id AND cl.is_active = 1
WHERE p.is_active = 1
GROUP BY car.carrier_name
ORDER BY loss_ratio_pct ASC
""",
    ),

    # ─── PRODUCT METRICS ──────────────────────────────────────────────────

    SQLTemplate(
        id="product_categories",
        description="List of product categories",
        required=[["product", "products", "category", "categories"]],
        boost=[["list", "show", "all", "active"]],
        exclude=["premium", "claim", "commission", "policy", "carrier", "sub", "loss", "performance"],
        sql="""
SELECT DISTINCT pr.category
FROM products pr
WHERE pr.is_active = 1
ORDER BY pr.category
""",
    ),

    SQLTemplate(
        id="product_subcategories",
        description="List of product sub-categories",
        required=[["sub_category", "sub category", "subcategory", "sub-category", "subcategories", "sub-categories"]],
        boost=[["list", "show", "all"]],
        exclude=["premium", "claim", "commission"],
        sql="""
SELECT DISTINCT pr.category, pr.sub_category
FROM products pr
WHERE pr.is_active = 1
ORDER BY pr.category, pr.sub_category
""",
    ),

    SQLTemplate(
        id="product_categories_and_carriers",
        description="Product categories with their carriers",
        required=[["product", "category", "categories"], ["carrier", "carriers", "insurer"]],
        exclude=["premium", "claim", "commission", "loss", "performance", "policy"],
        sql="""
SELECT DISTINCT pr.category, car.carrier_name
FROM products pr
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE pr.is_active = 1
ORDER BY pr.category, car.carrier_name
""",
    ),

    SQLTemplate(
        id="product_performance",
        description="Product category performance (premium, claims, loss ratio)",
        required=[["product", "category"], ["performance", "overview", "summary", "analysis"]],
        sql="""
SELECT pr.category,
       COUNT(DISTINCT p.policy_id) AS policy_count,
       SUM(p.premium_amount) AS total_premium,
       SUM(cl.quote_approved_amount) AS total_claims,
       ROUND(SUM(cl.quote_approved_amount) / NULLIF(SUM(p.premium_amount), 0) * 100, 2) AS loss_ratio_pct
FROM policies p
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
LEFT JOIN claims cl ON cl.policy_id = p.policy_id AND cl.is_active = 1
WHERE p.is_active = 1
GROUP BY pr.category
ORDER BY total_premium DESC
""",
    ),

    # ─── COMMISSION METRICS ───────────────────────────────────────────────

    SQLTemplate(
        id="commission_total",
        description="Total commission/brokerage earned",
        required=[["commission", "brokerage"], ["total", "sum", "overall", "earned", "what", "how much", "show", "our"]],
        exclude=["carrier", "product", "region", "user", "status", "rate", "month", "year", "average"],
        sql="""
SELECT SUM(sc.calculated_amount) AS total_commission
FROM sales_commissions sc
WHERE sc.is_active = 1
""",
    ),

    SQLTemplate(
        id="commission_by_status",
        description="Commission breakdown by status",
        required=[["commission", "brokerage"], ["status", "breakdown"]],
        sql="""
SELECT sc.status, COUNT(*) AS commission_count, SUM(sc.calculated_amount) AS total_amount
FROM sales_commissions sc
WHERE sc.is_active = 1
GROUP BY sc.status
ORDER BY total_amount DESC
""",
    ),

    SQLTemplate(
        id="commission_by_carrier",
        description="Commission earned per carrier",
        required=[["commission", "brokerage"], ["carrier", "insurer"]],
        exclude=["user", "product", "region", "rate", "percentage", "ratio"],
        sql="""
SELECT car.carrier_name, SUM(sc.calculated_amount) AS total_commission
FROM sales_commissions sc
JOIN policies p ON sc.policy_id = p.policy_id AND p.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE sc.is_active = 1
GROUP BY car.carrier_name
ORDER BY total_commission DESC
""",
    ),

    SQLTemplate(
        id="commission_by_product",
        description="Commission earned per product category",
        required=[["commission", "brokerage"], ["product", "category"]],
        exclude=["carrier", "user", "region", "rate", "percentage", "ratio"],
        sql="""
SELECT pr.category, SUM(sc.calculated_amount) AS total_commission
FROM sales_commissions sc
JOIN policies p ON sc.policy_id = p.policy_id AND p.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
WHERE sc.is_active = 1
GROUP BY pr.category
ORDER BY total_commission DESC
""",
    ),

    SQLTemplate(
        id="commission_by_user",
        description="Commission earned per user/agent",
        required=[["commission", "brokerage"], ["user", "agent", "executive"]],
        exclude=["rate", "percentage", "ratio"],
        sql="""
SELECT bu.username,
       SUM(sc.calculated_amount) AS total_commission,
       COUNT(*) AS policies_with_commission
FROM sales_commissions sc
JOIN policies p ON sc.policy_id = p.policy_id AND p.is_active = 1
JOIN backoffice_users bu ON p.created_by_user_id = bu.user_id AND bu.is_active = 1
WHERE sc.is_active = 1
GROUP BY bu.username
ORDER BY total_commission DESC
""",
    ),

    SQLTemplate(
        id="commission_rate",
        description="Commission rate / commission as percentage of premium",
        required=[["commission", "brokerage"], ["rate", "percentage", "ratio"]],
        sql="""
SELECT car.carrier_name, pr.category,
       SUM(p.premium_amount) AS total_premium,
       SUM(sc.calculated_amount) AS total_commission,
       ROUND(SUM(sc.calculated_amount) / NULLIF(SUM(p.premium_amount), 0) * 100, 2) AS commission_rate_pct
FROM sales_commissions sc
JOIN policies p ON sc.policy_id = p.policy_id AND p.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE sc.is_active = 1
GROUP BY car.carrier_name, pr.category
ORDER BY commission_rate_pct DESC
""",
    ),

    SQLTemplate(
        id="commission_average",
        description="Average commission amount",
        required=[["average", "avg", "mean"], ["commission", "brokerage"]],
        sql="""
SELECT ROUND(AVG(sc.calculated_amount), 2) AS average_commission
FROM sales_commissions sc
WHERE sc.is_active = 1
""",
    ),

    SQLTemplate(
        id="commission_monthly_trend",
        description="Monthly commission trend",
        required=[["commission", "brokerage"], ["month", "monthly", "trend"]],
        sql="""
SELECT DATE_FORMAT(p.issue_date, '%Y-%m') AS month,
       SUM(sc.calculated_amount) AS total_commission,
       COUNT(*) AS commission_count
FROM sales_commissions sc
JOIN policies p ON sc.policy_id = p.policy_id AND p.is_active = 1
WHERE sc.is_active = 1
GROUP BY DATE_FORMAT(p.issue_date, '%Y-%m')
ORDER BY month DESC
LIMIT 24
""",
    ),

    # ─── USER / AGENT METRICS ─────────────────────────────────────────────

    SQLTemplate(
        id="users_list",
        description="List all backoffice users",
        required=[["user", "users", "agent", "agents", "executive", "staff", "employee"]],
        boost=[["list", "show", "all", "active"]],
        exclude=["premium", "claim", "commission", "policy", "performance", "top", "best"],
        sql="""
SELECT bu.user_id, bu.username, bu.system_role, bu.is_active
FROM backoffice_users bu
WHERE bu.is_active = 1
ORDER BY bu.username
""",
    ),

    SQLTemplate(
        id="users_by_role",
        description="Users grouped by system role",
        required=[["user", "users", "agent", "staff"], ["role", "roles", "designation"]],
        sql="""
SELECT bu.system_role, COUNT(*) AS user_count
FROM backoffice_users bu
WHERE bu.is_active = 1
GROUP BY bu.system_role
ORDER BY user_count DESC
""",
    ),

    SQLTemplate(
        id="users_top_performing",
        description="Top performing users by premium generated",
        required=[["top", "best"], ["user", "agent", "executive", "performer", "performing"]],
        boost=[["premium", "policy"]],
        sql="""
SELECT bu.username, bu.system_role,
       COUNT(*) AS policies_sold,
       SUM(p.premium_amount) AS total_premium
FROM policies p
JOIN backoffice_users bu ON p.created_by_user_id = bu.user_id AND bu.is_active = 1
WHERE p.is_active = 1
GROUP BY bu.user_id, bu.username, bu.system_role
ORDER BY total_premium DESC
LIMIT 10
""",
    ),

    # ─── CROSS-DIMENSIONAL / OVERVIEW METRICS ─────────────────────────────

    SQLTemplate(
        id="regional_overview",
        description="Regional performance overview",
        required=[["region", "state", "regional"], ["overview", "performance", "summary", "analysis"]],
        sql="""
SELECT cli.region_name,
       COUNT(DISTINCT p.policy_id) AS policy_count,
       COUNT(DISTINCT cli.client_id) AS client_count,
       SUM(p.premium_amount) AS total_premium,
       SUM(cl.quote_approved_amount) AS total_claims,
       ROUND(SUM(cl.quote_approved_amount) / NULLIF(SUM(p.premium_amount), 0) * 100, 2) AS loss_ratio_pct
FROM policies p
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
LEFT JOIN claims cl ON cl.policy_id = p.policy_id AND cl.is_active = 1
WHERE p.is_active = 1
GROUP BY cli.region_name
ORDER BY total_premium DESC
""",
    ),

    SQLTemplate(
        id="channel_analysis",
        description="Distribution channel performance analysis",
        required=[["channel", "distribution"], ["analysis", "performance", "overview", "summary", "comparison"]],
        sql="""
SELECT p.distribution_channel,
       COUNT(*) AS policy_count,
       SUM(p.premium_amount) AS total_premium,
       ROUND(AVG(p.premium_amount), 2) AS avg_premium
FROM policies p
WHERE p.is_active = 1
GROUP BY p.distribution_channel
ORDER BY total_premium DESC
""",
    ),

    SQLTemplate(
        id="business_overview",
        description="Overall business KPI summary / dashboard data",
        required=[["overview", "summary", "dashboard", "kpi", "snapshot", "overall"]],
        boost=[["business", "total", "give", "show"]],
        exclude=["carrier", "product", "region", "client", "user"],
        sql="""
SELECT
  (SELECT COUNT(*) FROM policies p WHERE p.is_active = 1) AS total_policies,
  (SELECT SUM(p.premium_amount) FROM policies p WHERE p.is_active = 1) AS total_premium,
  (SELECT COUNT(*) FROM claims cl WHERE cl.is_active = 1) AS total_claims,
  (SELECT SUM(cl.quote_approved_amount) FROM claims cl WHERE cl.is_active = 1) AS total_claim_amount,
  (SELECT COUNT(*) FROM clients cli WHERE cli.is_active = 1) AS total_clients,
  (SELECT COUNT(*) FROM carriers car WHERE car.is_active = 1) AS total_carriers,
  (SELECT SUM(sc.calculated_amount) FROM sales_commissions sc WHERE sc.is_active = 1) AS total_commission
""",
    ),

    SQLTemplate(
        id="profitability_analysis",
        description="Profitability analysis (premium - claims - commission)",
        required=[["profit", "profitability", "margin", "net", "revenue"]],
        boost=[["analysis", "carrier", "product", "show", "give"]],
        sql="""
SELECT car.carrier_name,
       SUM(p.premium_amount) AS total_premium,
       SUM(cl.quote_approved_amount) AS total_claims,
       SUM(sc.calculated_amount) AS total_commission,
       SUM(p.premium_amount) - SUM(cl.quote_approved_amount) - SUM(sc.calculated_amount) AS net_margin
FROM policies p
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
LEFT JOIN claims cl ON cl.policy_id = p.policy_id AND cl.is_active = 1
LEFT JOIN sales_commissions sc ON sc.policy_id = p.policy_id AND sc.is_active = 1
WHERE p.is_active = 1
GROUP BY car.carrier_name
ORDER BY net_margin DESC
""",
    ),

    # ─── TIME-BASED QUERIES ───────────────────────────────────────────────

    SQLTemplate(
        id="this_month_premium",
        description="Premium collected this month",
        required=[["this month", "current month"], ["premium"]],
        boost=[["collected", "earned", "generated"]],
        sql="""
SELECT SUM(p.premium_amount) AS this_month_premium, COUNT(*) AS policy_count
FROM policies p
WHERE p.is_active = 1
  AND MONTH(p.issue_date) = MONTH(CURDATE())
  AND YEAR(p.issue_date) = YEAR(CURDATE())
""",
    ),

    SQLTemplate(
        id="this_year_premium",
        description="Premium collected this year",
        required=[["this year", "current year", "ytd", "year to date"], ["premium"]],
        sql="""
SELECT SUM(p.premium_amount) AS ytd_premium, COUNT(*) AS policy_count
FROM policies p
WHERE p.is_active = 1
  AND YEAR(p.issue_date) = YEAR(CURDATE())
""",
    ),

    SQLTemplate(
        id="last_month_premium",
        description="Premium collected last month",
        required=[["last month", "previous month"], ["premium"]],
        sql="""
SELECT SUM(p.premium_amount) AS last_month_premium, COUNT(*) AS policy_count
FROM policies p
WHERE p.is_active = 1
  AND MONTH(p.issue_date) = MONTH(DATE_SUB(CURDATE(), INTERVAL 1 MONTH))
  AND YEAR(p.issue_date) = YEAR(DATE_SUB(CURDATE(), INTERVAL 1 MONTH))
""",
    ),

    SQLTemplate(
        id="this_month_claims",
        description="Claims this month",
        required=[["this month", "current month"], ["claim", "claims"]],
        sql="""
SELECT COUNT(*) AS claim_count, SUM(cl.quote_approved_amount) AS total_claims
FROM claims cl
JOIN policies p ON cl.policy_id = p.policy_id AND p.is_active = 1
WHERE cl.is_active = 1
  AND MONTH(p.issue_date) = MONTH(CURDATE())
  AND YEAR(p.issue_date) = YEAR(CURDATE())
""",
    ),

    SQLTemplate(
        id="this_month_policies",
        description="Policies issued this month",
        required=[["this month", "current month"], ["policy", "policies"]],
        exclude=["premium", "claim"],
        sql="""
SELECT COUNT(*) AS policies_this_month
FROM policies p
WHERE p.is_active = 1
  AND MONTH(p.issue_date) = MONTH(CURDATE())
  AND YEAR(p.issue_date) = YEAR(CURDATE())
""",
    ),

    # ─── PREMIUM + CARRIER + PRODUCT COMBINATIONS ─────────────────────────

    SQLTemplate(
        id="premium_carrier_product",
        description="Premium by carrier and product category",
        required=[["premium", "gwp"], ["carrier", "insurer"], ["product", "category"]],
        sql="""
SELECT car.carrier_name, pr.category,
       SUM(p.premium_amount) AS total_premium, COUNT(*) AS policy_count
FROM policies p
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE p.is_active = 1
GROUP BY car.carrier_name, pr.category
ORDER BY total_premium DESC
""",
    ),

    SQLTemplate(
        id="premium_carrier_region",
        description="Premium by carrier and region",
        required=[["premium", "gwp"], ["carrier", "insurer"], ["region", "state"]],
        sql="""
SELECT car.carrier_name, cli.region_name,
       SUM(p.premium_amount) AS total_premium, COUNT(*) AS policy_count
FROM policies p
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE p.is_active = 1
GROUP BY car.carrier_name, cli.region_name
ORDER BY total_premium DESC
""",
    ),

    SQLTemplate(
        id="active_products_carriers",
        description="Active product categories and their carriers",
        required=[["active"], ["product", "category"], ["carrier"]],
        sql="""
SELECT DISTINCT pr.category, car.carrier_name
FROM products pr
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE pr.is_active = 1
ORDER BY pr.category, car.carrier_name
""",
    ),

    SQLTemplate(
        id="expired_policies",
        description="List of expired policies",
        required=[["expired", "lapsed"]],
        boost=[["policy", "policies", "show", "list"]],
        exclude=["expiring", "soon", "renew", "upcoming"],
        sql="""
SELECT p.policy_number, cli.name AS client_name, pr.category, car.carrier_name,
       p.premium_amount, p.expiry_date
FROM policies p
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE p.is_active = 1 AND p.status = 'Expired'
ORDER BY p.expiry_date DESC
LIMIT 50
""",
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  Matching engine
# ═══════════════════════════════════════════════════════════════════════════════

def match_dynamic_template(user_query: str) -> tuple[str | None, str | None]:
    """
    Looks for dynamic patterns (like policy IDs, specific client names, or agent names)
    and dynamically constructs the correct parameterized SELECT query.
    """
    query_upper = user_query.upper().strip()
    query_lower = user_query.lower().strip()

    # 1. Specific Policy Number Lookup (e.g. "details for policy POL-1082")
    # Match POL-XXXX or POLXXXX
    pol_match = re.search(r'\b(POL-?\d+)\b', query_upper)
    if pol_match:
        pol_num = pol_match.group(1)
        sql = f"""
SELECT p.policy_number, cli.name AS client_name, pr.category, pr.sub_category,
       car.carrier_name, p.issue_date, p.expiry_date, p.premium_amount, p.status, p.distribution_channel
FROM policies p
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
JOIN carriers car ON pr.carrier_id = car.carrier_id AND car.is_active = 1
WHERE p.is_active = 1 AND p.policy_number = '{pol_num}'
"""
        return sql.strip(), f"dynamic_policy_lookup:{pol_num}"

    # 2. Client Name Search (e.g. "find details for client John Doe", "client John")
    # Look for "client [Name]" or "customer [Name]"
    cli_match = re.search(r'\b(?:client|customer|details of|details for|find)\s+([a-zA-Z\s]+?)(?:\s+in\s+[a-zA-Z\s]+)?$', query_lower)
    if cli_match and any(x in query_lower for x in ("client", "customer", "details for", "details of")):
        # Clean up client name
        client_name = cli_match.group(1).strip()
        # Exclude common noise words
        noise = {"details", "of", "for", "client", "customer", "find", "show", "me", "get", "view", "list"}
        client_words = [w for w in client_name.split() if w not in noise]
        if client_words:
            cleaned_client = " ".join(client_words).title()
            sql = f"""
SELECT cli.client_id, cli.name AS client_name, cli.client_type, cli.region_name, cli.address, cli.is_active
FROM clients cli
WHERE cli.is_active = 1 AND cli.name LIKE '%{cleaned_client}%'
LIMIT 15
"""
            return sql.strip(), f"dynamic_client_search:{cleaned_client}"

    # 3. Specific Agent/User Lookup (e.g. "policies issued by agent arun.kumar")
    # Look for "agent [Name]" or "user [Name]" or "issued by [Name]" or "sold by [Name]"
    agent_match = re.search(r'\b(?:issued by agent|sold by agent|by agent|issued by|sold by|agent|user|executive)\s+([a-zA-Z0-9\._\-]+)', query_lower)
    if agent_match:
        agent_name = agent_match.group(1).strip()
        # Avoid matching generic words
        if agent_name not in ("the", "a", "an", "active", "expired", "status", "premium", "claim", "commission", "product", "carrier", "region", "channel", "any", "all"):
            sql = f"""
SELECT bu.username, p.policy_number, cli.name AS client_name, pr.category, p.premium_amount, p.issue_date
FROM policies p
JOIN backoffice_users bu ON p.created_by_user_id = bu.user_id AND bu.is_active = 1
JOIN clients cli ON p.client_id = cli.client_id AND cli.is_active = 1
JOIN products pr ON p.product_id = pr.product_id AND pr.is_active = 1
WHERE p.is_active = 1 AND (bu.username LIKE '%{agent_name}%' OR bu.username = '{agent_name}')
ORDER BY p.issue_date DESC
LIMIT 30
"""
            return sql.strip(), f"dynamic_agent_search:{agent_name}"

    return None, None


def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)
    return re.sub(r'\s+', ' ', text)


def match_template(user_query: str) -> tuple[str | None, str | None]:
    """
    Match *user_query* against the template library (both dynamic and static).

    Returns
    -------
    (sql, template_id)  if a confident match is found.
    (None, None)        if no template matches.
    """
    # ── Check dynamic patterns first (variables extraction) ───────────────
    dyn_sql, dyn_id = match_dynamic_template(user_query)
    if dyn_sql:
        return dyn_sql, dyn_id

    normalised = _normalise(user_query)
    tokens = set(normalised.split())

    best_sql: str | None = None
    best_id: str | None = None
    best_score: float = 0

    for tpl in TEMPLATES:
        # ── Check exclusions first (fast reject) ──────────────────────────
        excluded = False
        for kw in tpl.exclude:
            # Multi-word exclusions checked as substrings
            if ' ' in kw:
                if kw in normalised:
                    excluded = True
                    break
            else:
                if kw in tokens:
                    excluded = True
                    break
        if excluded:
            continue

        # ── Check required keyword groups (ALL groups must match) ─────────
        required_matched = 0
        for group in tpl.required:
            group_hit = False
            for kw in group:
                if ' ' in kw:          # multi-word → substring match
                    if kw in normalised:
                        group_hit = True
                        break
                else:                   # single word → token match
                    # Also check partial/stem match for flexibility
                    if kw in tokens:
                        group_hit = True
                        break
                    # Fuzzy: check if any token starts with the keyword
                    for t in tokens:
                        if t.startswith(kw) or kw.startswith(t):
                            group_hit = True
                            break
                    if group_hit:
                        break
            if group_hit:
                required_matched += 1

        if required_matched < len(tpl.required):
            continue  # not all required groups satisfied

        # ── Score: base + specificity bonus + boost ───────────────────────
        score = required_matched * 10.0
        score += len(tpl.required) * 3.0     # prefer more-specific templates

        for group in tpl.boost:
            for kw in group:
                if ' ' in kw:
                    if kw in normalised:
                        score += 5.0
                        break
                else:
                    if kw in tokens:
                        score += 5.0
                        break

        if score > best_score:
            best_score = score
            best_sql = tpl.sql.strip()
            best_id = tpl.id

    # Confidence threshold: at least 13 points to allow single-required-group
    # templates (10 for match + 3 specificity = 13 base).  Multi-group templates
    # score 23+ naturally, so they always win in ties.
    if best_score >= 13:
        return best_sql, best_id

    return None, None
