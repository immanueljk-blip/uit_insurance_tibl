from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

TVS_BLUE   = "#1B3B8B"
TVS_ORANGE = "#E55B13"
GREEN      = "#10B981"
RED        = "#EF4444"
PURPLE     = "#8B5CF6"
AMBER      = "#F59E0B"

PALETTE = [TVS_BLUE, TVS_ORANGE, GREEN, PURPLE, AMBER, RED, "#3B82F6", "#EC4899"]

# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────

def _cfg():
    return {
        "plot_bgcolor": "rgba(0,0,0,0)",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "Plus Jakarta Sans, Inter, sans-serif", "color": "#374151"},
        "margin": {"t": 10, "b": 10, "l": 10, "r": 10},
        "hoverlabel": {
            "bgcolor": "#1B3B8B",
            "font_size": 13,
            "font_family": "Plus Jakarta Sans, Inter, sans-serif",
            "font_color": "white",
            "bordercolor": "#E55B13",
            "namelength": -1,
        },
        "colorway": PALETTE,
    }

def _ax(fig, tickangle=0):
    fig.update_xaxes(showgrid=False, zeroline=False,
                     title_font=dict(size=10, color="#374151"),
                     tickfont=dict(size=9.5, color="#374151"),
                     tickangle=tickangle, automargin=True)
    fig.update_yaxes(showgrid=True, gridcolor="#E5E7EB", zeroline=False,
                     title_font=dict(size=10, color="#374151"),
                     tickfont=dict(size=9.5, color="#374151"), automargin=True)
    fig.update_layout(legend=dict(
        orientation="h", 
        yanchor="bottom", 
        y=1.02, 
        xanchor="right", 
        x=1, 
        font=dict(size=9),
        title_text=""
    ))
    return fig

def wrap_chart(fig, height="260px", graph_id=None):
    kwargs = {}
    if graph_id:
        kwargs['id'] = {"type": "dynamic-chart", "index": graph_id}
    return html.Div(
        dcc.Graph(figure=fig, config={"displayModeBar": False}, style={"height": height}, **kwargs),
        style={"background": "white", "borderRadius": "10px", "padding": "10px 12px",
               "boxShadow": "0 2px 8px rgba(0,0,0,0.04)", "marginBottom": "8px",
               "border": "1px solid #E5E7EB"}
    )

def format_currency(val):
    if pd.isna(val) or val == 0: return "₹0"
    sign = "-" if val < 0 else ""
    abs_val = abs(val)
    if abs_val >= 10_000_000:
        return f"{sign}₹{abs_val/10_000_000:.2f} Cr"
    elif abs_val >= 100_000:
        return f"{sign}₹{abs_val/100_000:.2f} L"
    elif abs_val >= 1_000:
        return f"{sign}₹{abs_val/1_000:.1f}k"
    return f"{sign}₹{abs_val:,.0f}"


def kpi_card(title, value, subtitle=None, subtitle_color=GREEN, accent=TVS_ORANGE, icon="", sparkline=None, id=None, theme=None):
    val_kwargs = {"className": "kpi-value"}
    if id:
        val_kwargs["id"] = f"{id}-val"
        
    children = [
        html.Div(icon + " " + title if icon else title, className="kpi-title"),
        html.Div(value, **val_kwargs),
    ]
    if subtitle:
        children.append(html.Div(subtitle, className="kpi-sub", style={"--sub-color": subtitle_color}))
    
    style = {"--card-color": accent}
    className = "kpi-card-premium"
    if theme:
        className += f" kpi-card-premium--{theme}"
        
    kwargs = {
        "className": className,
        "style": style
    }
    if id is not None:
        kwargs["id"] = id
        kwargs["n_clicks"] = 0  # type: ignore
        style["cursor"] = "pointer"
        
    return html.Div(children, **kwargs)


def kpi_row(*cards):
    """Equal-width flex KPI strip — replaces dbc.Row for tab headers."""
    return html.Div([html.Div(c, className="kpi-col") for c in cards], className="kpi-row")

def section_title(text, sub=""):
    return html.Div([
        html.H4(text, style={"color": TVS_BLUE, "fontWeight": "800",
                              "fontSize": "17px", "margin": "0 0 2px 0"}),
        html.P(sub, style={"color": "#9CA3AF", "fontSize": "12px", "margin": "0"}) if sub else None,
    ], style={"marginBottom": "8px", "marginTop": "4px"})




# ─────────────────────────────────────────────
# Layout Primitives (Definitive v4)
# ─────────────────────────────────────────────

_CARD_STYLE = {
    "background": "white", "borderRadius": "10px",
    "padding": "8px 12px", "border": "1px solid #E5E7EB",
    "boxShadow": "0 2px 8px rgba(0,0,0,0.04)",
    "overflow": "hidden",
}

def chart_box(fig, gid=None, flex="1", min_width="0"):
    """Flex-filling chart card. Extracts title to HTML to save space."""
    kwargs = {}
    if gid:
        kwargs["id"] = {"type": "dynamic-chart", "index": gid}

    title_text = ""
    if hasattr(fig, 'layout') and hasattr(fig.layout, 'title') and fig.layout.title and fig.layout.title.text:
        title_text = fig.layout.title.text
        fig.layout.title.text = ""

    children: list = []
    if title_text:
        children.append(html.Div(title_text, className="chart-title"))

    children.append(
        dcc.Graph(figure=fig,
                  config={"displayModeBar": False, "responsive": True},
                  style={"flex": "1", "minHeight": "0", "height": "100%"},
                  **kwargs)
    )

    return html.Div(children, className="chart-card-flex",
                    style={"flex": flex, "minWidth": min_width})


def content_box(children, flex="1", scrollable=False, style=None):
    """Flex-filling generic content card (for tables, panels)."""
    cls = "content-card-flex content-card-flex--scroll" if scrollable else "content-card-flex"
    base_style = {"flex": flex, "minWidth": "0"}
    if style:
        base_style.update(style)
    return html.Div(children, className=cls, style=base_style)


def hrow(*items, gap="6px"):
    """One horizontal row of chart_boxes / content_boxes — flex:1 vertically."""
    return html.Div(list(items), className="tab-pane-row", style={"gap": gap})


def tab_layout(kpi_row_element, *chart_rows):
    """Full tab container — zero scroll, fills viewport."""
    return html.Div([
        kpi_row_element,
        html.Div(
            chart_rows,
            className="tab-pane-charts",
        ),
    ], className="tab-pane")


# ─────────────────────────────────────────────
# TAB 1 — Executive Summary
# ─────────────────────────────────────────────

def tab1(df):
    if df.empty: return html.Div("No Data")

    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    claim_col   = 'claim_amount'   if 'claim_amount'   in df.columns else None
    comm_col    = 'commission_earned' if 'commission_earned' in df.columns else None

    total_prem  = df[premium_col].sum() if premium_col else 0
    total_claim = df[claim_col].sum()   if claim_col   else 0
    total_comm  = df[comm_col].sum()    if comm_col    else 0
    loss_ratio  = (total_claim / total_prem * 100) if total_prem > 0 else 0
    lr_color    = RED if loss_ratio > 65 else GREEN

    # ── Retention Rate ──
    if 'policy_status' in df.columns:
        status_counts = df['policy_status'].value_counts()
        renewed    = status_counts.get('Renewed', 0)
        expired    = status_counts.get('Expired', 0)
        cancelled  = status_counts.get('Cancelled', 0)
        active     = status_counts.get('Active', 0)
        
        today = pd.Timestamp.now().normalize()
        eligible_expired = 0
        if 'expiry_date' in df.columns:
            expired_df = df[df['policy_status'] == 'Expired']
            if not expired_df.empty:
                exp_dates = pd.to_datetime(expired_df['expiry_date'], errors='coerce')
                eligible_expired = ((exp_dates >= (today - pd.Timedelta(days=30))) & (exp_dates <= today)).sum()
                
        true_expired_churn = max(0, expired - eligible_expired)
        denom      = renewed + expired + cancelled
        ret_rate   = (renewed / denom * 100) if denom > 0 else 0
        ret_color  = GREEN if ret_rate >= 40 else (AMBER if ret_rate >= 25 else RED)
        churn_rate = ((cancelled + true_expired_churn) / denom * 100) if denom > 0 else 0
        active_prem = df[df['policy_status'] == 'Active'][premium_col].sum() if premium_col else 0
    else:
        ret_rate = 0; churn_rate = 0; active_prem = 0; ret_color = GREEN
        active = renewed = expired = cancelled = 0

    # ── Sparklines ──
    spark_prem, spark_comm, spark_claim = None, None, None
    if 'issue_date' in df.columns:
        trend_df = df.dropna(subset=['issue_date']).copy()
        if not trend_df.empty:
            trend_df['month'] = trend_df['issue_date'].dt.to_period('M').astype(str)  # type: ignore
            trend_grp = trend_df.groupby('month')[[premium_col, claim_col, comm_col]].sum().reset_index()
            trend_grp = trend_grp.sort_values('month')
            
            def make_spark(y_col, color):
                rgba_fill = f"rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.15)"
                fig = go.Figure(go.Scatter(x=trend_grp['month'], y=trend_grp[y_col], mode='lines', 
                                           line=dict(color=color, width=2.5), fill='tozeroy', fillcolor=rgba_fill))
                fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=40, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                  xaxis=dict(visible=False, fixedrange=True), yaxis=dict(visible=False, fixedrange=True))
                return fig
            
            if premium_col: spark_prem = make_spark(premium_col, TVS_BLUE)
            if comm_col: spark_comm = make_spark(comm_col, GREEN)
            if claim_col: spark_claim = make_spark(claim_col, RED)

    # ── Policy Status Bar ──
    if 'policy_status' in df.columns:
        status_df = df['policy_status'].value_counts().reset_index()
        status_df.columns = ['status', 'count']
        colors_map = {'Active': GREEN, 'Renewed': TVS_BLUE,
                      'Cancelled': RED, 'Expired': AMBER}
        fig_status = px.bar(status_df, y='status', x='count', orientation='h',
                            title="Portfolio Health — Policy Status",
                            color='status',
                            color_discrete_map=colors_map, text='count')
        fig_status.update_traces(textposition='auto', showlegend=False)
        fig_status.update_layout(**_cfg())
        fig_status.update_layout(margin=dict(t=40, r=20))
        fig_status.update_yaxes(categoryorder='total ascending', title=None, automargin=True)
        fig_status.update_xaxes(title="Number of Policies", automargin=True)
    else:
        fig_status = px.bar(title="Status N/A")

    # ── Monthly New Business vs Renewals Stacked Bar ──
    if 'issue_date' in df.columns and premium_col:
        df2 = df.copy()
        df2['issue_month'] = pd.to_datetime(df2['issue_date']).dt.to_period('M').astype(str)  # type: ignore
        df2['biz_type'] = df2['policy_status'].apply(
            lambda s: 'Renewal' if s == 'Renewed' else 'New Business'
        ) if 'policy_status' in df2.columns else 'New Business'
        monthly = df2.groupby(['issue_month', 'biz_type'])[premium_col].sum().reset_index()
        monthly = monthly.sort_values('issue_month')
        all_months = sorted(monthly['issue_month'].unique())
        tick_vals  = [m for i, m in enumerate(all_months) if i % 3 == 0]
        fig_monthly = px.bar(monthly, x='issue_month', y=premium_col, color='biz_type',
                             title="Monthly Written Premium — New Business vs Renewals",
                             barmode='stack',
                             color_discrete_map={'New Business': TVS_BLUE, 'Renewal': TVS_ORANGE},
                             custom_data=['biz_type'])
        fig_monthly.update_traces(
            hovertemplate="<b>%{x}</b><br>%{customdata[0]}: ₹%{y:,.0f}<extra></extra>"
        )
        _ax(fig_monthly.update_layout(
            **_cfg(), legend_title="Business Type",
            xaxis_title="Month", yaxis_title="Premium (₹)",
            xaxis=dict(tickvals=tick_vals, tickangle=-35,
                       tickfont=dict(size=11, color="#374151")),
            legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="center", x=0.5)
        ))
    else:
        fig_monthly = px.bar(title="Monthly Data N/A")

    return tab_layout(
        kpi_row(
            kpi_card("Written Premium",  format_currency(total_prem),  f"{len(df):,} policies",             sparkline=spark_prem, theme="tvs-blue"),
            kpi_card("Gross Commission", format_currency(total_comm),  f"{(total_comm/total_prem*100):.1f}% of premium" if total_prem else "", sparkline=spark_comm, theme="tvs-orange"),
            kpi_card("Claims Incurred",  format_currency(total_claim), f"Loss Ratio: {loss_ratio:.1f}%", lr_color, sparkline=spark_claim),
            kpi_card("Loss Ratio",       f"{loss_ratio:.1f}%",         "Target < 65%",               lr_color, accent=lr_color),
        ),
        hrow(
            chart_box(fig_status,  "status-chart"),
            chart_box(fig_monthly, "monthly-chart", flex="2"),
        ),
    )

# ─────────────────────────────────────────────
# TAB 2 — Growth & Renewals
# ─────────────────────────────────────────────

def tab2(df):
    if df.empty: return html.Div("No Data")

    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None

    # ── KPI Row 2 (Portfolio Health) ──
    if 'policy_status' in df.columns:
        status_counts = df['policy_status'].value_counts()
        renewed    = status_counts.get('Renewed', 0)
        expired    = status_counts.get('Expired', 0)
        cancelled  = status_counts.get('Cancelled', 0)
        active     = status_counts.get('Active', 0)
        
        today = pd.Timestamp.now().normalize()
        eligible_expired = 0
        if 'expiry_date' in df.columns:
            expired_df = df[df['policy_status'] == 'Expired']
            if not expired_df.empty:
                exp_dates = pd.to_datetime(expired_df['expiry_date'], errors='coerce')
                eligible_expired = ((exp_dates >= (today - pd.Timedelta(days=30))) & (exp_dates <= today)).sum()
                
        true_expired_churn = max(0, expired - eligible_expired)
        denom      = renewed + expired + cancelled
        ret_rate   = (renewed / denom * 100) if denom > 0 else 0
        ret_color  = GREEN if ret_rate >= 40 else (AMBER if ret_rate >= 25 else RED)
        churn_rate = ((cancelled + true_expired_churn) / denom * 100) if denom > 0 else 0
        active_prem = df[df['policy_status'] == 'Active'][premium_col].sum() if premium_col else 0
    else:
        ret_rate = 0; churn_rate = 0; active_prem = 0; ret_color = GREEN
        active = renewed = expired = cancelled = 0

    # ── Premium Growth Trajectory Line ──
    if 'issue_date' in df.columns and premium_col:
        df3 = df.copy()
        df3['issue_month'] = pd.to_datetime(df3['issue_date']).dt.to_period('M').astype(str)  # type: ignore
        growth_df = df3.groupby('issue_month')[premium_col].sum().reset_index().sort_values('issue_month')
        growth_df['cumulative'] = growth_df[premium_col].cumsum()
        all_months_g = sorted(growth_df['issue_month'].unique())
        tick_vals_g  = [m for i, m in enumerate(all_months_g) if i % 3 == 0]
        fig_growth = px.line(growth_df, x='issue_month', y='cumulative',
                             title="Cumulative Premium Written (All-Time)",
                             markers=True)
        fig_growth.update_traces(line_color=TVS_BLUE, line_width=3,
                                 fill='tozeroy', fillcolor='rgba(27,59,139,0.09)',
                                 hovertemplate="<b>%{x}</b><br>Cumulative: ₹%{y:,.0f}<extra></extra>")
        _ax(fig_growth.update_layout(
            **_cfg(), yaxis_title="Cumulative Premium (₹)",
            xaxis=dict(tickvals=tick_vals_g, tickangle=-35,
                       tickfont=dict(size=11, color="#374151"))
        ))
    else:
        fig_growth = px.line(title="Time Series Data N/A")

    return tab_layout(
        kpi_row(
            kpi_card("Active Portfolio", format_currency(active_prem), f"{active:,} active",        GREEN,   accent=GREEN, theme="tvs-blue"),
            kpi_card("Retention Rate",   f"{ret_rate:.1f}%",           "Ren/(Exp+Can+Ren)",          ret_color, accent=ret_color, theme="tvs-orange"),
            kpi_card("Churn Rate",       f"{churn_rate:.1f}%",         f"{cancelled:,} cancelled",
                     RED if churn_rate > 30 else AMBER, accent=RED if churn_rate > 30 else AMBER),
            kpi_card("Policies Renewed", f"{renewed:,}",               f"vs {expired:,} expired",   AMBER,   accent=PURPLE),
        ),
        hrow(chart_box(fig_growth, "growth-chart", flex="1")),
    )

