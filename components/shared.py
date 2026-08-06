"""
components/shared.py
====================
Shared constants, helpers, and rendering functions used across all pages
of the Financial Planner application.

Extracted from planning_app.py so that each page module can import from
a single source of truth rather than duplicating code.

Now integrated with the unified theme system from components/theme.py
"""
from __future__ import annotations

from typing import cast
import datetime
import calendar as _calendar

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from streamlit_extras.add_vertical_space import add_vertical_space

from load_data import (
    get_networth_by_month,
    get_networth_by_month,
    render_networth,
    save_networth_cache,
)
from portfolio import render_portfolio, save_portfolio_cache, get_effective_portfolio_month_year

# Import theme system
try:
    from components.theme import Colors, ChartConfig
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False

# ---------------------------------------------------------------------------
# App-wide CSS injected once per page load
# ---------------------------------------------------------------------------
HIDE_ST_STYLE = """
    <style>
    MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    #header {visibility: hidden;}
    [data-testid="stMetricValue"] {
      font-size: 24px;
    }
    /* Center align all dataframe columns */
    [data-testid="stDataFrame"] td,
    [data-testid="stDataFrame"] th,
    [data-testid="stDataFrameResizable"] td,
    [data-testid="stDataFrameResizable"] th,
    div[data-testid="stDataFrame"] table td,
    div[data-testid="stDataFrame"] table th,
    div[data-testid="stDataFrameResizable"] table td,
    div[data-testid="stDataFrameResizable"] table th,
    .stDataFrame td,
    .stDataFrame th,
    .dataframe td,
    .dataframe th {
      text-align: center !important;
    }
    [data-testid="stDataFrame"] [data-testid="StyledDataFrameRowHeaderCell"],
    [data-testid="stDataFrame"] [data-testid="StyledDataFrameDataCell"],
    [data-testid="stDataFrameResizable"] [data-testid="StyledDataFrameRowHeaderCell"],
    [data-testid="stDataFrameResizable"] [data-testid="StyledDataFrameDataCell"] {
      text-align: center !important;
    }
    </style>
"""

# ---------------------------------------------------------------------------
# Color palette — consistent across all charts (with theme integration)
# ---------------------------------------------------------------------------
if THEME_AVAILABLE:
    COLOR_PALETTE = ChartConfig.get_palette()
    COLOR_SCALE = ChartConfig.get_color_scale()
else:
    # Fallback to original colors
    COLOR_PALETTE = px.colors.qualitative.Pastel
    COLOR_SCALE = [
        [0.0, "rgb(246, 207, 113)"],   # Pastel yellow  (low)
        [0.5, "rgb(180, 151, 231)"],   # Pastel purple  (mid)
        [1.0, "rgb(139, 224, 164)"],   # Pastel green   (high)
    ]

# Account type → internal key mapping
ACCOUNT_TYPE_MAP: dict[str, str] = {
    'Cash': 'cash',
    'Savings': 'cash',  # Savings accounts are treated as cash/emergency funds
    'Brokerage': 'taxable',
    'Traditional': 'tax_deferred',
    'Roth': 'tax_free',
}

