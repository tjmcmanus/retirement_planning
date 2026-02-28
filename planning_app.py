from typing import cast
import streamlit as st
import datetime
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from streamlit_card import card
from streamlit_extras.metric_cards import style_metric_cards 
from streamlit_extras.add_vertical_space import add_vertical_space
import graphviz
from load_data import get_month_account_values,get_cap_gains_brackets, get_income_tax_brackets, get_net_worth, get_medicare_costs, get_atm_costs, get_std_deduction, get_networth_by_month, get_portfolio_truth_by_month
from strategy import build_withdrawal_strategy_display, build_accumulation_strategy_display
from calculations import calc_roth_conversions_tax, getlower_atm_amount_n_deduction,calc_roth_conversions,calc_agi,calc_daf_value,getUpperIncomeRate,calculate_atm, calculate_std_deduction,get_std_deduction_by_year, calculate_irmma_penalty, calculate_cap_gains, calculate_taxable_income
from portfolio import get_portfolio_dividend_total,get_current_dividend,get_current_price,get_entry_in_portfolio,get_list_of_tickers,get_purchase_price,get_qty,getPortfolioData,calculate_cost_basis,calculate_current_value, get_ticker_name,get_sector,color_negative_positive,build_portfolio_display
from income_expense import build_income_expenses_display,calculate_taxes
from components.sidebar import sidebar
st.set_page_config(page_title="Financial Planner", page_icon="😊", layout="wide")