def tab2b(df):
    """New dedicated tab for Renewal Targeting Engine."""
    renewal_column = html.Div([
        # Top Card: Stats at the very top
        dcc.Loading(
            html.Div(id="renewal-stats-section",
                     style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr 1fr", "gap": "16px", "marginBottom": "20px", "maxWidth": "1000px"}),
            type="dot", color=TVS_ORANGE),
        
        # Middle Card: Filter Control Box
        content_box([
            html.Div([
                html.Span("Renewal Targeting Control",
                          style={"fontSize": "15px", "fontWeight": "800", "color": TVS_BLUE}),
                html.P("Enter custom number of days to filter upcoming policy expirations",
                       style={"fontSize": "11px", "color": "#9CA3AF", "margin": "1px 0 12px"}),
            ]),
            html.Div([
                html.Label("Target Expiry Window (Days)", 
                           style={"fontSize": "12px", "fontWeight": "600", "color": "#374151", "marginBottom": "6px", "display": "block"}),
                dcc.Input(
                    id="renewal-input",
                    type="number",
                    min=1,
                    max=365,
                    step=1,
                    value=30,
                    placeholder="Enter days (e.g. 30)...",
                    style={
                        "width": "100%",
                        "maxWidth": "300px",
                        "padding": "10px 14px",
                        "border": "1px solid #D1D5DB",
                        "borderRadius": "8px",
                        "fontSize": "13px",
                        "fontFamily": "Plus Jakarta Sans, Inter, sans-serif",
                        "color": "#374151",
                        "backgroundColor": "#F9FAFB",
                        "outline": "none",
                        "boxShadow": "inset 0 1px 2px rgba(0,0,0,0.05)",
                        "transition": "border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out"
                    }
                )
            ], style={"marginTop": "8px"}),
        ], style={"marginBottom": "20px", "flexShrink": "0", "padding": "24px"}),
        
        # Bottom Card: Data Table
        content_box([
            html.Div([
                html.Span("Expiring Policies",
                          style={"fontSize": "15px", "fontWeight": "800", "color": TVS_BLUE}),
            ], style={"marginBottom": "12px"}),
            dcc.Loading(
                html.Div(id="renewal-table-section",
                         style={"height": "auto", "flexShrink": 0, "overflowY": "hidden"}),
                type="dot", color=TVS_ORANGE),
        ], style={"height": "auto", "flexShrink": 0, "display": "flex", "flexDirection": "column", "padding": "24px"})
    ], style={"flex": "1", "display": "flex", "flexDirection": "column", "minHeight": "0", "padding": "12px"})

    return tab_layout(
        html.Div(renewal_column, style={"flex": "1", "display": "flex", "flexDirection": "column", "minHeight": "0"})
    )




# ─────────────────────────────────────────────
# TAB 3 — Claims Overview
# ─────────────────────────────────────────────
def tab3(df):
    if df.empty: return html.Div("No Data")
    claim_col   = 'claim_amount'   if 'claim_amount'   in df.columns else None
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None

    # ── Open Claims Exposure KPIs ──
    open_statuses = ['Registered', 'Survey Completed']
    if 'claim_status' in df.columns and claim_col:
        open_df   = df[df['claim_status'].isin(open_statuses)]
        open_exp  = open_df[claim_col].sum()
        open_cnt  = len(open_df)
        settled   = df[df['claim_status'] == 'Settled'][claim_col].sum()
        approved  = df[df['claim_status'] == 'Approved'][claim_col].sum()
        total_claims_count = df[df[claim_col] > 0].shape[0]
        claim_freq = (total_claims_count / len(df) * 100) if len(df) > 0 else 0
    else:
        open_exp = open_cnt = settled = approved = claim_freq = total_claims_count = 0

    # ── ICR Speedometer Gauge ──
    total_claim = df[claim_col].sum() if claim_col else 0
    total_prem  = df[premium_col].sum() if premium_col else 0
    loss_ratio  = (total_claim / total_prem * 100) if total_prem > 0 else 0

    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number", value = loss_ratio, domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Global Incurred Claims Ratio", 'font': {'size': 12, 'color': "#6B7280"}},
        number = {'suffix': "%", 'font': {'size': 28, 'color': TVS_BLUE, 'weight': 'bold'}},
        gauge = {
            'axis': {'range': [None, 150], 'tickwidth': 1, 'tickcolor': "#D1D5DB"},
            'bar': {'color': TVS_BLUE, 'thickness': 0.15}, 'bgcolor': "white", 'borderwidth': 0,
            'steps': [{'range': [0, 75], 'color': "rgba(16, 185, 129, 0.2)"},
                      {'range': [75, 85], 'color': "rgba(245, 158, 11, 0.2)"},
                      {'range': [85, 150], 'color': "rgba(239, 68, 68, 0.2)"}],
            'threshold': {'line': {'color': "black", 'width': 3}, 'thickness': 0.75, 'value': loss_ratio}
        }
    ))
    fig_gauge.update_layout(**{**_cfg(), 'margin': dict(t=30, b=20, l=20, r=20)})

    # ── Claim Settlement Funnel ──
    if 'claim_status' in df.columns and claim_col:
        stage_order = ['Registered', 'Survey Completed', 'Approved', 'Settled']
        
        # Calculate mutually exclusive current statuses
        raw_vals = {s: df[df['claim_status'] == s][claim_col].sum() for s in stage_order}
        
        # Mathematically model the pipeline (cumulative sum from bottom-up)
        # E.g., any claim that is 'Settled' MUST have passed through 'Approved', 'Survey', and 'Registered'
        cumulative_vals = {}
        running_sum = 0
        for s in reversed(stage_order):
            running_sum += raw_vals[s]
            cumulative_vals[s] = running_sum

        funnel_data = [{'Stage': s, 'Value': cumulative_vals[s]} for s in stage_order]
        funnel_df = pd.DataFrame(funnel_data)
        fig_funnel = px.bar(funnel_df, x='Value', y='Stage', orientation='h', title="Claim Settlement Pipeline (₹ Value)",
                            color='Stage', text=funnel_df['Value'].apply(format_currency),
                            color_discrete_sequence=[RED, AMBER, PURPLE, GREEN])
        fig_funnel.update_traces(textposition='auto')
        _ax(fig_funnel.update_layout(**_cfg(), showlegend=False, yaxis={'categoryorder': 'array', 'categoryarray': stage_order[::-1]}))
    else:
        fig_funnel = go.Figure()

    # ── Claims by Status (bar) ──
    if 'claim_status' in df.columns and claim_col:
        status_df = df[df['claim_status'] != 'No Claim'].groupby('claim_status')[claim_col].sum().reset_index()
        fig_status = px.bar(status_df, x='claim_status', y=claim_col, title="Claims Value by Status",
                            text=status_df[claim_col].apply(format_currency), color='claim_status', color_discrete_sequence=PALETTE)
        fig_status.update_traces(textposition='outside', cliponaxis=False)
        _ax(fig_status.update_layout(**_cfg(), showlegend=False), tickangle=-25)
    else:
        fig_status = px.bar(title="Claims Data N/A")

    return tab_layout(
        kpi_row(
            kpi_card("Claims Filed", f"{total_claims_count:,}", f"{claim_freq:.1f}% frequency", TVS_BLUE, id={"type": "kpi-card", "index": "claims-filed"}),
            kpi_card("Open Exposure", format_currency(open_exp), f"{open_cnt} unresolved", RED, accent=RED, id={"type": "kpi-card", "index": "open-exposure"}),
            kpi_card("Claims Approved", format_currency(approved), "Awaiting settlement", AMBER, accent=AMBER, id={"type": "kpi-card", "index": "claims-approved"}),
            kpi_card("Claims Settled", format_currency(settled), "Fully closed", GREEN, accent=GREEN, id={"type": "kpi-card", "index": "claims-settled"}),
        ),
        hrow(chart_box(fig_gauge, "icr-gauge"), chart_box(fig_funnel, "funnel"), chart_box(fig_status, "status"))
    )