# ---------------------------------------------------------------------------
# Life stage descriptions
# ---------------------------------------------------------------------------
LIFE_STAGE_DESCRIPTIONS: dict[str, str] = {
    "Stage 1: Accumulation": (
        "🏗️ Building wealth while working.\n\n"
        "You're still earning wages. The plan routes your paycheck into a "
        "Traditional 401k (pre-tax), Roth account, and brokerage at the rates "
        "you configured. Any leftover take-home above your cash target goes to "
        "brokerage. Roth conversions are considered if you're in a low bracket."
    ),
    "Stage 2: Prep for Retirement": (
        "🎯 Fine-tuning before you retire (within ~10 years).\n\n"
        "Still working, but now the focus shifts to balance. If your Traditional "
        "account is much larger than your Roth, new 401k contributions are "
        "redirected to Roth. A backdoor Roth IRA is executed if your income is "
        "too high for a direct contribution. Your cash buffer gradually ramps up "
        "toward the full retirement reserve target."
    ),
    "Stage 3: Early Retirement": (
        "🌅 Retired but before Medicare & Social Security.\n\n"
        "No wages yet. Living expenses come from your brokerage account first "
        "(long-term capital gains taxed at 0% when possible). This is the prime "
        "window for large Roth conversions — income is low, so you fill up lower "
        "tax brackets cheaply. ACA marketplace health insurance costs are managed "
        "to preserve subsidy eligibility."
    ),
    "Stage 4: Medicare": (
        "🏥 On Medicare, still before Social Security.\n\n"
        "Medicare Part B/D premiums are now in play, including IRMAA surcharges "
        "if your income from 2 years ago was high. Roth conversions continue but "
        "are sized carefully to avoid jumping an IRMAA tier. The goal is to keep "
        "converting while your income is still relatively low."
    ),
    "Stage 5: Social Security": (
        "💰 Collecting Social Security + Medicare.\n\n"
        "SS benefits add a new income stream — up to 85% of benefits are taxable. "
        "Roth conversions are still possible but must account for the 'SS torpedo' "
        "effect where extra income makes more SS taxable. IRMAA management remains "
        "important. Withdrawals shift toward a mix of brokerage and traditional."
    ),
    "Stage 6: RMD": (
        "📋 Required Minimum Distributions are mandatory.\n\n"
        "The IRS requires you to withdraw a minimum amount from your Traditional "
        "accounts each year based on your age and balance. These withdrawals are "
        "fully taxable. The strategy focuses on minimizing the tax hit by "
        "coordinating RMDs with other income, using DAF charitable contributions "
        "to offset taxes, and preserving Roth assets as long as possible."
    ),
}

_STAGE_COLUMN_HELP = (
    "The life stage determines which financial priorities and rules apply this year. "
    "Hover over the stage name in the legend below the table for a plain-English summary."
)

# Shared column config for account balance tables
BALANCE_COLUMN_CONFIG: dict = {
    "Year": st.column_config.NumberColumn("Year", format="%d"),
    "Cash Balance": st.column_config.TextColumn("Cash"),
    "Taxable Balance": st.column_config.TextColumn("Taxable"),
    "Traditional Balance": st.column_config.TextColumn("Traditional"),
    "Roth Balance": st.column_config.TextColumn("Roth"),
    "DAF Balance": st.column_config.TextColumn("DAF"),
    "Total Portfolio": st.column_config.TextColumn("Total Portfolio"),
}

# ---------------------------------------------------------------------------
# Net worth statement style constants
# ---------------------------------------------------------------------------
_ACCOUNT_TYPE_LABELS: dict[str, str] = {
    "Savings":     "Savings",
    "Cash":        "Cash",
    "Brokerage":   "Investment",
    "Traditional": "Tax Deferred",
    "Roth":        "Tax Free",
    "Real Estate": "Real Estate",
}

_ACCOUNT_TYPE_ORDER: list[str] = [
    "Savings", "Cash", "Brokerage", "Traditional", "Roth", "Real Estate"
]

_ACCOUNT_TYPE_COLORS: dict[str, str] = {
    "Savings":     "rgba(135, 206, 250, 0.35)",
    "Cash":        "rgba(246, 207, 113, 0.35)",
    "Brokerage":   "rgba(254, 136, 177, 0.35)",
    "Traditional": "rgba(139, 224, 164, 0.35)",
    "Roth":        "rgba(180, 151, 231, 0.35)",
    "Real Estate": "rgba(255, 190, 122, 0.35)",
}

_ACCOUNT_TYPE_ACCENT: dict[str, str] = {
    "Savings":     "rgb(135, 206, 250)",
    "Cash":        "rgb(246, 207, 113)",
    "Brokerage":   "rgb(254, 136, 177)",
    "Traditional": "rgb(139, 224, 164)",
    "Roth":        "rgb(180, 151, 231)",
    "Real Estate": "rgb(255, 190, 122)",
}

