from dash import html, dcc
import dash_bootstrap_components as dbc

TVS_BLUE   = "#1B3B8B"
TVS_ORANGE = "#E55B13"

# ── Tab group definitions ─────────────────────────────────────────────────────
TAB_GROUPS = [
    {
        "label": "Overview",
        "icon": "▦",
        "tabs": [
            {"label": "Executive Summary", "value": "tab-1"},
            {"label": "Growth & Renewals", "value": "tab-2"},
            {"label": "Targeting Engine", "value": "tab-2b"},
        ],
    },
    {
        "label": "Clients",
        "icon": "●",
        "tabs": [
            {"label": "Channel Mix",  "value": "tab-6b"},
            {"label": "Top Clients",  "value": "tab-6"},
        ],
    },
    {
        "label": "Products",
        "icon": "◈",
        "tabs": [
            {"label": "Product Mix",      "value": "tab-5"},
            {"label": "Carrier Scorecard","value": "tab-5b"},
        ],
    },
    {
        "label": "Portfolio",
        "icon": "◎",
        "tabs": [
            {"label": "Portfolio Renewals", "value": "tab-9"},
            {"label": "Churn & Vintage",    "value": "tab-10"},
        ],
    },
    {
        "label": "Risk",
        "icon": "⚠",
        "tabs": [
            {"label": "High Risk Register","value": "tab-4b"},
        ],
    },
    {
        "label": "Claims",
        "icon": "⚕",
        "tabs": [
            {"label": "Claims Overview",  "value": "tab-3"},
            {"label": "Claims Breakdown", "value": "tab-3b"},
        ],
    },
    {
        "label": "Profitability",
        "icon": "₹",
        "tabs": [
            {"label": "Profitability Trends", "value": "tab-7"},
            {"label": "Margin Analysis",      "value": "tab-8"},
        ],
    },
    {
        "label": "Regional",
        "icon": "⊕",
        "tabs": [
            {"label": "Regional Analytics", "value": "tab-11"},
        ],
    },
    {
        "label": "Explorer",
        "icon": "⊞",
        "tabs": [
            {"label": "Pivot Explorer", "value": "tab-12"},
        ],
    },
    {
        "label": "Leads",
        "icon": "⟳",
        "tabs": [
            {"label": "Sales Pipeline", "value": "tab-14"},
        ],
    },
    {
        "label": "Data Manager",
        "icon": "⛃",
        "tabs": [
            {"label": "Data Source", "value": "tab-13"},
        ],
    },
]