# ─────────────────────────────────────────────
# TAB 3b — Claims Breakdown
# ─────────────────────────────────────────────
def tab3b(df):
    if df.empty: return html.Div("No Data")
    claim_col   = 'claim_amount'   if 'claim_amount'   in df.columns else None
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None

    # KPI values
    open_statuses = ['Registered', 'Survey Completed']
    open_cnt = len(df[df['claim_status'].isin(open_statuses)]) if 'claim_status' in df.columns else 0
    total_claim = df[claim_col].sum() if claim_col else 0
    total_prem  = df[premium_col].sum() if premium_col else 0
    loss_ratio  = (total_claim / total_prem * 100) if total_prem > 0 else 0
    total_claims_count = df[df[claim_col] > 0].shape[0] if claim_col else 0
    avg_claim = (total_claim / total_claims_count) if total_claims_count > 0 else 0
    settled_claims = len(df[(df[claim_col] > 0) & (df['claim_status'] == 'Settled')]) if (claim_col and 'claim_status' in df.columns) else 0
    settlement_rate = (settled_claims / total_claims_count * 100) if total_claims_count > 0 else 0

    # ── Claims by Category Bar (Value) ──
    if 'category' in df.columns and claim_col:
        cat_claim = df[df[claim_col] > 0].groupby('category')[claim_col].sum().reset_index()
        fig_cat = px.bar(cat_claim, y='category', x=claim_col, orientation='h', title="Claims Value by Category",
                         color='category', color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_cat.update_traces(showlegend=False)
        _ax(fig_cat.update_layout(**_cfg(), yaxis={'categoryorder':'total ascending', 'title':None}, xaxis={'title':"Total Claims (₹)"}))
    else:
        fig_cat = px.bar(title="N/A")

    # ── Claims Frequency by Category (Count) ──
    if 'category' in df.columns and claim_col:
        freq_df = df[df[claim_col] > 0].groupby('category').size().reset_index(name='claim_count')
        freq_df = freq_df.sort_values('claim_count', ascending=True)
        fig_freq = px.bar(freq_df, y='category', x='claim_count', orientation='h',
                          title="Claims Frequency by Category (No. of Claims)",
                          color='claim_count',
                          color_continuous_scale=["#DBEAFE", "#EF4444"])
        fig_freq.update_layout(**{**_cfg(), 'coloraxis_showscale': False})
        _ax(fig_freq, )
        fig_freq.update_xaxes(title="Number of Claims")
        fig_freq.update_yaxes(title=None)
    else:
        fig_freq = px.bar(title="N/A")

    # ── Premium vs Claims by Carrier ──
    if 'carrier_name' in df.columns and claim_col and premium_col:
        g = df.groupby('carrier_name')[[premium_col, claim_col]].sum().reset_index()
        fig_vs = px.bar(g, x='carrier_name', y=[premium_col, claim_col], barmode='group', title="Premium vs Claims by Carrier",
                        color_discrete_map={premium_col: TVS_BLUE, claim_col: TVS_ORANGE})
        fig_vs.for_each_trace(lambda t: t.update(name="Premium" if t.name == premium_col else "Claims"))
        _ax(fig_vs, tickangle=-35)
        
        # ── ICR by Carrier ──
        g['ICR_%'] = np.where(g[premium_col] > 0, (g[claim_col] / g[premium_col]) * 100, 0)
        g_icr = g.sort_values('ICR_%', ascending=False)
        fig_icr = px.bar(g_icr, x='carrier_name', y='ICR_%', title="ICR by Carrier",
                         color='ICR_%', color_continuous_scale=px.colors.sequential.OrRd, range_color=[0, g_icr['ICR_%'].max()])
        _ax(fig_icr.update_layout(**_cfg()), tickangle=-35)
    else:
        fig_vs = px.bar(title="Carrier Data N/A")
        fig_icr = px.bar(title="ICR Data N/A")

    return tab_layout(
        kpi_row(
            kpi_card("Total Claims",  format_currency(total_claim), f"{open_cnt} unresolved", RED,        accent=RED),
            kpi_card("Avg Claim Size", format_currency(avg_claim),   "Across all filed claims", GREEN,      accent=GREEN),
            kpi_card("Settlement Rate", f"{settlement_rate:.1f}%",   "Settled vs total filed",  TVS_ORANGE, accent=TVS_ORANGE),
        ),
        hrow(
            chart_box(fig_vs,  "carrier-vs-chart", flex="3"),
            chart_box(fig_icr, "icr-chart",         flex="2"),
        ),
        hrow(
            chart_box(fig_cat,  "cat-chart",  flex="1"),
            chart_box(fig_freq, "freq-chart", flex="1"),
        ),
    )

# ─────────────────────────────────────────────
# TAB 4 — Risk Overview
# ─────────────────────────────────────────────
def tab4(df):
    if df.empty: return html.Div("No Data")
    claim_col   = 'claim_amount'   if 'claim_amount'   in df.columns else None
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None

    total_claim = df[claim_col].sum() if claim_col else 0
    total_prem  = df[premium_col].sum() if premium_col else 0
    loss_ratio  = (total_claim / total_prem * 100) if total_prem > 0 else 0
    icr_color = RED if loss_ratio > 85 else (AMBER if loss_ratio > 65 else GREEN)

    high_risk_carrier = "N/A"
    high_risk_icr = 0.0
    if 'carrier_name' in df.columns and claim_col and premium_col:
        try:
            cg = df.groupby('carrier_name').agg(P=(premium_col, 'sum'), C=(claim_col, 'sum')).reset_index()
            cg['icr'] = np.where(cg['P'] > 0, cg['C'] / cg['P'] * 100, 0)
            if not cg.empty:
                max_row = cg.loc[cg['icr'].idxmax()]
                high_risk_carrier = max_row['carrier_name']
                high_risk_icr = max_row['icr']
        except Exception:
            pass

    avg_exposure = (total_claim / len(df)) if len(df) > 0 else 0
    open_statuses = ['Registered', 'Survey Completed']
    pending_claims_val = df[df['claim_status'].isin(open_statuses)][claim_col].sum() if (claim_col and 'claim_status' in df.columns) else 0

    fig_gauge = go.Figure(go.Indicator(
        mode = "gauge+number", value = loss_ratio, title={'text':"Overall ICR"},
        number = {'suffix': "%"},
        gauge = {'axis': {'range': [None, 150]}, 'bar': {'color': icr_color}, 
                 'threshold': {'line': {'color': "black", 'width': 3}, 'value': loss_ratio}}
    ))
    fig_gauge.update_layout(**{**_cfg(), 'margin': dict(t=30, b=10)})

    if 'carrier_name' in df.columns and claim_col and premium_col:
        g = df.groupby('carrier_name')[[premium_col, claim_col]].sum().reset_index()
        fig_vs = px.bar(g, x='carrier_name', y=[premium_col, claim_col], barmode='group', title="Premium vs Claims",
                        color_discrete_map={premium_col: TVS_BLUE, claim_col: TVS_ORANGE})
        fig_vs.for_each_trace(lambda t: t.update(name="Premium" if t.name == premium_col else "Claims"))
        _ax(fig_vs, tickangle=-35)
        g['ICR_%'] = np.where(g[premium_col] > 0, (g[claim_col] / g[premium_col]) * 100, 0)
        g_icr = g.sort_values('ICR_%', ascending=False)
        fig_icr = px.bar(g_icr, x='carrier_name', y='ICR_%', title="ICR by Carrier", color='ICR_%', color_continuous_scale=px.colors.sequential.OrRd, range_color=[0, g_icr['ICR_%'].max()])
        _ax(fig_icr.update_layout(**_cfg()), tickangle=-35)
    else:
        fig_vs = px.bar(); fig_icr = px.bar()

    return tab_layout(
        kpi_row(
            kpi_card("High-Risk Carrier", f"{high_risk_carrier} ({high_risk_icr:.1f}%)", "Carrier with highest ICR", icr_color, accent=icr_color),
            kpi_card("Avg Risk Exposure", format_currency(avg_exposure),  "Avg claims per policy",      RED),
            kpi_card("Pending Claims Value", format_currency(pending_claims_val), "Unresolved claims exposure",      GREEN),
        ),
        hrow(
            chart_box(fig_gauge, "icr-gauge", flex="1"),
            chart_box(fig_icr, "icr-chart", flex="1"),
        ),
    )

# ─────────────────────────────────────────────
# TAB 4b — High Risk Register
# ─────────────────────────────────────────────
def tab4b(df):
    if df.empty: return html.Div("No Data")
    claim_col   = 'claim_amount'   if 'claim_amount'   in df.columns else None
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None

    high_risk = html.Div("No risk scoring data.")
    risk_count = 0
    if 'client_name' in df.columns and premium_col and claim_col:
        risk_df = df.groupby('client_name').agg(
            Premium=(premium_col, 'sum'), Claims=(claim_col, 'sum'),
            Policies=('policy_number', 'count') if 'policy_number' in df.columns else (premium_col, 'count')
        ).reset_index()
        risk_df['Loss_Ratio_%'] = np.where(
            risk_df['Premium'] > 0,
            (risk_df['Claims'] / risk_df['Premium'] * 100).round(1),
            0
        )
        hr = risk_df[risk_df['Loss_Ratio_%'] > 100].sort_values('Loss_Ratio_%', ascending=False)
        risk_count = len(hr)
        if not hr.empty:
            hr_disp = hr.copy()
            hr_disp['Premium'] = hr_disp['Premium'].apply(format_currency)
            hr_disp['Claims']  = hr_disp['Claims'].apply(format_currency)
            hr_cols = ['client_name', 'Policies', 'Premium', 'Claims', 'Loss_Ratio_%']
            high_risk = dash_table.DataTable(
                data=hr_disp[hr_cols].to_dict('records'),
                columns=[{"name": c.replace('_', ' ').title(), "id": c} for c in hr_cols],
                page_size=10, sort_action='native',
                style_table={'overflowX': 'auto', 'borderRadius': '8px', 'border': '1px solid #E5E7EB'},
                style_cell={
                    'padding': '6px 12px',
                    'fontFamily': 'Plus Jakarta Sans, sans-serif',
                    'fontSize': '11px',
                    'border': '1px solid #E5E7EB',
                    'height': 'auto'
                },
                style_header={
                    'backgroundColor': RED,
                    'color': 'white',
                    'fontWeight': 'bold',
                    'padding': '8px 12px',
                    'fontSize': '11px',
                    'height': 'auto'
                },
                style_cell_conditional=[
                    {'if': {'column_id': 'client_name'}, 'textAlign': 'left'},
                    {'if': {'column_id': 'Policies'}, 'textAlign': 'right'},
                    {'if': {'column_id': 'Premium'}, 'textAlign': 'right'},
                    {'if': {'column_id': 'Claims'}, 'textAlign': 'right'},
                    {'if': {'column_id': 'Loss_Ratio_%'}, 'textAlign': 'right'},
                ],
                style_data_conditional=[
                    {'if': {'row_index': 'odd'}, 'backgroundColor': '#FEF2F2'},
                    {'if': {'filter_query': '{Loss_Ratio_%} > 200', 'column_id': 'Loss_Ratio_%'}, 'color': RED, 'fontWeight': 'bold'}
                ],
                export_format='csv',
            )

    return tab_layout(
        kpi_row(
            kpi_card("High Risk Clients", f"{risk_count}", "Loss Ratio > 100%", RED, accent=RED),
            kpi_card("Action", "Review", "Flag for underwriting", TVS_ORANGE),
        ),
        content_box([html.Div("High Risk Client Register", style={"color":TVS_BLUE,"fontSize":"12px","fontWeight":"800","marginBottom":"6px"}), high_risk], style={"height": "auto", "flexShrink": 0})
    )

# ─────────────────────────────────────────────
# TAB 5 — Product Mix
# ─────────────────────────────────────────────
def tab5(df):
    if df.empty: return html.Div("No Data")
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    claim_col   = 'claim_amount' if 'claim_amount' in df.columns else None
    comm_col    = 'commission_earned' if 'commission_earned' in df.columns else None

    # ── B2B vs B2C Revenue Breakdown ──
    if 'client_type' in df.columns and premium_col and claim_col and comm_col:
        seg = df.groupby('client_type').agg(
            Premium=(premium_col, 'sum'), Claims=(claim_col, 'sum'), Commission=(comm_col, 'sum')
        ).reset_index()
        seg_melted = seg.melt(id_vars='client_type', value_vars=['Premium', 'Claims', 'Commission'], var_name='Metric', value_name='Value')
        seg_melted['Label'] = seg_melted['Value'].apply(format_currency)
        fig_seg = px.bar(seg_melted, x='Metric', y='Value', color='client_type', barmode='group', title="B2B vs B2C Breakdown",
                         color_discrete_map={'Individual/B2C': TVS_BLUE, 'Corporate/B2B': TVS_ORANGE},
                         text='Label')
        fig_seg.update_traces(textposition='outside', cliponaxis=False)
        _ax(fig_seg.update_layout(**_cfg(), legend_title="Segment", yaxis=dict(title='Value (₹)')))
    else: fig_seg = px.bar(title="Segment Data N/A")

    # Policy duration removed by request

    n_cats     = df['category'].nunique()     if 'category'      in df.columns else 0
    n_sub_cat5 = df['sub_category'].nunique() if 'sub_category'   in df.columns else 0
    prem5      = df[premium_col].sum()        if premium_col else 0
    b2b_pct    = 0
    if 'client_type' in df.columns and premium_col:
        b2b = df[df['client_type'].str.contains('B2B|Corporate', case=False, na=False)][premium_col].sum()
        b2b_pct = (b2b / prem5 * 100) if prem5 > 0 else 0
    avg_prem = (prem5 / len(df)) if len(df) > 0 else 0
    return tab_layout(
        kpi_row(
            kpi_card("Categories",     str(n_cats),                 "Product categories",        TVS_ORANGE, accent=TVS_ORANGE),
            kpi_card("Sub-Categories", str(n_sub_cat5),             "Sub-product lines",         PURPLE,     accent=PURPLE),
            kpi_card("Avg Policy Premium", format_currency(avg_prem), "Avg premium per policy",    GREEN,      accent=GREEN),
            kpi_card("B2B Share",      f"{b2b_pct:.1f}%",          "Corporate premium mix",      TVS_BLUE,   accent=TVS_BLUE),
        ),
        hrow(chart_box(fig_seg, "seg-chart"))
    )

# ─────────────────────────────────────────────
# TAB 5b — Carrier Scorecard
# ─────────────────────────────────────────────
def tab5b(df):
    if df.empty: return html.Div("No Data")
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    claim_col   = 'claim_amount' if 'claim_amount' in df.columns else None
    comm_col    = 'commission_earned' if 'commission_earned' in df.columns else None

    carrier_section = html.Div("Carrier data unavailable.")
    if 'carrier_name' in df.columns and premium_col and claim_col and comm_col:
        cs = df.groupby('carrier_name').agg(
            Policies=('policy_number', 'count') if 'policy_number' in df.columns else (premium_col, 'count'),
            Written_Premium=(premium_col, 'sum'), Claims_Paid=(claim_col, 'sum'), Commission=(comm_col, 'sum'),
        ).reset_index()
        cs['Loss_Ratio_%'] = np.where(
            cs['Written_Premium'] > 0,
            (cs['Claims_Paid'] / cs['Written_Premium'] * 100).round(1),
            0
        )
        cs['Margin_%'] = np.where(
            cs['Written_Premium'] > 0,
            (cs['Commission'] / cs['Written_Premium'] * 100).round(1),
            0
        )
        cs = cs.sort_values('Written_Premium', ascending=False)
        disp = cs.copy()
        disp['Written_Premium'] = disp['Written_Premium'].apply(format_currency)
        disp['Claims_Paid']     = disp['Claims_Paid'].apply(format_currency)
        disp['Commission']      = disp['Commission'].apply(format_currency)
        cols_order = ['carrier_name', 'Policies', 'Written_Premium', 'Claims_Paid', 'Loss_Ratio_%', 'Margin_%']
        carrier_section = dash_table.DataTable(
            data=disp[cols_order].to_dict('records'),
            columns=[
                {"name": "Carrier", "id": "carrier_name"},
                {"name": "Policies", "id": "Policies"},
                {"name": "Premium", "id": "Written_Premium"},
                {"name": "Claims", "id": "Claims_Paid"},
                {"name": "Loss Ratio %", "id": "Loss_Ratio_%"},
                {"name": "Margin %", "id": "Margin_%"},
            ],
            sort_action='native',
            style_table={'overflowX': 'auto', 'border': '1px solid #E5E7EB'},
            style_cell={
                'padding': '6px 12px',
                'fontFamily': 'Plus Jakarta Sans, sans-serif',
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
                {'if': {'column_id': 'carrier_name'}, 'textAlign': 'left', 'fontWeight': '700'},
                {'if': {'column_id': 'Policies'}, 'textAlign': 'right'},
                {'if': {'column_id': 'Written_Premium'}, 'textAlign': 'right'},
                {'if': {'column_id': 'Claims_Paid'}, 'textAlign': 'right'},
                {'if': {'column_id': 'Loss_Ratio_%'}, 'textAlign': 'right'},
                {'if': {'column_id': 'Margin_%'}, 'textAlign': 'right'},
            ],
            style_data_conditional=[
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#F0F4FF'},
                {'if': {'filter_query': '{Loss_Ratio_%} > 65', 'column_id': 'Loss_Ratio_%'}, 'color': RED, 'fontWeight': 'bold'},
                {'if': {'filter_query': '{Loss_Ratio_%} <= 65', 'column_id': 'Loss_Ratio_%'}, 'color': GREEN, 'fontWeight': 'bold'},
            ],
            export_format='csv',
        )

    req_cols = ['carrier_name', 'category', 'sub_category']
    if all(c in df.columns for c in req_cols) and premium_col:
        sun_df = df.groupby(req_cols)[premium_col].sum().reset_index()
        sun_df = sun_df[sun_df[premium_col] > 0]
        sun_df['formatted_premium'] = sun_df[premium_col].apply(format_currency)
        order = sun_df.groupby('carrier_name')[premium_col].sum().sort_values().index
        fig_motor = px.bar(sun_df, y='carrier_name', x=premium_col, color='category', orientation='h',
                           title="Carrier Portfolio Breakdown", color_discrete_sequence=px.colors.qualitative.Pastel,
                           custom_data=['sub_category', 'category', 'formatted_premium'])
        fig_motor.update_traces(
            hovertemplate="<b>%{y}</b><br>Category: %{customdata[1]}<br>Sub-Category: %{customdata[0]}<br>Premium: %{customdata[2]}<extra></extra>"
        )
        fig_motor.update_layout(**{**_cfg(), 'margin': dict(t=30, l=120, r=20)}, barmode='stack')
        fig_motor.update_yaxes(categoryorder='array', categoryarray=order, title=None, automargin=False)
        fig_motor.update_xaxes(title="Premium (₹)")
    else: fig_motor = px.bar(title="Breakdown N/A")

    n_carriers  = df['carrier_name'].nunique() if 'carrier_name' in df.columns else 0
    try:
        top_carrier = df.groupby('carrier_name')[premium_col].sum().idxmax() if ('carrier_name' in df.columns and premium_col) else "N/A"
    except (ValueError, TypeError, KeyError):
        top_carrier = "N/A"
    total_carr_prem = df[premium_col].sum() if premium_col else 0
    high_icr_count  = 0
    if 'carrier_name' in df.columns and premium_col and claim_col:
        cs_check = df.groupby('carrier_name').agg(P=(premium_col,'sum'), C=(claim_col,'sum')).reset_index()
        cs_check['icr'] = cs_check['C'] / cs_check['P'].replace(0, float('nan')) * 100
        high_icr_count = int((cs_check['icr'] > 65).sum())
    carrier_concentration = 0.0
    if 'carrier_name' in df.columns and premium_col and total_carr_prem > 0:
        try:
            top_carrier_prem = df.groupby('carrier_name')[premium_col].sum().max()
            carrier_concentration = (top_carrier_prem / total_carr_prem * 100)
        except Exception:
            pass
    return tab_layout(
        kpi_row(
            kpi_card("Active Carriers",   str(n_carriers),              "In portfolio",          TVS_BLUE,   accent=TVS_BLUE),
            kpi_card("Top Carrier",        top_carrier,                  "By written premium",    PURPLE,     accent=PURPLE),
            kpi_card("Carrier Concentration", f"{carrier_concentration:.1f}%", "Top carrier share", GREEN,      accent=GREEN),
            kpi_card("High ICR Carriers",  str(high_icr_count),          "ICR > 65% — review",   RED,        accent=RED),
        ),
        hrow(content_box([
                html.Div("Carrier Scorecard", style={"fontSize": "12px", "fontWeight": "800",
                                                      "color": TVS_BLUE, "marginBottom": "6px"}),
                carrier_section,
              ], flex="1"),
             chart_box(fig_motor, "motor-chart", flex="1"))
    )

# ─────────────────────────────────────────────
# TAB 6 — Client Mix
# ─────────────────────────────────────────────
def tab6(df):
    if df.empty: return html.Div("No Data")
    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None

    if 'sub_category' in df.columns and 'category' in df.columns and premium_col:
        g = df.groupby(['category', 'sub_category'])[premium_col].sum().reset_index().sort_values(premium_col, ascending=False)
        g['Label'] = g[premium_col].apply(format_currency)
        fig_sub = px.bar(g, x='sub_category', y=premium_col, color='category', title="Premium by Sub-Category", text='Label')
        fig_sub.update_traces(textposition='outside', cliponaxis=False)
        _ax(fig_sub.update_layout(**_cfg()), tickangle=-40)
    else: fig_sub = px.bar(title="Subcategory Data N/A")

    if 'client_name' in df.columns and premium_col:
        top_clients = df.groupby('client_name')[premium_col].sum().nlargest(15).reset_index().sort_values(premium_col)
        fig_top = px.bar(top_clients, y='client_name', x=premium_col, orientation='h', title="Top 15 Clients by Premium",
                         text=top_clients[premium_col].apply(format_currency))
        fig_top.update_traces(marker_color=TVS_BLUE, textposition='outside', cliponaxis=False)
        _ax(fig_top.update_layout(**{**_cfg(), 'margin': dict(t=30, l=150, r=40)}, xaxis_title="Premium (₹)", yaxis_title=""))
        fig_top.update_yaxes(automargin=False) # Fix for long names
    else: fig_top = px.bar(title="Top Clients N/A")

    n_clients  = df['client_name'].nunique()   if 'client_name'  in df.columns else 0
    try:
        top_client = df.groupby('client_name')[premium_col].sum().idxmax() if ('client_name' in df.columns and premium_col) else "N/A"
    except (ValueError, TypeError, KeyError):
        top_client = "N/A"
    n_sub_cats = df['sub_category'].nunique() if 'sub_category' in df.columns else 0
    total_cli_prem = df[premium_col].sum() if premium_col else 0
    avg_client_prem = (total_cli_prem / n_clients) if n_clients > 0 else 0
    client_concentration = 0.0
    if 'client_name' in df.columns and premium_col and total_cli_prem > 0:
        try:
            top_client_prem = df.groupby('client_name')[premium_col].sum().max()
            client_concentration = (top_client_prem / total_cli_prem * 100)
        except Exception:
            pass
    return tab_layout(
        kpi_row(
            kpi_card("Total Clients",   str(n_clients),                "Unique accounts",        TVS_BLUE,   accent=TVS_BLUE),
            kpi_card("Top Client",      top_client,                    "By premium volume",      PURPLE,     accent=PURPLE),
            kpi_card("Avg Client Premium", format_currency(avg_client_prem), "Avg premium per account", GREEN,      accent=GREEN),
            kpi_card("Client Concentration", f"{client_concentration:.1f}%", "Top client share",     TVS_ORANGE, accent=TVS_ORANGE),
        ),
        hrow(chart_box(fig_sub, "sub-cat", flex="1"), chart_box(fig_top, "top-client-chart", flex="1"))
    )

# ─────────────────────────────────────────────
# TAB 6b — Channel Mix
# ─────────────────────────────────────────────
def build_tab6b_content(df_filtered, selected_channel="all", df_all=None):
    if df_filtered.empty: return html.Div("No Data matching filter")
    premium_col = 'premium_amount' if 'premium_amount' in df_filtered.columns else None

    if df_all is None:
        df_all = df_filtered

    n_channels = df_filtered['distribution_channel'].nunique() if 'distribution_channel' in df_filtered.columns else 0
    total_chan_prem = df_filtered[premium_col].sum() if premium_col else 0
    total_channel_policies = len(df_filtered)
    avg_chan_policy_premium = (total_chan_prem / total_channel_policies) if total_channel_policies > 0 else 0

    # ── LEFT: Sunburst — Channel → Category → Sub-Category ──────────
    channel_palette = [TVS_BLUE, TVS_ORANGE, GREEN, PURPLE, AMBER, RED, "#3B82F6", "#EC4899"]
    category_palette = ["#93C5FD", "#FCA5A5", "#6EE7B7", "#C4B5FD", "#FDE68A", "#A5F3FC", "#FBCFE8", "#D9F99D"]

    if 'distribution_channel' in df_filtered.columns and 'category' in df_filtered.columns and 'sub_category' in df_filtered.columns and premium_col:
        sun_df = df_filtered[df_filtered[premium_col] > 0].groupby(
            ['distribution_channel', 'category', 'sub_category']
        )[premium_col].sum().reset_index()

        ids, labels, parents, values, colors_list = [], [], [], [], []
        ids.append("Total"); labels.append("All Channels"); parents.append(""); values.append(sun_df[premium_col].sum()); colors_list.append(TVS_BLUE)

        for ci, ch in enumerate(sun_df['distribution_channel'].unique()):
            ch_df = sun_df[sun_df['distribution_channel'] == ch]
            ch_id = f"ch_{ch}"
            ids.append(ch_id); labels.append(str(ch)); parents.append("Total"); values.append(ch_df[premium_col].sum()); colors_list.append(channel_palette[ci % len(channel_palette)])
            for cati, cat in enumerate(ch_df['category'].unique()):
                cat_df = ch_df[ch_df['category'] == cat]
                cat_id = f"cat_{ch}_{cat}"
                ids.append(cat_id); labels.append(str(cat)); parents.append(ch_id); values.append(cat_df[premium_col].sum()); colors_list.append(category_palette[cati % len(category_palette)])
                for _, row in cat_df.iterrows():
                    sub_id = f"sub_{ch}_{cat}_{row['sub_category']}"
                    ids.append(sub_id); labels.append(str(row['sub_category'])); parents.append(cat_id); values.append(row[premium_col]); colors_list.append(category_palette[cati % len(category_palette)])

        fig_sun = go.Figure(go.Sunburst(
            ids=ids, labels=labels, parents=parents, values=values,
            marker=dict(colors=colors_list, line=dict(color="white", width=1.5)),
            hovertemplate="<b>%{label}</b><br>Premium: ₹%{value:,.0f}<extra></extra>",
            textfont=dict(family="Plus Jakarta Sans, Inter, sans-serif", size=10),
            branchvalues="total", maxdepth=3,
        ))
        _sun_cfg = {**_cfg(), "margin": dict(t=10, b=10, l=10, r=10)}
        fig_sun.update_layout(**_sun_cfg)

        top_value = sun_df.groupby('distribution_channel')[premium_col].sum().idxmax() if not sun_df.empty else "N/A"
        if selected_channel != "all":
            top_value = selected_channel
        kpi_title_3 = "Top Channel"
    else:
        fig_sun = go.Figure()
        kpi_title_3 = "Top Channel"
        top_value = "N/A"

    # ── RIGHT: Stacked horizontal bar — Category mix per Channel ────
    if 'distribution_channel' in df_filtered.columns and 'category' in df_filtered.columns and premium_col:
        stack_df = df_filtered[df_filtered[premium_col] > 0].groupby(
            ['distribution_channel', 'category']
        )[premium_col].sum().reset_index()

        categories = sorted(stack_df['category'].unique())
        channels_sorted = stack_df.groupby('distribution_channel')[premium_col].sum().sort_values(ascending=True).index.tolist()

        fig_bar = go.Figure()
        for i, cat in enumerate(categories):
            cat_data = stack_df[stack_df['category'] == cat]
            x_vals = [cat_data[cat_data['distribution_channel'] == ch][premium_col].sum() if not cat_data[cat_data['distribution_channel'] == ch].empty else 0 for ch in channels_sorted]
            fig_bar.add_trace(go.Bar(
                name=cat, x=x_vals, y=channels_sorted, orientation='h',
                marker_color=channel_palette[i % len(channel_palette)],
                hovertemplate=f"<b>{cat}</b><br>Channel: %{{y}}<br>Premium: ₹%{{x:,.0f}}<extra></extra>",
                text=[f"₹{v/100000:.1f}L" if v > 0 else "" for v in x_vals],
                textposition="inside", insidetextanchor="middle",
                textfont=dict(size=9, color="white"),
            ))

        _bar_cfg = {
            **_cfg(),
            "barmode": "stack",
            "legend": dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                           font=dict(size=9, family="Plus Jakarta Sans, Inter, sans-serif")),
            "xaxis": dict(title="Premium (₹)", tickformat=",", gridcolor="#F3F4F6", 
                          title_font=dict(size=10, color="#374151"), tickfont=dict(size=9.5, color="#374151")),
            "yaxis": dict(title="", tickfont=dict(size=10, color="#374151")),
            "margin": dict(t=40, b=10, l=10, r=10),
        }
        fig_bar.update_layout(**_bar_cfg)
    else:
        fig_bar = go.Figure()

    kpi_card_1_val = str(n_channels) if selected_channel == "all" else selected_channel
    kpi_card_1_title = "Channels" if selected_channel == "all" else "Selected Channel"
    kpi_card_1_sub = "Distribution channels" if selected_channel == "all" else "Filter applied"

    return tab_layout(
        kpi_row(
            kpi_card(kpi_card_1_title, kpi_card_1_val, kpi_card_1_sub, theme="tvs-blue"),
            kpi_card("Avg Premium/Policy", format_currency(avg_chan_policy_premium), "Avg premium per policy", theme="tvs-orange"),
            kpi_card(kpi_title_3, top_value, "By written premium", theme="tvs-blue"),
        ),
        html.Div([
            html.Div([
                html.Div("Channel Hierarchy", className="chart-title"),
                html.P("Click any segment to drill into Channel → Category → Sub-Category",
                       style={"fontSize": "10px", "color": "#6B7280", "margin": "0 0 8px 0",
                              "fontFamily": "Plus Jakarta Sans, Inter, sans-serif"}),
                dcc.Graph(figure=fig_sun, config={"displayModeBar": False},
                          style={"height": "380px"}, id="channel-sunburst"),
            ], style={"flex": "1", "minWidth": "340px", "padding": "16px", "background": "white",
                      "borderRadius": "12px", "border": "1px solid #E5E7EB",
                      "boxShadow": "0 2px 8px rgba(0,0,0,0.06)"}),
            html.Div([
                html.Div("Premium Mix by Channel & Category", className="chart-title"),
                html.P("Each bar shows how premium is split across insurance categories per channel.",
                       style={"fontSize": "10px", "color": "#6B7280", "margin": "0 0 8px 0",
                              "fontFamily": "Plus Jakarta Sans, Inter, sans-serif"}),
                dcc.Graph(figure=fig_bar, config={"displayModeBar": False},
                          style={"height": "380px"}, id="channel-stacked-bar"),
            ], style={"flex": "1", "minWidth": "340px", "padding": "16px", "background": "white",
                      "borderRadius": "12px", "border": "1px solid #E5E7EB",
                      "boxShadow": "0 2px 8px rgba(0,0,0,0.06)"}),
        ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"})
    )

def tab6b(df):
    if df.empty: return html.Div("No Data")
    
    # Styled channel selector dropdown at the top
    channel_options = [{"label": "All Channels", "value": "all"}]
    if 'distribution_channel' in df.columns:
        channels = sorted(df['distribution_channel'].dropna().unique())
        for ch in channels:
            channel_options.append({"label": str(ch), "value": str(ch)})
            
    initial_content = build_tab6b_content(df, "all")
    
    return html.Div([
        dcc.Loading(
            html.Div(id="tab6b-content-container", children=initial_content),
            type="dot",
            color=TVS_ORANGE
        )
    ])


# ─────────────────────────────────────────────
# TAB 12 — Pivot Explorer
# ─────────────────────────────────────────────

def tab12(df):
    if df.empty: return html.Div("No Data")
    cols    = [c for c in df.columns if df[c].dtype == 'object' or df[c].nunique() < 20]
    metrics = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not cols or not metrics:
        return html.Div("Insufficient dimensions or metrics.", style={"padding": "20px"})

    def_row = 'carrier_name' if 'carrier_name' in cols else cols[0]
    def_col = 'category' if 'category' in cols and len(cols) > 1 else (cols[1] if len(cols) > 1 else cols[0])
    def_met = 'premium_amount' if 'premium_amount' in metrics else metrics[0]

    ctrls = html.Div([
        dbc.Row([
            dbc.Col([
                html.Label("Row Dimension", style={"fontSize": "10px", "fontWeight": "700",
                                                    "color": "#6B7280", "textTransform": "uppercase",
                                                    "letterSpacing": "0.5px", "marginBottom": "2px"}),
                dcc.Dropdown(id="pivot-row", options=[{"label": c, "value": c} for c in cols],
                             value=def_row, clearable=False),
            ], width=3),
            dbc.Col([
                html.Label("Column Dimension", style={"fontSize": "10px", "fontWeight": "700",
                                                       "color": "#6B7280", "textTransform": "uppercase",
                                                       "letterSpacing": "0.5px", "marginBottom": "2px"}),
                dcc.Dropdown(id="pivot-col", options=[{"label": c, "value": c} for c in cols],
                             value=def_col, clearable=False),
            ], width=3),
            dbc.Col([
                html.Label("Metric", style={"fontSize": "10px", "fontWeight": "700",
                                             "color": "#6B7280", "textTransform": "uppercase",
                                             "letterSpacing": "0.5px", "marginBottom": "2px"}),
                dcc.Dropdown(id="pivot-metric", options=[{"label": c, "value": c} for c in metrics],
                             value=def_met, clearable=False),
            ], width=3),
            dbc.Col([
                html.Label("Aggregation", style={"fontSize": "10px", "fontWeight": "700",
                                                  "color": "#6B7280", "textTransform": "uppercase",
                                                  "letterSpacing": "0.5px", "marginBottom": "2px"}),
                dcc.Dropdown(id="pivot-agg",
                             options=[{"label": "Sum", "value": "sum"},
                                      {"label": "Average", "value": "mean"},
                                      {"label": "Count", "value": "count"}],
                             value="sum", clearable=False),
            ], width=3),
        ], className="g-2"),
    ], className="pivot-controls")

    return html.Div([
        ctrls,
        html.Div(id="pivot-results-container", className="pivot-results"),
    ], className="pivot-shell")


# ─────────────────────────────────────────────
# TAB 7 & 8 — Profitability (to be split)
# ─────────────────────────────────────────────

def tab7(df):

    if df.empty: return html.Div("No Data")

    premium_col = 'premium_amount'    if 'premium_amount'    in df.columns else None
    claim_col   = 'claim_amount'      if 'claim_amount'      in df.columns else None
    comm_col    = 'commission_earned' if 'commission_earned' in df.columns else None

    # ── Carrier Underwriting Profit (Premium − Claims − Commission) ──
    if 'carrier_name' in df.columns and comm_col and claim_col and premium_col:
        nr = df.groupby('carrier_name').agg(
            Premium=(premium_col, 'sum'),
            Commission=(comm_col, 'sum'),
            Claims=(claim_col, 'sum'),
        ).reset_index()
        nr['Underwriting_Profit'] = nr['Premium'] - nr['Claims'] - nr['Commission']
        nr = nr.sort_values('Underwriting_Profit', ascending=True)
        colors_nr = [GREEN if v >= 0 else RED for v in nr['Underwriting_Profit']]
        fig_nr = px.bar(nr, y='carrier_name', x='Underwriting_Profit', orientation='h',
                        title="Carrier Underwriting Profit (Prem − Claims − Comm)",
                        text=nr['Underwriting_Profit'].apply(format_currency))
        fig_nr.update_traces(marker_color=colors_nr, textposition='outside', cliponaxis=False,
                             hovertemplate="<b>%{y}</b><br>Profit: ₹%{x:,.0f}<extra></extra>")
        fig_nr.update_layout(**_cfg(), xaxis_title="Underwriting Profit (₹)")
        fig_nr.update_layout(margin=dict(t=48, r=100))
        _ax(fig_nr)
    else:
        fig_nr = px.bar(title="Profit Data N/A")

    # ── Total Commission by Carrier ──
    if 'carrier_name' in df.columns and comm_col:
        comm_df = df.groupby('carrier_name')[comm_col].sum().reset_index().sort_values(comm_col, ascending=False)
        fig_comm = px.bar(comm_df, x='carrier_name', y=comm_col,
                          title="Total Commission Earned by Carrier",
                          text=comm_df[comm_col].apply(format_currency))
        fig_comm.update_traces(textposition='outside', cliponaxis=False,
                               hovertemplate="<b>%{x}</b><br>Commission: ₹%{y:,.0f}<extra></extra>")
        fig_comm.update_layout(**_cfg())
        fig_comm.update_layout(margin=dict(t=60, r=30))
        _ax(fig_comm, tickangle=-35)
    else:
        fig_comm = px.bar(title="Commission Data N/A")

    # ── Commission Margin % Trend Over Time ──
    if 'issue_date' in df.columns and premium_col and comm_col:
        df2 = df.copy()
        df2['issue_month'] = pd.to_datetime(df2['issue_date']).dt.to_period('M').astype(str)  # type: ignore
        trend = df2.groupby('issue_month').agg(
            Premium=(premium_col, 'sum'),
            Commission=(comm_col, 'sum')
        ).reset_index()
        trend['Margin_%'] = np.where(
            trend['Premium'] > 0,
            (trend['Commission'] / trend['Premium'] * 100).round(2),
            np.nan
        )
        trend = trend.sort_values('issue_month')
        all_months_t = sorted(trend['issue_month'].unique())
        tick_vals_t  = [m for i, m in enumerate(all_months_t) if i % 3 == 0]
        fig_trend = px.line(trend, x='issue_month', y='Margin_%',
                            title="Commission Margin % Trend (Monthly)",
                            markers=True)
        fig_trend.update_traces(line_color=TVS_ORANGE, line_width=3, marker_size=7,
                                hovertemplate="<b>%{x}</b><br>Margin: %{y:.2f}%<extra></extra>")
        avg_margin = trend['Margin_%'].mean()
        fig_trend.add_hline(y=avg_margin, line_dash="dot", line_color="#9CA3AF",
                            annotation_text=f"Avg {avg_margin:.1f}%",
                            annotation_position="bottom right",
                            annotation_font=dict(color="#6B7280", size=11))
        _ax(fig_trend.update_layout(
            **_cfg(), yaxis_title="Margin (%)",
            xaxis=dict(tickvals=tick_vals_t, tickangle=-35,
                       tickfont=dict(size=11, color="#374151"))
        ))
    else:
        fig_trend = px.line(title="Margin Trend N/A")

    total_comm7  = df[comm_col].sum()    if comm_col    else 0
    total_claim7 = df[claim_col].sum()   if claim_col   else 0
    total_prem7  = df[premium_col].sum() if premium_col else 0
    carrier_profit = total_prem7 - total_claim7 - total_comm7
    comm_margin  = (total_comm7 / total_prem7 * 100) if total_prem7 > 0 else 0
    avg_comm_per_policy = (total_comm7 / len(df)) if len(df) > 0 else 0
    return tab_layout(
        kpi_row(
            kpi_card("Avg Comm/Policy", format_currency(avg_comm_per_policy), "Avg commission / policy",
                     GREEN, accent=GREEN, theme="tvs-blue"),
            kpi_card("Carrier Profit",   format_currency(carrier_profit), "Prem − Claims − Comm",
                     GREEN if carrier_profit >= 0 else RED,
                     accent=GREEN if carrier_profit >= 0 else RED),
            kpi_card("Comm Margin",      f"{comm_margin:.1f}%", "Of written premium",
                     TVS_ORANGE, accent=TVS_ORANGE, theme="tvs-orange"),
        ),
        hrow(
            chart_box(fig_trend, "margin-trend-chart7", flex="2"),
        ),
        hrow(
            chart_box(fig_nr,   "nr-chart",  flex="1"),
            chart_box(fig_comm, "comm-chart7", flex="1"),
        ),
    )

# ─────────────────────────────────────────────
# TAB 8 — Margin Analysis
# ─────────────────────────────────────────────
def tab8(df):

    if df.empty: return html.Div("No Data")

    premium_col = 'premium_amount'    if 'premium_amount'    in df.columns else None
    claim_col   = 'claim_amount'      if 'claim_amount'      in df.columns else None
    comm_col    = 'commission_earned' if 'commission_earned' in df.columns else None

    # Compute trend summary for metrics calculations
    trend = None
    if 'issue_date' in df.columns and premium_col and comm_col:
        df2 = df.copy()
        df2['issue_month'] = pd.to_datetime(df2['issue_date']).dt.to_period('M').astype(str)  # type: ignore
        trend = df2.groupby('issue_month').agg(
            Premium=(premium_col, 'sum'),
            Commission=(comm_col, 'sum')
        ).reset_index()
        trend['Margin_%'] = np.where(
            trend['Premium'] > 0,
            (trend['Commission'] / trend['Premium'] * 100).round(2),
            np.nan
        )

    # ── Margin % by Category ──
    if 'category' in df.columns and premium_col and comm_col:
        mg = df.groupby('category')[[premium_col, comm_col]].sum().reset_index()
        mg['margin_pct'] = np.where(
            mg[premium_col] > 0,
            (mg[comm_col] / mg[premium_col] * 100).round(1),
            0
        )
        mg['MarginLabel'] = mg['margin_pct'].apply(lambda x: f"{x:.1f}%")
        fig_margin = px.bar(mg, x='category', y='margin_pct',
                            title="Average Margin % by Product Category", text='MarginLabel')
        fig_margin.update_traces(marker_color=TVS_ORANGE, textposition='outside', cliponaxis=False)
        _ax(fig_margin.update_layout(**_cfg(), yaxis_title="Margin (%)"))
    else:
        fig_margin = px.bar(title="Margin Data N/A")

    # ── Commissions by Client Type Bar ──
    if 'client_type' in df.columns and comm_col:
        ct = df.groupby('client_type')[comm_col].sum().reset_index()
        ct['Label'] = ct[comm_col].apply(format_currency)
        fig_client = px.bar(ct, y='client_type', x=comm_col, orientation='h',
                            title="Commissions by Client Type",
                            color='client_type', color_discrete_sequence=px.colors.qualitative.Pastel,
                            text='Label')
        fig_client.update_traces(showlegend=False, textposition='outside', cliponaxis=False,
                                 hovertemplate="<b>%{y}</b><br>₹%{x:,.0f}<extra></extra>")
        fig_client.update_layout(**_cfg())
        fig_client.update_layout(margin=dict(t=60, r=120))
        fig_client.update_yaxes(categoryorder='total ascending', title=None, automargin=True)
        fig_client.update_xaxes(title="Total Commissions (₹)", automargin=True)
    else:
        fig_client = px.bar(title="N/A")


    # Safely compute avg margin — trend variable only exists if dates + cols are available
    if trend is not None:
        avg_margin8 = trend['Margin_%'].mean()
    else:
        avg_margin8 = 0
    comm_total8  = df[comm_col].sum()    if comm_col    else 0
    prem_total8  = df[premium_col].sum() if premium_col else 0
    comm_margin8 = (comm_total8 / prem_total8 * 100) if prem_total8 > 0 else 0
    
    b2b_margin = 0.0
    if 'client_type' in df.columns and premium_col and comm_col:
        b2b_df = df[df['client_type'].str.contains('B2B|Corporate', case=False, na=False)]
        b2b_prem = b2b_df[premium_col].sum()
        b2b_comm = b2b_df[comm_col].sum()
        b2b_margin = (b2b_comm / b2b_prem * 100) if b2b_prem > 0 else 0

    top_margin_cat = "N/A"
    top_margin_val = 0.0
    if 'category' in df.columns and premium_col and comm_col:
        try:
            cg8 = df.groupby('category').agg(P=(premium_col, 'sum'), C=(comm_col, 'sum')).reset_index()
            cg8['margin'] = np.where(cg8['P'] > 0, cg8['C'] / cg8['P'] * 100, 0)
            if not cg8.empty:
                max_row = cg8.loc[cg8['margin'].idxmax()]
                top_margin_cat = max_row['category']
                top_margin_val = max_row['margin']
        except Exception:
            pass

    return tab_layout(
        kpi_row(
            kpi_card("Avg Margin Trend", f"{avg_margin8:.1f}%",        "Monthly avg margin",     TVS_ORANGE, accent=TVS_ORANGE, theme="tvs-orange"),
            kpi_card("Corporate Margin", f"{b2b_margin:.1f}%",         "Corporate/B2B margin",   GREEN,      accent=GREEN),
            kpi_card("Top Margin Category", f"{top_margin_cat} ({top_margin_val:.1f}%)", "LOB with highest avg margin", TVS_BLUE, theme="tvs-blue"),
        ),
        hrow(
            chart_box(fig_margin, "margin-cat-chart", flex="1"),
            chart_box(fig_client, "client-type-chart8", flex="1"),
        ),
    )


# ─────────────────────────────────────────────
# TAB 9 — Portfolio Renewals
# ─────────────────────────────────────────────

def tab9(df):
    if df.empty: return html.Div("No Data")

    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    now = pd.Timestamp.today().normalize()

    df2 = df.copy()
    if 'expiry_date' in df2.columns:
        df2['expiry_date'] = pd.to_datetime(df2['expiry_date'], errors='coerce')

    fig_heat = px.bar(title="Renewal Data N/A")
    if 'expiry_date' in df2.columns and premium_col:
        future = df2[df2['expiry_date'] >= now].copy()
        future['exp_month_period'] = future['expiry_date'].dt.to_period('M')  # type: ignore
        exp_monthly = future.groupby('exp_month_period').agg(
            Policies=('policy_number', 'count') if 'policy_number' in future.columns else (premium_col, 'count'),
            At_Risk_Premium=(premium_col, 'sum')
        ).reset_index()
        exp_monthly = exp_monthly.sort_values('exp_month_period').head(18)
        exp_monthly['exp_month'] = exp_monthly['exp_month_period'].astype(str)
        exp_monthly = exp_monthly.drop(columns=['exp_month_period'])

        fig_heat = px.bar(exp_monthly, x='exp_month', y='Policies',
                          title="Renewal Calendar — Policies Expiring by Month (Next 18 Months)",
                          text='Policies',
                          color='At_Risk_Premium',
                          color_continuous_scale=['#DBEAFE', TVS_BLUE],
                          labels={'At_Risk_Premium': 'Premium at Risk (₹)'})
        _ax(fig_heat.update_layout(**_cfg(), xaxis_title="Expiry Month", yaxis_title="Policy Count"))

    if 'expiry_date' in df2.columns and premium_col:
        df2['days_to_expiry'] = (df2['expiry_date'] - now).dt.days  # type: ignore
        b0_30   = df2[(df2['days_to_expiry'] >= 0) & (df2['days_to_expiry'] <= 30)]
        b31_60  = df2[(df2['days_to_expiry'] > 30) & (df2['days_to_expiry'] <= 60)]
        b61_90  = df2[(df2['days_to_expiry'] > 60) & (df2['days_to_expiry'] <= 90)]
        b91_180 = df2[(df2['days_to_expiry'] > 90) & (df2['days_to_expiry'] <= 180)]
        kpis = kpi_row(
            kpi_card("0–30 Days",   format_currency(b0_30[premium_col].sum()),   f"{len(b0_30)} policies — CRITICAL",   RED,    accent=RED),
            kpi_card("31–60 Days",  format_currency(b31_60[premium_col].sum()),  f"{len(b31_60)} policies — URGENT",    AMBER,  accent=AMBER),
            kpi_card("61–90 Days",  format_currency(b61_90[premium_col].sum()),  f"{len(b61_90)} policies — PLAN",      PURPLE, accent=PURPLE),
            kpi_card("91–180 Days", format_currency(b91_180[premium_col].sum()), f"{len(b91_180)} policies — WATCH",    GREEN,  accent=GREEN),
        )
    else:
        kpis = kpi_row(kpi_card("Renewal Data", "N/A", "Expiry date not found", AMBER))

    return tab_layout(
        kpis,
        hrow(chart_box(fig_heat, "renewal-heatmap")),
    )


# ─────────────────────────────────────────────
# TAB 10 — Churn & Vintage
# ─────────────────────────────────────────────

def tab10(df):
    if df.empty: return html.Div("No Data")

    df2 = df.copy()
    if 'issue_date' in df2.columns:
        df2['issue_date'] = pd.to_datetime(df2['issue_date'], errors='coerce')

    fig_can = px.bar(title="Cancellation Data N/A")
    fig_can_cat = px.bar(title="Category Data N/A")
    if 'policy_status' in df2.columns and 'carrier_name' in df2.columns:
        total_by_carrier = df2.groupby('carrier_name').size().reset_index(name='total')
        cancel_by_carrier = df2[df2['policy_status'] == 'Cancelled'].groupby('carrier_name').size().reset_index(name='cancelled')
        cancel_rate = total_by_carrier.merge(cancel_by_carrier, on='carrier_name', how='left').fillna(0)
        cancel_rate['Cancel_Rate_%'] = (cancel_rate['cancelled'] / cancel_rate['total'] * 100).round(1)
        cancel_rate = cancel_rate.sort_values('Cancel_Rate_%', ascending=False)

        total_by_cat = df2.groupby('category').size().reset_index(name='total')
        cancel_by_cat = df2[df2['policy_status'] == 'Cancelled'].groupby('category').size().reset_index(name='cancelled')
        cancel_cat = total_by_cat.merge(cancel_by_cat, on='category', how='left').fillna(0)
        cancel_cat['Cancel_Rate_%'] = (cancel_cat['cancelled'] / cancel_cat['total'] * 100).round(1)

        fig_can = px.bar(cancel_rate, x='carrier_name', y='Cancel_Rate_%',
                         title="Cancellation Rate by Carrier (%)",
                         text='Cancel_Rate_%', color='Cancel_Rate_%',
                         color_continuous_scale=[GREEN, AMBER, RED])
        _ax(fig_can.update_layout(**_cfg(), yaxis_title="Cancel Rate (%)"), tickangle=-35)

        fig_can_cat = px.bar(cancel_cat, x='category', y='Cancel_Rate_%',
                             title="Cancellation Rate by Product Category (%)",
                             text='Cancel_Rate_%', color='Cancel_Rate_%',
                             color_continuous_scale=[GREEN, AMBER, RED])
        _ax(fig_can_cat.update_layout(**_cfg(), yaxis_title="Cancel Rate (%)"), tickangle=-35)

    fig_vintage = px.bar(title="Vintage Data N/A")
    if 'issue_date' in df2.columns and 'policy_status' in df2.columns:
        df2['issue_quarter'] = df2['issue_date'].dt.to_period('Q').astype(str)  # type: ignore
        cohort = df2.groupby(['issue_quarter', 'policy_status']).size().reset_index(name='count')
        fig_vintage = px.bar(cohort, x='issue_quarter', y='count', color='policy_status',
                             title="Policy Vintage Cohort — Outcome by Issue Quarter",
                             barmode='stack',
                             color_discrete_map={'Active': GREEN, 'Renewed': TVS_BLUE,
                                                 'Cancelled': RED, 'Expired': AMBER})
        _ax(fig_vintage.update_layout(**_cfg(), xaxis_title="Issue Quarter",
                                      yaxis_title="Policies", legend_title="Status"))

    cancelled_total = (df['policy_status'] == 'Cancelled').sum() if 'policy_status' in df.columns else 0
    expired_total  = (df['policy_status'] == 'Expired').sum() if 'policy_status' in df.columns else 0
    renewed_total  = (df['policy_status'] == 'Renewed').sum() if 'policy_status' in df.columns else 0
    denom = renewed_total + expired_total + cancelled_total
    
    cancelled_rate_val = (cancelled_total/denom*100) if denom > 0 else 0
    expired_rate_val = (expired_total/denom*100) if denom > 0 else 0
    renewed_rate_val = (renewed_total/denom*100) if denom > 0 else 0
    total_pols = len(df)

    return tab_layout(
        kpi_row(
            kpi_card("Cancelled",  str(cancelled_total), f"{cancelled_rate_val:.1f}% cancellation rate", RED,     accent=RED),
            kpi_card("Expired",    str(expired_total),   f"{expired_rate_val:.1f}% expiration rate",     AMBER,   accent=AMBER),
            kpi_card("Renewed",    str(renewed_total),   f"{renewed_rate_val:.1f}% retention rate",      GREEN,   accent=GREEN),
            kpi_card("Total",      str(total_pols),      "Policies in dataset",                          TVS_BLUE),
        ),
        hrow(
            chart_box(fig_can,     "cancel-carrier", flex="1.4"),
            chart_box(fig_can_cat, "cancel-cat",     flex="1"),
        ),
        hrow(chart_box(fig_vintage, "vintage-chart")),
    )


# TAB 11 — Regional Analytics
# ─────────────────────────────────────────────

def tab11(df):
    if df.empty: return html.Div("No Data")

    premium_col = 'premium_amount' if 'premium_amount' in df.columns else None
    claim_col = 'claim_amount' if 'claim_amount' in df.columns else None
    
    # ── Premium & Claims by Region ──
    if 'region' in df.columns and premium_col and claim_col:
        reg_df = df.groupby('region')[[premium_col, claim_col]].sum().reset_index()
        fig_reg = px.bar(reg_df, x='region', y=[premium_col, claim_col], barmode='group',
                         title="Total Premium & Claims by Region",
                         color_discrete_map={premium_col: TVS_BLUE, claim_col: TVS_ORANGE})
        fig_reg.for_each_trace(lambda t: t.update(
            text=[format_currency(v) for v in t.y],
            textposition='outside', cliponaxis=False
        ))
        fig_reg.update_traces(hovertemplate="<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>")
        fig_reg.update_layout(**_cfg(), legend_title="Metric")
        fig_reg.update_layout(margin=dict(t=60, r=30))
        fig_reg.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="center", x=0.5))
        _ax(fig_reg, tickangle=-25)
    else:
        fig_reg = px.bar(title="Regional Data N/A")
        
    # ── Region Distribution ──
    if 'region' in df.columns:
        reg_cnt = df['region'].value_counts().reset_index()
        reg_cnt.columns = ['region', 'count']
        reg_cnt = reg_cnt.sort_values('count', ascending=True)
        fig_dist = px.bar(reg_cnt, x='count', y='region', orientation='h',
                          title="Policy Distribution by Region",
                          color='region', color_discrete_sequence=PALETTE)
        fig_dist.update_traces(hovertemplate="<b>%{y}</b><br>Policies: %{x}<extra></extra>")
        fig_dist.update_layout(**_cfg(), showlegend=False)
        fig_dist.update_layout(margin=dict(t=60, b=20, l=20, r=20))
        fig_dist.update_yaxes(title="", showgrid=False)
        fig_dist.update_xaxes(title="Policies Count", showgrid=True, gridcolor="#E5E7EB")
    else:
        fig_dist = px.bar(title="Regional Data N/A")

    n_regions   = df['region'].nunique()         if 'region'      in df.columns else 0
    try:
        top_region  = df.groupby('region')[premium_col].sum().idxmax() if ('region' in df.columns and premium_col) else 'N/A'
    except (ValueError, TypeError, KeyError):
        top_region = "N/A"
    reg_prem    = df[premium_col].sum()          if premium_col else 0
    reg_claim   = df[claim_col].sum()            if claim_col   else 0
    avg_reg_prem = (reg_prem / n_regions) if n_regions > 0 else 0
    top_reg_lr = 0.0
    if 'region' in df.columns and premium_col and claim_col and top_region != "N/A":
        try:
            top_reg_df = df[df['region'] == top_region]
            top_reg_prem = top_reg_df[premium_col].sum()
            top_reg_claim = top_reg_df[claim_col].sum()
            top_reg_lr = (top_reg_claim / top_reg_prem * 100) if top_reg_prem > 0 else 0
        except Exception:
            pass
    return tab_layout(
        kpi_row(
            kpi_card("Regions",       str(n_regions),            "Distinct regions",     TVS_BLUE),
            kpi_card("Top Region",    top_region,                "By written premium",   TVS_ORANGE, accent=TVS_ORANGE),
            kpi_card("Avg Premium/Region", format_currency(avg_reg_prem), "Avg premium / active region", GREEN,      accent=GREEN),
            kpi_card("Top Region Loss Ratio", f"{top_reg_lr:.1f}%", f"Loss Ratio in {top_region}", RED,        accent=RED),
        ),
        hrow(
            chart_box(fig_reg, "region-bar-chart", flex="2"),
            chart_box(fig_dist, "region-dist-chart"),
        ),
    )