_NW_STYLES: dict[str, str] = {
    "hdr_bg":   "#1a1a2e",
    "hdr_fg":   "white",
    "total_bg": "#e8f4fd",
    "summ_bg":  "#f8f9fa",
    "pos_clr":  "#21c354",
    "neg_clr":  "#ff4b4b",
    "border":   "1px solid #dee2e6",
}


# ---------------------------------------------------------------------------
# Currency formatting helpers
# ---------------------------------------------------------------------------

def format_currency(val) -> str:
    """Format a numeric value as currency (no decimals for whole numbers)."""
    if pd.isna(val):
        return ""
    
    # Handle string values that are already formatted
    if isinstance(val, str):
        return val
    
    try:
        # Convert to float first to handle any numeric type
        num_val = float(val)
        if num_val == int(num_val):
            return f"${int(num_val):,}"
        return f"${num_val:,.2f}"
    except (TypeError, ValueError, OverflowError):
        return ""


def _fmt_currency(v: float) -> str:
    """Accounting-style currency: negatives in parentheses, always 2 dp."""
    if v < 0:
        return f"$({abs(v):,.2f})"
    return f"${v:,.2f}"


def _change_style(v: float, styles: dict[str, str]) -> str:
    clr = styles["pos_clr"] if v >= 0 else styles["neg_clr"]
    return f"color:{clr};font-weight:600"


# ---------------------------------------------------------------------------
# Net worth HTML builder helpers
# ---------------------------------------------------------------------------

def _nw_header_row(styles: dict[str, str]) -> str:
    bg, fg = styles["hdr_bg"], styles["hdr_fg"]
    return (
        f'<tr style="background:{bg};color:{fg};font-size:12px;'
        f'text-transform:uppercase;letter-spacing:.05em;">'
        f'<th style="padding:8px 12px;text-align:left;">Type</th>'
        f'<th style="padding:8px 12px;text-align:right;">Type Total</th>'
        f'<th style="padding:8px 12px;text-align:right;">Account Total</th>'
        f'<th style="padding:8px 12px;text-align:left;">Account</th>'
        f'</tr>'
    )


def _acct_cells(value: float, name: str, td_r: str, td_l: str) -> str:
    return (
        f'<td {td_r}>{_fmt_currency(value)}</td>'
        f'<td {td_l}>{name}</td>'
    )


def _nw_type_rows(
    acct_type: str,
    accounts: pd.DataFrame,
    styles: dict[str, str],
) -> list[str]:
    label      = _ACCOUNT_TYPE_LABELS.get(acct_type, acct_type)
    type_total = float(accounts["market_value"].sum())
    row_bg     = _ACCOUNT_TYPE_COLORS.get(acct_type, "rgba(240,242,246,0.4)")
    accent     = _ACCOUNT_TYPE_ACCENT.get(acct_type, "#cccccc")
    border     = styles["border"]
    n          = len(accounts)

    _td_base = f"padding:6px 12px;border:{border};background:{row_bg};"
    td_r     = f'style="{_td_base}text-align:right;"'
    td_l     = f'style="{_td_base}text-align:left;"'
    td_span  = f'style="{_td_base}border-left:4px solid {accent};text-align:left;font-weight:700;vertical-align:middle;"'
    td_total = f'style="{_td_base}text-align:right;font-weight:600;vertical-align:middle;"'

    fmt_total = _fmt_currency(type_total)
    first = accounts.iloc[0]
    rows: list[str] = [
        f'<tr>'
        f'<td rowspan="{n}" {td_span}>{label}</td>'
        f'<td rowspan="{n}" {td_total}>{fmt_total}</td>'
        + _acct_cells(float(first["market_value"]), str(first["account_name"]), td_r, td_l)
        + '</tr>'
    ]
    for row in accounts.iloc[1:].itertuples(index=False):
        rows.append(
            '<tr>'
            + _acct_cells(float(row.market_value), row.account_name, td_r, td_l)
            + '</tr>'
        )
    return rows


