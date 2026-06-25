# KPI Study: MyTVS Insurance Analytics Dashboard Metrics
**Date:** 22/06/2026  
**Author:** TVS Analytics Engineering Group  
**Target:** Business Operations & Executive Teams

---

## 1. What do "Cr", "L", and "k" stand for?

In the dashboard, currency and counts are automatically formatted to keep the interface clean and easy to read in the traditional Indian numbering system:
*   **Cr (Crores):** Indicates value in Crores of Rupees (₹).
    *   *Example:* **₹2.77 Cr** = 2.77 Crore Rupees = **₹2,77,00,000** (equivalent to 27.7 Million in Western notation).
*   **L (Lakhs):** Indicates value in Lakhs of Rupees (₹).
    *   *Example:* **₹36.60 L** = 36.60 Lakh Rupees = **₹36,60,000** (equivalent to 3.66 Million in Western notation).
*   **k (Thousands):** Indicates value in thousands (from "kilo").
    *   *Example:* **₹15.2k** = 15.2 Thousand Rupees = **₹15,200**.
    *   *Example:* **1.2k policies** = 1,200 policies.

---

## 2. Page-by-Page KPI Cards Reference

This guide details what each KPI card across the different pages does, how it is calculated, and what it means for the business.

### Tab 1: Executive Summary
The starting screen that gives the leadership team a 5-second health check of the business.

| KPI Card Name | What it Displays | Business Meaning |
| :--- | :--- | :--- |
| **Written Premium** | Total gross premiums billed (e.g., ₹2.77 Cr) and policy count (e.g., 1,000). | Measures the scale of active business we have brought in. |
| **Gross Commission** | Total broker commissions earned (e.g., ₹36.60 L) and commission rate % (e.g., 13.2%). | The top-line revenue earned by the brokerage. Tells us our pricing power. |
| **Claims Incurred** | Total value of claims approved (e.g., ₹42.00 L) and the Loss Ratio (e.g., 15.2%). | Measures the cost we impose on our underwriting carriers. |
| **Loss Ratio** | The Incurred Claim Ratio (ICR) as a percentage (Claims / Premiums). | The key safety metric. If this is **green** ($< 65\%$), the portfolio is highly profitable for carriers, securing our commission agreements. |

---

### Tab 2: Growth & Renewals
Focuses on how fast the business is acquiring new customers and retaining old ones.

| KPI Card Name | What it Displays | Business Meaning |
| :--- | :--- | :--- |
| **Active Portfolio** | Total active premium in-force (e.g., ₹52.00 L) and count of active policies. | Measures the revenue currently live and protected. |
| **Retention Rate** | Percentage of policies successfully renewed upon expiry. | Measures client satisfaction and loyalty. Higher is better. |
| **Churn Rate** | Percentage of policies cancelled or expired without renewal. | Measures customer leakage. High churn rates require immediate action. |
| **Policies Renewed** | Count of renewed policies vs. expired policies. | A headcount comparison showing if we are keeping more clients than we lose. |

---

### Tab 3 & 4: Claims Overview & Details
Monitors the lifecycle of claims submitted by policyholders.

| KPI Card Name | What it Displays | Business Meaning |
| :--- | :--- | :--- |
| **Claims Filed** | Total number of claims submitted and claim frequency % (Claims / Policies). | Tells us how often policyholders file claims. Helps price risk. |
| **Open Exposure** | Total value and count of claims currently unresolved/pending. | Unpaid liability. Shows how much claim money is currently tied up in processing. |
| **Claims Approved** | Total value of claims approved, awaiting final settlement payout. | Approved claims ready for payment. |
| **Claims Settled** | Total value of claims fully closed and paid out. | Measures finalized claims payouts. |

---

### Tab 7: Product Mix
Analyzes the distribution of sales across different types of policies.