# ─────────────────────────────────────────────
# TAB 13 — Data Manager
# ─────────────────────────────────────────────
def tab13(df, filename=None, is_mapped=False, is_schema_valid=True, validation_errors=None, mapping_suggestions=None):
    if df.empty:
        return html.Div("No Data Available")

    # Step progress tracker
    # If custom data is active (filename is not None):
    #   - If is_mapped is True: Step 1 = Checked, Step 2 = Checked, Step 3 = Checked/Ingested
    #   - If is_mapped is False: Step 1 = Checked, Step 2 = Active Orange, Step 3 = Gray Pending
    # If Live DB:
    #   - Step 1 = Active, Step 2 = Gray, Step 3 = Gray
    step1_checked = filename is not None
    step2_checked = filename is not None and is_mapped
    step3_checked = False
    
    step_progress_bar = html.Div([
        html.Div([
            # Step 1: Select Source
            html.Div([
                html.Div("✓" if step1_checked else "1", style={
                    "width": "22px", "height": "22px", "borderRadius": "50%",
                    "background": GREEN if step1_checked else TVS_BLUE, "color": "white", "display": "flex",
                    "alignItems": "center", "justifyContent": "center", "fontWeight": "700",
                    "fontSize": "11px", "marginRight": "8px"
                }),
                html.Div([
                    html.Div("Step 1", style={"fontSize": "8px", "fontWeight": "700", "color": "#6B7280", "textTransform": "uppercase", "lineHeight": "1.1"}),
                    html.Div("Select Source", style={"fontSize": "10px", "fontWeight": "700", "color": TVS_BLUE, "lineHeight": "1.1"})
                ])
            ], style={"display": "flex", "alignItems": "center"}),
            
            html.Div(style={"width": "30px", "height": "2px", "background": GREEN if step2_checked or (filename and not is_mapped) else "#E5E7EB", "margin": "0 8px"}),
            
            # Step 2: Design & Preview
            html.Div([
                html.Div("✓" if step2_checked else "2", style={
                    "width": "22px", "height": "22px", "borderRadius": "50%",
                    "background": GREEN if step2_checked else (TVS_ORANGE if filename else "#E5E7EB"),
                    "color": "white" if (filename or step2_checked) else "#9CA3AF", "display": "flex",
                    "alignItems": "center", "justifyContent": "center", "fontWeight": "700",
                    "fontSize": "11px", "marginRight": "8px"
                }),
                html.Div([
                    html.Div("Step 2", style={"fontSize": "8px", "fontWeight": "700", "color": "#6B7280", "textTransform": "uppercase", "lineHeight": "1.1"}),
                    html.Div("Design & Preview", style={"fontSize": "10px", "fontWeight": "700", "color": TVS_BLUE if filename else "#9CA3AF", "lineHeight": "1.1"})
                ])
            ], style={"display": "flex", "alignItems": "center"}),
            
            html.Div(style={"width": "30px", "height": "2px", "background": GREEN if step3_checked else "#E5E7EB", "margin": "0 8px"}),
            
            # Step 3: Ingested
            html.Div([
                html.Div("3", style={
                    "width": "22px", "height": "22px", "borderRadius": "50%",
                    "background": GREEN if step3_checked else "#E5E7EB", "color": "white" if step3_checked else "#9CA3AF", "display": "flex",
                    "alignItems": "center", "justifyContent": "center", "fontWeight": "700",
                    "fontSize": "11px", "marginRight": "8px"
                }),
                html.Div([
                    html.Div("Step 3", style={"fontSize": "8px", "fontWeight": "700", "color": "#6B7280", "textTransform": "uppercase", "lineHeight": "1.1"}),
                    html.Div("Ingested", style={"fontSize": "10px", "fontWeight": "700", "color": TVS_BLUE if step3_checked else "#9CA3AF", "lineHeight": "1.1"})
                ])
            ], style={"display": "flex", "alignItems": "center"})
        ], style={"display": "flex", "alignItems": "center", "background": "white", "padding": "6px 14px", "borderRadius": "20px", "border": "1px solid #E5E7EB"})
    ], style={"display": "flex", "justifyContent": "flex-end", "flex": "1"})

    header_row = html.Div([
        html.Div([
            html.H3("Data Ingestion Wizard", style={
                "margin": 0, "fontSize": "16px", "fontWeight": "800", "color": TVS_BLUE, "letterSpacing": "-0.5px"
            }),
            html.P("Preview live database schema or map and upload custom Excel/CSV files.", style={
                "margin": "2px 0 0", "fontSize": "11px", "color": "#6B7280"
            })
        ], style={"display": "flex", "flexDirection": "column"}),
        step_progress_bar
    ], style={
        "display": "flex", "alignItems": "center", "justifyContent": "between",
        "background": "linear-gradient(135deg, #ffffff 0%, #f3f6ff 100%)",
        "padding": "10px 16px", "borderRadius": "12px",
        "marginBottom": "12px", "border": "1px solid #E5E7EB",
        "borderLeft": f"4px solid {TVS_ORANGE}",
        "boxShadow": "0 4px 20px rgba(27, 59, 139, 0.05)"
    })

    # Status Badge
    if filename:
        status_text = "Pending Verification (Staged)"
        status_color = TVS_ORANGE
    else:
        status_text = "Live Database Connected"
        status_color = GREEN

    status_badge = html.Span(
        status_text,
        style={
            "backgroundColor": "rgba(244,121,32,0.12)" if status_color == TVS_ORANGE else "rgba(16,185,129,0.12)",
            "color": status_color,
            "padding": "3px 10px", "borderRadius": "12px", "fontWeight": "700",
            "fontSize": "10px", "display": "inline-block", "marginBottom": "10px",
            "border": f"1px solid {status_color}"
        }
    )

    # Helper for meta-row
    def meta_row(label, val):
        return html.Div([
            html.Span(label, style={"color": "#6B7280", "fontSize": "11px"}),
            html.Span(val, style={"fontWeight": "700", "fontSize": "11px", "color": TVS_BLUE})
        ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "6px", "borderBottom": "1px dashed #E5E7EB", "paddingBottom": "4px"})

    # Ingestion Source Details Card
    meta_card = content_box([
        html.Div("Ingestion Source Details", style={"fontSize": "12px", "fontWeight": "800", "color": TVS_BLUE, "marginBottom": "10px"}),
        status_badge,
        meta_row("Active File:", filename if filename else "MySQL Database"),
        meta_row("Total Rows:", f"{len(df):,} records"),
        meta_row("Total Columns:", f"{df.shape[1]} fields"),
        meta_row("Data Integrity:", "100% Parsed" if len(df) > 0 else "N/A"),
        # Commit Ingest Button
        html.Button(
            "Commit Ingestion",
            id="btn-verify-commit",
            n_clicks=0,
            className="hdr-btn hdr-btn--green" if is_mapped else "hdr-btn hdr-btn--outline",
            style={
                "width": "100%", "marginTop": "12px", 
                "display": "block" if filename else "none",
                "fontSize": "11px", "padding": "8px 16px",
                "fontWeight": "bold"
            },
            disabled=not is_mapped
        ),
        # Local Loading spinner & status text
        dcc.Loading(
            id="loading-local-ingestion",
            type="circle",
            color="#FF6B00",
            children=html.Div(
                id="ingestion-status-local",
                style={"marginTop": "10px", "textAlign": "center", "fontSize": "11px", "color": "#1B3B8B", "fontWeight": "bold"}
            )
        )
    ], flex="1", style={"padding": "14px", "width": "100%", "boxShadow": "var(--shadow-sm)", "maxWidth": "350px"})

    # Upload Data Source Card
    upload_card = content_box([
        html.Div("Upload Data Source", style={"fontSize": "12px", "fontWeight": "800", "color": TVS_BLUE, "marginBottom": "8px"}),
        dcc.Upload(
            id='upload-data',   
            children=html.Div([
                html.A("Select CSV/Excel File", style={"color": TVS_BLUE, "textDecoration": "underline", "fontWeight": "700", "display": "block", "marginTop": "15px"})
            ]),
            style={
                "width": "100%", "height": "80px", "lineHeight": "20px", "borderWidth": "1.5px",
                "borderStyle": "dashed", "borderRadius": "8px", "borderColor": "rgba(27,59,139,0.25)",
                "textAlign": "center", "backgroundColor": "rgba(27,59,139,0.02)", "cursor": "pointer",
                "paddingTop": "10px", "color": "#4B5563", "fontSize": "11px", "transition": "all 0.2s ease"
            },
            multiple=False
        ),
    ], flex="1", style={"padding": "14px", "width": "100%", "boxShadow": "var(--shadow-sm)", "maxWidth": "350px"})

    # Header Verification Checklist Card (Hidden to support existing callbacks if needed)
    checklist_card = html.Div([
        dcc.Checklist(id='header-verify-checklist', value=[]),
        html.Span(id="checklist-counter-badge")
    ], style={"display": "none"})

    # Column mapping card (unused but kept for structure)
    mapping_card = html.Div()
    
    # Assemble top_panel
    top_panel = html.Div([upload_card, meta_card, checklist_card], style={"display": "flex", "flexDirection": "row", "gap": "16px", "width": "100%", "marginTop": "8px"})

    # Custom Column type inference helper
    def infer_column_type(c_name, s):
        c_lower = c_name.lower()
        if pd.api.types.is_numeric_dtype(s):
            return "Number"
        elif pd.api.types.is_datetime64_any_dtype(s) or "date" in c_lower:
            return "Date"
        elif c_lower in ["client_type", "category", "sub_category", "policy_status"]:
            return "Category"
        else:
            return "Text"

    # Format dataframe for clean display in DataTable
    df_formatted = df.copy()
    for col in df_formatted.columns:
        col_type = infer_column_type(col, df_formatted[col])
        if col_type == "Number":
            if col in ["premium_amount", "claim_amount", "commission_earned"]:
                df_formatted[col] = df_formatted[col].apply(lambda val: f"₹{val:,.2f}" if pd.notnull(val) and val != "" else "N/A")
            else:
                df_formatted[col] = df_formatted[col].apply(lambda val: f"{val:,.0f}" if pd.notnull(val) and val != "" and val % 1 == 0 else (f"{val:,.2f}" if pd.notnull(val) and val != "" else "N/A"))
        elif col_type == "Date":
            df_formatted[col] = df_formatted[col].apply(lambda val: pd.to_datetime(val).strftime('%Y-%m-%d') if pd.notnull(val) and val is not pd.NaT else "N/A")
        else:
            df_formatted[col] = df_formatted[col].apply(lambda val: "" if pd.isna(val) else str(val))

    expected_list = [
        "policy_number", "client_name", "client_type", "carrier_name",
        "category", "sub_category", "premium_amount", "claim_amount",
        "commission_earned", "policy_status", "issue_date", "expiry_date",
        "region", "distribution_channel", "claim_status"
    ]
    expected_labels = {
        "policy_number": "Policy Number",
        "client_name": "Client Name",
        "client_type": "Client Type",
        "carrier_name": "Carrier Name",
        "category": "Category",
        "sub_category": "Sub Category",
        "premium_amount": "Premium Amount",
        "claim_amount": "Claim Amount",
        "commission_earned": "Commission Earned",
        "policy_status": "Policy Status",
        "issue_date": "Issue Date",
        "expiry_date": "Expiry Date",
        "region": "Region",
        "distribution_channel": "Distribution Channel",
        "claim_status": "Claim Status"
    }
    
    dropdown_options = [{"label": expected_labels[exp], "value": exp} for exp in expected_list]
    expected_set = set(expected_list)
    
    thead_cells = []
    for c in df_formatted.columns:
        col_lower = str(c).lower().strip()
        if filename and col_lower not in expected_set:
            # Unrecognized column, add inline dropdown mapping
            suggested_val = None
            if mapping_suggestions:
                for exp_col, sug_col in mapping_suggestions.items():
                    if sug_col == c:
                        suggested_val = exp_col
                        break
            
            dropdown = dcc.Dropdown(
                id={"type": "column-map-dropdown", "index": str(c)},
                options=dropdown_options,
                value=suggested_val,
                placeholder="Map to...",
                clearable=True,
                style={
                    "width": "150px", "fontSize": "10px", "fontFamily": "Plus Jakarta Sans",
                    "marginTop": "4px", "fontWeight": "normal", "color": "#374151"
                }
            )
            
            thead_cells.append(html.Th([
                html.Div([
                    html.Span(str(c), style={"fontSize": "11px", "fontWeight": "bold", "color": "#B91C1C"})
                ]),
                dropdown
            ], style={
                "backgroundColor": "#FEE2E2", "color": "#991B1B", "padding": "8px 12px", 
                "border": "1px solid #FCA5A5", "textAlign": "left", "verticalAlign": "top"
            }))
        else:
            # Recognized column
            thead_cells.append(html.Th([
                html.Div(str(c).replace('_', ' ').title(), style={"fontSize": "11px", "fontWeight": "bold"}),
                html.Div("Mapped", style={"fontSize": "9px", "color": "#10B981", "marginTop": "2px", "fontWeight": "normal"}) if filename else html.Div()
            ], style={
                "backgroundColor": TVS_BLUE if not filename else "#F3F4F6", 
                "color": "white" if not filename else "#374151", 
                "padding": "10px 12px", "border": "1px solid #E5E7EB", 
                "textAlign": "left", "verticalAlign": "top"
            }))
            
    thead = html.Thead(html.Tr(thead_cells))
    
    table_rows = []
    df_preview = df_formatted.head(10)
    for idx, row in df_preview.iterrows():
        row_cells = []
        for c in df_formatted.columns:
            cell_style = {
                "padding": "8px 12px", "border": "1px solid #E5E7EB",
                "fontSize": "11px", "color": "#374151", "textAlign": "left"
            }
            if idx % 2 != 0:
                cell_style["backgroundColor"] = "#F9FAFB"
                
            col_lower = str(c).lower().strip()
            if filename and col_lower not in expected_set:
                cell_style["backgroundColor"] = "#FEF2F2"
                cell_style["color"] = "#991B1B"
                
            cell_errors = validation_errors.get("cell_errors", []) if validation_errors else []
            has_err = False
            for err in cell_errors:
                if err["row_idx"] == idx and str(err["col"]) == str(c):
                    has_err = True
                    break
            if has_err:
                cell_style["backgroundColor"] = "#FEE2E2"
                cell_style["color"] = "#B91C1C"
                cell_style["fontWeight"] = "bold"
                
            row_cells.append(html.Td(row[c], style=cell_style))
        table_rows.append(html.Tr(row_cells))
        
    tbody = html.Tbody(table_rows)
    
    preview_table = html.Div(
        html.Table([thead, tbody], style={"width": "100%", "borderCollapse": "collapse"}),
        style={"overflowX": "auto"}
    )

    alert_banner = html.Div()
    if filename and not is_schema_valid and validation_errors:
        # Skip showing the big red schema warning block if mapping suggestions are active
        if not mapping_suggestions:
            missing_cols = validation_errors.get("missing_cols", [])
            field_errors = validation_errors.get("field_errors", [])
            
            alert_content = []
            if missing_cols:
                alert_content.append(html.Div([
                    html.Strong("Schema Compliance Error: "),
                    "The uploaded file is missing the following required columns: ",
                    html.Span(", ".join([c.replace('_', ' ').title() for c in missing_cols]), style={"fontWeight": "700", "textDecoration": "underline"})
                ], style={"color": "#B91C1C", "fontSize": "11px", "marginBottom": "6px" if field_errors else "0px"}))
                
            if field_errors:
                alert_content.append(html.Div([
                    html.Strong("Data Validation Error: "),
                    f"Found {len(field_errors)} cell-level validation issues in this dataset. First few errors:",
                    html.Ul([html.Li(err, style={"fontSize": "10px"}) for err in field_errors[:5]], style={"marginTop": "4px", "marginBottom": "0px", "paddingLeft": "20px"})
                ], style={"color": "#B91C1C", "fontSize": "11px"}))
                
            alert_banner = html.Div(
                alert_content,
                style={
                    "background": "#FFF5F5", "border": "1.5px solid #FCA5A5", 
                    "padding": "12px 16px", "borderRadius": "8px", "marginBottom": "14px"
                }
            )

    grid_card = content_box([
        html.Div([
            html.Div([
                html.Div([
                    html.Div("Data Grid Ingestion Preview", style={"fontSize": "13px", "fontWeight": "800", "color": TVS_BLUE}),
                    html.P("Previewing the first 10 rows of the active dataset. Mapped/unrecognized columns and cells are highlighted.", style={"fontSize": "10px", "color": "#6B7280", "margin": "0"}),
                ], style={"flex": 1}),
                # Apply Mapping Button
                html.Button(
                    "Confirm & Apply Mapping",
                    id="btn-apply-schema-mapping",
                    n_clicks=0,
                    className="hdr-btn hdr-btn--primary",
                    style={
                        "display": "block" if (filename and not is_schema_valid) else "none",
                        "fontSize": "11px",
                        "padding": "6px 16px"
                    }
                )
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "10px"}),
            preview_table
        ])
    ], style={"padding": "16px", "boxShadow": "var(--shadow-sm)", "marginTop": "14px"})

    return html.Div([
        header_row,
        top_panel,
        alert_banner,
        grid_card
    ], className="tab-pane", style={"padding": "14px", "height": "100%", "display": "flex", "flexDirection": "column", "gap": "0px"})