def serve_layout():

    # ── SIDEBAR ───────────────────────────────────────────────────────────────
    sidebar = html.Div([



        # ── Nav label ─────────────────────────────────────────────────────────
        html.Div("NAVIGATION", className="sidebar-nav-label"),

        # ── Nav group buttons (vertical) ──────────────────────────────────────
        html.Div([
            html.Button(
                [
                    html.Span(g["icon"], className="nav-icon"),
                    html.Span(g["label"], className="nav-label"),
                ],
                id=f"nav-group-btn-{i}",
                className="nav-group-btn",
                **{"data-group": str(i)},
                n_clicks=0,
            ) for i, g in enumerate(TAB_GROUPS)
        ], id="nav-group-row"),

        # ── Footer ────────────────────────────────────────────────────────────
        html.Div([
            html.Div("IRDAI Broker No.", className="sidebar-footer-text", style={
                "fontSize": "8px", "color": "rgba(255,255,255,0.28)",
                "letterSpacing": "0.8px", "textTransform": "uppercase", "marginBottom": "2px",
            }),
            html.Div("DB-392/08", className="sidebar-footer-text", style={
                "fontSize": "10px", "color": "rgba(255,255,255,0.50)", "fontWeight": "600",
            }),
            html.Div("Simplified Insurance Solutions", className="sidebar-footer-text", style={
                "fontSize": "8px", "color": "rgba(255,255,255,0.25)", "marginTop": "4px",
            }),
        ], className="sidebar-footer"),

        dcc.Store(id="active-group-store", data=0),

    ], className="sidebar")

    # ── TOP BAR ───────────────────────────────────────────────────────────────
    topbar = html.Div([

        # Left: Brand + breadcrumb + sub-tab pills
        html.Div([
            html.Div(
                html.Img(src="/assets/tvs_logo_final.png", style={"height": "32px", "width": "auto", "display": "block", "objectFit": "contain"}),
                style={"paddingRight": "24px", "marginRight": "20px", "borderRight": "2px solid var(--tvs-orange)", "display": "flex", "alignItems": "center", "height": "100%"}
            ),
            html.Div([
                html.Div(id="sub-tab-context", className="topbar-breadcrumb"),
            html.Div([
                dcc.RadioItems(
                    id="tab-selector",
                    options=TAB_GROUPS[0]["tabs"],
                    value="tab-1",
                    inline=True,
                    inputStyle={"display": "none"},
                    labelStyle={
                        "padding": "4px 14px",
                        "cursor": "pointer",
                        "fontWeight": "600",
                        "fontSize": "11px",
                        "color": "#6B7280",
                        "borderRadius": "20px",
                        "marginRight": "4px",
                        "fontFamily": "DM Sans, Inter, sans-serif",
                        "userSelect": "none",
                        "display": "inline-block",
                        "transition": "all 0.18s",
                    },
                    className="dash-tab-radio",
                ),
                ], id="sub-tab-strip"),
            ], style={"display": "flex", "flexDirection": "column", "justifyContent": "center"}),
        ], className="topbar-left", style={"flexDirection": "row", "alignItems": "center", "justifyContent": "flex-start"}),

        # Right: ICR chip + record count + divider + actions
        html.Div([

            html.Div(id="header-icr-kpi", className="topbar-kpi-chip"),

            html.Div(id="header-record-count", className="topbar-record-count"),

            html.Div(className="topbar-divider"),

            html.Div(id='upload-status', style={"display": "none"}),

            html.Button([
                "Clear",
            ], id="btn-clear-upload", n_clicks=0, className="hdr-btn hdr-btn--outline"),

            html.Button([
                "Refresh",
            ], id="btn-refresh-data", n_clicks=0, className="hdr-btn hdr-btn--green"),

        ], className="topbar-right"),

    ], id="main-header", className="topbar")

    # ── FULL PAGE ASSEMBLY ────────────────────────────────────────────────────
    content = html.Div([
        dcc.Store(id='uploaded-data-store'),
        dcc.Store(id='uploaded-raw-data-store'),
        dcc.Store(id='uploaded-filename-store'),
        dcc.Store(id='uploaded-schema-mapping-store'),
        dcc.Store(id='refresh-trigger'),

        # Top Navigation spanning full width
        topbar,

        # Bottom Area: Sidebar + Main Content
        html.Div([
            sidebar,
            html.Div([
                html.Div([
                    dcc.Loading(
                        html.Div(id="tab-content", style={"display": "flex", "flexDirection": "column"}),
                        type="circle",
                        color=TVS_ORANGE,
                    )
                ], className="scroll-wrapper", style={"flex": 1, "minHeight": 0, "padding": "8px 12px"})
            ], className="main-content")
        ], style={"display": "flex", "flex": 1, "overflow": "hidden"}),

        # Drilldown modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(
                id="drilldown-modal-title",
                style={"color": "white", "fontWeight": "bold"},
            )),
            dbc.ModalBody(id="drilldown-modal-body"),
            dbc.ModalFooter(
                dbc.Button("Close", id="btn-close-drilldown", className="ms-auto", n_clicks=0)
            )
        ], id="drilldown-modal", size="xl", is_open=False, scrollable=True),

        # Schema Validation Error Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(
                "Data Upload Failed",
                style={"color": "white", "fontWeight": "bold"}
            ), style={"backgroundColor": "#EF4444"}),
            dbc.ModalBody(id="schema-error-modal-body"),
            dbc.ModalFooter(
                dbc.Button("Close", id="btn-close-schema-error", className="ms-auto", n_clicks=0, color="danger")
            )
        ], id="schema-error-modal", is_open=False, size="lg"),

        # Ingestion Result Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(
                "Database Ingestion Summary",
                style={"color": "white", "fontWeight": "bold"}
            ), style={"backgroundColor": "#10B981"}),
            dbc.ModalBody(id="ingestion-result-modal-body"),
            dbc.ModalFooter(
                dbc.Button("Close", id="btn-close-ingestion-result", className="ms-auto", n_clicks=0, color="success")
            )
        ], id="ingestion-result-modal", is_open=False, size="lg"),

    ], id="page-content")

    return content