| KPI Card Name | What it Displays | Business Meaning |
| :--- | :--- | :--- |
| **Categories** | Number of main product categories (e.g., Motor, Health, Home). | Shows the diversity of our insurance lines. |
| **Sub-Categories** | Number of detailed sub-product lines (e.g., Two-Wheeler, Private Car). | Measures product depth. |
| **Total Premium** | Total written premium generated across all products. | Overall product sales volume. |
| **B2B Share** | Percentage of written premium from corporate accounts vs. B2C retail. | Shows our customer segment mix. Corporate accounts have higher premiums but lower margins. |

---

### Tab 8: Carrier Scorecard
Evaluates the performance of our underwriting insurance company partners (carriers).

| KPI Card Name | What it Displays | Business Meaning |
| :--- | :--- | :--- |
| **Active Carriers** | Total number of underwriting partners. | Measures our market partnerships. |
| **Top Carrier** | The carrier with the largest written premium volume. | Identifies our most critical underwriting partner. |
| **Total Premium** | Total premium placed across all carriers. | Volume of insurance placed. |
| **High ICR Carriers** | Number of carriers with a loss ratio $> 65\%$. | Flags underwriters experiencing high losses. These require risk mitigation or rate changes. |

---

### Tab 9 & 10: Top Clients & Channels
Monitors where our sales are coming from.

| KPI Card Name | What it Displays | Business Meaning |
| :--- | :--- | :--- |
| **Total Clients** | Count of unique client accounts. | Indicates the size of our customer base. |
| **Top Client** | The individual/corporate client with the largest premium spend. | Highlights our key account concentration risk. |
| **Channels** | Count of active sales channels (Direct, Broker, Online, etc.). | Tells us how diversified our distribution is. |
| **Top Channel** | The sales channel bringing in the most premium volume. | Identifies our most efficient sales route. |

---

### Tab 11 & 12: Profitability & Margins
Monitors the financial bottom line of the business.

| KPI Card Name | What it Displays | Business Meaning |
| :--- | :--- | :--- |
| **Gross Commission** | Total broker commissions earned. | The brokerage's primary revenue. |
| **Carrier Profit** | Estimated net profit left for underwriters ($\text{Premium} - \text{Claims} - \text{Commission}$). | Evaluates if the carriers are making money from our books of business. |
| **Comm Margin** | Broker commission as a percentage of written premium. | Our average margins. Higher margins mean more profitable contracts. |
| **Avg Margin Trend** | Monthly average margin percentage over time. | Tells us if our broker commission rate is improving or declining. |
| **Portfolio Margin** | Overall commission to premium ratio. | The blended profit margin across the entire business portfolio. |

---

### Tab 13: Portfolio Renewals (Expiry Pipeline)
Tracks expiring policies grouped by time remaining to help sales teams prioritize actions.

| KPI Card Name | What it Displays | Business Meaning |
| :--- | :--- | :--- |
| **0–30 Days** | Premium and count of policies expiring within 30 days. | **CRITICAL:** High immediate churn risk. Needs immediate contact. |
| **31–60 Days** | Premium and count of policies expiring in 31–60 days. | **URGENT:** Needs active renewal campaigns. |
| **61–90 Days** | Premium and count of policies expiring in 61–90 days. | **PLAN:** Upcoming opportunities for sales outreach. |
| **91–180 Days** | Premium and count of policies expiring in 91–180 days. | **WATCH:** Medium-term renewal pipeline. |

---

### Tab 15: Regional Analytics
Tracks geographic distribution of business across different states/regions.

| KPI Card Name | What it Displays | Business Meaning |
| :--- | :--- | :--- |
| **Regions** | Count of distinct regions/states active in the dataset. | Extent of our geographic footprint. |
| **Top Region** | The state/region with the highest written premium volume. | Identifies our key regional market. |
| **Total Premium** | Cumulative premium written across all regions. | Overall sales volume. |
| **Total Claims** | Cumulative claims approved across all regions. | Combined regional claim losses. |