# ─────────────────────────────────────────────────────────────────────────────
# Lead Tracker — Insurance Broking Pipeline Module (tab-14)
# ─────────────────────────────────────────────────────────────────────────────

# --- Lead stage mapping from policy_status values ---
STATUS_TO_STAGE = {
    'Lead':                       'New Lead',
    'Caselogin':                  'Follow-Up',
    'Docs And Inspection Pending':'Follow-Up',
    'Soft Copy Received':         'Follow-Up',
    'Booked':                     'Quote Issued',
    'Active':                     'Policy Issued',
    'Policy Issued':              'Policy Issued',
    'Renewed':                    'Policy Issued',
    'Lost':                       'Lost / Lapsed',
    'Lapse':                      'Lost / Lapsed',
    'Cancelled':                  'Lost / Lapsed',
    'Reject':                     'Lost / Lapsed',
    'Expired':                    'Lost / Lapsed',
}

STAGE_ORDER  = ['New Lead', 'Follow-Up', 'Quote Issued', 'Policy Issued', 'Lost / Lapsed', 'Unknown']

STAGE_COLORS = {
    'New Lead':      '#3B82F6',   # blue
    'Follow-Up':     '#F59E0B',   # amber
    'Quote Issued':  '#8B5CF6',   # purple
    'Policy Issued': '#10B981',   # green
    'Lost / Lapsed': '#EF4444',   # red
    'Unknown':       '#9CA3AF',   # grey
}