hide_st_style = """
            <style>
            MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            #header {visibility: hidden;}
            [data-testid="stMetricValue"] {
              font-size: 24px;
            }
            /* Center align all dataframe columns - comprehensive selectors */
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
            /* Override any inline styles */
            [data-testid="stDataFrame"] [data-testid="StyledDataFrameRowHeaderCell"],
            [data-testid="stDataFrame"] [data-testid="StyledDataFrameDataCell"],
            [data-testid="stDataFrameResizable"] [data-testid="StyledDataFrameRowHeaderCell"],
            [data-testid="stDataFrameResizable"] [data-testid="StyledDataFrameDataCell"] {
              text-align: center !important;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# Module-level constant for account type mapping
ACCOUNT_TYPE_MAP: dict[str, str] = {
    'Cash': 'cash',
    'Brokerage': 'taxable',
    'Traditional': 'tax_deferred',
    'Roth': 'tax_free',
}

def clear_submit():
    st.session_state["submit"] = False

def _build_networth_row(date: pd.Timestamp, summary_df: pd.DataFrame) -> dict:
    """
    Build a single net worth row dict from a monthly summary DataFrame.
    
    Args:
        date: The date for this row
        summary_df: Summary DataFrame with account_type and market_value columns
    
    Returns:
        dict: Row data with keys: cash, taxable, tax_deferred, tax_free, total, date
    """
    # Single-pass aggregation with reindex to ensure all account types present
    account_totals = (
        summary_df[summary_df['account_type'].isin(list(ACCOUNT_TYPE_MAP.keys()))]
        .groupby('account_type')['market_value']
        .sum()
        .reindex(list(ACCOUNT_TYPE_MAP.keys()), fill_value=0.0)
    )
    
    # Map account types to column names
    row_data = {ACCOUNT_TYPE_MAP[str(k)]: v for k, v in account_totals.items()}
    row_data['total'] = account_totals.sum()
    row_data['date'] = date
    
    return row_data

@st.cache_data(ttl=300)  # Cache for 5 minutes
def build_historical_networth(num_months: int = 12) -> pd.DataFrame:
    """
    Build historical net worth DataFrame using get_networth_by_month.
    
    Args:
        num_months: Number of months of historical data to fetch (default: 12)
    
    Returns:
        pd.DataFrame: Historical net worth with datetime index and columns:
                     cash, taxable, tax_deferred, tax_free, total
    """
    # Generate date range using pandas date_range
    end_date = pd.Timestamp.today().normalize()
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
            # Catch expected exceptions from get_networth_by_month
            st.warning(f"Could not fetch data for {date.strftime('%m/%Y')}: {e}")
            continue
    
    # Create DataFrame with datetime index
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
        # Return empty DataFrame with correct structure and datetime index
        return pd.DataFrame(
            data={col: pd.Series(dtype=float) for col in ['cash', 'taxable', 'tax_deferred', 'tax_free', 'total']}
        ).set_index(pd.DatetimeIndex([], name='date'))

currentDate = datetime.date.today()
curr_year = currentDate.year
curr_month = currentDate.month

# ---------------------------------------------------------------------------
# Module-level helpers shared across tabs
# ---------------------------------------------------------------------------

# Consistent color palette used by all charts
COLOR_PALETTE = px.colors.qualitative.Pastel

def format_currency(val) -> str:
    """Format a numeric value as currency.
    
    Whole-number values are shown without decimals (e.g. $1,234).
    Non-whole values are shown with 2 decimal places (e.g. $1,234.56).
    Returns empty string for NaN/None.
    """
    if pd.isna(val):
        return ""
    try:
        if val == int(val):
            return f"${int(val):,}"
        return f"${val:,.2f}"
    except (TypeError, ValueError):
        return ""


def render_balance_chart(balances_df: pd.DataFrame, title: str = "Projected Account Balances") -> None:
    """Render a stacked-area chart for Cash / Taxable / Traditional / Roth balances.

    Args:
        balances_df: DataFrame with columns Year, Cash Balance, Taxable Balance,
                     Traditional Balance, Roth Balance.
        title: Chart title shown in the layout.
    """
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
    st.plotly_chart(fig, width='stretch')


def render_income_chart(strategy_df: pd.DataFrame, title: str = "Income Sources by Year") -> None:
    """Render a stacked bar chart for Wages / Social Security / Portfolio Withdrawal.

    Args:
        strategy_df: DataFrame that may contain columns Wages, Social Security,
                     Portfolio Withdrawal, and Total Income.
        title: Chart title shown in the layout.
    """
    if 'Total Income' not in strategy_df.columns:
        return

    fig = go.Figure()
    if 'Wages' in strategy_df.columns:
        fig.add_trace(go.Bar(
            x=strategy_df['Year'], y=strategy_df['Wages'],
            name='Wages', marker_color='rgb(99, 110, 250)'
        ))
    if 'Social Security' in strategy_df.columns:
        fig.add_trace(go.Bar(
            x=strategy_df['Year'], y=strategy_df['Social Security'],
            name='Social Security', marker_color='rgb(239, 85, 59)'
        ))
    if 'SS Benefits' in strategy_df.columns and 'Social Security' not in strategy_df.columns:
        fig.add_trace(go.Bar(
            x=strategy_df['Year'], y=strategy_df['SS Benefits'],
            name='Social Security', marker_color='rgb(239, 85, 59)'
        ))
    if 'Portfolio Withdrawal' in strategy_df.columns:
        fig.add_trace(go.Bar(
            x=strategy_df['Year'], y=strategy_df['Portfolio Withdrawal'],
            name='Portfolio Withdrawal', marker_color='rgb(0, 204, 150)'
        ))
    fig.update_layout(
        title=title,
        xaxis_title='Year',
        yaxis_title='Amount ($)',
        barmode='stack',
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white'
    )
    st.plotly_chart(fig, width='stretch')


# ---------------------------------------------------------------------------
# Life stage descriptions (plain-English summaries shown as tooltips / legend)
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

# Tooltip shown on the Stage column header in both accumulation and withdrawal tables
_STAGE_COLUMN_HELP = (
    "The life stage determines which financial priorities and rules apply this year. "
    "Hover over the stage name in the legend below the table for a plain-English summary."
)


# Shared column config for account balance tables (used by both Strategy phases)
BALANCE_COLUMN_CONFIG: dict = {
    "Year": st.column_config.NumberColumn("Year", format="%d"),
    "Cash Balance": st.column_config.TextColumn("Cash"),
    "Taxable Balance": st.column_config.TextColumn("Taxable"),
    "Traditional Balance": st.column_config.TextColumn("Traditional"),
    "Roth Balance": st.column_config.TextColumn("Roth"),
    "DAF Balance": st.column_config.TextColumn("DAF"),
    "Total Portfolio": st.column_config.TextColumn("Total Portfolio"),
}


def render_balance_table(balances_df: pd.DataFrame) -> None:
    """Render a formatted account balances dataframe using the shared column config.

    Applies format_currency() to all balance columns before display.

    Args:
        balances_df: DataFrame with Year and balance columns.
    """
    display = balances_df.copy()
    balance_cols = ['Cash Balance', 'Taxable Balance', 'Traditional Balance',
                    'Roth Balance', 'DAF Balance', 'Total Portfolio']
    for col in balance_cols:
        if col in display.columns:
            display[col] = pd.Series(pd.to_numeric(display[col], errors='coerce')).map(format_currency)
    st.dataframe(display, column_config=BALANCE_COLUMN_CONFIG, hide_index=True, width='stretch')


# Type-label mapping: account_type value → display label
_ACCOUNT_TYPE_LABELS: dict[str, str] = {
    "Cash":        "Cash",
    "Brokerage":   "Investment",
    "Traditional": "Tax Deferred",
    "Roth":        "Tax Free",
    "Real Estate": "Real Estate",
}

# Display order for account types
_ACCOUNT_TYPE_ORDER: list[str] = [
    "Cash", "Brokerage", "Traditional", "Roth", "Real Estate"
]

# Per-type background colors — match the chart palette used throughout the app
# Cash=yellow, Brokerage=pink, Traditional=green, Roth=purple, Real Estate=orange
_ACCOUNT_TYPE_COLORS: dict[str, str] = {
    "Cash":        "rgba(246, 207, 113, 0.35)",   # yellow
    "Brokerage":   "rgba(254, 136, 177, 0.35)",   # pink
    "Traditional": "rgba(139, 224, 164, 0.35)",   # green
    "Roth":        "rgba(180, 151, 231, 0.35)",   # purple
    "Real Estate": "rgba(255, 190, 122, 0.35)",   # orange
}

# Darker left-border accent per type (solid strip for visual grouping)
_ACCOUNT_TYPE_ACCENT: dict[str, str] = {
    "Cash":        "rgb(246, 207, 113)",
    "Brokerage":   "rgb(254, 136, 177)",
    "Traditional": "rgb(139, 224, 164)",
    "Roth":        "rgb(180, 151, 231)",
    "Real Estate": "rgb(255, 190, 122)",
}


# ---------------------------------------------------------------------------
# Net worth statement — style constants (shared by all row-builder helpers)
# ---------------------------------------------------------------------------
_NW_STYLES: dict[str, str] = {
    "hdr_bg":   "#1a1a2e",
    "hdr_fg":   "white",
    "total_bg": "#e8f4fd",
    "summ_bg":  "#f8f9fa",
    "pos_clr":  "#21c354",
    "neg_clr":  "#ff4b4b",
    "border":   "1px solid #dee2e6",
}


def _fmt_currency(v: float) -> str:
    """Format *v* as an accounting-style currency string.

    Negative values are shown in parentheses: ``$(1,234.56)``.

    Note:
        This is intentionally distinct from :func:`format_currency` (line 151),
        which omits decimals for whole numbers and returns ``""`` for NaN.
        ``_fmt_currency`` always shows two decimal places and uses accounting
        parentheses for negatives — the correct style for a formal net worth
        statement.
    """
    if v < 0:
        return f"$({abs(v):,.2f})"
    return f"${v:,.2f}"


def _change_style(v: float, styles: dict[str, str]) -> str:
    """Return an inline CSS snippet that colours *v* green (≥0) or red (<0)."""
    clr = styles["pos_clr"] if v >= 0 else styles["neg_clr"]
    return f"color:{clr};font-weight:600"


def _nw_header_row(styles: dict[str, str]) -> str:
    """Return the ``<tr>`` HTML for the column-header row of the net worth table."""
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


def _nw_type_rows(
    acct_type: str,
    accounts: pd.DataFrame,
    styles: dict[str, str],
) -> list[str]:
    """Return a list of ``<tr>`` HTML strings for one account-type group.

    The first row carries ``rowspan`` cells for the type label and type total;
    subsequent rows contain only the account value and name cells.

    Args:
        acct_type: Key into ``_ACCOUNT_TYPE_LABELS`` / ``_ACCOUNT_TYPE_COLORS``.
        accounts:  Filtered DataFrame with columns ``account_name``, ``market_value``.
        styles:    Style-constant dict (``_NW_STYLES``).
    """
    label      = _ACCOUNT_TYPE_LABELS.get(acct_type, acct_type)
    type_total = float(accounts["market_value"].sum())
    row_bg     = _ACCOUNT_TYPE_COLORS.get(acct_type, "rgba(240,242,246,0.4)")
    accent     = _ACCOUNT_TYPE_ACCENT.get(acct_type, "#cccccc")
    border     = styles["border"]
    n          = len(accounts)

    # Shared base style eliminates three-way duplication of padding/border/bg
    _td_base = f"padding:6px 12px;border:{border};background:{row_bg};"
    td_r     = f'style="{_td_base}text-align:right;"'
    td_l     = f'style="{_td_base}text-align:left;"'
    td_span  = f'style="{_td_base}border-left:4px solid {accent};text-align:left;font-weight:700;vertical-align:middle;"'
    td_total = f'style="{_td_base}text-align:right;font-weight:600;vertical-align:middle;"'

    # Use itertuples() uniformly for all rows — consistent attribute access,
    # avoids the mixed iloc[0]/label-index pattern that breaks on column rename.
    rows: list[str] = []
    for i, row in enumerate(accounts.itertuples(index=False)):
        if i == 0:
            rows.append(
                f'<tr>'
                f'<td rowspan="{n}" {td_span}>{label}</td>'
                f'<td rowspan="{n}" {td_total}>{_fmt_currency(type_total)}</td>'
                f'<td {td_r}>{_fmt_currency(float(row.market_value))}</td>'
                f'<td {td_l}>{str(row.account_name)}</td>'
                f'</tr>'
            )
        else:
            rows.append(
                f'<tr>'
                f'<td {td_r}>{_fmt_currency(float(row.market_value))}</td>'
                f'<td {td_l}>{str(row.account_name)}</td>'
                f'</tr>'
            )
    return rows


def _nw_total_row(
    grand_total: float,
    mom_change: float,
    styles: dict[str, str],
) -> str:
    """Return the ``<tr>`` HTML for the total net worth row."""
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
    """Return the ``<tr>`` HTML for a two-column summary row (YTD / rolling gains).

    Args:
        label:  Row description shown in the left two merged cells.
        value:  Gain/loss value shown in the right two merged cells.
        styles: Style-constant dict (``_NW_STYLES``).
    """
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


# ---------------------------------------------------------------------------
# Proposal 1 — pure data layer
# ---------------------------------------------------------------------------

def _compute_net_worth_summary(networth: pd.DataFrame) -> dict:
    """Compute MoM, YTD, and rolling-12-month summary figures from *networth*.

    Args:
        networth: DataFrame with DatetimeIndex and a ``total`` column.
                  Must contain at least 2 rows.

    Returns:
        dict with keys:
            ``current_total`` – latest total net worth,
            ``mom_change``    – month-over-month change,
            ``ytd_gain``      – year-to-date gain/loss,
            ``rolling_gain``  – rolling 12-month gain/loss,
            ``as_of``         – ``pd.Timestamp`` of the latest entry.
    """
    current_total = float(networth["total"].iloc[-1])
    prior_total   = float(networth["total"].iloc[-2])
    mom_change    = current_total - prior_total

    # YTD: compare to first available entry in the current calendar year
    dti: pd.DatetimeIndex = pd.DatetimeIndex(networth.index)
    curr_year_mask = dti.year == dti[-1].year  # type: ignore[union-attr]
    ytd_start_val  = (
        float(networth.loc[curr_year_mask, "total"].iloc[0])
        if curr_year_mask.any()
        else current_total
    )
    ytd_gain = current_total - ytd_start_val

    # Rolling 12-month: compare to entry 12 months ago (or earliest available)
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


# ---------------------------------------------------------------------------
# Proposal 2 — pure HTML builder
# ---------------------------------------------------------------------------

def _build_net_worth_html(
    acct_grp: pd.DataFrame,
    summary: dict,
    styles: dict[str, str] = _NW_STYLES,
) -> str:
    """Build and return the complete net worth statement HTML string.

    Iterates over ``_ACCOUNT_TYPE_ORDER``, delegates per-type row generation to
    ``_nw_type_rows``, and appends the total and summary rows.

    Args:
        acct_grp: DataFrame with columns ``account_type``, ``account_name``,
                  ``market_value`` (already grouped/summed).
        summary:  Dict returned by ``_compute_net_worth_summary``.
        styles:   Style-constant dict; defaults to ``_NW_STYLES``.  Pass a
                  custom dict to override colours without touching the module
                  global — useful for tests or themed variants.

    Returns:
        A self-contained HTML string (``<h4>`` heading + ``<table>``).
    """
    rows: list[str] = [_nw_header_row(styles)]

    for acct_type in _ACCOUNT_TYPE_ORDER:
        accounts = acct_grp.loc[acct_grp["account_type"] == acct_type]
        if accounts.empty:
            continue
        rows.extend(_nw_type_rows(acct_type, accounts, styles))

    # Fix 2: use the authoritative total from the historical series rather than
    # re-summing account detail rows (avoids a subtle dual-source inconsistency).
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


# ---------------------------------------------------------------------------
# Public render function — thin Streamlit wrapper (call site unchanged)
# ---------------------------------------------------------------------------

def _get_real_estate_rows() -> pd.DataFrame:
    """Load real estate properties from config and return as account-detail rows.

    Returns:
        DataFrame with columns account_type, account_name, market_value
        representing each property at its purchase price.
        Returns an empty typed DataFrame when no properties are configured or
        when the config cannot be loaded.
    """
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
    """Render a hierarchical net worth statement matching the user's layout.

    Columns: Type | Type Total | Account Total | Account

    Rows:
    - One header row per account type (merged across its accounts) with type total
    - One detail row per account within that type
    - Total net worth row with MoM change
    - YTD gains row
    - Rolling 12-month gains row

    Args:
        networth: DataFrame with DatetimeIndex and columns
                  cash, taxable, tax_deferred, tax_free, total.
                  Must have at least 2 rows.
        detailed_df: DataFrame with columns account_type, account_name, market_value
                     for the current month (from get_networth_by_month).
    """
    # Fix 4: guard against insufficient history so _compute_net_worth_summary
    # cannot raise IndexError on networth["total"].iloc[-2].
    if len(networth) < 2:
        st.warning("Need at least 2 months of data to compute net worth changes.")
        return
    if detailed_df.empty:
        st.warning("No account detail data available for net worth statement.")
        return

    # Append real estate rows from configuration
    re_rows = _get_real_estate_rows()
    if not re_rows.empty:
        combined_df = pd.concat([detailed_df, re_rows], ignore_index=True)
    else:
        combined_df = detailed_df

    acct_grp: pd.DataFrame = pd.DataFrame(
        combined_df
        .groupby(["account_type", "account_name"], as_index=False)["market_value"]
        .sum()
    )

    # Augment only the current-month (last) row with real estate purchase prices.
    # Adding re_total to every historical row would inflate the baseline used by
    # _compute_net_worth_summary, causing MoM/YTD/rolling gains to be understated.
    re_total = float(re_rows["market_value"].sum()) if not re_rows.empty else 0.0
    nw_augmented = networth.copy()
    if re_total > 0:
        nw_augmented.iloc[-1, nw_augmented.columns.get_loc("total")] += re_total

    summary = _compute_net_worth_summary(nw_augmented)
    html    = _build_net_worth_html(acct_grp, summary)
    st.markdown(html, unsafe_allow_html=True)


st.header("Financial Planner")
##############################################################################################

sidebar()

##############################################################################################


# Build historical net worth once at module scope — shared by Dashboard and Tax Planner tabs
networth = build_historical_networth(num_months=12)

tab1, tab3, tab_accum, tab_tax, tab_flow, tab5 = st.tabs(
    ["📊 Dashboard", "💼 Portfolio", "📈 Strategy", "🧮 Tax Planner", "💸 Flow of Funds", "⚙️ Settings"]
)
with tab1:
   # Check if we have enough data
   if networth.empty or len(networth) < 2:
       st.error("Insufficient historical data. Need at least 2 months of portfolio data.")
       st.stop()

   row2_col1, row2_col2, row2_col3 = st.columns(3)
   with row2_col1:
       st.markdown('<h4 style="text-align: center;">Total Net Worth</h4>', unsafe_allow_html=True)
       fig2 = px.histogram(networth, x=networth.index, y='total', nbins=10, color="total", color_discrete_sequence=COLOR_PALETTE)
       
       # Calculate y-axis range with 10% padding
       y_min = networth['total'].min()
       y_max = networth['total'].max()
       y_range = y_max - y_min
       y_axis_min = y_min - (y_range * 1)
       y_axis_max = y_max + (y_range * 0.1)
       
       # Configure chart layout with consistent styling
       fig2.update_layout(
           autosize=True,
           showlegend=False,  # Consolidated: legend disabled for cleaner histogram view
           plot_bgcolor='white',
           paper_bgcolor='white',
           xaxis=dict(
               title='Date',
               tickfont=dict(color='black')
           ),
           yaxis=dict(
               title='Net Worth',
               tickfont=dict(color='black'),
               range=[y_axis_min, y_axis_max]  # 10% padding above and below data
           )
       )
       
       # Render chart with responsive width
       st.plotly_chart(fig2, width='stretch')

   with row2_col2:
      st.markdown('<h4 style="text-align: center;">Net Worth by Account</h4>', unsafe_allow_html=True)
      
      # Calculate stacked totals for y-axis range with 10% padding
      stacked_totals = (
          networth.cash +
          networth.taxable +
          networth.tax_deferred +
          networth.tax_free
      )
      y_min = 0
      y_max = stacked_totals.max()
      y_range = y_max - y_min
      y_axis_max = y_max + (y_range * 0.1)
      
      # Create bar traces with consistent styling
      trace1 = go.Bar(
          x=networth.index,
          y=networth.cash,
          name='Cash',
          legendgroup='1',
          marker_color='rgb(246, 207, 113)'
      )
      trace2 = go.Bar(
          x=networth.index,
          y=networth.taxable,
          name='Broker',
          legendgroup='2',
          marker_color='rgb(254, 136, 177)'
      )
      trace3 = go.Bar(
          x=networth.index,
          y=networth.tax_deferred,
          name='Traditional',
          legendgroup='3',
          marker_color='rgb(139, 224, 164)'
      )
      trace4 = go.Bar(
          x=networth.index,
          y=networth.tax_free,
          name='Roth',
          legendgroup='4',
          marker_color='rgb(180, 151, 231)'
      )
      
      # Configure layout with consistent styling and y-axis range
      layout = go.Layout(
          autosize=True,
          plot_bgcolor='white',
          paper_bgcolor='white',
          barmode='stack',
          xaxis=dict(
              title='Dates',
              tickfont=dict(color='black')
          ),
          yaxis=dict(
              title='Amount',
              tickfont=dict(color='black'),
              range=[y_min, y_axis_max]  # 10% padding above stacked max
          ),
          legend=dict(
              title='Account Type',
              orientation='h',
              yanchor='bottom',
              y=1.1,
              groupclick='togglegroup',
              font=dict(color='black')
          )
      )
      
      # Create and display the figure
      fig = go.Figure(data=[trace3, trace4, trace2, trace1], layout=layout)
      st.plotly_chart(fig, width='stretch', key='selection')
   
   with row2_col3:
       st.markdown('<h4 style="text-align: center;">Asset mix</h4>', unsafe_allow_html=True)
       # 2. Select the specific row to plot
       row_to_plot = networth.iloc[-1,1:5] # Select the first row

       # 3. Create the pie chart using plotly.express
       fig = px.pie(
          #names=row_to_plot.index,    # Labels for the slices (column names)
           names=["Cash","Broker","Traditional","Roth"],    # Labels for the slices (column names)
           values=row_to_plot.values,  # Values for the slices
           color_discrete_sequence=COLOR_PALETTE,
           title=' '
        )
       # Customize the chart (optional)
       fig.update_traces(textinfo='label+percent+value',  # Display percentage and label
                  pull=[0, 0, 0, 0],      # "Explode" a slice (e.g., category C)
                  marker_colors=['rgb(246, 207, 113)', 'rgb(254, 136, 177)','rgb(139, 224, 164)', 'rgb(180, 151, 231)'],
                  title_font=dict(color="black"),
                  hoverinfo='label+percent+value',
                  insidetextfont=dict(color='black')) # Custom colors
       title_text=''
       fig.update_layout(
           autosize=True,
           plot_bgcolor='white',
           paper_bgcolor='white',
           title_font=dict(color="black"),
           legend=dict(title='Account Type', orientation="h",yanchor='bottom',y=1.1, groupclick = 'togglegroup',font=dict(color="black")),
           margin=dict(l=1,r=1,b=1,t=1)
       )
       st.plotly_chart(fig, width='stretch')
   
   add_vertical_space(1)
   # --- Net Worth Statement widget (formal balance-sheet view) ---
   # Fetch account-level detail for current month to populate the hierarchy
   try:
       _nw_detailed_df, _ = get_networth_by_month(curr_month, curr_year)
   except Exception:
       _nw_detailed_df = pd.DataFrame()
   render_net_worth_statement(networth, _nw_detailed_df)

   # ------------------------------------------------------------------ #
   # YoY Net Worth Trend Line                                             #
   # ------------------------------------------------------------------ #
   if len(networth) >= 2:
       nw_trend_fig = go.Figure()
       nw_trend_fig.add_trace(go.Scatter(
           x=networth.index,
           y=networth['total'],
           mode='lines+markers',
           name='Total Net Worth',
           line=dict(color='#4c78a8', width=2),
           marker=dict(size=6),
           fill='tozeroy',
           fillcolor='rgba(76,120,168,0.12)',
           hovertemplate='%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>',
       ))
       # Annotate MoM change on the last point
       last_val  = float(networth['total'].iloc[-1])
       prev_val  = float(networth['total'].iloc[-2])
       mom_delta = last_val - prev_val
       mom_pct   = (mom_delta / prev_val * 100) if prev_val else 0.0
       arrow_clr = '#21c354' if mom_delta >= 0 else '#ff4b4b'
       nw_trend_fig.add_annotation(
           x=networth.index[-1], y=last_val,
           text=f"{'▲' if mom_delta >= 0 else '▼'} ${abs(mom_delta):,.0f} ({mom_pct:+.1f}%)",
           showarrow=True, arrowhead=2, arrowcolor=arrow_clr,
           font=dict(color=arrow_clr, size=11),
           bgcolor='white', bordercolor=arrow_clr, borderwidth=1,
           ax=0, ay=-36,
       )
       nw_trend_fig.update_layout(
           title='Net Worth Trend (12 months)',
           xaxis_title='Month',
           yaxis_title='Net Worth ($)',
           plot_bgcolor='white', paper_bgcolor='white',
           showlegend=False,
           margin=dict(t=40, l=10, r=10, b=10),
           yaxis=dict(tickformat='$,.0f'),
       )
       st.plotly_chart(nw_trend_fig, width='stretch')

   # ------------------------------------------------------------------ #
   # Tax Efficiency Score                                                 #
   # ------------------------------------------------------------------ #
   try:
       _te_trad  = float(networth['tax_deferred'].iloc[-1]) if not networth.empty else 0.0
       _te_roth  = float(networth['tax_free'].iloc[-1])     if not networth.empty else 0.0
       _te_brok  = float(networth['taxable'].iloc[-1])      if not networth.empty else 0.0
       _te_cash  = float(networth['cash'].iloc[-1])         if not networth.empty else 0.0
       _te_total = _te_trad + _te_roth + _te_brok + _te_cash
       # Tax efficiency = (tax-free + taxable) / total  (higher = more tax-efficient)
       _te_score = ((_te_roth + _te_brok) / _te_total * 100) if _te_total > 0 else 0.0
       # Roth ratio: proportion of retirement assets in Roth vs Traditional
       _roth_ratio = (_te_roth / (_te_roth + _te_trad) * 100) if (_te_roth + _te_trad) > 0 else 0.0
   except Exception:
       _te_score = _roth_ratio = 0.0
       _te_trad = _te_roth = _te_brok = _te_cash = _te_total = 0.0

   st.markdown("#### 🧮 Tax Efficiency")
   _te_col1, _te_col2, _te_col3, _te_col4 = st.columns(4)
   with _te_col1:
       _te_label = "🟢 Excellent" if _te_score >= 60 else ("🟡 Good" if _te_score >= 40 else "🔴 Improve")
       st.metric("Tax Efficiency Score", f"{_te_score:.0f}%", help="(Roth + Taxable Brokerage) ÷ Total Portfolio. Higher = more tax-flexible assets.")
       st.caption(_te_label)
   with _te_col2:
       st.metric("Roth Ratio", f"{_roth_ratio:.0f}%", help="Roth ÷ (Roth + Traditional). Higher = more tax-free retirement assets.")
   with _te_col3:
       st.metric("Tax-Deferred (Trad)", f"${_te_trad:,.0f}")
   with _te_col4:
       st.metric("Tax-Free (Roth)", f"${_te_roth:,.0f}")

   add_vertical_space(1)

   tab1_row2_col1,tab1_row2_col2 = st.columns(2)
   with tab1_row2_col1:
       st.markdown('<h4 style="text-align: center;">Account Mix Breakdown</h4>', unsafe_allow_html=True)
    # CURRENT MONTH SPEND BY CATEGORY [TREEMAP CHART]
    
    # CURRENT MONTH SPEND BY CATEGORY [TREEMAP CHART]
       # 2. Select the specific row to plot

       mtd_spend = get_month_account_values(curr_month,curr_year)
       #print(mtd_spend)
      # monthly_balance = account_data.iloc[-1,1:15] # Select the first row
       fig_mtd_spend_by_cateogry = px.treemap(mtd_spend, path=['account_type','account_name'],
                     values='market_value',color='market_value', color_continuous_scale=COLOR_PALETTE,color_continuous_midpoint=np.average(mtd_spend['market_value'], weights=mtd_spend['market_value']), title="")
       fig_mtd_spend_by_cateogry.data[0].textinfo = "label+text+value+percent root"

       #fig_mtd_spend_by_cateogry.update_layout(margin=dict(l=0,r=0,t=0,b=0))
       fig_mtd_spend_by_cateogry.update_layout(margin = dict(t=50, l=25, r=25, b=25))

       st.plotly_chart(fig_mtd_spend_by_cateogry, width='stretch')

   with tab1_row2_col2:
        st.markdown('<h4 style="text-align: center;">Portfolio mix</h4>', unsafe_allow_html=True)
        portdf_with_totals = build_portfolio_display()
        # Exclude the totals row (last row where Account == 'Portfolio Totals')
        portdf_no_totals = portdf_with_totals[portdf_with_totals['Account'] != 'Portfolio Totals'].copy()
        portfolio_by_sector = px.treemap(portdf_no_totals, path=['Tax Type','Sector'],
        values='Current value',color='Current value', color_continuous_scale=COLOR_PALETTE,color_continuous_midpoint=np.average(portdf_no_totals['Current value'], weights=portdf_no_totals['Current value']), title="")
        #values='Current value',color='Current value', title="")
        portfolio_by_sector.data[0].textinfo = "label+text+value+percent root"
        portfolio_by_sector.update_traces(texttemplate="%{label}<br>$%{value:,.2f}")
        portfolio_by_sector.update_layout(margin = dict(t=50, l=25, r=25, b=25))

        st.plotly_chart(portfolio_by_sector, width='stretch')

with tab3:
    
    st.header("💼 Portfolio")
    #add_vertical_space(2)
    portdf = build_portfolio_display()
    
    # Note: build_portfolio_display() already includes a totals row at the bottom
    #print(portdf)
    
    # Exclude the totals row (last row where Account == 'Portfolio Totals')
    portdf_no_totals = portdf[portdf['Account'] != 'Portfolio Totals'].copy()
    
    # Define styles for center alignment of headers and specific columns
    from pandas.io.formats.style import CSSStyles
    styles = cast(CSSStyles, [
        {"selector": "th", "props": [("text-align", "center")]},
        {"selector": "td", "props": [("text-align", "center")]},
    ])
    
    # Apply styles and color formatting
    styled_portdf = portdf.style.set_table_styles(styles).map(color_negative_positive)
    styled_portdf_no_total = portdf_no_totals.style.set_table_styles(styles).map(color_negative_positive)
    
    map_tab, details_tab = st.tabs(["Map Of Portfolio", "Details"])
    with map_tab:
        st.markdown('<h4 style="text-align: center;">Account Mix Breakdown</h4>', unsafe_allow_html=True)

        portfolio_by_sector = px.treemap(portdf_no_totals, path=['Tax Type','Sector', 'Ticker'],
            values='Current value',color='Current value', color_continuous_scale=COLOR_PALETTE,color_continuous_midpoint=np.average(portdf_no_totals['Current value'], weights=portdf_no_totals['Current value']), title="")
                    #values='Current value',color='Current value', title="")
        portfolio_by_sector.data[0].textinfo = "label+text+value+percent root"
        portfolio_by_sector.update_traces(texttemplate="%{label}<br>$%{value:,.2f}")
        portfolio_by_sector.update_layout(margin = dict(t=50, l=25, r=25, b=25))

        st.plotly_chart(portfolio_by_sector, width='stretch')

        # ------------------------------------------------------------------ #
        # Portfolio Performance vs Benchmark                                   #
        # ------------------------------------------------------------------ #
        st.markdown("#### 📈 Portfolio Performance vs Benchmark")
        if not networth.empty and len(networth) >= 2:
            _bench_rate = 0.07 / 12  # 7% annual → monthly
            _start_val  = float(networth['total'].iloc[0])
            _bench_vals = [_start_val * ((1 + _bench_rate) ** i) for i in range(len(networth))]

            _perf_fig = go.Figure()
            _perf_fig.add_trace(go.Scatter(
                x=networth.index,
                y=networth['total'],
                mode='lines+markers',
                name='Your Portfolio',
                line=dict(color='#4c78a8', width=2),
                marker=dict(size=5),
                hovertemplate='%{x|%b %Y}<br>Portfolio: $%{y:,.0f}<extra></extra>',
            ))
            _perf_fig.add_trace(go.Scatter(
                x=networth.index,
                y=_bench_vals,
                mode='lines',
                name='Benchmark (7% p.a.)',
                line=dict(color='#f58518', width=2, dash='dash'),
                hovertemplate='%{x|%b %Y}<br>Benchmark: $%{y:,.0f}<extra></extra>',
            ))
            # Shade the gap between portfolio and benchmark
            _perf_fig.add_trace(go.Scatter(
                x=list(networth.index) + list(networth.index[::-1]),
                y=networth['total'].tolist() + _bench_vals[::-1],
                fill='toself',
                fillcolor='rgba(76,120,168,0.10)',
                line=dict(color='rgba(255,255,255,0)'),
                showlegend=False,
                hoverinfo='skip',
            ))
            _last_port  = float(networth['total'].iloc[-1])
            _last_bench = _bench_vals[-1]
            _vs_bench   = _last_port - _last_bench
            _vs_pct     = (_vs_bench / _last_bench * 100) if _last_bench else 0.0
            _vs_clr     = '#21c354' if _vs_bench >= 0 else '#ff4b4b'
            _vs_lbl     = f"{'▲' if _vs_bench >= 0 else '▼'} ${abs(_vs_bench):,.0f} ({_vs_pct:+.1f}%) vs benchmark"
            _perf_fig.add_annotation(
                x=networth.index[-1], y=_last_port,
                text=_vs_lbl,
                showarrow=True, arrowhead=2, arrowcolor=_vs_clr,
                font=dict(color=_vs_clr, size=11),
                bgcolor='white', bordercolor=_vs_clr, borderwidth=1,
                ax=0, ay=-40,
            )
            _perf_fig.update_layout(
                xaxis_title='Month',
                yaxis_title='Portfolio Value ($)',
                plot_bgcolor='white', paper_bgcolor='white',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                margin=dict(t=40, l=10, r=10, b=10),
                yaxis=dict(tickformat='$,.0f'),
            )
            st.plotly_chart(_perf_fig, width='stretch')
        else:
            st.info("📈 Portfolio performance chart requires at least 2 months of historical data.")

    with details_tab:
        desired_height = (len(portdf) + 1) * 35 + 3
        st.dataframe(styled_portdf,height=desired_height,
        column_config={
            "Price": st.column_config.NumberColumn(
            "Closing Price", # Column header name in UI
            format="dollar"
            ),
            "Current value": st.column_config.NumberColumn(
            "Current value", # Column header name in UI
            format="dollar"
            ),
            "Cost Basis": st.column_config.NumberColumn(
            "Cost Basis", # Column header name in UI
            format="dollar"
            ),
            "Net Return": st.column_config.NumberColumn(
            "Net Return", # Column header name in UI
            format="dollar"
            ),"Dividend Amount": st.column_config.NumberColumn(
            "Dividend", # Column header name in UI
            format="dollar"
            ),"annual dividend amount": st.column_config.NumberColumn(
            "Annual Div", # Column header name in UI
            format="dollar"
            ),"dividend yield": st.column_config.NumberColumn(
            "Yield", # Column header name in UI
            format="percent")
        },hide_index=True,
        width='stretch',
        column_order=None)

        


with tab_accum:
    st.header("📈 Strategy")
    st.markdown("Plan and review your accumulation and withdrawal strategy across all life stages.")

    # ------------------------------------------------------------------ #
    # 🎯 Retirement Readiness Indicator                                    #
    # ------------------------------------------------------------------ #
    st.markdown("#### 🎯 Retirement Readiness Indicator")
    st.caption(
        "A composite snapshot of how prepared you are across key retirement planning dimensions. "
        "Each indicator is scored 0–100. Click any expander for details and next steps."
    )

    try:
        from config import get_config_manager as _get_cfg
        import json as _json
        import os as _os

        _cfg = _get_cfg()

        # ── 1. Portfolio Funding (4% rule: need 25× annual expenses) ──────────
        _annual_exp   = float(_cfg.get("financial_assumptions", "expected_annual_expenses", 50_000) or 50_000)
        _target_port  = _annual_exp * 25.0
        _current_port = float(networth["total"].iloc[-1]) if not networth.empty else 0.0
        # Add real estate to portfolio total for funding check
        try:
            _re_props = _cfg.get("real_estate", "properties", []) or []
            _re_total_rri = sum(float(p.get("purchase_price", 0) or 0) for p in _re_props)
        except Exception:
            _re_total_rri = 0.0
        _total_assets = _current_port + _re_total_rri
        _funding_pct  = min(_total_assets / _target_port * 100, 100) if _target_port > 0 else 0.0
        _funding_score = _funding_pct  # 0–100

        # ── 2. Estate Planning Completeness ───────────────────────────────────
        _estate_score = 0.0
        _ep_done, _ep_tot = 0, 0
        try:
            if _os.path.exists("estate_planning_data.json"):
                with open("estate_planning_data.json") as _ef:
                    _ed = _json.load(_ef)
                # Count boolean "done" flags recursively
                def _count_done(d: dict) -> tuple[int, int]:
                    tot, done = 0, 0
                    for v in d.values():
                        if isinstance(v, dict):
                            if "done" in v:
                                tot += 1
                                if v["done"]:
                                    done += 1
                            else:
                                s_done, s_tot = _count_done(v)
                                done += s_done; tot += s_tot
                    return done, tot
                _ep_done, _ep_tot = _count_done(_ed)
                # Also credit core documents from assessment
                _assess = _ed.get("assessment", {})
                _core_checks = ["has_will", "has_poa", "has_healthcare_directive", "beneficiaries_current"]
                _core_done = sum(1 for k in _core_checks if _assess.get(k, False))
                _estate_score = min((_ep_done / _ep_tot * 70 if _ep_tot > 0 else 0) + (_core_done / len(_core_checks) * 30), 100)
            else:
                _estate_score = 0.0
        except Exception:
            _estate_score = 0.0

        # ── 3. Tax Diversification (Roth ratio target: 30–50%) ────────────────
        _trad_bal  = float(networth["tax_deferred"].iloc[-1]) if not networth.empty else 0.0
        _roth_bal  = float(networth["tax_free"].iloc[-1])     if not networth.empty else 0.0
        _roth_r    = (_roth_bal / (_roth_bal + _trad_bal) * 100) if (_roth_bal + _trad_bal) > 0 else 0.0
        # Score peaks at 40% Roth ratio, falls off on either side
        _tax_div_score = max(0.0, 100.0 - abs(_roth_r - 40.0) * 2.5)

        # ── 4. Social Security Configured ─────────────────────────────────────
        _p1_ssi = float(_cfg.get("social_security", "person1_ssi_amount", 0) or 0)
        _p2_ssi = float(_cfg.get("social_security", "person2_ssi_amount", 0) or 0)
        _ssi_score = 100.0 if (_p1_ssi > 0 and _p2_ssi > 0) else (50.0 if (_p1_ssi > 0 or _p2_ssi > 0) else 0.0)

        # ── 5. Healthcare Coverage Configured ─────────────────────────────────
        _aca_enrolled = bool(_cfg.get("healthcare", "aca_marketplace_enrolled", False))
        _p1_aca_amt   = float(_cfg.get("healthcare", "person1_aca_insurance_monthly", 0) or 0)
        _p2_aca_amt   = float(_cfg.get("healthcare", "person2_aca_insurance_monthly", 0) or 0)
        _medicare_age = int(_cfg.get("healthcare", "person1_medicare_start_age", 65) or 65)
        _healthcare_score = 100.0 if (_aca_enrolled and (_p1_aca_amt > 0 or _p2_aca_amt > 0)) else (
            60.0 if (_p1_aca_amt > 0 or _p2_aca_amt > 0) else 20.0
        )

        # ── 6. Emergency / Cash Buffer ────────────────────────────────────────
        _target_months = int(_cfg.get("financial_assumptions", "accumulation_cash_buffer_months", 6) or 6)
        _wages_total   = (
            float(_cfg.get("income", "person1_annual_wages", 0) or 0) +
            float(_cfg.get("income", "person2_annual_wages", 0) or 0)
        )
        _cash_bal = float(networth["cash"].iloc[-1]) if not networth.empty else 0.0
        _yrs_cash = float(_cfg.get("financial_assumptions", "years_of_expenses_in_cash", 4) or 4)
        _cash_target_ret = _annual_exp * _yrs_cash  # always defined
        _cash_target = _wages_total * _target_months / 12 if _wages_total > 0 else _cash_target_ret
        if _wages_total > 0:
            _cash_score = min(_cash_bal / _cash_target * 100, 100) if _cash_target > 0 else 50.0
        else:
            # Retired: score based on years-of-expenses in cash
            _cash_score = min(_cash_bal / _cash_target_ret * 100, 100) if _cash_target_ret > 0 else 50.0

        # ── Weighted composite score ───────────────────────────────────────────
        # Weights: Funding 35%, Estate 20%, Tax Div 15%, SSI 10%, Healthcare 10%, Cash 10%
        _weights = [0.35, 0.20, 0.15, 0.10, 0.10, 0.10]
        _scores  = [_funding_score, _estate_score, _tax_div_score, _ssi_score, _healthcare_score, _cash_score]
        _overall = sum(w * s for w, s in zip(_weights, _scores))

        def _rri_color(score: float) -> str:
            if score >= 75: return "#21c354"
            if score >= 50: return "#ffa500"
            return "#ff4b4b"

        def _rri_label(score: float) -> str:
            if score >= 75: return "🟢 On Track"
            if score >= 50: return "🟡 Needs Attention"
            return "🔴 Action Required"

        # ── Overall gauge ──────────────────────────────────────────────────────
        _gauge_fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=_overall,
            delta={"reference": 75, "valueformat": ".0f"},
            title={"text": "Overall Retirement Readiness", "font": {"size": 16}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": _rri_color(_overall)},
                "steps": [
                    {"range": [0,  50], "color": "rgba(255,75,75,0.15)"},
                    {"range": [50, 75], "color": "rgba(255,165,0,0.15)"},
                    {"range": [75,100], "color": "rgba(33,195,84,0.15)"},
                ],
                "threshold": {
                    "line": {"color": "#333", "width": 3},
                    "thickness": 0.75,
                    "value": 75,
                },
            },
            number={"suffix": "%", "valueformat": ".0f"},
        ))
        _gauge_fig.update_layout(
            height=260,
            margin=dict(t=40, b=10, l=20, r=20),
            paper_bgcolor="white",
        )

        _rri_col_gauge, _rri_col_metrics = st.columns([2, 3])
        with _rri_col_gauge:
            st.plotly_chart(_gauge_fig, width='stretch')
            st.markdown(
                f'<p style="text-align:center;font-size:18px;font-weight:700;'
                f'color:{_rri_color(_overall)}">{_rri_label(_overall)}</p>',
                unsafe_allow_html=True,
            )

        with _rri_col_metrics:
            _ind_labels = [
                ("💰 Portfolio Funding",      _funding_score,    f"{_funding_pct:.0f}% of 25× expenses target  (${_total_assets:,.0f} / ${_target_port:,.0f})"),
                ("⚖️ Estate Planning",        _estate_score,     f"{_ep_done if _estate_score > 0 else 0} of {_ep_tot if _estate_score > 0 else '?'} checklist items complete"),
                ("🔀 Tax Diversification",    _tax_div_score,    f"Roth ratio {_roth_r:.0f}%  (target 30–50%)"),
                ("📋 Social Security",        _ssi_score,        "Both persons configured" if _ssi_score == 100 else ("One person configured" if _ssi_score == 50 else "Not configured — add SSI amounts in Configuration")),
                ("🏥 Healthcare Coverage",    _healthcare_score, "ACA enrolled & premiums set" if _healthcare_score == 100 else ("Premiums set" if _healthcare_score == 60 else "Configure ACA/Medicare in Configuration")),
                ("🏦 Cash / Emergency Fund",  _cash_score,       f"${_cash_bal:,.0f} vs ${_cash_target:,.0f} target"),
            ]
            for _ind_name, _ind_score, _ind_detail in _ind_labels:
                _bar_color = _rri_color(_ind_score)
                _bar_pct   = int(_ind_score)
                st.markdown(
                    f'<div style="margin-bottom:8px;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<span style="font-size:13px;font-weight:600;">{_ind_name}</span>'
                    f'<span style="font-size:13px;color:{_bar_color};font-weight:700;">{_bar_pct}%</span>'
                    f'</div>'
                    f'<div style="background:#e9ecef;border-radius:4px;height:8px;margin:3px 0;">'
                    f'<div style="background:{_bar_color};width:{_bar_pct}%;height:8px;border-radius:4px;"></div>'
                    f'</div>'
                    f'<div style="font-size:11px;color:#666;">{_ind_detail}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ── Action items ───────────────────────────────────────────────────────
        _actions: list[str] = []
        if _funding_score < 75:
            _gap = _target_port - _total_assets
            _actions.append(f"💰 **Portfolio gap:** ${_gap:,.0f} below the 25× expenses target. Increase savings rate or adjust expense expectations.")
        if _estate_score < 50:
            _actions.append("⚖️ **Estate planning incomplete.** Visit the ⚖️ Estate Planning page to complete your checklist.")
        if _tax_div_score < 50:
            if _roth_r < 30:
                _actions.append("🔀 **Low Roth ratio.** Consider Roth conversions to improve tax diversification.")
            else:
                _actions.append("🔀 **High Roth ratio.** Ensure you have sufficient Traditional assets for tax-bracket management in retirement.")
        if _ssi_score < 100:
            _actions.append("📋 **Social Security not fully configured.** Add SSI amounts in ⚙️ Configuration → Social Security.")
        if _healthcare_score < 60:
            _actions.append("🏥 **Healthcare coverage not configured.** Add ACA premiums in ⚙️ Configuration → Healthcare.")
        if _cash_score < 50:
            _actions.append(f"🏦 **Cash buffer below target.** Current: ${_cash_bal:,.0f}. Build toward ${_cash_target:,.0f}.")

        if _actions:
            with st.expander(f"📋 {len(_actions)} Action Item(s) to Improve Your Score", expanded=False):
                for _act in _actions:
                    st.markdown(f"- {_act}")
        else:
            st.success("✅ All retirement readiness indicators are on track!")

    except Exception as _rri_err:
        st.warning(f"⚠️ Could not compute retirement readiness indicator: {_rri_err}")

    st.markdown("---")

    # Phase toggle: Accumulation (pre-retirement) vs Withdrawal (distribution)
    phase = st.radio(
        "Planning Phase",
        options=["📈 Accumulation (Pre-Retirement)", "💸 Withdrawal (Distribution)"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.markdown("---")

    strategy_sub_tab, balances_sub_tab, charts_sub_tab = st.tabs(
        ["📋 Annual Plan", "💰 Account Balances", "📊 Visualizations"]
    )

    if phase == "📈 Accumulation (Pre-Retirement)":
        # ------------------------------------------------------------------ #
        # ACCUMULATION PHASE                                                   #
        # ------------------------------------------------------------------ #

        # Read parameters from session state / config
        try:
            accum_rate_of_return_s = float(st.session_state.get("RATE", 6)) / 100
        except (ValueError, TypeError):
            accum_rate_of_return_s = 0.06

        try:
            from config import get_config_manager as _acfg_mgr
            _acfg = _acfg_mgr()
            accum_expense_inflation = _acfg.get("financial_assumptions", "expense_inflation_rate", 3.0) / 100.0
            accum_person1_name = _acfg.get("personal_info", "person1_name", "Person1")
            accum_person2_name = _acfg.get("personal_info", "person2_name", "Person2")
            accum_annual_expenses = _acfg.get("financial_assumptions", "expected_annual_expenses", 120_000)
        except Exception:
            accum_expense_inflation = 0.03
            accum_person1_name = "Person1"
            accum_person2_name = "Person2"
            accum_annual_expenses = 120_000

        # Parameters summary bar
        ap_col1, ap_col2, ap_col3 = st.columns(3)
        with ap_col1:
            st.metric("Rate of Return", f"{accum_rate_of_return_s * 100:.1f}%")
        with ap_col2:
            st.metric("Expense Inflation", f"{accum_expense_inflation * 100:.1f}%")
        with ap_col3:
            st.metric("Annual Expenses", f"${accum_annual_expenses:,.0f}")

        add_vertical_space(1)

        try:
            with st.spinner("Calculating accumulation strategy..."):
                accum_strategy_df, accum_balances_df = build_accumulation_strategy_display(
                    start_year=curr_year,
                    growth_rate=1 + accum_rate_of_return_s,
                    expense_inflation_rate=accum_expense_inflation,
                    person1_name=accum_person1_name,
                    person2_name=accum_person2_name,
                )

            with strategy_sub_tab:
                st.subheader("Annual Accumulation Plan")

                display_df_a = accum_strategy_df.copy()

                display_cols_a = [
                    'Year', 'Age', 'Stage',
                    'Wages', 'Wages→\nPayroll', 'Wages→\nTrad', 'Wages→\nRoth',
                    'Trad→\nRoth', 'Cash→\nRoth', 'Cash→\nBrok',
                    'Expenses', 'Healthcare Cost', 'AGI', 'Federal Tax',
                    'Cash Balance',
                ]
                available_cols_a = [c for c in display_cols_a if c in display_df_a.columns]
                display_df_a = cast(pd.DataFrame, display_df_a[available_cols_a].copy())

                numeric_cols_a = [c for c in available_cols_a if c not in ['Year', 'Age', 'Stage']]
                for col in numeric_cols_a:
                    display_df_a[col] = display_df_a[col].map(format_currency)

                accum_column_config = {
                    "Year": st.column_config.NumberColumn("Year", format="%d"),
                    "Age": st.column_config.TextColumn("Age"),
                    "Stage": st.column_config.TextColumn("Life Stage", help=_STAGE_COLUMN_HELP),
                    "Wages": st.column_config.TextColumn("Wages"),
                    "Wages→\nPayroll": st.column_config.TextColumn("Payroll Tax"),
                    "Wages→\nTrad": st.column_config.TextColumn("Wages→Trad"),
                    "Wages→\nRoth": st.column_config.TextColumn("Wages→Roth"),
                    "Trad→\nRoth": st.column_config.TextColumn("Trad→Roth"),
                    "Cash→\nRoth": st.column_config.TextColumn("Cash→Roth"),
                    "Cash→\nBrok": st.column_config.TextColumn("Cash→Brok"),
                    "Expenses": st.column_config.TextColumn("Expenses"),
                    "Healthcare Cost": st.column_config.TextColumn("Healthcare", help="Combined IRMAA penalty and ACA premium"),
                    "AGI": st.column_config.TextColumn("AGI"),
                    "Federal Tax": st.column_config.TextColumn("Fed Tax"),
                    "Cash Balance": st.column_config.TextColumn("Cash End"),
                }
                st.dataframe(display_df_a, column_config=accum_column_config, hide_index=True, width='stretch')

                # Stage legend — plain-English descriptions for each stage in the table
                _accum_stages_present = display_df_a['Stage'].unique() if 'Stage' in display_df_a.columns else []
                with st.expander("ℹ️ Life Stage Guide", expanded=False):
                    for _stage_name, _stage_desc in LIFE_STAGE_DESCRIPTIONS.items():
                        if _stage_name in list(_accum_stages_present):
                            st.markdown(f"**{_stage_name}**")
                            st.caption(_stage_desc)
                            st.markdown("---")

            with balances_sub_tab:
                st.subheader("Account Balances Over Time")
                render_balance_table(accum_balances_df)

            with charts_sub_tab:
                st.subheader("Portfolio Balance Projections")
                render_balance_chart(accum_balances_df, title="Projected Account Balances (Accumulation)")
                st.subheader("Income Sources Over Time")
                render_income_chart(accum_strategy_df, title="Income Sources by Year (Accumulation)")

        except Exception as e:
            st.error(f"Error calculating accumulation strategy: {e}")
            st.info("Please ensure all configuration parameters are properly set and try refreshing the data.")

    else:
        # ------------------------------------------------------------------ #
        # WITHDRAWAL / DISTRIBUTION PHASE                                      #
        # ------------------------------------------------------------------ #
        # Get parameters from session state (set by sidebar)
        try:
            ssi_age_s = int(st.session_state.get("SSI_AGE", 70))
            conv_tax_rate_s = float(st.session_state.get("CONV_TAX_RATE", 12))
            annual_expenses_s = float(st.session_state.get("EXPENSE", 50000))
            expense_multiplier_s = float(st.session_state.get("EXPENSE_MULTIPLIER", 4))
            rate_of_return_s = float(st.session_state.get("RATE", 6)) / 100
            daf_rate_s = float(st.session_state.get("DAF_RATE", 25)) / 100
            planned_dist_2027_s = float(st.session_state.get("PLANNED_DIST_2027", 5000))
        except (ValueError, TypeError):
            ssi_age_s = 70; conv_tax_rate_s = 12; annual_expenses_s = 50000
            expense_multiplier_s = 4; rate_of_return_s = 0.06
            daf_rate_s = 0.25; planned_dist_2027_s = 75000

        # Parameters summary bar
        param_col1, param_col2, param_col3, param_col4 = st.columns(4)
        with param_col1:
            st.metric("Social Security Age", ssi_age_s)
            st.metric("Annual Expenses", f"${annual_expenses_s:,.0f}")
        with param_col2:
            st.metric("Max Roth Conv Rate", f"{conv_tax_rate_s}%")
            st.metric("Expense Multiplier", f"{expense_multiplier_s}x")
        with param_col3:
            st.metric("Rate of Return", f"{rate_of_return_s*100:.1f}%")
        with param_col4:
            st.metric("DAF Disbursement", f"{daf_rate_s*100:.0f}%")
            st.metric("2027 Planned Dist", f"${planned_dist_2027_s:,.0f}")

        add_vertical_space(1)

        try:
            max_conversion_rate = float(st.session_state.get("CONV_TAX_RATE", "24")) / 100.0
        except (ValueError, TypeError):
            max_conversion_rate = 0.24

        try:
            from config import get_config_manager as _cfg_mgr
            _cfg = _cfg_mgr()
            aca_marketplace_enrolled = _cfg.get("healthcare", "aca_marketplace_enrolled", False)
            expense_inflation_rate = _cfg.get("financial_assumptions", "expense_inflation_rate", 3.0) / 100.0
            person1_name = _cfg.get("personal_info", "person1_name", "Person1")
            person2_name = _cfg.get("personal_info", "person2_name", "Person2")
        except Exception:
            aca_marketplace_enrolled = False; expense_inflation_rate = 0.03
            person1_name = "Person1"; person2_name = "Person2"

        try:
            with st.spinner("Calculating withdrawal strategy..."):
                strategy_df_w, balances_df_w = build_withdrawal_strategy_display(
                    start_year=curr_year,
                    end_year=2050,
                    growth_rate=1 + rate_of_return_s,
                    expense_inflation_rate=expense_inflation_rate,
                    person1_name=person1_name,
                    person2_name=person2_name,
                    max_conversion_rate=max_conversion_rate,
                    aca_optimize=aca_marketplace_enrolled,
                    ss_claiming_age=ssi_age_s
                )

            with strategy_sub_tab:
                st.subheader("Year-by-Year Withdrawal Strategy")

                display_df_w = strategy_df_w.copy()

                # Prepend Cash Start column (prior year's Cash Balance)
                try:
                    _, summary_df_w = get_networth_by_month(curr_month, curr_year)
                    actual_cash_start = float(
                        summary_df_w[summary_df_w['account_type'] == 'Cash']['market_value'].sum()
                    ) if not summary_df_w.empty else display_df_w.loc[display_df_w.index[0], 'Cash Balance']
                except Exception:
                    actual_cash_start = display_df_w.loc[display_df_w.index[0], 'Cash Balance']

                display_df_w['Cash Start'] = display_df_w['Cash Balance'].shift(1)
                display_df_w.loc[display_df_w.index[0], 'Cash Start'] = actual_cash_start

                display_cols_w = [
                    'Year', 'Age', 'Stage', 'Cash Start',
                    'Wages', 'SS Benefits', 'RMD',
                    'Trad→\nCash', 'Trad→\nBrok', 'Trad→\nRoth',
                    'Brok→\nCash', 'Roth→\nCash',
                    'Expenses', 'Healthcare Cost',
                    'DAF Contribution', 'AGI', 'MAGI', 'Federal Tax', 'Cash Balance'
                ]
                available_cols_w = [c for c in display_cols_w if c in display_df_w.columns]
                display_df_w = cast(pd.DataFrame, display_df_w[available_cols_w].copy())

                numeric_cols_w = [c for c in available_cols_w if c not in ['Year', 'Age', 'Stage']]
                for col in numeric_cols_w:
                    display_df_w[col] = display_df_w[col].map(format_currency)

                withdrawal_column_config = {
                    "Year": st.column_config.NumberColumn("Year", format="%d"),
                    "Age": st.column_config.TextColumn("Age"),
                    "Stage": st.column_config.TextColumn("Life Stage", help=_STAGE_COLUMN_HELP),
                    "Cash Start": st.column_config.TextColumn("Cash Start"),
                    "Wages": st.column_config.TextColumn("Wages"),
                    "SS Benefits": st.column_config.TextColumn("Social Security"),
                    "RMD": st.column_config.TextColumn("RMD"),
                    "Trad→\nCash": st.column_config.TextColumn("Trad→Cash"),
                    "Trad→\nBrok": st.column_config.TextColumn("Trad→Brok"),
                    "Trad→\nRoth": st.column_config.TextColumn("Trad→Roth"),
                    "Brok→\nCash": st.column_config.TextColumn("Brok→Cash"),
                    "Roth→\nCash": st.column_config.TextColumn("Roth→Cash"),
                    "Expenses": st.column_config.TextColumn("Expenses"),
                    "Healthcare Cost": st.column_config.TextColumn("Healthcare", help="Combined IRMAA penalty and ACA premium"),
                    "DAF Contribution": st.column_config.TextColumn("DAF Contrib"),
                    "AGI": st.column_config.TextColumn("AGI"),
                    "MAGI": st.column_config.TextColumn("MAGI"),
                    "Federal Tax": st.column_config.TextColumn("Fed Tax"),
                    "Cash Balance": st.column_config.TextColumn("Cash End"),
                }
                st.dataframe(display_df_w, column_config=withdrawal_column_config, hide_index=True, width='stretch')

                # Stage legend — plain-English descriptions for each stage in the table
                _with_stages_present = display_df_w['Stage'].unique() if 'Stage' in display_df_w.columns else []
                with st.expander("ℹ️ Life Stage Guide", expanded=False):
                    for _stage_name, _stage_desc in LIFE_STAGE_DESCRIPTIONS.items():
                        if _stage_name in list(_with_stages_present):
                            st.markdown(f"**{_stage_name}**")
                            st.caption(_stage_desc)
                            st.markdown("---")

            with balances_sub_tab:
                st.subheader("Account Balances Over Time")
                render_balance_table(balances_df_w)

            with charts_sub_tab:
                st.subheader("Portfolio Balance Projections")
                render_balance_chart(balances_df_w, title="Projected Account Balances (Withdrawal)")
                st.subheader("Income Sources Over Time")
                render_income_chart(strategy_df_w, title="Income Sources by Year (Withdrawal)")

        except Exception as e:
            st.error(f"Error calculating withdrawal strategy: {e}")
            st.info("Please ensure all sidebar parameters are properly configured and try refreshing the data.")


with tab_tax:
    st.header("🧮 Tax Planner")
    st.markdown("Estimate taxes, Roth conversions, and account changes for a given year.")
    st.markdown("---")

    # Use module-level networth; build a 2-row summary for current/prior month
    try:
        _tp_curr_val  = float(networth["cash"].iloc[-1])   if not networth.empty else 0.0
        _tp_trad_val  = float(networth["tax_deferred"].iloc[-1]) if not networth.empty else 0.0
        _tp_roth_val  = float(networth["tax_free"].iloc[-1])     if not networth.empty else 0.0
        _tp_brok_val  = float(networth["taxable"].iloc[-1])      if not networth.empty else 0.0
        cash_value    = _tp_curr_val
        trad_value    = _tp_trad_val
        roth_value    = _tp_roth_val
        taxable_value = _tp_brok_val
    except Exception:
        cash_value = trad_value = roth_value = taxable_value = 0.0

    with st.expander("Create estimated taxes for next year", expanded=True):
        col5, col6, col7, col8, col14 = st.columns(5)
        with col5:
            wages = st.number_input("Wages", key="tp_wages", on_change=clear_submit)
        with col6:
            deferred_distribution = st.number_input("Trad IRA Distribution", key="tp_trad_dist", on_change=clear_submit)
        with col14:
            interest = st.number_input("Interest", key="tp_interest", on_change=clear_submit)
        with col7:
            cg_income_lt = st.number_input("Long Term Cap Gains", key="tp_ltcg", on_change=clear_submit)
        with col8:
            cg_income_st = st.number_input("Short Term Cap Gains", key="tp_stcg", on_change=clear_submit)

        col9, col10, col12, col11, col13 = st.columns(5)
        with col9:
            people = st.selectbox("Medicare Eligible", [0, 1, 2], key="tp_medicare", on_change=clear_submit)
        with col10:
            year = st.selectbox("Tax Year", [2023, 2024, 2025, 2026, 2027], key="tp_year", on_change=clear_submit, index=3)
        with col12:
            maxdaf = st.selectbox("Max Donor Advisor Fund", ['N', 'Y'], key="tp_maxdaf", on_change=clear_submit)
        with col11:
            if maxdaf == 'Y':
                daf1 = st.number_input("Charitable Contrib", key="tp_daf1", disabled=True)
            else:
                daf1 = st.number_input("Charitable Contrib", key="tp_daf1b", on_change=clear_submit)
        with col13:
            headroom_rate = st.selectbox("Max Conversion Rate", [10, 12, 22, 24, 32, 35, 37], key="tp_headroom", on_change=clear_submit, index=3) / 100

        col14b, col15, _col16, _col17, _col18 = st.columns(5)
        with col14b:
            roth_amount = st.number_input("Roth Conversion Amount", key="tp_roth_amt", on_change=clear_submit)
        with col15:
            pd_tax_amount = st.number_input("Estimated prepaid Fed taxes", key="tp_prepaid", on_change=clear_submit)
        summarize_button = st.button("Project this years changes!", key="tp_summarize")

    if summarize_button:
        try:
            taxratedf  = get_income_tax_brackets(year)
            cgdf       = cast(pd.DataFrame, get_cap_gains_brackets(year))
            irmaadf    = get_medicare_costs(year)
            stddectdf  = get_std_deduction(year)
            atmdf      = get_atm_costs(year)
        except Exception as e:
            st.error(f"Error loading tax data for year {year}: {e}")
            st.stop()

        try:
            calc_daf = calc_daf_value(deferred_distribution + wages, interest, daf1, maxdaf)
        except Exception as e:
            st.error(f"Error calculating Donor Advisor Fund: {e}")
            calc_daf = 0

        try:
            agi = calc_agi(deferred_distribution + wages + cg_income_st, interest, stddectdf, calc_daf)
        except Exception as e:
            st.error(f"Error calculating AGI: {e}")
            st.stop()

        try:
            irmaa_fees_income = calculate_irmma_penalty(agi, irmaadf, people)
        except Exception:
            irmaa_fees_income = 0

        try:
            taxable_income, maxrate, uppermax = calculate_taxable_income(agi, taxratedf)
        except Exception as e:
            st.error(f"Error calculating taxable income: {e}")
            st.stop()

        try:
            headroom_max = getUpperIncomeRate(headroom_rate, taxratedf)
        except Exception:
            headroom_max = 0

        if maxrate > headroom_rate:
            st.warning("Current tax rate exceeds target conversion rate")

        lowerby = 0

        try:
            atm_lower, atm_deduction = getlower_atm_amount_n_deduction(year, atmdf)
            std_deduction = get_std_deduction_by_year(year)
            if uppermax >= (atm_lower + atm_deduction):
                uppermax = atm_lower + atm_deduction
        except Exception:
            atm_lower, atm_deduction = 0, 0

        try:
            if roth_amount > 0:
                conversions = roth_amount
                conversion_tax = calc_roth_conversions_tax(maxrate, headroom_rate, uppermax, agi, headroom_max, conversions)
            else:
                conversions, conversion_tax = calc_roth_conversions(maxrate, headroom_rate, uppermax, agi, headroom_max, lowerby)
        except ValueError as e:
            st.error(str(e))
            conversions, conversion_tax = 0, 0
        except Exception as e:
            st.error(f"Error calculating Roth conversion: {e}")
            conversions, conversion_tax = 0, 0

        try:
            if conversions >= 0:
                agi = calc_agi(deferred_distribution + wages + cg_income_st + conversions, interest, stddectdf, calc_daf)
                taxable_income, maxrate, uppermax = calculate_taxable_income(agi, taxratedf)
        except Exception:
            pass

        try:
            cg_tax = 0 if cg_income_lt == 0 else calculate_cap_gains(agi, cgdf, cg_income_lt)
        except Exception:
            cg_tax = 0

        try:
            atm_tax, init_lowerby = calculate_atm(agi, cg_income_lt, atmdf)
            if taxable_income > atm_tax:
                atm_tax = 0
        except Exception:
            atm_tax, init_lowerby = 0, 0

        try:
            irmaa_fees_income_headroom = calculate_irmma_penalty(uppermax, irmaadf, people)
        except Exception:
            irmaa_fees_income_headroom = 0

        # Display results
        col1row3, col1row5, col1row6, col1row7, col1row8 = st.columns(5)
        with col1row3:
            st.markdown('##### Ordinary Income')
            if 0 < (agi + conversions):
                st.metric(label="Adjusted Gross Income", value=f"${agi:,.2f}")
            if interest > 0:
                st.metric(label="Interest", value=f"${interest:,.2f}")
            if cg_income_st > 0:
                st.metric(label="Short Term Capital Gains", value=f"${cg_income_st:,.2f}")
            if cg_income_lt != 0:
                st.metric(label="Long Term Capital Gains", value=f"${cg_income_lt:,.2f}")

        with col1row5:
            st.markdown('##### Taxes Owed')
            state_tax = ((wages + cg_income_lt + cg_income_st + interest) * 0.03) if (wages + cg_income_lt + cg_income_st + interest) != 0 else 0
            quarterly_state_tax = state_tax / 4
            quarterly_fed_tax = (taxable_income + cg_tax - pd_tax_amount) / 4
            if taxable_income > 0:
                st.metric(label="Income Tax", value=f"${taxable_income + cg_tax - pd_tax_amount:,.2f}")
                st.metric(label="Quarterly Fed Tax Payment", value=f"${quarterly_fed_tax:,.2f}")
            if state_tax > 0:
                st.metric(label="State Tax", value=f"${state_tax:,.2f}")
                st.metric(label="Quarterly State Tax Payment", value=f"${quarterly_state_tax:,.2f}")
            st.markdown('##### Other Costs')
            if calc_daf > 0:
                st.metric(label="Donor Advisory Fund", value=f"${calc_daf:,.2f}")
            if cg_tax > 0:
                st.metric(label="Long Term Capital Gains Tax", value=f"${cg_tax:,.2f}")
            if irmaa_fees_income > 0:
                st.metric(label="Medicare Surcharge", value=f"${irmaa_fees_income:,.2f}")
            if irmaa_fees_income_headroom > 0 and conversions > 0:
                st.metric(label="Medicare Cost w. Roth Conversion", value=f"${irmaa_fees_income_headroom:,.2f}")
            if atm_tax > taxable_income:
                st.metric(label="Additional ATM Taxes", value=f"${atm_tax - taxable_income:,.2f}")
                st.metric(label="Decrease Income or LT Cap Gains by", value=f"${lowerby:,.2f}")

        with col1row6:
            st.markdown('##### Traditional Updates')
            if deferred_distribution + conversions > 0:
                st.metric(label="New Traditional Balance",
                          value=f"${trad_value - deferred_distribution - conversions:,.2f}",
                          delta=f"{-deferred_distribution - conversions:,.2f}")
            else:
                st.metric(label="Pre-Changes Traditional", value=f"${trad_value:,.2f}")

        with col1row7:
            st.markdown('##### Roth Updates')
            if conversions > 0:
                st.metric(label="New Roth Account Balance", value=f"${roth_value + conversions:,.2f}", delta=f"{conversions:,.2f}")
                st.metric(label="Roth Conversion", value=f"${conversions:,.2f}")
                st.metric(label="Estimated Roth Conversion Tax", value=f"${conversion_tax:,.2f}")
            else:
                st.metric(label="Pre-Changes Roth", value=f"${roth_value:,.2f}")

        with col1row8:
            st.markdown('##### Broker & Cash Updates')
            new_cash_value = cash_value - state_tax - cg_tax - taxable_income + pd_tax_amount
            new_broker_value = taxable_value - calc_daf + deferred_distribution
            if new_cash_value != cash_value:
                st.metric(label="New Cash Balance", value=f"${new_cash_value:,.2f}", delta=f"{new_cash_value - cash_value:,.2f}")
            else:
                st.metric(label="Pre-Changes Cash Balance", value=f"${cash_value:,.2f}")
            if new_broker_value != taxable_value:
                st.metric(label="New Broker Balance", value=f"${new_broker_value:,.2f}", delta=f"{new_broker_value - taxable_value:,.2f}")
            else:
                st.metric(label="Pre-Changes Broker Balance", value=f"${taxable_value:,.2f}")

with tab_flow:
    st.header("💸 Flow of Funds")
    st.markdown("Visualize how money moves between your accounts and to charitable giving.")
    st.markdown("---")

    # Month/Year selector
    _ff_col1, _ff_col2, _ = st.columns([1, 1, 4])
    with _ff_col1:
        _ff_month = st.selectbox("Month", range(1, 13), index=curr_month - 1, key="ff_month")
    with _ff_col2:
        _ff_years = [2024, 2025, 2026]
        _ff_year_idx = _ff_years.index(curr_year) if curr_year in _ff_years else len(_ff_years) - 1
        _ff_year = st.selectbox("Year", _ff_years, index=_ff_year_idx, key="ff_year")

    flow_sub_tab, account_sub_tab = st.tabs(["Investment Flow", "Account Details"])

    with account_sub_tab:
        _ff_portfolio = get_portfolio_truth_by_month(_ff_month, _ff_year)
        if not _ff_portfolio.empty:
            _ff_portfolio = _ff_portfolio.copy()
            _ff_portfolio['symbol'] = cast(pd.Series, _ff_portfolio['symbol']).str.replace('^MF:', '', regex=True)
            st.subheader("Holdings by Account")
            for _acct_type in cast(pd.Series, _ff_portfolio['account_type']).unique():
                with st.expander(f"{_acct_type} Accounts"):
                    _type_data = _ff_portfolio[_ff_portfolio['account_type'] == _acct_type]
                    st.dataframe(_type_data[['account_name', 'symbol', 'name', 'qty', 'purchase_price']], hide_index=True, use_container_width=True)
        else:
            st.warning(f"No portfolio data found for {_ff_month}/{_ff_year}")

    with flow_sub_tab:
        _ff_portfolio = get_portfolio_truth_by_month(_ff_month, _ff_year)
        if not _ff_portfolio.empty:
            _ff_accounts = _ff_portfolio.groupby(['account_name', 'account_type']).size().reset_index()

            buckets = graphviz.Digraph()
            buckets.attr(rankdir='LR')
            buckets.attr('node', shape='box', style='rounded,filled', fillcolor='lightblue')

            cash_accounts = []
            brokerage_accounts = []
            traditional_accounts = []
            roth_accounts = []

            for _, _row in _ff_accounts.iterrows():
                _label = f"{_row['account_name']}\n({_row['account_type']})"
                if _row['account_type'] == 'Cash':
                    cash_accounts.append(_label)
                    buckets.node(_label, fillcolor='lightgreen')
                elif _row['account_type'] == 'Brokerage':
                    brokerage_accounts.append(_label)
                    buckets.node(_label, fillcolor='lightyellow')
                elif _row['account_type'] == 'Traditional':
                    traditional_accounts.append(_label)
                    buckets.node(_label, fillcolor='lightcoral')
                elif _row['account_type'] == 'Roth':
                    roth_accounts.append(_label)
                    buckets.node(_label, fillcolor='lavender')

            buckets.node("Donor Advised\nFund", fillcolor='lightgray')

            for trad in traditional_accounts:
                for cash in cash_accounts:
                    buckets.edge(trad, cash, "Withdrawals\n(stocks down)")
            for brok in brokerage_accounts:
                for cash in cash_accounts:
                    buckets.edge(brok, cash, "Withdrawals\n(stocks up)")
            for trad in traditional_accounts:
                for brok in brokerage_accounts:
                    buckets.edge(trad, brok, "RMDs/\nReplenish")
            for trad in traditional_accounts:
                for roth in roth_accounts:
                    buckets.edge(trad, roth, "Roth\nConversions")
            for roth in roth_accounts:
                for cash in cash_accounts:
                    buckets.edge(roth, cash, "Big\nPurchases")
            for brok in brokerage_accounts:
                buckets.edge(brok, "Donor Advised\nFund", "Charitable\nGiving")

            st.graphviz_chart(buckets)

            st.subheader("Account Summary")
            _s_col1, _s_col2, _s_col3, _s_col4 = st.columns(4)
            with _s_col1:
                _d = _ff_portfolio[_ff_portfolio['account_type'] == 'Cash']
                st.metric("Cash Accounts", f"${(_d['qty'] * _d['purchase_price']).sum():,.0f}")
            with _s_col2:
                _d = _ff_portfolio[_ff_portfolio['account_type'] == 'Brokerage']
                st.metric("Brokerage Accounts", f"${(_d['qty'] * _d['purchase_price']).sum():,.0f}")
            with _s_col3:
                _d = _ff_portfolio[_ff_portfolio['account_type'] == 'Traditional']
                st.metric("Traditional Accounts", f"${(_d['qty'] * _d['purchase_price']).sum():,.0f}")
            with _s_col4:
                _d = _ff_portfolio[_ff_portfolio['account_type'] == 'Roth']
                st.metric("Roth Accounts", f"${(_d['qty'] * _d['purchase_price']).sum():,.0f}")

            st.subheader("Flow Strategy Notes")
            st.info("""
            **Investment Flow Strategy:**
            - **Traditional → Cash**: Withdraw from tax-deferred accounts when market is down
            - **Brokerage → Cash**: Withdraw from taxable accounts when market is up (tax-efficient)
            - **Traditional → Roth**: Convert to Roth during low-income years for tax optimization
            - **Traditional → Brokerage**: Required Minimum Distributions (RMDs) after age 73
            - **Roth → Cash**: Emergency funds or large purchases (tax-free withdrawals)
            - **Brokerage → DAF**: Donate appreciated securities for tax deduction
            """)
        else:
            st.warning(f"No portfolio data found for {_ff_month}/{_ff_year}")

with tab5:
    st.header("⚙️ Settings")
    st.markdown("Configure planning parameters and open the full configuration page.")
    st.markdown("---")

    st.markdown("### 🎛️ Quick Parameters")
    st.caption("Adjust strategy parameters below. Changes take effect immediately on the Strategy tab.")

    # Reuse sidebar config definitions
    from components.sidebar import (
        SIDEBAR_NUMBER_CONFIGS,
        VALIDATION_RULES,
        _safe_float,
        save_sidebar_value_to_config,
        CACHE_CLEAR_KEYS,
        clear_withdrawal_strategy_cache,
    )

    _qp_cols = st.columns(3)
    for _i, (label, key, min_val, max_val, step, fmt, help_text, unit) in enumerate(SIDEBAR_NUMBER_CONFIGS):
        current_raw = st.session_state.get(key, min_val)
        current_val = _safe_float(current_raw, default=min_val)
        current_val = max(min_val, min(max_val, current_val))
        widget_key = f"_tab5_num_{key}"
        with _qp_cols[_i % 3]:
            new_val = st.number_input(
                label=f"{label} ({unit})",
                min_value=min_val,
                max_value=max_val,
                value=current_val,
                step=step,
                format=fmt,
                help=help_text,
                key=widget_key,
            )
            if new_val != current_val:
                st.session_state[key] = str(new_val)
                if key in CACHE_CLEAR_KEYS:
                    clear_withdrawal_strategy_cache()
                save_sidebar_value_to_config(key, new_val)
            else:
                st.session_state[key] = str(new_val)

    # Inline validation warnings
    for key, condition_fn, warning_msg in VALIDATION_RULES:
        val = _safe_float(st.session_state.get(key, 0))
        if condition_fn(val):
            st.warning(warning_msg)

    st.markdown("---")
    st.markdown("### Full Configuration")
    st.info("⚙️ Open the [Configuration page](configuration) to edit personal information, healthcare settings, Social Security, tax strategy, and portfolio data.")
    st.markdown("---")