def _nw_total_row(grand_total: float, mom_change: float, styles: dict[str, str]) -> str:
    border    = styles["border"]
    total_bg  = styles["total_bg"]
    chg_style = _change_style(mom_change, styles)
    return (
        f'<tr style="background:{total_bg};font-weight:700;font-size:14px;">'
        f'<td style="padding:8px 12px;border:{border};text-align:left;">Total net worth</td>'
        f'<td style="padding:8px 12px;border:{border};text-align:right;">{_fmt_currency(grand_total)}</td>'
        f'<td style="padding:8px 12px;border:{border};text-align:right;{chg_style}">Change from last month</td>'
        f'<td style="padding:8px 12px;border:{border};text-align:right;{chg_style}">{_fmt_currency(mom_change)}</td>'
        f'</tr>'
    )


def _nw_summary_row(label: str, value: float, styles: dict[str, str]) -> str:
    border    = styles["border"]
    summ_bg   = styles["summ_bg"]
    chg_style = _change_style(value, styles)
    return (
        f'<tr style="background:{summ_bg};">'
        f'<td colspan="2" style="padding:6px 12px;border:{border};text-align:left;'
        f'font-style:italic;">{label}</td>'
        f'<td colspan="2" style="padding:6px 12px;border:{border};text-align:right;'
        f'{chg_style}">{_fmt_currency(value)}</td>'
        f'</tr>'
    )


def _compute_net_worth_summary(networth: pd.DataFrame) -> dict:
    """Compute MoM, YTD, and rolling-12-month summary figures."""
    current_total = float(networth["total"].iloc[-1])
    prior_total   = float(networth["total"].iloc[-2])
    mom_change    = current_total - prior_total

    dti: pd.DatetimeIndex = pd.DatetimeIndex(networth.index)
    curr_year_mask = dti.year == dti[-1].year  # type: ignore[union-attr]
    ytd_start_val  = (
        float(networth.loc[curr_year_mask, "total"].iloc[0])
        if curr_year_mask.any()
        else current_total
    )
    ytd_gain = current_total - ytd_start_val

    twelve_ago    = dti[-1] - pd.DateOffset(months=12)
    older         = networth.loc[networth.index <= twelve_ago]
    rolling_start = (
        float(older["total"].iloc[-1])
        if not older.empty
        else float(networth["total"].iloc[0])
    )
    rolling_gain = current_total - rolling_start

    return dict(
        current_total=current_total,
        mom_change=mom_change,
        ytd_gain=ytd_gain,
        rolling_gain=rolling_gain,
        as_of=dti[-1],
    )


def _build_net_worth_html(
    acct_grp: pd.DataFrame,
    summary: dict,
    styles: dict[str, str] = _NW_STYLES,
) -> str:
    rows: list[str] = [_nw_header_row(styles)]
    for acct_type in _ACCOUNT_TYPE_ORDER:
        accounts = acct_grp.loc[acct_grp["account_type"] == acct_type]
        if accounts.empty:
            continue
        rows.extend(_nw_type_rows(acct_type, accounts, styles))
    rows.append(_nw_total_row(summary["current_total"], summary["mom_change"], styles))
    rows.append(_nw_summary_row("Year to date gains (losses)",     summary["ytd_gain"],     styles))
    rows.append(_nw_summary_row("Rolling 12 month gains (losses)", summary["rolling_gain"], styles))
    as_of = summary["as_of"].strftime("%B %Y")
    return (
        f'<h4 style="margin-bottom:6px;">📊 Net Worth Statement — {as_of}</h4>'
        f'<table style="width:100%;border-collapse:collapse;font-size:13px;">'
        + "".join(rows)
        + "</table>"
    )