STAGE_ICONS = {
    'New Lead':      '',
    'Follow-Up':     '',
    'Quote Issued':  '',
    'Policy Issued': '',
    'Lost / Lapsed': '',
    'Unknown':       '',
}


def _map_stages(dff):
    """Add a lead_stage column to the dataframe."""
    df = dff.copy()
    if 'policy_status' in df.columns:
        df['lead_stage'] = df['policy_status'].apply(lambda x: STATUS_TO_STAGE.get(str(x).strip().title() if pd.notna(x) else '', 'Unknown'))
    else:
        df['lead_stage'] = 'Unknown'
    return df


def _lt_kpi_bar(dff):
    df_stage = _map_stages(dff)
    total = len(df_stage)
    
    stages = df_stage['lead_stage'].value_counts() if 'lead_stage' in df_stage.columns else pd.Series()
    
    new_lead = stages.get('New Lead', 0)
    follow_up = stages.get('Follow-Up', 0)
    quote_issued = stages.get('Quote Issued', 0)
    policy_issued = stages.get('Policy Issued', 0)
    lost_lapsed = stages.get('Lost / Lapsed', 0)
    
    active_pipeline = new_lead + follow_up + quote_issued
    
    conv_rate = (policy_issued / total * 100) if total > 0 else 0.0
    lost_rate = (lost_lapsed / total * 100) if total > 0 else 0.0
    
    return kpi_row(
        kpi_card("Total Enquiries", f"{total:,}", "Leads in selected period", TVS_BLUE),
        kpi_card("Active Pipeline", f"{active_pipeline:,}", "New + Follow-Up + Quote", TVS_ORANGE, accent=TVS_ORANGE),
        kpi_card("Conversion Rate", f"{conv_rate:.1f}%", "Policy Issued / Total Enquiries", GREEN, accent=GREEN),
        kpi_card("Lost Rate", f"{lost_rate:.1f}%", "Lost & Lapsed / Total Enquiries", RED, accent=RED)
    )


def _lt_funnel_bar(dff):
    df_stage = _map_stages(dff)
    total = len(df_stage)
    if total == 0:
        return html.Div()
        
    stages_counts = df_stage['lead_stage'].value_counts()
    
    funnel_items = []
    for stage in STAGE_ORDER:
        count = stages_counts.get(stage, 0)
        pct = (count / total * 100) if total > 0 else 0
        bg_color = STAGE_COLORS.get(stage, '#9CA3AF')
        
        funnel_items.append(html.Div([
            html.Div([
                html.Span(stage, style={"fontWeight": "700", "fontSize": "11px", "color": "#374151"}),
                html.Span(f" {count:,} ({pct:.1f}%)", style={"fontSize": "11px", "color": "#6B7280", "marginLeft": "4px"})
            ], style={"display": "flex", "justifyContent": "between", "marginBottom": "4px"}),
            html.Div(style={
                "height": "6px", "background": "#F3F4F6", "borderRadius": "3px", "overflow": "hidden"
            }, children=[
                html.Div(style={
                    "width": f"{pct}%", "height": "100%", "background": bg_color, "borderRadius": "3px"
                })
            ])
        ], style={"flex": "1", "minWidth": "140px"}))
        
    return html.Div(
        funnel_items,
        style={
            "display": "flex", "gap": "16px", "flexWrap": "wrap",
            "background": "white", "borderRadius": "10px", "padding": "14px 16px",
            "boxShadow": "0 2px 8px rgba(27,59,139,0.07)", "border": "1px solid #E5E7EB",
            "marginBottom": "14px"
        }
    )


def build_lead_pivot(dff, group_col, show_subcategories=False):
    df_stage = _map_stages(dff)
    
    is_product_view = (group_col == 'category' and show_subcategories and 'sub_category' in df_stage.columns)
    
    if is_product_view:
        df_stage['category'] = df_stage['category'].fillna("Unknown")
        df_stage['sub_category'] = df_stage['sub_category'].fillna("Unknown")
        groupby_cols = ['category', 'sub_category']
    else:
        if group_col in df_stage.columns:
            df_stage[group_col] = df_stage[group_col].fillna("Unknown")
        else:
            df_stage[group_col] = "Unknown"
        groupby_cols = [group_col]
        
    pivot = df_stage.groupby(groupby_cols + ['lead_stage']).size().unstack(fill_value=0)
    
    for stage in STAGE_ORDER:
        if stage not in pivot.columns:
            pivot[stage] = 0
            
    pivot = pivot[STAGE_ORDER]
    pivot['Total'] = pivot.sum(axis=1)
    pivot = pivot.sort_values(by='Total', ascending=False)
    
    data_rows = []
    grand_totals = {stage: pivot[stage].sum() for stage in STAGE_ORDER}
    grand_total_all = pivot['Total'].sum()
    
    if is_product_view:
        # Get sorted main categories based on total category enquiries
        cat_totals = pivot.groupby('category')['Total'].sum().sort_values(ascending=False)
        
        for cat in cat_totals.index:
            cat_rows = pivot[pivot.index.get_level_values('category') == cat]
            cat_sum = cat_rows.sum()
            cat_total = cat_sum['Total']
            
            # 1. Main category row
            cat_row_data = {
                "category": str(cat),
                "sub_category": "",
                "display_category": str(cat),
                "Total": f"{cat_total:,}",
                "is_subcategory": "No"
            }
            for stage in STAGE_ORDER:
                cnt = cat_sum[stage]
                pct = (cnt / cat_total * 100) if cat_total > 0 else 0.0
                cat_row_data[stage] = f"{cnt:,} ({pct:.1f}%)"
            data_rows.append(cat_row_data)
            
            # 2. Sorted subcategory rows under this category
            sorted_cat_rows = cat_rows.sort_values(by='Total', ascending=False)
            for (c, sub), sub_row in sorted_cat_rows.iterrows():
                sub_total = sub_row['Total']
                sub_row_data = {
                    "category": str(cat),
                    "sub_category": str(sub),
                    "display_category": f"\u00a0\u00a0\u00a0\u00a0↳ {sub}",
                    "Total": f"{sub_total:,}",
                    "is_subcategory": "Yes"
                }
                for stage in STAGE_ORDER:
                    cnt = sub_row[stage]
                    pct = (cnt / sub_total * 100) if sub_total > 0 else 0.0
                    sub_row_data[stage] = f"{cnt:,} ({pct:.1f}%)"
                data_rows.append(sub_row_data)
                
        # 3. Grand total row
        gt_row = {
            "category": "Grand Total",
            "sub_category": "",
            "display_category": "Grand Total",
            "Total": f"{grand_total_all:,}",
            "is_subcategory": "No"
        }
        for stage in STAGE_ORDER:
            cnt = grand_totals[stage]
            pct = (cnt / grand_total_all * 100) if grand_total_all > 0 else 0.0
            gt_row[stage] = f"{cnt:,} ({pct:.1f}%)"
        data_rows.append(gt_row)
        
        dt_columns = [
            {"name": "Category", "id": "display_category"},
            {"name": "Total Enquiries", "id": "Total"},
        ]
    else:
        for label, row in pivot.iterrows():
            row_total = row['Total']
            row_data = {
                "label": str(label), 
                "Total": f"{row_total:,}",
                "is_subcategory": "No"
            }
            for stage in STAGE_ORDER:
                cnt = row[stage]
                pct = (cnt / row_total * 100) if row_total > 0 else 0.0
                row_data[stage] = f"{cnt:,} ({pct:.1f}%)"
            data_rows.append(row_data)
            
        gt_row = {
            "label": "Grand Total", 
            "Total": f"{grand_total_all:,}",
            "is_subcategory": "No"
        }
        for stage in STAGE_ORDER:
            cnt = grand_totals[stage]
            pct = (cnt / grand_total_all * 100) if grand_total_all > 0 else 0.0
            gt_row[stage] = f"{cnt:,} ({pct:.1f}%)"
        data_rows.append(gt_row)
        
        dt_columns = [
            {"name": group_col.replace('_', ' ').title(), "id": "label"},
            {"name": "Total Enquiries", "id": "Total"},
        ]
        
    for stage in STAGE_ORDER:
        dt_columns.append({"name": stage, "id": stage})
        
    grand_total_filter = '{display_category} = "Grand Total"' if is_product_view else '{label} = "Grand Total"'
    not_grand_total_filter = '{display_category} != "Grand Total"' if is_product_view else '{label} != "Grand Total"'
    
    style_data_cond = [
        {
            'if': {'filter_query': grand_total_filter},
            'backgroundColor': TVS_BLUE,
            'color': 'white',
            'fontWeight': 'bold'
        },
        {
            'if': {
                'column_id': 'Policy Issued',
                'filter_query': not_grand_total_filter
            },
            'backgroundColor': '#ECFDF5',
            'color': '#065F46',
            'fontWeight': '600'
        },
        {
            'if': {
                'column_id': 'Lost / Lapsed',
                'filter_query': not_grand_total_filter
            },
            'backgroundColor': '#FEF2F2',
            'color': '#991B1B'
        }
    ]
    
    if is_product_view:
        # Style main categories with bold text and subcategories with normal text
        style_data_cond.extend([
            {
                'if': {
                    'filter_query': '{is_subcategory} = "No" and {display_category} != "Grand Total"'
                },
                'fontWeight': 'bold',
                'backgroundColor': '#F9FAFB',
                'color': TVS_BLUE
            },
            {
                'if': {
                    'filter_query': '{is_subcategory} = "Yes"'
                },
                'color': '#4B5563',
                'fontWeight': 'normal'
            }
        ])
    
    table = dash_table.DataTable(
        id='lt-pivot-table',
        data=data_rows,
        columns=dt_columns,
        style_cell={
            'fontFamily': 'Plus Jakarta Sans, Inter, sans-serif',
            'fontSize': '11px',
            'padding': '10px 12px',
            'textAlign': 'left',
            'border': '1px solid #E5E7EB'
        },
        style_header={
            'backgroundColor': '#F3F4F6',
            'color': '#374151',
            'fontWeight': 'bold',
            'textAlign': 'left'
        },
        style_data_conditional=style_data_cond,
        export_format="csv"
    )
    return table


def build_nonconversion_table(dff):
    df_stage = _map_stages(dff)
    lost_df = df_stage[df_stage['lead_stage'] == 'Lost / Lapsed'].copy()
    if lost_df.empty:
        return html.Div("No non-converted (Lost/Lapsed) leads in the selected period.", style={
            "padding": "20px", "textAlign": "center", "color": "#6B7280", "fontStyle": "italic"
        })
        
    cols_to_show = ['policy_number', 'client_name', 'category', 'carrier_name', 'premium_amount', 'policy_status']
    for col in cols_to_show:
        if col not in lost_df.columns:
            lost_df[col] = "N/A"
            
    display_df = lost_df[cols_to_show].head(50).copy()
    display_df['premium_amount'] = display_df['premium_amount'].apply(lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "₹0.00")
    
    dt_columns = [{"name": c.replace('_', ' ').title(), "id": c} for c in cols_to_show]
    
    table = dash_table.DataTable(
        data=display_df.to_dict('records'),
        columns=dt_columns,
        page_size=10,
        sort_action='native',
        filter_action='native',
        style_cell={
            'fontFamily': 'Plus Jakarta Sans, Inter, sans-serif',
            'fontSize': '11px',
            'padding': '8px 10px',
            'textAlign': 'left',
            'border': '1px solid #E5E7EB'
        },
        style_header={
            'backgroundColor': '#FEE2E2',
            'color': '#991B1B',
            'fontWeight': 'bold'
        },
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#FEF2F2'}
        ],
        export_format="csv"
    )
    return table


def build_followup_table(dff):
    df_stage = _map_stages(dff)
    pending_df = df_stage[df_stage['lead_stage'].isin(['New Lead', 'Follow-Up', 'Quote Issued'])].copy()
    if pending_df.empty:
        return html.Div("No active pending follow-ups in the selected period.", style={
            "padding": "20px", "textAlign": "center", "color": "#6B7280", "fontStyle": "italic"
        })
        
    cols_to_show = ['policy_number', 'client_name', 'category', 'carrier_name', 'premium_amount', 'policy_status']
    for col in cols_to_show:
        if col not in pending_df.columns:
            pending_df[col] = "N/A"
            
    display_df = pending_df[cols_to_show].head(50).copy()
    display_df['premium_amount'] = display_df['premium_amount'].apply(lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "₹0.00")
    
    dt_columns = [{"name": c.replace('_', ' ').title(), "id": c} for c in cols_to_show]
    
    table = dash_table.DataTable(
        data=display_df.to_dict('records'),
        columns=dt_columns,
        page_size=10,
        sort_action='native',
        filter_action='native',
        style_cell={
            'fontFamily': 'Plus Jakarta Sans, Inter, sans-serif',
            'fontSize': '11px',
            'padding': '8px 10px',
            'textAlign': 'left',
            'border': '1px solid #E5E7EB'
        },
        style_header={
            'backgroundColor': '#FEF3C7',
            'color': '#92400E',
            'fontWeight': 'bold'
        },
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#FFFBEB'}
        ],
        export_format="csv"
    )
    return table



def _lt_kpi_and_funnel_panel(dff):
    return _lt_kpi_bar(dff)


def tab14(dff):
    if dff.empty:
        return html.Div("No Data Available")
        
    cats = [{"label": "All Products", "value": "__all__"}] + [{"label": str(c), "value": str(c)} for c in sorted(dff['category'].dropna().unique())] if 'category' in dff.columns else []
    channels = [{"label": "All Channels", "value": "__all__"}] + [{"label": str(c), "value": str(c)} for c in sorted(dff['distribution_channel'].dropna().unique())] if 'distribution_channel' in dff.columns else []
    carriers = [{"label": "All Carriers", "value": "__all__"}] + [{"label": str(c), "value": str(c)} for c in sorted(dff['carrier_name'].dropna().unique())] if 'carrier_name' in dff.columns else []
    ctypes = [{"label": "All Clients", "value": "__all__"}] + [{"label": str(c), "value": str(c)} for c in sorted(dff['client_type'].dropna().unique())] if 'client_type' in dff.columns else []

    if 'issue_date' in dff.columns:
        dates = pd.to_datetime(dff['issue_date'], errors='coerce').dropna()  # type: ignore
        min_d = dates.min().date().isoformat() if not dates.empty else None
        max_d = dates.max().date().isoformat() if not dates.empty else None
    else:
        min_d = max_d = None

    dd_style = {"width": "140px", "fontSize": "11px", "fontFamily": "Plus Jakarta Sans"}

    filter_bar = html.Div([
        # Row 1: Date & Time Period controls
        html.Div([
            html.Div([
                html.Span("Date Range:", style={"fontWeight": "700", "fontSize": "11px", "color": TVS_BLUE, "marginRight": "8px"}),
                dcc.DatePickerSingle(
                    id='lt-date-from', placeholder="From",
                    date=min_d, display_format='DD MMM YYYY',
                    className="lt-date-picker"
                ),
                html.Span("to", style={"fontSize": "11px", "color": "#6B7280", "margin": "0 6px"}),
                dcc.DatePickerSingle(
                    id='lt-date-to', placeholder="To",
                    date=max_d, display_format='DD MMM YYYY',
                    className="lt-date-picker"
                ),
            ], style={"display": "flex", "alignItems": "center"}),
            
            dcc.Dropdown(
                id='lt-preset',
                options=[
                    {"label": "Today", "value": "today"},
                    {"label": "Yesterday", "value": "yesterday"},
                    {"label": "This Week", "value": "this_week"},
                    {"label": "Last Week", "value": "last_week"},
                    {"label": "This Month", "value": "this_month"},
                    {"label": "Last Month", "value": "last_month"},
                    {"label": "Last 30 Days", "value": "last_30_days"},
                    {"label": "Last 90 Days", "value": "last_90_days"},
                ],
                value=None,
                clearable=True,
                style={"width": "110px", "fontSize": "11px", "fontFamily": "Plus Jakarta Sans"},
                placeholder="Preset"
            ),
            
            html.Button(
                "Go",
                id="lt-go",
                n_clicks=0,
                className="hdr-btn",
                style={
                    "backgroundColor": TVS_BLUE,
                    "color": "white",
                    "border": f"1.5px solid {TVS_BLUE}",
                    "fontSize": "11px",
                    "padding": "6px 16px",
                    "height": "34px",
                    "borderRadius": "8px",
                    "fontWeight": "700",
                    "cursor": "pointer",
                    "transition": "all 0.2s ease"
                }
            ),
            
            html.Span(
                "ℹ Yesterday 6:30 PM to Today 6:30 PM = Today",
                style={
                    "fontSize": "10px", "color": "#4B5563", 
                    "background": "#F3F4F6", "padding": "4px 12px",
                    "borderRadius": "6px", "border": "1px solid #E5E7EB",
                    "fontWeight": "500"
                }
            ),
        ], style={"display": "flex", "alignItems": "center", "gap": "12px", "width": "100%", "flexWrap": "wrap"}),
        
        # Divider Line
        html.Div(style={"width": "100%", "height": "1px", "background": "#E5E7EB", "margin": "8px 0"}),
        
        # Row 2: Category Dropdowns & Clear
        html.Div([
            dcc.Dropdown(id='lt-product',     options=cats,     value='__all__',
                         clearable=False, style=dd_style, placeholder="Product"),
            dcc.Dropdown(id='lt-source',      options=channels, value='__all__',
                         clearable=False, style=dd_style, placeholder="Source"),
            dcc.Dropdown(id='lt-carrier',     options=carriers, value='__all__',
                         clearable=False, style=dd_style, placeholder="Carrier"),
            dcc.Dropdown(id='lt-client-type', options=ctypes,   value='__all__',
                         clearable=False, style=dd_style, placeholder="Client Type"),
            html.Button([
                html.Span("✕ ", style={"fontSize": "10px"}), "Clear Filters"
            ], id="lt-clear", n_clicks=0, className="hdr-btn hdr-btn--outline",
               style={"whiteSpace": "nowrap", "fontSize": "11px", "marginLeft": "auto", "height": "34px"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "12px", "width": "100%", "flexWrap": "wrap"})
        
    ], style={
        "display": "flex", "flexDirection": "column", "gap": "6px",
        "background": "white", "borderRadius": "10px",
        "padding": "12px 16px", "boxShadow": "0 2px 8px rgba(27,59,139,0.07)",
        "marginBottom": "14px", "border": "1px solid #E5E7EB",
    })

    subtab_strip = dcc.Tabs(
        id='lt-subtab', value='product',
        children=[
            dcc.Tab(label='By Product',     value='product',       className='lt-tab', selected_className='lt-tab--active'),
            dcc.Tab(label='By Source',       value='source',        className='lt-tab', selected_className='lt-tab--active'),
            dcc.Tab(label='By Carrier',      value='carrier',       className='lt-tab', selected_className='lt-tab--active'),
            dcc.Tab(label='Non-Conversion',  value='nonconversion', className='lt-tab', selected_className='lt-tab--active'),
            dcc.Tab(label='Follow-Up',       value='followup',      className='lt-tab', selected_className='lt-tab--active'),
        ],
        style={"marginBottom": "12px"},
    )

    header = html.Div([
        html.Div([
            html.H3("Sales Pipeline", style={
                "color": TVS_BLUE, "fontWeight": "900", "fontSize": "20px", "margin": "0 0 2px 0"
            }),
            html.P("Insurance Broking — Sales Pipeline & Conversion Analysis", style={
                "color": "#6B7280", "fontSize": "11px", "margin": "0"
            }),
        ]),
        html.Span("Live Pipeline", style={
            "background": "#ECFDF5", "color": "#065F46", "fontWeight": "700",
            "fontSize": "10px", "padding": "4px 12px", "borderRadius": "20px",
            "border": "1px solid #A7F3D0",
        }),
    ], style={
        "display": "flex", "justifyContent": "space-between", "alignItems": "center",
        "marginBottom": "14px",
    })

    table_wrapper = html.Div([
        html.Div([
            html.Div([
                html.Div(id='lt-table-title', children="Sales Pipeline Summary", style={
                    "fontSize": "13px", "fontWeight": "800", "color": TVS_BLUE, "marginBottom": "2px"
                }),
                html.P("Counts show total leads. Percentages are relative to each row total.",
                       style={"fontSize": "10px", "color": "#9CA3AF", "margin": "0 0 10px 0"}),
            ]),
            html.Div(
                id='lt-toggle-container',
                children=[
                    dcc.Checklist(
                        id='lt-product-detailed',
                        options=[{'label': ' Show Sub-Categories Breakdown', 'value': 'show'}],
                        value=[],
                        labelStyle={
                            "display": "flex",
                            "alignItems": "center",
                            "gap": "6px",
                            "fontSize": "11px",
                            "fontWeight": "600",
                            "color": TVS_BLUE,
                            "cursor": "pointer",
                            "background": "rgba(27,59,139,0.06)",
                            "padding": "5px 12px",
                            "borderRadius": "20px",
                            "border": "1px solid rgba(27,59,139,0.15)",
                            "transition": "all 0.2s ease"
                        }
                    )
                ],
                style={"display": "block"}
            )
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "6px"}),
        html.Div(id='lt-table-container', children=build_lead_pivot(dff, 'category')),
    ], style={
        "background": "white", "borderRadius": "10px",
        "padding": "16px", "boxShadow": "0 2px 8px rgba(27,59,139,0.07)",
        "border": "1px solid #E5E7EB",
    })

    return html.Div([
        header,
        html.Div(id='lt-kpi-container', children=_lt_kpi_and_funnel_panel(dff), style={"marginBottom": "14px"}),
        filter_bar,
        subtab_strip,
        table_wrapper,
        # Drill-down Modal
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Lead Details", id="lt-drilldown-modal-title", style={"fontWeight": "bold", "color": TVS_BLUE})),
                dbc.ModalBody(id="lt-drilldown-modal-body"),
                dbc.ModalFooter(
                    html.Button("Close", id="lt-drilldown-modal-close", className="hdr-btn hdr-btn--outline", style={"fontSize": "11px", "padding": "6px 16px"})
                ),
            ],
            id="lt-drilldown-modal",
            size="xl",
            is_open=False,
            scrollable=True,
            style={"fontFamily": "Plus Jakarta Sans, Inter, sans-serif"}
        )
    ], className="tab-pane", style={
        "padding": "14px", "height": "100%",
        "display": "flex", "flexDirection": "column", "gap": "0px",
    })

def build_ai_chart(data):
    if not data or not isinstance(data, list) or len(data) == 0:
        return None
    
    df = pd.DataFrame(data)
    
    # Try to convert columns to numeric if they are strings of numbers
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
        try:
            cleaned = df[col].astype(str).str.replace(r'[₹$,]', '', regex=True).str.strip()
            df[col] = pd.to_numeric(cleaned, errors='coerce')
        except Exception:
            pass

    num_cols = []
    cat_cols = []
    date_cols = []
    
    for col in df.columns:
        col_lower = col.lower()
        if 'date' in col_lower or 'time' in col_lower or pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            if 'id' in col_lower or 'code' in col_lower:
                cat_cols.append(col)
            else:
                num_cols.append(col)
        else:
            cat_cols.append(col)

    # 1. KPI Card Case (1 row, 1 numeric column)
    if len(df) == 1 and len(num_cols) == 1:
        val = df[num_cols[0]].iloc[0]
        col_name = num_cols[0].replace('_', ' ').title()
        
        def format_rupee(val):
            try:
                val = float(val)
                s = f"{val:.2f}"
                parts = s.split('.')
                integer_part = parts[0]
                decimal_part = parts[1]
                if len(integer_part) <= 3:
                    formatted_int = integer_part
                else:
                    last_three = integer_part[-3:]
                    remaining = integer_part[:-3]
                    groups = []
                    while remaining:
                        groups.append(remaining[-2:])
                        remaining = remaining[:-2]
                    groups.reverse()
                    formatted_int = ",".join(groups) + "," + last_three
                return f"₹{formatted_int}.{decimal_part}"
            except Exception:
                return str(val)

        fmt_val = format_rupee(val) if any(x in col_name.lower() for x in ['premium', 'claim', 'commission', 'brokerage', 'amount', 'earned', 'paid', 'revenue']) else f"{val:,.2f}"
        
        return html.Div([
            html.Div(col_name, className="report-kpi-label"),
            html.Div(fmt_val, className="report-kpi-value"),
            html.Div("Single Metric Query Result", className="report-kpi-sub")
        ], className="report-kpi-card")

    if not num_cols:
        return None

    label_x = cat_cols[0] if cat_cols else df.columns[0]
    label_y = num_cols[0]
    
    clean_x = label_x.replace('_', ' ').title()
    clean_y = label_y.replace('_', ' ').title()
    
    # 2. Time-series Line Chart
    if date_cols and len(df) > 1:
        try:
            date_col = date_cols[0]
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.sort_values(by=date_col)
            fig = px.line(
                df, 
                x=date_col, 
                y=label_y,
                labels={date_col: date_col.replace('_', ' ').title(), label_y: clean_y},
                template="plotly_white",
                color_discrete_sequence=[TVS_BLUE]
            )
            fig.update_layout(
                margin=dict(l=40, r=40, t=30, b=30),
                height=300,
                font_family="Plus Jakarta Sans, sans-serif"
            )
            return dcc.Graph(figure=fig, config={"displayModeBar": False})
        except Exception:
            pass

    # 3. Bar Chart
    if len(df) > 1:
        if len(df) > 15:
            df = df.head(15)
        is_horizontal = len(df) <= 8 or df[label_x].astype(str).str.len().max() > 10
        
        if is_horizontal:
            fig = px.bar(
                df,
                x=label_y,
                y=label_x,
                orientation='h',
                labels={label_x: clean_x, label_y: clean_y},
                template="plotly_white",
                color_discrete_sequence=[TVS_BLUE]
            )
            fig.update_layout(yaxis={'categoryorder':'total ascending'})
        else:
            fig = px.bar(
                df,
                x=label_x,
                y=label_y,
                labels={label_x: clean_x, label_y: clean_y},
                template="plotly_white",
                color_discrete_sequence=[TVS_BLUE]
            )
            fig.update_layout(xaxis={'categoryorder':'total descending'})

        fig.update_layout(
            margin=dict(l=40, r=40, t=30, b=30),
            height=300,
            font_family="Plus Jakarta Sans, sans-serif"
        )
        fig.update_traces(marker_line_color='rgb(8,48,107)', marker_line_width=1, opacity=0.85)
        return dcc.Graph(figure=fig, config={"displayModeBar": False})

    return None


def render_text_block(text, label="AI Insights Summary"):
    if not text:
        return None
    is_error = text.startswith("⚠️") or "Error:" in text or "Exception" in text
    if is_error:
        return html.Div([
            html.Div(label, className="report-section-label", style={"color": "#EF4444"}),
            html.Div(text, style={
                "color": "#B91C1C", "fontFamily": "Consolas, Monaco, monospace",
                "fontSize": "11.5px", "whiteSpace": "pre-wrap", "lineHeight": "1.5"
            })
        ], className="report-ai-summary", style={"background": "#FEF2F2", "borderLeft": "3px solid #EF4444", "borderColor": "#EF4444"})
    else:
        return html.Div([
            html.Div(label, className="report-section-label"),
            dcc.Markdown(text, style={"margin": "0"})
        ], className="report-ai-summary")


def build_report_panel(history):
    if not history:
        return html.Div([
            html.Div("No active session data to generate a report from. Ask some questions first!",
                     style={"textAlign": "center", "color": "#64748B", "padding": "40px"})
        ])
        
    user_msgs = [m for m in history if m.get("sender") == "user"]
    ai_msgs   = [m for m in history if m.get("sender") == "ai"]
    
    banner = html.Div([
        html.Div([
            html.Span("Session Summary: ", style={"fontWeight": "bold", "color": TVS_BLUE}),
            html.Span(f"This session contains {len(user_msgs)} user question(s) and {len(ai_msgs)} AI analysis reports.")
        ])
    ], className="report-session-banner")
    
    sections = []
    q_idx = 0
    i = 0
    while i < len(history):
        msg = history[i]
        if msg.get("sender") == "user":
            q_idx += 1
            q_text = msg.get("text", "")
            
            ai_msg = {}
            if i + 1 < len(history) and history[i + 1].get("sender") == "ai":
                ai_msg = history[i + 1]
                
            ai_text = ai_msg.get("text", "")
            ai_sql = ai_msg.get("sql")
            ai_data = ai_msg.get("data")
            
            chart_el = None
            if ai_data:
                chart_el = build_ai_chart(ai_data)
                
            table_el = None
            if ai_data and isinstance(ai_data, list) and len(ai_data) > 0:
                def format_rupee(val):
                    if val is None:
                        return ""
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        return str(val)
                    s = f"{val:.2f}"
                    parts = s.split('.')
                    integer_part = parts[0]
                    decimal_part = parts[1]
                    if len(integer_part) <= 3:
                        formatted_int = integer_part
                    else:
                        last_three = integer_part[-3:]
                        remaining = integer_part[:-3]
                        groups = []
                        while remaining:
                            groups.append(remaining[-2:])
                            remaining = remaining[:-2]
                        groups.reverse()
                        formatted_int = ",".join(groups) + "," + last_three
                    return f"₹{formatted_int}.{decimal_part}"

                formatted_data = []
                currency_cols = set()
                sample_row = ai_data[0]
                for col_key in sample_row.keys():
                    col_lower = col_key.lower()
                    if any(term in col_lower for term in ['premium', 'claim', 'commission', 'brokerage', 'amount', 'earned', 'paid', 'revenue']):
                        currency_cols.add(col_key)
                
                for row in ai_data:
                    formatted_row = {}
                    for k, v in row.items():
                        if k in currency_cols and v is not None:
                            formatted_row[k] = format_rupee(v)
                        else:
                            if isinstance(v, float):
                                formatted_row[k] = f"{v:.2f}"
                            else:
                                formatted_row[k] = v
                    formatted_data.append(formatted_row)

                columns = [{"name": k.replace('_', ' ').title(), "id": k} for k in ai_data[0].keys()]
                table_el = html.Div([
                    html.Div("Raw Data Table", className="report-section-label", style={"marginTop": "14px"}),
                    dash_table.DataTable(
                        data=formatted_data,
                        columns=columns,
                        page_size=5,
                        style_cell={
                            'fontFamily': 'Plus Jakarta Sans, Inter, sans-serif',
                            'fontSize': '11px',
                            'padding': '6px 10px',
                            'border': '1px solid #E2E8F0',
                            'textAlign': 'left'
                        },
                        style_header={
                            'backgroundColor': '#F1F5F9',
                            'fontWeight': '700',
                            'color': '#334155',
                            'border': '1px solid #CBD5E1'
                        },
                        style_table={'overflowX': 'auto', 'marginTop': '4px', 'borderRadius': '6px'},
                        style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#F8FAFC'}]
                    )
                ])

            sql_el = None
            if ai_sql:
                sql_el = html.Div([
                    html.Details([
                        html.Summary("View Generated SQL Query", style={"fontWeight": "600", "color": TVS_BLUE, "cursor": "pointer"}),
                        html.Pre(
                            ai_sql,
                            style={
                                "background": "#F1F5F9", "padding": "12px", "borderRadius": "6px",
                                "fontFamily": "Consolas, Monaco, monospace", "fontSize": "11px", "marginTop": "8px",
                                "overflowX": "auto", "whiteSpace": "pre-wrap", "border": "1px solid #E2E8F0"
                            }
                        )
                    ], style={"marginTop": "14px", "fontSize": "12px"})
                ])
                
            sections.append(
                html.Div([
                    html.Div(f"Question {q_idx}", className="report-q-badge"),
                    html.H2(q_text, className="report-q-text"),
                    
                    html.Div(chart_el, className="report-chart-wrap") if chart_el else None,
                    
                    render_text_block(ai_text, "AI Insights Summary") if ai_text else None,
                    
                    table_el,
                    sql_el
                ], className="report-section")
            )
            i += 2
        else:
            i += 1
            
    return html.Div([banner] + sections)


def format_sql_query(sql_str):
    if not sql_str:
        return html.Pre("")
    keywords = {
        'SELECT', 'FROM', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'WHERE',
        'AND', 'OR', 'GROUP', 'BY', 'ORDER', 'LIMIT', 'SUM', 'COUNT', 'AVG', 'MIN',
        'MAX', 'IFNULL', 'COALESCE', 'AS', 'IN', 'HAVING', 'CASE', 'WHEN', 'THEN',
        'ELSE', 'END', 'LIKE', 'DESC', 'ASC', 'UNION', 'ALL'
    }
    
    lines = sql_str.split('\n')
    formatted_lines = []
    
    for line in lines:
        import re
        tokens = re.split(r'(\s+|,|\(|\))', line)
        line_children = []
        for token in tokens:
            if not token:
                continue
            token_clean = token.strip().upper()
            if token_clean in keywords:
                line_children.append(html.Span(token, style={"color": "#1B3B8B", "fontWeight": "700"}))
            elif token.startswith("'") or token.startswith('"'):
                line_children.append(html.Span(token, style={"color": "#0F766E"}))
            elif token.isdigit():
                line_children.append(html.Span(token, style={"color": "#7C3AED"}))
            else:
                line_children.append(html.Span(token, style={"color": "#334155"}))
        formatted_lines.append(html.Div(line_children, style={"minHeight": "1.2em"}))
        
    return html.Pre(formatted_lines, style={
        "background": "#F8FAFC", "padding": "12px", "borderRadius": "6px",
        "fontFamily": "Consolas, Monaco, monospace", "fontSize": "11px", "marginTop": "8px",
        "overflowX": "auto", "border": "1px solid #E2E8F0", "lineHeight": "1.4"
    })



def _build_auto_chart(data: list) -> dcc.Graph | None:
    """Auto-generates a Plotly chart based on the shape of the data."""
    if not data or len(data) == 0:
        return None
    
    df = pd.DataFrame(data)
    if len(df) < 2 or len(df.columns) < 2:
        return None  # Single-row KPIs don't need a chart
    
    # Identify column types
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    text_cols = [c for c in df.columns if c not in numeric_cols]
    date_cols = [c for c in text_cols if any(kw in c.lower() for kw in ['date', 'month', 'year', 'quarter', 'period'])]
    
    if not numeric_cols:
        return None
    
    # Pick the best chart type
    primary_numeric = numeric_cols[0]
    
    if date_cols and len(date_cols) > 0:
        # Time-series → Line chart
        x_col = date_cols[0]
        fig = px.line(
            df, x=x_col, y=primary_numeric,
            title=f"{primary_numeric.replace('_', ' ').title()} Over Time",
            color_discrete_sequence=[TVS_BLUE, TVS_ORANGE, GREEN, PURPLE]
        )
    elif text_cols:
        # Categorical → Horizontal bar chart
        cat_col = text_cols[0]
        if len(numeric_cols) > 1:
            # Multiple metrics → Grouped bar
            fig = go.Figure()
            colors = [TVS_BLUE, TVS_ORANGE, GREEN, PURPLE, AMBER, RED]
            for i, nc in enumerate(numeric_cols[:4]):
                fig.add_trace(go.Bar(
                    name=nc.replace('_', ' ').title(),
                    x=df[nc], y=df[cat_col],
                    orientation='h',
                    marker_color=colors[i % len(colors)]
                ))
            fig.update_layout(
                barmode='group',
                title=f"Comparison by {cat_col.replace('_', ' ').title()}"
            )
        else:
            fig = px.bar(
                df, x=primary_numeric, y=cat_col,
                orientation='h',
                title=f"{primary_numeric.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}",
                color_discrete_sequence=[TVS_BLUE]
            )
    else:
        return None
    
    fig.update_layout(
        height=280,
        margin=dict(l=10, r=10, t=35, b=10),
        font=dict(family="Plus Jakarta Sans, Inter, sans-serif", size=11),
        plot_bgcolor="white",
        paper_bgcolor="white",
        title_font_size=13,
        showlegend=len(numeric_cols) > 1
    )
    fig.update_xaxes(showgrid=True, gridcolor="#F1F5F9")
    fig.update_yaxes(showgrid=False)
    
    return dcc.Graph(
        figure=fig,
        config={'displayModeBar': False},
        style={"marginTop": "8px", "borderRadius": "6px", "border": "1px solid #E2E8F0"}
    )


_FOLLOWUP_MAP = {
    'premium': ["Break down by carrier", "Show monthly premium trend", "Top 5 regions by premium"],
    'claim': ["Show loss ratio by carrier", "Break down claims by product", "Which clients have highest claims?"],
    'client': ["Show their premium breakdown", "Premium by client segment", "Which region has most clients?"],
    'carrier': ["Premium by carrier", "Claims by carrier", "Commission breakdown by carrier"],
    'product': ["Premium by product category", "Claims by product", "Which products are most popular?"],
    'commission': ["Commission by carrier", "Top 5 clients by commission", "Commission trend by month"],
    'loss': ["Loss ratio by region", "Loss ratio by carrier", "Loss ratio trend by month"],
    'region': ["Premium by region", "Claims by region", "Top clients in each region"],
}


def _get_followup_suggestions(user_query: str) -> list:
    """Returns 3 follow-up suggestions based on keywords in the user query."""
    query_lower = user_query.lower() if user_query else ""
    for keyword, suggestions in _FOLLOWUP_MAP.items():
        if keyword in query_lower:
            return suggestions[:3]
    return ["Show monthly trend", "Break down by region", "Top 5 by premium"]