def _get_real_estate_rows() -> pd.DataFrame:
    """Load real estate properties from config as account-detail rows."""
    _empty = pd.DataFrame({
        "account_type": pd.Series(dtype=str),
        "account_name": pd.Series(dtype=str),
        "market_value": pd.Series(dtype=float),
    })
    try:
        from config import get_config_manager
        cfg = get_config_manager()
        properties = cfg.get("real_estate", "properties", [])
        if not properties:
            return _empty
        rows = []
        for prop in properties:
            name = prop.get("property_name", "Property")
            price = float(prop.get("purchase_price", 0) or 0)
            rows.append({
                "account_type": "Real Estate",
                "account_name": name,
                "market_value": price,
            })
        return pd.DataFrame(rows)
    except Exception as exc:
        st.warning(f"Could not load real estate config: {exc}")
        return _empty


def render_net_worth_statement(
    networth: pd.DataFrame,
    detailed_df: pd.DataFrame,
) -> None:
    """Render a hierarchical net worth statement (Type | Type Total | Account Total | Account)."""
    if len(networth) < 2:
        st.warning("Need at least 2 months of data to compute net worth changes.")
        return
    if detailed_df.empty:
        st.warning("No account detail data available for net worth statement.")
        return

    re_rows = _get_real_estate_rows()
    combined_df = pd.concat([detailed_df, re_rows], ignore_index=True) if not re_rows.empty else detailed_df

    acct_grp: pd.DataFrame = pd.DataFrame(
        combined_df
        .groupby(["account_type", "account_name"], as_index=False)["market_value"]
        .sum()
    )

    re_total = re_rows["market_value"].sum()
    nw_augmented = networth.copy()
    if re_total > 0:
        nw_augmented.at[nw_augmented.index[-1], "total"] += re_total

    summary = _compute_net_worth_summary(nw_augmented)
    html    = _build_net_worth_html(acct_grp, summary)
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Chart rendering helpers
# ---------------------------------------------------------------------------