def _build_comparison_card(data: list, entity_a: str, entity_b: str) -> list:
    """Builds a side-by-side comparison card with KPI tiles and a grouped bar chart."""
    if not data or len(data) == 0:
        return []
    
    df = pd.DataFrame(data)
    kpi_cards = []
    colors = [TVS_BLUE, TVS_ORANGE, GREEN, PURPLE, AMBER]
    
    for i, (_, row) in enumerate(df.iterrows()):
        name = row.get('carrier_name', f'Entity {i+1}')
        premium = row.get('total_premium', 0)
        claims = row.get('total_claims', 0)
        policies = row.get('policy_count', 0)
        loss_ratio = row.get('loss_ratio', 0)
        commission = row.get('total_commission', 0)
        
        prem_cr = premium / 1e7 if premium else 0
        claims_cr = claims / 1e7 if claims else 0
        comm_cr = commission / 1e7 if commission else 0
        
        color = colors[i % len(colors)]
        
        card = html.Div([
            html.Div(name, style={
                "fontWeight": "800", "fontSize": "14px", "color": color,
                "marginBottom": "8px", "borderBottom": f"2px solid {color}", "paddingBottom": "4px"
            }),
            html.Div([
                html.Div([html.Div("Policies", style={"fontSize": "10px", "color": "#717784"}),
                          html.Div(f"{policies:,}", style={"fontSize": "16px", "fontWeight": "700", "color": "#1E293B"})]),
                html.Div([html.Div("Premium", style={"fontSize": "10px", "color": "#717784"}),
                          html.Div(f"₹{prem_cr:,.2f} Cr", style={"fontSize": "16px", "fontWeight": "700", "color": TVS_BLUE})]),
                html.Div([html.Div("Claims", style={"fontSize": "10px", "color": "#717784"}),
                          html.Div(f"₹{claims_cr:,.2f} Cr", style={"fontSize": "16px", "fontWeight": "700", "color": RED})]),
                html.Div([html.Div("Commission", style={"fontSize": "10px", "color": "#717784"}),
                          html.Div(f"₹{comm_cr:,.2f} Cr", style={"fontSize": "16px", "fontWeight": "700", "color": GREEN})]),
                html.Div([html.Div("Loss Ratio", style={"fontSize": "10px", "color": "#717784"}),
                          html.Div(f"{loss_ratio:.1f}%", style={
                              "fontSize": "16px", "fontWeight": "700",
                              "color": RED if loss_ratio > 70 else (AMBER if loss_ratio > 50 else GREEN)
                          })]),
            ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr 1fr 1fr", "gap": "8px"})
        ], style={
            "flex": "1", "padding": "12px", "background": "white", "borderRadius": "8px",
            "border": f"1px solid {color}22", "boxShadow": f"0 2px 8px {color}11"
        })
        kpi_cards.append(card)
    
    card_row = html.Div(kpi_cards, style={"display": "flex", "gap": "12px", "marginTop": "10px"})
    
    # Grouped bar chart
    metrics = ['total_premium', 'total_claims', 'total_commission']
    metric_labels = ['Premium', 'Claims', 'Commission']
    chart_data = []
    for _, row in df.iterrows():
        for m, ml in zip(metrics, metric_labels):
            chart_data.append({
                'Entity': row.get('carrier_name', 'Unknown'),
                'Metric': ml,
                'Value (₹ Crore)': (row.get(m, 0) or 0) / 1e7
            })
    
    chart_df = pd.DataFrame(chart_data)
    fig = px.bar(
        chart_df, x='Metric', y='Value (₹ Crore)', color='Entity',
        barmode='group', color_discrete_sequence=[TVS_BLUE, TVS_ORANGE, GREEN, PURPLE]
    )
    fig.update_layout(
        height=250,
        margin=dict(l=10, r=10, t=10, b=10),
        font=dict(family="Plus Jakarta Sans, Inter, sans-serif", size=11),
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    chart = dcc.Graph(figure=fig, config={'displayModeBar': False},
                      style={"marginTop": "8px", "borderRadius": "6px", "border": "1px solid #E2E8F0"})
    
    return [card_row, chart]


def build_chat_bubbles(history):
    if not history:
        return [
            html.Div([
                html.Div("✧", style={"fontSize": "32px", "color": TVS_ORANGE, "textAlign": "center", "marginBottom": "8px"}),
                html.Div("Hello! I am your AI Insurance Assistant.", style={
                    "fontWeight": "700", "fontSize": "15px", "color": TVS_BLUE, 
                    "textAlign": "center", "marginBottom": "6px", "fontFamily": "Plus Jakarta Sans, sans-serif"
                }),
                html.Div("Ask me business questions in natural language, and I will translate them to SQL, query your database, and summarize the findings. Try clicking a suggestion above!", style={
                    "fontSize": "12px", "color": "#474D5A", "textAlign": "center", "lineHeight": "1.5"
                })
            ], style={"padding": "32px 24px", "background": "white", "borderRadius": "8px", "border": "1px dashed #CBD5E1", "maxWidth": "480px", "margin": "60px auto 0"})
        ]
        
    bubbles = []
    msg_index = 0
    for msg in history:
        sender = msg.get("sender")
        text = msg.get("text", "")
        sql = msg.get("sql")
        data = msg.get("data")
        user_query = msg.get("user_query", "")
        is_comparison = msg.get("is_comparison", False)
        
        if sender == "user":
            bubbles.append(
                html.Div(
                    html.Div(text, className="chat-bubble chat-bubble--user"),
                    className="chat-bubble-row chat-bubble-row--user"
                )
            )
        else:
            if msg.get("is_placeholder"):
                ai_children = [
                    html.Div([
                        html.Div(className="premium-spinner"),
                        html.Div([
                            html.Span("AI Assistant Status: ", style={"fontWeight": "700", "color": TVS_BLUE}),
                            html.Span(text, style={"color": TVS_ORANGE, "fontWeight": "600"})
                        ], style={"fontSize": "12px", "marginLeft": "8px"})
                    ], style={"display": "flex", "alignItems": "center", "padding": "4px 0"})
                ]
            else:
                is_error = text.startswith("⚠️") or "Error:" in text or "Exception" in text
                if is_error:
                    ai_children = [
                        html.Div(text, style={
                            "color": "#B91C1C", "fontFamily": "Consolas, Monaco, monospace",
                            "fontSize": "11.5px", "whiteSpace": "pre-wrap", "lineHeight": "1.5",
                            "padding": "10px 14px", "background": "#FEF2F2", "borderRadius": "6px",
                            "borderLeft": "3px solid #EF4444"
                        })
                    ]
                else:
                    ai_children = [
                        dcc.Markdown(text, style={"margin": "0"})
                    ]
            
            if sql:
                ai_children.append(
                    html.Div([
                        html.Details([
                            html.Summary("View Generated SQL Query", style={"fontWeight": "600", "color": TVS_BLUE, "cursor": "pointer", "outline": "none"}),
                            format_sql_query(sql)
                        ], style={"marginTop": "10px", "fontSize": "12px"})
                    ])
                )
                
            if data and isinstance(data, list) and len(data) > 0:
                def format_rupee(val):
                    if val is None:
                        return ""
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        return str(val)
                    s = f"{val:.2f}"
                    parts = s.split('.')
                    integer_part = parts[0]
                    decimal_part = parts[1]
                    if len(integer_part) <= 3:
                        formatted_int = integer_part
                    else:
                        last_three = integer_part[-3:]
                        remaining = integer_part[:-3]
                        groups = []
                        while remaining:
                            groups.append(remaining[-2:])
                            remaining = remaining[:-2]
                        groups.reverse()
                        formatted_int = ",".join(groups) + "," + last_three
                    return f"₹{formatted_int}.{decimal_part}"

                formatted_data = []
                currency_cols = set()
                sample_row = data[0]
                for col_key in sample_row.keys():
                    col_lower = col_key.lower()
                    if any(term in col_lower for term in ['premium', 'claim', 'commission', 'brokerage', 'amount', 'earned', 'paid', 'revenue']):
                        currency_cols.add(col_key)
                
                for row in data:
                    formatted_row = {}
                    for k, v in row.items():
                        if k in currency_cols and v is not None:
                            formatted_row[k] = format_rupee(v)
                        else:
                            if isinstance(v, float):
                                formatted_row[k] = f"{v:.2f}"
                            else:
                                formatted_row[k] = v
                    formatted_data.append(formatted_row)

                columns = [{"name": k.replace('_', ' ').title(), "id": k} for k in data[0].keys()]
                table = dash_table.DataTable(
                    data=formatted_data,
                    columns=columns,
                    page_size=5,
                    style_cell={
                        'fontFamily': 'Plus Jakarta Sans, Inter, sans-serif',
                        'fontSize': '11px',
                        'padding': '6px 10px',
                        'border': '1px solid #E2E8F0',
                        'textAlign': 'left'
                    },
                    style_header={
                        'backgroundColor': '#F1F5F9',
                        'fontWeight': '700',
                        'color': '#334155',
                        'border': '1px solid #CBD5E1'
                    },
                    style_table={'overflowX': 'auto', 'marginTop': '10px', 'borderRadius': '6px'},
                    style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': '#F8FAFC'}]
                )
                ai_children.append(table)
                
                # ── CSV Download Button ────────────────────────────────────
                ai_children.append(
                    html.Button(
                        "📥 Download CSV",
                        id={"type": "chat-download-csv", "index": msg_index},
                        n_clicks=0,
                        style={
                            "marginTop": "8px", "fontSize": "11px", "padding": "5px 14px",
                            "background": "#F1F5F9", "border": "1px solid #CBD5E1",
                            "borderRadius": "6px", "cursor": "pointer", "color": "#334155",
                            "fontWeight": "600", "fontFamily": "Plus Jakarta Sans, sans-serif"
                        }
                    )
                )
                
                # ── Auto-Generated Chart or Comparison Card ────────────────
                if is_comparison:
                    entity_a = msg.get("entity_a", "A")
                    entity_b = msg.get("entity_b", "B")
                    comparison_elements = _build_comparison_card(data, entity_a, entity_b)
                    ai_children.extend(comparison_elements)
                else:
                    chart = _build_auto_chart(data)
                    if chart:
                        ai_children.append(
                            html.Details([
                                html.Summary("📊 View Chart", style={"fontWeight": "600", "color": TVS_BLUE, "cursor": "pointer", "outline": "none", "marginTop": "6px"}),
                                chart
                            ], open=True, style={"marginTop": "6px", "fontSize": "12px"})
                        )
            
            # ── Follow-Up Suggestion Chips ────────────────────────────
            if not msg.get("is_placeholder") and not is_error:
                q = user_query or text
                followups = _get_followup_suggestions(q)
                followup_chips = html.Div([
                    html.Button(
                        s,
                        id={"type": "chat-followup", "index": f"{msg_index}-{i}"},
                        n_clicks=0,
                        style={
                            "fontSize": "10.5px", "padding": "4px 12px", "marginRight": "6px",
                            "marginTop": "8px", "background": f"{TVS_BLUE}0A", "border": f"1px solid {TVS_BLUE}33",
                            "borderRadius": "20px", "cursor": "pointer", "color": TVS_BLUE,
                            "fontWeight": "600", "fontFamily": "Plus Jakarta Sans, sans-serif"
                        }
                    ) for i, s in enumerate(followups)
                ], style={"display": "flex", "flexWrap": "wrap"})
                ai_children.append(followup_chips)
                
            bubbles.append(
                html.Div(
                    html.Div(ai_children, className="chat-bubble chat-bubble--ai"),
                    className="chat-bubble-row chat-bubble-row--ai"
                )
            )
        msg_index += 1
    return bubbles

def tab15(df):
    header = html.Div([
        html.Div([
            html.H1("AI Chat Assistant", style={
                "fontSize": "22px", "fontWeight": "800", "color": TVS_BLUE, 
                "margin": "0", "fontFamily": "Plus Jakarta Sans, sans-serif"
            }),
            html.Div("Ask questions in natural language. Powered by Gemini, querying your local MySQL database securely.", style={
                "fontSize": "11px", "color": "#717784", "marginTop": "2px"
            })
        ]),
    ], style={
        "display": "flex", "justifyContent": "space-between", "alignItems": "center",
        "paddingBottom": "10px", "borderBottom": "1px solid #E5E7EB", "marginBottom": "14px"
    })
    
    suggestions = [
        "What is our total written premium?",
        "Show me the top 3 clients by premium",
        "Which region has the highest claim amount?",
        "List our active product categories and carriers",
        "What is our overall loss ratio?"
    ]
    
    suggestion_elements = html.Div([
        html.Button(
            s, 
            id={"type": "chat-suggestion", "index": idx}, 
            n_clicks=0,
            className="suggestion-chip"
        ) for idx, s in enumerate(suggestions)
    ], style={"display": "flex", "flexWrap": "wrap", "marginBottom": "10px"})
    
    chat_history_div = html.Div([
        dcc.Interval(
            id="chat-status-interval",
            interval=600,
            disabled=True,
            n_intervals=0
        ),
        dcc.Store(id="chat-session-id"),
        html.Div(
            id="chat-history-container",
            children=build_chat_bubbles([]),
            className="chat-history",
            style={"flex": "1", "overflowY": "auto", "marginBottom": "0px"}
        ),
    ], style={"flex": "1", "display": "flex", "flexDirection": "column", "overflow": "hidden", "marginBottom": "12px"})
    
    input_box = html.Div([
        dcc.Textarea(
            id="chat-user-input",
            placeholder="Ask anything about written premiums, claims, clients, or commissions... (e.g. 'Show me the total premium for HDFC Ergo')",
            className="chat-input-textarea",
            style={"width": "100%", "height": "60px", "minHeight": "60px", "resize": "none"}
        ),
        dcc.Textarea(
            id="pdf-executive-notes",
            placeholder="Optional: Add custom executive summary notes to Page 1 of the PDF report...",
            className="chat-input-textarea",
            style={"width": "100%", "height": "40px", "minHeight": "40px", "resize": "none", "marginTop": "8px", "fontSize": "11px", "borderColor": "#CBD5E1"}
        ),
        html.Div([
            html.Button("Clear Chat", id="btn-clear-chat", n_clicks=0, className="hdr-btn hdr-btn--outline", style={"fontSize": "11.5px", "padding": "7px 18px"}),
            html.Div([
                html.Button("Ask AI", id="btn-send-chat", n_clicks=0, className="hdr-btn hdr-btn--green", style={"fontSize": "11.5px", "padding": "7px 24px"}),
            ], style={"display": "flex", "gap": "8px"}),
        ], style={"display": "flex", "justifyContent": "space-between", "marginTop": "10px"}),
    ], style={
        "background": "white", "borderRadius": "8px", "padding": "12px",
        "border": "1px solid #E2E8F0", "boxShadow": "0 2px 8px rgba(27,59,139,0.05)", "marginTop": "4px"
    })
    
    layout = html.Div([
        header,
        html.Div("Quick Suggestions:", style={"fontSize": "12px", "fontWeight": "600", "color": "#474D5A", "marginBottom": "6px"}),
        suggestion_elements,
        chat_history_div,
        input_box
    ], className="tab-pane", style={
        "padding": "14px", "height": "calc(100vh - 100px)",
        "display": "flex", "flexDirection": "column", "gap": "0px",
    })
    
    return layout


# ─────────────────────────────────────────────
# TAB 13b — Rewind (Data Versioning & Rollback)
# ─────────────────────────────────────────────
def tab13b(df):
    if df.empty:
        return html.Div("No Data Available")
    
    # 1. Page Title & Info Banner
    header = section_title(
        "Rewind - Data Versioning & Rollback",
        "View CSV ingestion history and rollback the database state to a previous snapshot."
    )
    
    # 2. KPI Cards Row
    kpis = kpi_row(
        kpi_card("Active Policies", f"{len(df):,}", "Current master records", TVS_BLUE, id="rewind-kpi-policies"),
        kpi_card("Total Revisions", "Loading...", "Backup points stored in revisions/", TVS_ORANGE, accent=TVS_ORANGE, id="rewind-kpi-revisions"),
        kpi_card("Eligible Rollbacks", "Loading...", "Within 4-hour window", GREEN, accent=GREEN, id="rewind-kpi-eligible"),
        kpi_card("Last Activity", "Loading...", "Last system operation", PURPLE, accent=PURPLE, id="rewind-kpi-activity")
    )
    
    # 3. Main content box: History Table
    history_table = dash_table.DataTable(
        id='rewind-history-table',
        columns=[
            {'name': 'Revision ID', 'id': 'revision_id'},
            {'name': 'Backup File Name', 'id': 'filename'},
            {'name': 'Timestamp', 'id': 'timestamp'},
            {'name': 'Size (KB)', 'id': 'size'},
            {'name': 'Status', 'id': 'status'},
            {'name': 'Actions', 'id': 'actions', 'presentation': 'markdown'}
        ],
        data=[],
        style_header={
            'backgroundColor': TVS_BLUE,
            'color': 'white',
            'fontWeight': 'bold',
            'padding': '8px 12px',
            'fontSize': '12px',
            'height': 'auto',
            'textAlign': 'left'
        },
        style_cell={
            'padding': '10px 12px',
            'fontSize': '11px',
            'fontFamily': 'Plus Jakarta Sans, Inter, sans-serif',
            'textAlign': 'left',
            'border': '1px solid #E5E7EB'
        },
        style_data_conditional=[
            {'if': {'row_index': 'odd'}, 'backgroundColor': '#f9fafb'},
            {'if': {'column_id': 'status', 'filter_query': '{status} contains "Current"'},\
             'backgroundColor': '#D1FAE5', 'color': '#047857', 'fontWeight': 'bold'},
            {'if': {'column_id': 'status', 'filter_query': '{status} contains "Rolled"'},\
             'color': '#EF4444', 'textDecoration': 'line-through'},
        ],
        markdown_options={'link_target': '_self'}
    )
    
    table_card = content_box([
        html.Div([
            html.Div([
                html.Div("Available Backups & Ingestion Registry", style={"fontSize": "13px", "fontWeight": "800", "color": TVS_BLUE}),
                html.P("To rollback, select a target state from the list. The system will restore the database to match that revision.", style={"fontSize": "10px", "color": "#6B7280", "margin": "0"}),
            ], style={"flex": 1}),
            # Refresh button
            html.Button(
                "Refresh History",
                id="btn-refresh-rewind",
                n_clicks=0,
                className="hdr-btn hdr-btn--outline",
                style={"fontSize": "11px", "padding": "4px 12px"}
            )
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "12px"}),
        history_table
    ], style={"padding": "16px", "boxShadow": "var(--shadow-sm)", "marginTop": "14px"})
    
    # 4. Confirmation Modal
    rollback_modal = dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(
            "Confirm Database Rollback",
            style={"color": "white", "fontWeight": "bold"}
        ), style={"backgroundColor": TVS_ORANGE}),
        dbc.ModalBody(id="rollback-modal-body"),
        dbc.ModalFooter([
            dbc.Button("Cancel & Stay Safe", id="btn-cancel-rollback", className="me-2", n_clicks=0, color="secondary"),
            dbc.Button("Yes, Rollback Database", id="btn-confirm-rollback", n_clicks=0, color="danger")
        ])
    ], id="rollback-modal", is_open=False, size="lg")
    
    # 5. Success Modal
    success_modal = dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle(
            "Rollback Success",
            style={"color": "white", "fontWeight": "bold"}
        ), style={"backgroundColor": "#10B981"}),
        dbc.ModalBody(id="rollback-success-modal-body"),
        dbc.ModalFooter(
            dbc.Button("Dismiss", id="btn-close-rollback-success", className="ms-auto", n_clicks=0, color="success")
        )
    ], id="rollback-success-modal", is_open=False, size="md")
    
    # 6. Global status alerts wrapper
    status_alert = html.Div(id="rollback-status-message", style={"marginTop": "10px"})
    
    # Return as tab layout
    return html.Div([
        header,
        kpis,
        table_card,
        rollback_modal,
        success_modal,
        status_alert,
        # Store to pass selected revision filename between callbacks
        dcc.Store(id="selected-revision-store")
    ], className="tab-pane", style={"padding": "14px", "height": "100%", "display": "flex", "flexDirection": "column", "gap": "0px"})