def render_balance_chart(balances_df: pd.DataFrame, title: str = "Projected Account Balances") -> None:
    """Render a stacked-area chart for Cash / Taxable / Traditional / Roth balances."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=balances_df['Year'], y=balances_df['Cash Balance'],
        name='Cash', mode='lines', stackgroup='one',
        fillcolor='rgb(246, 207, 113)'
    ))
    fig.add_trace(go.Scatter(
        x=balances_df['Year'], y=balances_df['Taxable Balance'],
        name='Taxable', mode='lines', stackgroup='one',
        fillcolor='rgb(254, 136, 177)'
    ))
    fig.add_trace(go.Scatter(
        x=balances_df['Year'], y=balances_df['Traditional Balance'],
        name='Traditional', mode='lines', stackgroup='one',
        fillcolor='rgb(139, 224, 164)'
    ))
    fig.add_trace(go.Scatter(
        x=balances_df['Year'], y=balances_df['Roth Balance'],
        name='Roth', mode='lines', stackgroup='one',
        fillcolor='rgb(180, 151, 231)'
    ))
    fig.update_layout(
        title=title,
        xaxis_title='Year',
        yaxis_title='Balance ($)',
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    st.plotly_chart(fig, use_container_width=True)


def render_income_chart(strategy_df: pd.DataFrame, title: str = "Income Sources by Year") -> None:
    """Render a stacked area chart of all income sources over time.

    Income layers (rendered bottom-to-top):
      1. Wages / Salary
      2. Social Security (SSI)
      3. Pension / Annuity
      4. Rental income
      5. Interest income (taxable + tax-exempt)
      6. Dividends
      7. Brokerage positions sold to cash (LTCG harvesting — basis + gains)
      8. Brokerage account withdrawals (Brok→Cash)
      9. Traditional IRA/401k withdrawals (Trad→Cash, incl. RMDs)
     10. Roth IRA/401k distributions (Roth→Cash)

    The function is resilient — any layer whose column is absent or all-zero
    is simply omitted, so it works for both accumulation and withdrawal phases.
    """
    if strategy_df.empty or 'Year' not in strategy_df.columns:
        return

    def _s(col: str) -> "pd.Series":
        """Return a non-negative series for *col*, zero-filled if absent."""
        if col in strategy_df.columns:
            return pd.to_numeric(strategy_df[col], errors='coerce').fillna(0).clip(lower=0)
        return pd.Series(0.0, index=strategy_df.index)

    years = strategy_df['Year']

    # -----------------------------------------------------------------------
    # Define each income layer: (label, series, hex-color)
    # -----------------------------------------------------------------------
    layers = [
        # Wages / earned income
        ("Wages / Salary",          _s('Wages'),            '#2ecc71'),
        # Social Security — column name differs slightly across phases
        ("Social Security (SSI)",
         _s('SS Benefits') if _s('SS Benefits').sum() > 0 else _s('Social Security'),
         '#3498db'),
        # Pension / annuity  (column written by Stage 5 / config if present)
        ("Pension / Annuity",       _s('Pension'),          '#9b59b6'),
        # Rental income
        ("Rental Income",           _s('Rental Income'),    '#16a085'),
        # Interest income (savings, bonds, CDs)
        ("Interest Income",         _s('Interest Income'),  '#1abc9c'),
        # Dividends (taxable brokerage dividends)
        ("Dividends",               _s('Dividends'),        '#f39c12'),
        # Brokerage withdrawal — split into its two tax components so the chart
        # shows the taxable (LTCG) portion vs. the tax-free basis return.
        # These two slices sum to Brok→Cash exactly; Brok→Cash is NOT added
        # separately (that would double-count the same dollars).
        ("Brokerage — Basis Returned",  _s('Basis Returned'),   '#e67e22'),
        ("Brokerage — Gains (LTCG)",    _s('LTCG Harvested'),   '#e74c3c'),
        # Traditional IRA / 401k withdrawals (direct cash withdrawals, excl. RMDs)
        ("Traditional Withdrawal",  _s('Trad→\nCash'),      '#d35400'),
        # RMDs — shown separately when the Trad→Cash column already excludes them;
        # if Trad→Cash already includes RMDs (single-column engines) this will be 0
        ("RMD",                     _s('RMD'),              '#e74c3c'),
        # Roth IRA / 401k distributions
        ("Roth Distribution",       _s('Roth→\nCash'),      '#8e44ad'),
    ]

    # Deduplicate Trad→Cash vs RMD: some strategy engines roll RMDs into
    # Trad→Cash and set RMD separately.  If both are non-zero and their sum
    # would double-count, prefer the explicit Trad→Cash (which already includes
    # the RMD) and zero-out the standalone RMD layer.
    trad_cash_total = _s('Trad→\nCash').sum()
    rmd_total       = _s('RMD').sum()
    if trad_cash_total > 0 and rmd_total > 0 and trad_cash_total >= rmd_total * 0.9:
        # Trad→Cash subsumes RMDs — drop the standalone RMD layer
        layers = [(lbl, s, c) for lbl, s, c in layers if lbl != "RMD"]

    # Optional: Roth conversions toggle
    roth_conv_series = _s('Trad→\nRoth')
    show_conversions = False
    if roth_conv_series.sum() > 500:
        show_conversions = st.checkbox(
            "Include Roth Conversions",
            value=False,
            help=(
                "Roth conversions move money from Traditional to Roth — they are not spendable "
                "income but do appear on your tax return as ordinary income. Toggle on to see "
                "how conversions affect the total income picture each year."
            ),
        )
        if show_conversions:
            layers.append(("Roth Conversion (Trad→Roth)", roth_conv_series, '#c0392b'))

    # Keep only layers with meaningful values (> $500 across the whole period)
    layers = [(lbl, s, c) for lbl, s, c in layers if s.sum() > 500]

    if not layers:
        st.caption("No income data available to display for this phase.")
        return

    fig = go.Figure()

    for label, series, color in layers:
        # Convert hex to rgba for fill transparency
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        fill_color = f"rgba({r},{g},{b},0.75)"
        line_color = f"rgba({r},{g},{b},1.0)"

        fig.add_trace(go.Scatter(
            x=years,
            y=series,
            name=label,
            mode='lines',
            stackgroup='income',
            line=dict(width=1, color=line_color),
            fillcolor=fill_color,
            hovertemplate=f'<b>{label}</b><br>Year %{{x}}: $%{{y:,.0f}}<extra></extra>',
        ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color='#333')),
        xaxis_title='Year',
        yaxis_title='Annual Income ($)',
        hovermode='x unified',
        height=430,
        margin=dict(l=20, r=20, t=55, b=20),
        plot_bgcolor='white',
        paper_bgcolor='white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        yaxis=dict(tickformat='$,.0f', gridcolor='#eee'),
        xaxis=dict(gridcolor='#eee'),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_balance_table(balances_df: pd.DataFrame) -> None:
    """Render a formatted account balances dataframe."""
    display = balances_df.copy()
    balance_cols = ['Cash Balance', 'Taxable Balance', 'Traditional Balance',
                    'Roth Balance', 'DAF Balance', 'Total Portfolio']
    for col in balance_cols:
        if col in display.columns:
            display[col] = pd.Series(pd.to_numeric(display[col], errors='coerce')).map(format_currency)
    st.dataframe(display, column_config=BALANCE_COLUMN_CONFIG, hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# Historical net worth builder (cached)
# ---------------------------------------------------------------------------

def _build_networth_row(date: pd.Timestamp, summary_df: pd.DataFrame) -> dict:
    account_totals = (
        summary_df[summary_df['account_type'].isin(list(ACCOUNT_TYPE_MAP.keys()))]
        .groupby('account_type')['market_value']
        .sum()
        .reindex(list(ACCOUNT_TYPE_MAP.keys()), fill_value=0.0)
    )
    row_data = {ACCOUNT_TYPE_MAP[str(k)]: v for k, v in account_totals.items()}
    row_data['total'] = account_totals.sum()
    row_data['date'] = date
    return row_data


@st.cache_data(ttl=300)
def build_historical_networth(num_months: int = 12) -> pd.DataFrame:
    """Build historical net worth DataFrame using get_networth_by_month."""
    end_date = pd.Timestamp.today().normalize().replace(day=1)
    start_date = end_date - pd.DateOffset(months=num_months - 1)
    date_range = pd.date_range(start=start_date, end=end_date, freq='MS')

    networth_rows = []
    for date in date_range:
        try:
            _, summary_df = get_networth_by_month(date.month, date.year)
            if summary_df.empty:
                continue
            networth_rows.append(_build_networth_row(date, summary_df))
        except (ValueError, RuntimeError) as e:
            st.warning(f"Could not fetch data for {date.strftime('%m/%Y')}: {e}")
            continue

    if networth_rows:
        return (
            pd.DataFrame.from_records(
                networth_rows,
                index='date',
                columns=['date', 'cash', 'taxable', 'tax_deferred', 'tax_free', 'total']
            )
            .sort_index()
        )
    else:
        return pd.DataFrame(
            data={col: pd.Series(dtype=float) for col in ['cash', 'taxable', 'tax_deferred', 'tax_free', 'total']}
        ).set_index(pd.DatetimeIndex([], name='date'))


# ---------------------------------------------------------------------------
# Shared page initialisation helpers
# ---------------------------------------------------------------------------

def init_page_minimal(title: str = "Financial Planner", icon: str = "😊") -> None:
    """Lightweight page setup: config + CSS only — no data fetching.

    Use this on pages that do not display portfolio or net worth data so they
    do not trigger unnecessary background yfinance rebuilds.

    Pages that need portfolio/net-worth data should call :func:`init_page`
    instead.
    """
    from config import ConfigManager

    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    st.markdown(HIDE_ST_STYLE, unsafe_allow_html=True)

    config_mgr = ConfigManager()
    st.session_state["filing_status"] = config_mgr.get_filing_status()


def init_page(title: str = "Financial Planner", icon: str = "😊") -> tuple[pd.DataFrame, pd.DataFrame, bool, str, int, int, int, int]:
    """
    Perform all shared page setup: config, CSS, background data loads.

    Returns
    -------
    networth : pd.DataFrame
        Historical net worth (12 months).
    portfolio_df : pd.DataFrame
        Current portfolio display DataFrame.
    portfolio_cache_ready : bool
        True when portfolio data is available.
    stale_label : str
        Human-readable label when portfolio data is from a prior month.
    curr_month : int
    curr_year : int
    eff_port_month : int
    eff_port_year : int
    """
    import threading as _threading
    from config import ConfigManager

    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    st.markdown(HIDE_ST_STYLE, unsafe_allow_html=True)

    # Load configuration and determine filing status
    config_mgr = ConfigManager()
    filing_status = config_mgr.get_filing_status()
    
    # Store filing status in session state for easy access
    st.session_state["filing_status"] = filing_status

    currentDate = datetime.date.today()
    curr_year   = currentDate.year
    curr_month  = currentDate.month

    eff_port_month, eff_port_year = get_effective_portfolio_month_year(curr_month, curr_year)
    portfolio_data_stale = (eff_port_month != curr_month or eff_port_year != curr_year)
    stale_label = (
        f"{_calendar.month_name[eff_port_month]} {eff_port_year}"
        if portfolio_data_stale else ""
    )

    # Net worth background rebuild
    if "_networth_done_event" not in st.session_state:
        _nw_init_event = _threading.Event()
        _nw_init_event.set()
        st.session_state["_networth_done_event"] = _nw_init_event
    _networth_done_event = st.session_state["_networth_done_event"]

    networth = render_networth(
        num_months=12,
        done_event=_networth_done_event,
        build_fn=build_historical_networth,
    )
    if networth.empty:
        networth = build_historical_networth(num_months=12)
        if not networth.empty:
            save_networth_cache(networth, 12)
            _networth_done_event.set()

    # Portfolio background rebuild
    if "_portfolio_done_event" not in st.session_state:
        _init_event = _threading.Event()
        _init_event.set()
        st.session_state["_portfolio_done_event"] = _init_event
    _portfolio_done_event = st.session_state["_portfolio_done_event"]

    portfolio_df = render_portfolio(eff_port_month, eff_port_year, _portfolio_done_event)
    portfolio_cache_ready = not portfolio_df.empty

    return (
        networth,
        portfolio_df,
        portfolio_cache_ready,
        stale_label,
        curr_month,
        curr_year,
        eff_port_month,
        eff_port_year,
    )


def get_filing_status() -> str:
    """
    Get the current filing status from session state.
    
    Returns:
        'married_filing_jointly' or 'single' based on configuration
    """
    return st.session_state.get("filing_status", "married_filing_jointly")


def auto_rerun_if_rebuilding() -> None:
    """Trigger st.rerun() if background data rebuilds are still in flight."""
    _portfolio_done_event = st.session_state.get("_portfolio_done_event")
    _networth_done_event  = st.session_state.get("_networth_done_event")
    if _portfolio_done_event is None or _networth_done_event is None:
        return
    _any_pending = (
        not _portfolio_done_event.is_set() or not _networth_done_event.is_set()
    )
    if _any_pending:
        if not _portfolio_done_event.is_set():
            _portfolio_done_event.wait(timeout=2)
        if not _networth_done_event.is_set():
            _networth_done_event.wait(timeout=2)
        st.rerun()

# Made with Bob
