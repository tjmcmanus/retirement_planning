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
from load_data import get_month_account_values,get_cap_gains_brackets, get_income_tax_brackets, get_net_worth, get_medicare_costs, get_atm_costs, get_std_deduction, get_networth_by_month, get_portfolio_truth_by_month, get_latest_portfolio_month_year
from strategy import build_withdrawal_strategy_display, build_accumulation_strategy_display
from calculations import calc_roth_conversions_tax, getlower_atm_amount_n_deduction,calc_roth_conversions,calc_agi,calc_daf_value,getUpperIncomeRate,calculate_atm, calculate_std_deduction,get_std_deduction_by_year, calculate_irmma_penalty, calculate_cap_gains, calculate_taxable_income
from monte_carlo import (
    MonteCarloInputs,
    run_monte_carlo,
    run_stress_tests,
    run_longevity_analysis,
    run_full_scenario_comparison,
    build_fan_chart_df,
    build_success_heatmap_df,
    build_scenario_comparison_df,
    generate_monte_carlo_report_csv,
    get_safe_withdrawal_rate,
    analyze_sequence_of_returns_risk,
    PORTFOLIO_PRESETS,
    STRESS_SCENARIOS,
    LONGEVITY_SCENARIOS,
)
from advanced_strategies import (
    build_rolling_tax_window,
    calculate_qbi_deduction_full,
    calculate_backdoor_roth,
    calculate_mega_backdoor_roth,
    calculate_nua_analysis,
    calculate_qcd_optimization,
    calculate_sepp,
    build_multi_year_loss_harvesting_plan,
    SEPP_METHODS,
)
from betr_roth_conversion import (
    BETRInputs,
    BETRResults,
    calculate_betr,
)
from portfolio import get_portfolio_dividend_total,get_current_dividend,get_current_price,get_entry_in_portfolio,get_list_of_tickers,get_purchase_price,get_qty,getPortfolioData,calculate_cost_basis,calculate_current_value, get_ticker_name,get_sector,color_negative_positive,build_portfolio_display,get_effective_portfolio_month_year
from tax_harvesting import (
    build_harvesting_analysis,
    classify_harvest_opportunities,
    compute_harvest_summary,
    check_market_drop_trigger,
    get_replacement_detail,
    compute_net_tax_impact,
    get_ltcg_zero_threshold,
    get_ltcg_rate_for_income,
    identify_daf_candidates,
    analyze_daf_bundling,
    DAFDonationCandidate,
    DAFBundlingAnalysis,
)
from portfolio_rebalancing import (
    compute_rebalance_plan,
    build_rebalance_display_df,
    build_actions_display_df,
    build_holdings_by_class_df,
)
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

# Determine the effective portfolio month/year (falls back to most recent if
# current month has no data yet).
_eff_port_month, _eff_port_year = get_effective_portfolio_month_year(curr_month, curr_year)
_portfolio_data_stale = (_eff_port_month != curr_month or _eff_port_year != curr_year)
import calendar as _calendar
_stale_label = (
    f"{_calendar.month_name[_eff_port_month]} {_eff_port_year}"
    if _portfolio_data_stale else ""
)

# ---------------------------------------------------------------------------
# Module-level helpers shared across tabs
# ---------------------------------------------------------------------------

# Consistent color palette used by all charts
COLOR_PALETTE = px.colors.qualitative.Pastel  # discrete: pie charts, legend-based bar traces
# Continuous scale for treemaps and color-by-value bar charts — built from the
# same Pastel hues so both chart types share a cohesive visual identity.
COLOR_SCALE = [
    [0.0, "rgb(246, 207, 113)"],   # Pastel yellow  (low)
    [0.5, "rgb(180, 151, 231)"],   # Pastel purple  (mid)
    [1.0, "rgb(139, 224, 164)"],   # Pastel green   (high)
]

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


def _acct_cells(value: float, name: str, td_r: str, td_l: str) -> str:
    """Return the two account-detail ``<td>`` elements shared by every data row.

    Extracted to eliminate the duplicated cell pair that appears in both the
    first (rowspan) row and all subsequent rows of ``_nw_type_rows``.

    Args:
        value: Account market value (raw float).
        name:  Account display name.
        td_r:  Prebuilt ``style="…"`` attribute string for right-aligned cells.
        td_l:  Prebuilt ``style="…"`` attribute string for left-aligned cells.
    """
    return (
        f'<td {td_r}>{_fmt_currency(value)}</td>'
        f'<td {td_l}>{name}</td>'
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

    # Cache the formatted total — loop-invariant value, computed once
    fmt_total = _fmt_currency(type_total)

    # First row: carries rowspan cells for the type label and type total.
    # The caller (_build_net_worth_html) guards against empty groups, so iloc[0] is safe.
    first = accounts.iloc[0]
    rows: list[str] = [
        f'<tr>'
        f'<td rowspan="{n}" {td_span}>{label}</td>'
        f'<td rowspan="{n}" {td_total}>{fmt_total}</td>'
        + _acct_cells(float(first["market_value"]), str(first["account_name"]), td_r, td_l)
        + '</tr>'
    ]

    # Remaining rows: account value and name only — no branch needed
    for row in accounts.iloc[1:].itertuples(index=False):
        rows.append(
            '<tr>'
            + _acct_cells(float(row.market_value), row.account_name, td_r, td_l)
            + '</tr>'
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
    combined_df = pd.concat([detailed_df, re_rows], ignore_index=True) if not re_rows.empty else detailed_df

    acct_grp: pd.DataFrame = pd.DataFrame(
        combined_df
        .groupby(["account_type", "account_name"], as_index=False)["market_value"]
        .sum()
    )

    # Augment only the current-month (last) row with real estate purchase prices.
    # Adding re_total to every historical row would inflate the baseline used by
    # _compute_net_worth_summary, causing MoM/YTD/rolling gains to be understated.
    re_total = re_rows["market_value"].sum()
    nw_augmented = networth.copy()
    if re_total > 0:
        nw_augmented.at[nw_augmented.index[-1], "total"] += re_total

    summary = _compute_net_worth_summary(nw_augmented)
    html    = _build_net_worth_html(acct_grp, summary)
    st.markdown(html, unsafe_allow_html=True)


st.header("Financial Planner")
##############################################################################################

sidebar()

##############################################################################################


# Build historical net worth once at module scope — shared by Dashboard and Tax Planner tabs
networth = build_historical_networth(num_months=12)

# ---------------------------------------------------------------------------
# Background portfolio pre-warming
# ---------------------------------------------------------------------------
# build_portfolio_display() makes many yfinance network calls and can take
# 10-30 seconds on first load.  We kick it off in a background thread so the
# Dashboard renders immediately while the data is fetched in parallel.
# The @st.cache_data() decorator on build_portfolio_display ensures that once
# the background thread populates the cache, all subsequent calls return
# instantly without re-fetching.
#
# Thread-safety note: we use a module-level threading.Event (not session_state)
# to signal completion because session_state writes from background threads are
# not safe in Streamlit.  The Event is stored in st.session_state as a plain
# Python object so it persists across reruns within the same session.
import threading as _threading

def _prewarm_portfolio_cache(month: int, year: int, done_event: "_threading.Event") -> None:
    """Populate the build_portfolio_display cache in a background thread."""
    try:
        build_portfolio_display(month=month, year=year)
    except Exception:
        pass  # Errors will surface when the foreground code calls the function
    finally:
        done_event.set()

# Only launch the background thread once per session (not on every rerun).
# We store the Event in session_state so it survives Streamlit reruns.
if "_portfolio_done_event" not in st.session_state:
    _done_event = _threading.Event()
    st.session_state["_portfolio_done_event"] = _done_event
    _t = _threading.Thread(
        target=_prewarm_portfolio_cache,
        args=(_eff_port_month, _eff_port_year, _done_event),
        daemon=True,
    )
    _t.start()

# Convenience flag — True once the background thread has finished
_portfolio_cache_ready: bool = st.session_state["_portfolio_done_event"].is_set()

tab1, tab3, tab_accum, tab_tax, tab_advanced, tab_mc, tab_flow, tab5 = st.tabs(
    ["📊 Dashboard", "💼 Portfolio", "📈 Strategy", "🧮 Tax Planner",
     "🎯 Advanced Strategies", "🎲 Monte Carlo", "💸 Flow of Funds", "⚙️ Settings"]
)
with tab1:
   # Check if we have enough data
   if networth.empty or len(networth) < 2:
       st.error("Insufficient historical data. Need at least 2 months of portfolio data.")
       st.stop()

   row2_col1, row2_col2, row2_col3 = st.columns(3)
   with row2_col1:
       st.markdown('<h4 style="text-align: center;">Total Net Worth</h4>', unsafe_allow_html=True)

       # Use bar chart (not histogram) so each month is its own bar with the
       # exact month-start date as the label — histogram bins continuous dates
       # and produces misaligned midpoint labels (e.g. "2026-03-08").
       _nw_labels = pd.DatetimeIndex(networth.index).strftime("%b %Y")
       fig2 = px.bar(
           networth,
           x=_nw_labels,
           y='total',
           color='total',
           color_continuous_scale=COLOR_SCALE,
       )

       # Calculate y-axis range with 10% padding
       y_min = networth['total'].min()
       y_max = networth['total'].max()
       y_range = y_max - y_min
       y_axis_min = y_min - (y_range * 1)
       y_axis_max = y_max + (y_range * 0.1)

       # Configure chart layout with consistent styling
       fig2.update_layout(
           autosize=True,
           showlegend=False,
           coloraxis_showscale=False,
           plot_bgcolor='white',
           paper_bgcolor='white',
           xaxis=dict(
               title='Date',
               tickfont=dict(color='black'),
               tickangle=-45,
           ),
           yaxis=dict(
               title='Net Worth',
               tickfont=dict(color='black'),
               range=[y_axis_min, y_axis_max],
           ),
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
      fig1 = go.Figure(data=[trace3, trace4, trace2, trace1], layout=layout)
      st.plotly_chart(fig1, width='stretch', key='selection')
   
   with row2_col3:
       st.markdown('<h4 style="text-align: center;">Asset mix</h4>', unsafe_allow_html=True)
       # 2. Select the specific row to plot
       row_to_plot = networth.iloc[-1,0:4] # Select the first row

       # 3. Create the pie chart using plotly.express
       fig1 = px.pie(
          #names=row_to_plot.index,    # Labels for the slices (column names)
           names=["Cash","Broker","Traditional","Roth"],    # Labels for the slices (column names)
           values=row_to_plot.values,  # Values for the slices
           color_discrete_sequence=COLOR_PALETTE,
           title=' '
        )
       # Customize the chart (optional)
       fig1.update_traces(textinfo='label+percent+value',  # Display percentage and label
                  pull=[0, 0, 0, 0],      # "Explode" a slice (e.g., category C)
                  marker_colors=['rgb(246, 207, 113)', 'rgb(254, 136, 177)','rgb(139, 224, 164)', 'rgb(180, 151, 231)'],
                  title_font=dict(color="black"),
                  hoverinfo='label+percent+value',
                  insidetextfont=dict(color='black')) # Custom colors
       title_text=''
       fig1.update_layout(
           autosize=True,
           plot_bgcolor='white',
           paper_bgcolor='white',
           title_font=dict(color="black"),
           legend=dict(title='Account Type', orientation="h",yanchor='bottom',y=1.1, groupclick = 'togglegroup',font=dict(color="black")),
           margin=dict(l=1,r=1,b=1,t=1)
       )
       st.plotly_chart(fig1, width='stretch')
   
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

   if _portfolio_data_stale:
       st.warning(
           f"⚠️ No portfolio data found for {_calendar.month_name[curr_month]} {curr_year}. "
           f"Showing **{_stale_label}** data instead. Please update your portfolio data.",
           icon="⚠️",
       )

   tab1_row2_col1,tab1_row2_col2 = st.columns(2)
   with tab1_row2_col1:
       st.markdown('<h4 style="text-align: center;">Account Mix Breakdown</h4>', unsafe_allow_html=True)
    # CURRENT MONTH SPEND BY CATEGORY [TREEMAP CHART]
    
    # CURRENT MONTH SPEND BY CATEGORY [TREEMAP CHART]
       # 2. Select the specific row to plot

       mtd_spend, _, _ = get_month_account_values(_eff_port_month, _eff_port_year)
       #print(mtd_spend)
      # monthly_balance = account_data.iloc[-1,1:15] # Select the first row
       fig_mtd_spend_by_cateogry = px.treemap(mtd_spend, path=['account_type','account_name'],
                     values='market_value',color='market_value', color_continuous_scale=COLOR_SCALE,color_continuous_midpoint=np.average(mtd_spend['market_value'], weights=mtd_spend['market_value']) if mtd_spend['market_value'].sum() != 0 else 0, title="")
       fig_mtd_spend_by_cateogry.data[0].textinfo = "label+text+value+percent root"

       #fig_mtd_spend_by_cateogry.update_layout(margin=dict(l=0,r=0,t=0,b=0))
       fig_mtd_spend_by_cateogry.update_layout(margin = dict(t=50, l=25, r=25, b=25))

       st.plotly_chart(fig_mtd_spend_by_cateogry, width='stretch')

   with tab1_row2_col2:
        st.markdown('<h4 style="text-align: center;">Portfolio mix</h4>', unsafe_allow_html=True)
        if not _portfolio_cache_ready:
            # Portfolio data is still loading in the background — show a
            # non-blocking placeholder so the rest of the Dashboard renders
            # immediately.  The auto-rerun at the bottom of the script will
            # refresh the page once the background fetch completes.
            st.info(
                "⏳ Portfolio data is loading in the background… "
                "The chart will appear automatically once prices are fetched.",
                icon="📊",
            )
        else:
            portdf_with_totals = build_portfolio_display(month=_eff_port_month, year=_eff_port_year)
            # Exclude the totals row (last row where Account == 'Portfolio Totals')
            portdf_no_totals = portdf_with_totals[portdf_with_totals['Account'] != 'Portfolio Totals'].copy()
            if portdf_no_totals.empty:
                st.info("No portfolio data available for the current month. Please add portfolio data via the Portfolio Data Entry page.")
            else:
                # Filter out rows with empty/NaN Sector — px.treemap requires all
                # rows to be leaf nodes; rows with a parent Tax Type but no Sector
                # value are treated as non-leaf intermediates and raise a ValueError.
                portdf_treemap = portdf_no_totals[
                    portdf_no_totals['Sector'].notna() & (portdf_no_totals['Sector'] != '')
                ].copy()
                portfolio_by_sector = px.treemap(portdf_treemap, path=['Tax Type','Sector'],
                values='Current value',color='Current value', color_continuous_scale=COLOR_SCALE,color_continuous_midpoint=np.average(portdf_treemap['Current value'], weights=portdf_treemap['Current value']) if portdf_treemap['Current value'].sum() != 0 else 0, title="")
                #values='Current value',color='Current value', title="")
                portfolio_by_sector.data[0].textinfo = "label+text+value+percent root"
                portfolio_by_sector.update_traces(texttemplate="%{label}<br>$%{value:,.2f}")
                portfolio_by_sector.update_layout(margin = dict(t=50, l=25, r=25, b=25))

                st.plotly_chart(portfolio_by_sector, width='stretch')

with tab3:
    
    st.header("💼 Portfolio")
    if _portfolio_data_stale:
        st.warning(
            f"⚠️ No portfolio data found for {_calendar.month_name[curr_month]} {curr_year}. "
            f"Showing **{_stale_label}** data instead. Please update your portfolio data.",
            icon="⚠️",
        )
    #add_vertical_space(2)
    # Load portfolio data with a spinner so the tab renders immediately and
    # shows progress feedback instead of a blank/frozen screen.
    with st.spinner("📈 Building portfolio — fetching live prices…"):
        portdf = build_portfolio_display(month=_eff_port_month, year=_eff_port_year)
    
    # Note: build_portfolio_display() already includes a totals row at the bottom
    #print(portdf)
    
    # Exclude the totals row (last row where Account == 'Portfolio Totals')
    portdf_no_totals = portdf[portdf['Account'] != 'Portfolio Totals'].copy()
    # Fill NaN/None in treemap hierarchy columns so Plotly doesn't raise
    # "None entries cannot have not-None children"
    for _col in ['Tax Type', 'Sector', 'Ticker']:
        if _col in portdf_no_totals.columns:
            portdf_no_totals[_col] = portdf_no_totals[_col].fillna('Unknown')
    # Drop rows with no value so they don't create empty leaf nodes
    portdf_no_totals = portdf_no_totals[portdf_no_totals['Current value'].notna() & (portdf_no_totals['Current value'] != 0)]
    
    # Define styles for center alignment of headers and specific columns
    from pandas.io.formats.style import CSSStyles
    styles = cast(CSSStyles, [
        {"selector": "th", "props": [("text-align", "center")]},
        {"selector": "td", "props": [("text-align", "center")]},
    ])
    
    # Apply styles and color formatting
    styled_portdf = portdf.style.set_table_styles(styles).map(color_negative_positive)
    styled_portdf_no_total = portdf_no_totals.style.set_table_styles(styles).map(color_negative_positive)
    
    map_tab, details_tab, harvest_tab, rebalance_tab = st.tabs(
        ["Map Of Portfolio", "Details", "🌾 Tax Harvesting", "⚖️ Rebalancing"]
    )
    with map_tab:
        st.markdown('<h4 style="text-align: center;">Account Mix Breakdown</h4>', unsafe_allow_html=True)

        _cv = portdf_no_totals['Current value']
        _midpoint = np.average(_cv, weights=_cv) if _cv.sum() != 0 else 0
        portfolio_by_sector = px.treemap(portdf_no_totals, path=['Tax Type','Sector', 'Ticker'],
            values='Current value',color='Current value', color_continuous_scale=COLOR_SCALE,color_continuous_midpoint=_midpoint, title="")
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

        
    # ======================================================================
    # 🌾 TAX HARVESTING / STOCK INDEXING TAB
    # ======================================================================
    with harvest_tab:
        st.markdown("## 🌾 Tax Loss & Gain Harvesting (Stock Indexing)")
        st.caption(
            "Analyzes your **Brokerage (taxable) account** holdings to identify opportunities to "
            "harvest losses (offset gains or up to $3,000 of ordinary income) and harvest gains "
            "at the **0% LTCG rate**. Wash-sale-safe replacement securities are suggested for every "
            "sell recommendation. Only taxable accounts are analyzed — Traditional and Roth accounts "
            "have no current-year tax consequence from unrealized gains/losses."
        )

        # ── User inputs ────────────────────────────────────────────────────
        st.markdown("#### ⚙️ Analysis Parameters")
        _h_col1, _h_col2, _h_col3, _h_col4, _h_col5 = st.columns(5)
        with _h_col1:
            _h_agi = st.number_input(
                "Estimated AGI (current year, $)",
                min_value=0,
                max_value=2_000_000,
                value=80_000,
                step=1_000,
                help="Your estimated Adjusted Gross Income for the current tax year, BEFORE any harvesting. "
                     "Used to determine your LTCG bracket (0%, 15%, or 20%).",
                key="harvest_agi",
            )
        with _h_col2:
            _h_marginal = st.number_input(
                "Marginal Ordinary Tax Rate (%)",
                min_value=0,
                max_value=50,
                value=22,
                step=1,
                help="Your federal marginal income tax rate. Used to estimate savings from loss harvesting "
                     "against ordinary income (up to $3,000/year).",
                key="harvest_marginal",
            )
        with _h_col3:
            _h_loss_thresh = st.number_input(
                "Loss Harvest Threshold ($)",
                min_value=0,
                max_value=100_000,
                value=500,
                step=100,
                help="Minimum unrealized loss (absolute value) to flag a position for loss harvesting.",
                key="harvest_loss_thresh",
            )
        with _h_col4:
            _h_drop_pct = st.number_input(
                "Market Drop Trigger (%)",
                min_value=1,
                max_value=50,
                value=10,
                step=1,
                help="Flag positions that have declined this % or more from cost basis "
                     "(simulates the 'S&P 500 drops 10%' trigger).",
                key="harvest_drop_pct",
            )
        with _h_col5:
            _h_gain_thresh = st.number_input(
                "Gain Harvest Threshold ($)",
                min_value=0,
                max_value=100_000,
                value=500,
                step=100,
                help="Minimum unrealized gain (absolute value) to flag a position for gain harvesting.",
                key="harvest_gain_thresh",
            )

        st.markdown("---")

        # ── LTCG bracket context ───────────────────────────────────────────
        _h_year = curr_year
        _h_zero_thresh = get_ltcg_zero_threshold(_h_year)
        _h_ltcg_rate   = get_ltcg_rate_for_income(float(_h_agi), _h_year)
        _h_headroom    = max(0.0, _h_zero_thresh - float(_h_agi))

        _bracket_col1, _bracket_col2, _bracket_col3, _bracket_col4 = st.columns(4)
        with _bracket_col1:
            _rate_color = "🟢" if _h_ltcg_rate == 0.0 else ("🟡" if _h_ltcg_rate == 0.15 else "🔴")
            st.metric(
                "Your LTCG Rate",
                f"{_rate_color} {_h_ltcg_rate:.0%}",
                help=f"Based on estimated AGI of ${_h_agi:,} for {_h_year}.",
            )
        with _bracket_col2:
            st.metric(
                "0% LTCG Threshold",
                f"${_h_zero_thresh:,.0f}",
                help=f"MFJ income limit for 0% long-term capital gains rate in {_h_year}.",
            )
        with _bracket_col3:
            st.metric(
                "Headroom to 0% Rate",
                f"${_h_headroom:,.0f}",
                help="How much more income you can realize before crossing into the 15% LTCG bracket. "
                     "This is the maximum gain you can harvest tax-free this year.",
            )
        with _bracket_col4:
            _h_strategy_label = (
                "🟢 Harvest Gains (0% rate!)" if _h_ltcg_rate == 0.0
                else ("🟡 Harvest Losses" if _h_ltcg_rate == 0.15
                      else "🔴 Harvest Losses (High Rate)")
            )
            st.metric("Recommended Strategy", _h_strategy_label)

        st.markdown("---")

        # ── Run analysis ───────────────────────────────────────────────────
        try:
            with st.spinner("Fetching current prices and analyzing brokerage holdings..."):
                _h_analysis = build_harvesting_analysis(curr_month, curr_year)

            if _h_analysis.empty:
                st.info(
                    "ℹ️ No taxable (Brokerage) holdings found for the current period. "
                    "Tax harvesting applies only to Brokerage accounts."
                )
            else:
                # Classify opportunities
                _h_classified = classify_harvest_opportunities(
                    _h_analysis,
                    estimated_agi=float(_h_agi),
                    year=_h_year,
                    loss_threshold=-max(float(_h_loss_thresh), 1.0),  # loss_threshold must be negative; UI input is positive; guard against 0
                    gain_threshold=float(_h_gain_thresh),
                )

                # Summary metrics
                _h_summary = compute_harvest_summary(_h_classified)
                _h_tax_impact = compute_net_tax_impact(
                    _h_classified,
                    estimated_agi=float(_h_agi),
                    year=_h_year,
                    marginal_ordinary_rate=float(_h_marginal) / 100.0,
                )

                # ── Summary cards ──────────────────────────────────────────
                st.markdown("#### 📊 Portfolio Gain/Loss Summary (Brokerage Only)")
                _sm_c1, _sm_c2, _sm_c3, _sm_c4, _sm_c5 = st.columns(5)
                with _sm_c1:
                    st.metric(
                        "Total Unrealized Gains",
                        f"${_h_summary['total_unrealized_gain']:,.0f}",
                        help="Sum of all unrealized gains in brokerage positions.",
                    )
                with _sm_c2:
                    _loss_val = _h_summary['total_unrealized_loss']
                    st.metric(
                        "Total Unrealized Losses",
                        f"${abs(_loss_val):,.0f}",
                        delta=f"-${abs(_loss_val):,.0f}" if _loss_val < 0 else None,
                        delta_color="inverse",
                        help="Sum of all unrealized losses in brokerage positions.",
                    )
                with _sm_c3:
                    _net = _h_summary['net_unrealized']
                    st.metric(
                        "Net Unrealized",
                        f"${_net:,.0f}",
                        delta=f"{'▲' if _net >= 0 else '▼'} ${abs(_net):,.0f}",
                        delta_color="normal" if _net >= 0 else "inverse",
                    )
                with _sm_c4:
                    st.metric(
                        "Harvestable Losses",
                        f"${abs(_h_summary['harvestable_losses']):,.0f}",
                        help=f"{_h_summary['num_loss_candidates']} position(s) flagged for loss harvesting.",
                    )
                with _sm_c5:
                    st.metric(
                        "Harvestable Gains @ 0%",
                        f"${_h_summary['harvestable_gains_at_zero']:,.0f}",
                        help=f"{_h_summary['num_gain_candidates']} position(s) eligible for 0% gain harvesting.",
                    )

                # ── Tax impact estimate ────────────────────────────────────
                if _h_tax_impact:
                    st.markdown("#### 💰 Estimated Tax Impact of Recommended Actions")
                    _ti_c1, _ti_c2, _ti_c3, _ti_c4 = st.columns(4)
                    with _ti_c1:
                        st.metric("Net Position (Gains − Losses)", f"${_h_tax_impact.net_position:,.0f}")
                    with _ti_c2:
                        st.metric("Tax on Net Gains", f"${_h_tax_impact.tax_on_net_gains:,.0f}")
                    with _ti_c3:
                        st.metric("Ordinary Income Offset", f"${_h_tax_impact.ordinary_income_offset:,.0f}",
                                  help="Up to $3,000 of net losses can offset ordinary income.")
                    with _ti_c4:
                        _net_impact = _h_tax_impact.net_tax_impact
                        _impact_label = f"${abs(_net_impact):,.0f} {'Savings' if _net_impact >= 0 else 'Owed'}"
                        st.metric(
                            "Net Tax Impact",
                            _impact_label,
                            delta=f"{'Save' if _net_impact >= 0 else 'Owe'} ${abs(_net_impact):,.0f}",
                            delta_color="normal" if _net_impact >= 0 else "inverse",
                        )

                st.markdown("---")

                # ── Market drop trigger check ──────────────────────────────
                _h_drop_result = check_market_drop_trigger(_h_analysis, drop_threshold_pct=float(_h_drop_pct))
                if _h_drop_result["triggered"]:
                    st.warning(_h_drop_result["message"])
                    with st.expander(
                        f"📉 {len(_h_drop_result['candidates'])} Position(s) Down ≥ {_h_drop_pct}% — Loss Harvest Candidates",
                        expanded=True,
                    ):
                        _drop_df = _h_drop_result["candidates"][
                            ["Account","Symbol","Name","Sector","Qty","Purchase Price",
                             "Current Price","Unrealized G/L","Return %","Gain Type"]
                        ].copy()
                        _drop_df["Return %"]       = _drop_df["Return %"].map(lambda x: f"{x:.1f}%")
                        _drop_df["Unrealized G/L"] = _drop_df["Unrealized G/L"].map(lambda x: f"${x:,.0f}")
                        _drop_df["Purchase Price"] = _drop_df["Purchase Price"].map(lambda x: f"${x:,.2f}")
                        _drop_df["Current Price"]  = _drop_df["Current Price"].map(lambda x: f"${x:,.2f}")
                        st.dataframe(_drop_df, hide_index=True, width='stretch')
                else:
                    st.success(f"✅ {_h_drop_result['message']}")

                st.markdown("---")

                # ── Main recommendations table ─────────────────────────────
                st.markdown("#### 🎯 Harvesting Recommendations — All Brokerage Positions")
                st.caption(
                    "Positions sorted by unrealized gain/loss. "
                    "🔴 = Harvest Loss  |  🟢 = Harvest Gain (0% rate)  |  🟡 = Monitor  |  ⚪ = Hold"
                )

                _display_cols = [
                    "Account", "Symbol", "Name", "Sector",
                    "Qty", "Purchase Price", "Current Price",
                    "Current Value", "Cost Basis", "Unrealized G/L",
                    "Return %", "Days Held", "Gain Type",
                    "Recommendation",
                ]
                _h_display = cast(pd.DataFrame, _h_classified[_display_cols].copy())
                _h_display["Purchase Price"] = cast(pd.Series, _h_display["Purchase Price"]).map(lambda x: f"${x:,.2f}")
                _h_display["Current Price"]  = cast(pd.Series, _h_display["Current Price"]).map(lambda x: f"${x:,.2f}")
                _h_display["Current Value"]  = cast(pd.Series, _h_display["Current Value"]).map(lambda x: f"${x:,.0f}")
                _h_display["Cost Basis"]     = cast(pd.Series, _h_display["Cost Basis"]).map(lambda x: f"${x:,.0f}")
                _h_display["Unrealized G/L"] = cast(pd.Series, _h_display["Unrealized G/L"]).map(lambda x: f"${x:,.0f}")
                _h_display["Return %"]       = cast(pd.Series, _h_display["Return %"]).map(lambda x: f"{x:.1f}%")
                _h_display["Qty"]            = cast(pd.Series, _h_display["Qty"]).map(lambda x: f"{x:,.0f}")

                _h_row_height = (len(_h_display) + 1) * 38 + 3
                st.dataframe(_h_display, hide_index=True, height=_h_row_height, width='stretch')

                st.markdown("---")

                # ── Detailed action cards with replacement suggestions ──────
                st.markdown("#### 🔄 Action Details & Wash-Sale Replacement Suggestions")
                st.caption(
                    "For each flagged position, a wash-sale-safe replacement is suggested. "
                    "**Wash Sale Rule:** Do not repurchase the same (or substantially identical) "
                    "security within 30 days before or after the sale."
                )

                _actionable = _h_classified[
                    _h_classified["Recommendation"].str.startswith("🔴") |
                    _h_classified["Recommendation"].str.startswith("🟢")
                ].copy()

                if _actionable.empty:
                    st.info("No immediate harvesting actions recommended at current thresholds and AGI.")
                else:
                    for _, _action_row in _actionable.iterrows():
                        _sym    = str(_action_row["Symbol"])
                        _rec    = str(_action_row["Recommendation"])
                        _gl     = float(_action_row["Unrealized G/L"])
                        _pct    = float(_action_row["Return %"])
                        _gtype  = str(_action_row["Gain Type"])
                        _detail = str(_action_row["Action Detail"])
                        _replacements = get_replacement_detail(_sym)

                        _card_color   = "#fff3f3" if _rec.startswith("🔴") else "#f0fff4"
                        _border_color = "#ff4b4b" if _rec.startswith("🔴") else "#21c354"

                        st.markdown(
                            f'<div style="border-left: 4px solid {_border_color}; '
                            f'background: {_card_color}; padding: 12px 16px; '
                            f'border-radius: 6px; margin-bottom: 12px;">'
                            f'<div style="font-size:15px;font-weight:700;">{_rec} — {_sym} '
                            f'<span style="font-weight:400;font-size:13px;color:#555;">'
                            f'({_action_row["Name"]})</span></div>'
                            f'<div style="font-size:13px;margin-top:4px;">'
                            f'Unrealized G/L: <b>${_gl:,.0f}</b> ({_pct:.1f}%) | '
                            f'Gain Type: <b>{_gtype}</b> | '
                            f'Account: <b>{_action_row["Account"]}</b></div>'
                            f'<div style="font-size:12px;color:#444;margin-top:6px;">{_detail}</div>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                        if _replacements:
                            _rep_cols = st.columns(min(len(_replacements), 3))
                            for _ri, _rep in enumerate(_replacements[:3]):
                                with _rep_cols[_ri]:
                                    st.markdown(
                                        f'<div style="background:#f8f9fa;border:1px solid #dee2e6;'
                                        f'border-radius:6px;padding:10px;text-align:center;">'
                                        f'<div style="font-size:16px;font-weight:700;color:#1a73e8;">'
                                        f'{_rep["symbol"]}</div>'
                                        f'<div style="font-size:12px;color:#333;">{_rep["name"]}</div>'
                                        f'<div style="font-size:11px;color:#666;margin-top:4px;">'
                                        f'💡 {_rep["reason"]}</div>'
                                        f'</div>',
                                        unsafe_allow_html=True,
                                    )
                            st.markdown("")

                st.markdown("---")

                # ── Educational expander ───────────────────────────────────
                with st.expander("📚 How Tax Harvesting Works — Strategy Guide", expanded=False):
                    st.markdown("""
**Tax Loss Harvesting**
- Sell a position with an unrealized loss to "realize" the loss for tax purposes.
- Immediately buy a *similar but not identical* security to maintain your market exposure.
- The realized loss offsets capital gains dollar-for-dollar. If losses exceed gains, up to **$3,000/year** can offset ordinary income. Excess losses carry forward indefinitely.
- **Wash Sale Rule:** You cannot buy the same (or substantially identical) security within **30 days before or after** the sale. Violating this rule disallows the loss.

**Tax Gain Harvesting (at 0% LTCG Rate)**
- When your income falls in the **0% long-term capital gains bracket**, you can sell appreciated positions and pay *zero federal tax* on the gain.
- Immediately repurchase the same security to reset your cost basis higher — reducing future taxable gains.
- This is most powerful during low-income years: early retirement, sabbaticals, or years with large deductions.

**Stock Indexing Strategy**
- Periodically review your brokerage account for positions that have declined ≥ 10% from cost basis (or from a recent market high).
- Replace losers with similar ETFs or stocks in the same sector to maintain your target allocation.
- Example: S&P 500 drops 10% → sell NVDA (down 15%) → buy AMD or SOXX → book the loss, stay invested in semiconductors.

**Long-Term vs Short-Term**
- **Long-Term (LT):** Held > 1 year. Taxed at 0%, 15%, or 20% depending on income.
- **Short-Term (ST):** Held ≤ 1 year. Taxed as ordinary income (10%–37%).
- Prefer to harvest LT gains at 0% and LT losses (same rate benefit as ST losses but with better holding-period optics).

**Account Location**
- Only **Brokerage (taxable)** accounts are relevant. Gains/losses in Traditional IRA, Roth IRA, or 401(k) accounts are not taxable events.

**Donor Advised Fund (DAF) Bundling**
- A DAF is a charitable giving account: you contribute assets, receive an immediate tax deduction, and recommend grants to charities over time.
- **Bundling:** Instead of giving $5,000/year (never exceeding the standard deduction), contribute $15,000 every 3 years — itemize in the bundle year, take the standard deduction in the other 2 years.
- **Appreciated securities:** Donate long-term appreciated stock directly to the DAF. You deduct the full fair-market value AND pay zero capital gains tax on the embedded gain.
- **IRS limits:** Securities donations deductible up to 30% of AGI; cash up to 60% of AGI. Excess carries forward 5 years (IRC §170(d)).
                    """)

                st.markdown("---")

                # ── DAF Bundling Advisor ───────────────────────────────────
                st.markdown("#### 🏦 Donor Advised Fund (DAF) Bundling Advisor")
                st.caption(
                    "A DAF lets you **front-load multiple years of charitable giving** into a single "
                    "high-deduction year, then distribute grants to charities over time. "
                    "Donating **low-cost-basis appreciated securities** (instead of cash) avoids "
                    "capital gains tax entirely while still claiming the full fair-market-value deduction."
                )

                with st.form("daf_inputs_form", border=False):
                    _daf_col1, _daf_col2, _daf_col3, _daf_col4, _daf_col5 = st.columns([3, 2, 3, 2, 1])
                    with _daf_col1:
                        _daf_annual_giving = st.number_input(
                            "Annual Charitable Giving ($)",
                            min_value=0,
                            max_value=500_000,
                            value=st.session_state.get("daf_annual_giving_val", 5_000),
                            step=500,
                            help="Your normal annual charitable giving amount. The bundling strategy "
                                 "front-loads multiple years into one DAF contribution.",
                        )
                    with _daf_col2:
                        _daf_years_bundle = st.number_input(
                            "Years to Bundle",
                            min_value=2,
                            max_value=5,
                            value=st.session_state.get("daf_years_bundle_val", 3),
                            step=1,
                            help="How many years of giving to front-load into a single DAF contribution. "
                                 "Typically 2–5 years. The DAF then distributes grants over those years.",
                        )
                    with _daf_col3:
                        _daf_std_deduction = st.number_input(
                            "Standard Deduction ($)",
                            min_value=0,
                            max_value=100_000,
                            value=st.session_state.get("daf_std_deduction_val", 30_000),
                            step=500,
                            help="Your standard deduction for the bundle year (2025 MFJ: $30,000). "
                                 "Bundling is only beneficial when the DAF contribution exceeds this.",
                        )
                    with _daf_col4:
                        _daf_marginal_rate = st.number_input(
                            "Marginal Tax Rate (%)",
                            min_value=0,
                            max_value=50,
                            value=st.session_state.get("daf_marginal_rate_val", 22),
                            step=1,
                            help="Your federal marginal income tax rate in the bundle year. "
                                 "Higher rates = greater tax savings from itemizing.",
                        )
                    with _daf_col5:
                        st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
                        _daf_submitted = st.form_submit_button("Update", use_container_width=True)
                    if _daf_submitted:
                        st.session_state["daf_annual_giving_val"]  = int(_daf_annual_giving)
                        st.session_state["daf_years_bundle_val"]   = int(_daf_years_bundle)
                        st.session_state["daf_std_deduction_val"]  = int(_daf_std_deduction)
                        st.session_state["daf_marginal_rate_val"]  = int(_daf_marginal_rate)

                _daf_annual_giving  = st.session_state.get("daf_annual_giving_val",  5_000)
                _daf_years_bundle   = st.session_state.get("daf_years_bundle_val",   3)
                _daf_std_deduction  = st.session_state.get("daf_std_deduction_val",  30_000)
                _daf_marginal_rate  = st.session_state.get("daf_marginal_rate_val",  22)

                # Identify DAF donation candidates from the harvesting analysis
                _daf_candidates = identify_daf_candidates(_h_analysis)

                # Run bundling analysis
                _daf_analysis = analyze_daf_bundling(
                    estimated_agi      = float(_h_agi),
                    annual_giving      = float(_daf_annual_giving),
                    years_to_bundle    = int(_daf_years_bundle),
                    marginal_rate      = float(_daf_marginal_rate) / 100.0,
                    standard_deduction = float(_daf_std_deduction),
                    ltcg_rate          = _h_ltcg_rate,
                    securities_candidates = _daf_candidates,
                    year               = _h_year,
                )

                # ── DAF summary metrics ────────────────────────────────────
                _daf_m1, _daf_m2, _daf_m3, _daf_m4, _daf_m5 = st.columns(5)
                with _daf_m1:
                    st.metric(
                        "Bundled Contribution",
                        f"${_daf_analysis.bundled_contribution:,.0f}",
                        help=f"{int(_daf_years_bundle)} years × ${float(_daf_annual_giving):,.0f}/yr",
                    )
                with _daf_m2:
                    st.metric(
                        "Deductible Amount",
                        f"${_daf_analysis.deductible_amount:,.0f}",
                        help="AGI-limited deductible amount (60% AGI cap for combined contributions).",
                    )
                with _daf_m3:
                    _incr = max(0.0, _daf_analysis.deductible_amount - _daf_analysis.standard_deduction)
                    st.metric(
                        "Incremental Deduction",
                        f"${_incr:,.0f}",
                        help="Amount above the standard deduction — this is what actually reduces your taxes.",
                    )
                with _daf_m4:
                    st.metric(
                        "Est. Tax Savings",
                        f"${_daf_analysis.tax_savings_vs_standard:,.0f}",
                        delta=f"vs. standard deduction each year",
                        delta_color="normal" if _daf_analysis.tax_savings_vs_standard > 0 else "off",
                        help="Incremental federal tax savings from itemizing via DAF vs. taking the "
                             "standard deduction every year.",
                    )
                with _daf_m5:
                    st.metric(
                        "CG Tax Avoided",
                        f"${_daf_analysis.total_avoided_cg_tax:,.0f}",
                        help="Estimated capital gains tax avoided by donating appreciated securities "
                             "instead of selling them first.",
                    )

                # ── Recommendation banner ──────────────────────────────────
                _rec_color = (
                    "#f0fff4" if _daf_analysis.recommendation.startswith("🟢")
                    else ("#fffbf0" if _daf_analysis.recommendation.startswith("🟡")
                          else "#f8f9fa")
                )
                _rec_border = (
                    "#21c354" if _daf_analysis.recommendation.startswith("🟢")
                    else ("#ffa500" if _daf_analysis.recommendation.startswith("🟡")
                          else "#adb5bd")
                )
                st.markdown(
                    f'<div style="border-left:4px solid {_rec_border};background:{_rec_color};'
                    f'padding:12px 16px;border-radius:6px;margin:12px 0;">'
                    f'<div style="font-size:15px;font-weight:700;">{_daf_analysis.recommendation}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # ── Notes ──────────────────────────────────────────────────
                for _note in _daf_analysis.notes:
                    st.info(_note)

                if _daf_analysis.carryforward_amount > 0:
                    st.warning(
                        f"⚠️ ${_daf_analysis.carryforward_amount:,.0f} of your contribution exceeds "
                        f"the AGI deduction limit and carries forward for up to 5 years (IRC §170(d))."
                    )

                # ── Securities donation candidates table ───────────────────
                if _daf_candidates:
                    st.markdown("##### 📋 Appreciated Securities — DAF Donation Candidates")
                    st.caption(
                        "These long-term appreciated positions are ideal for DAF donation: "
                        "you receive a deduction for the **full fair-market value** and pay "
                        "**zero capital gains tax** on the embedded gain. "
                        "Donate securities **before** selling them."
                    )
                    _daf_cand_rows = [
                        {
                            "Account":        c.account,
                            "Symbol":         c.symbol,
                            "Name":           c.name,
                            "Qty":            f"{c.qty:,.2f}",
                            "Cost Basis":     f"${c.cost_basis:,.0f}",
                            "Current Value":  f"${c.current_value:,.0f}",
                            "Unrealized Gain":f"${c.unrealized_gain:,.0f}",
                            "Gain %":         f"{c.gain_pct:.1f}%",
                            "Days Held":      c.days_held,
                            "Gain Type":      c.gain_type,
                            "CG Tax Avoided": f"${c.avoided_cg_tax:,.0f}",
                        }
                        for c in _daf_candidates
                    ]
                    _daf_cand_df = pd.DataFrame(_daf_cand_rows)
                    st.dataframe(_daf_cand_df, hide_index=True, width='stretch')
                else:
                    st.info(
                        "ℹ️ No long-term appreciated securities found in your brokerage account. "
                        "Consider a cash contribution to the DAF, or wait until positions "
                        "have been held > 1 year with meaningful gains."
                    )

                # ── DAF Strategy Guide expander ────────────────────────────
                with st.expander("📚 Donor Advised Fund (DAF) Bundling — Strategy Guide", expanded=False):
                    st.markdown("""
**What is a Donor Advised Fund (DAF)?**
- A DAF is a charitable giving account sponsored by a public charity (e.g., Fidelity Charitable, Schwab Charitable, Vanguard Charitable).
- You make an irrevocable contribution, receive an **immediate tax deduction**, and then recommend grants to your chosen charities over time — on your own schedule.

**The Bundling Strategy**
- Most taxpayers give small amounts annually (e.g., $5,000/yr) that never exceed the standard deduction, so they receive **no incremental tax benefit**.
- **Bundling** front-loads 2–5 years of giving into a single DAF contribution (e.g., $15,000 every 3 years).
- In the bundle year you **itemize** and deduct the full contribution; in the off-years you take the standard deduction.
- Net result: you give the same total amount to charity but capture **thousands of dollars in additional tax savings**.

**Donating Appreciated Securities (the Power Move)**
- Instead of donating cash, transfer **long-term appreciated stock or ETFs** directly to the DAF.
- You deduct the **full fair-market value** of the securities — not just your cost basis.
- You pay **zero capital gains tax** on the embedded gain (the gain is never "realized").
- Example: You own 50 shares of a stock worth $10,000 with a cost basis of $2,000. Donate to DAF → deduct $10,000, avoid $1,200 in capital gains tax (at 15% LTCG rate). Net benefit vs. selling first and donating cash: **$1,200 saved**.

**IRS Deduction Limits (IRC §170)**
| Contribution Type | AGI Deduction Limit |
|---|---|
| Cash to DAF | 60% of AGI |
| Appreciated securities to DAF | 30% of AGI |
| Combined (cash + securities) | 60% of AGI |
- Contributions exceeding the AGI limit **carry forward for up to 5 years**.

**Step-by-Step: How to Execute**
1. Open a DAF account at Fidelity Charitable, Schwab Charitable, or Vanguard Charitable (free, takes ~15 minutes).
2. Identify long-term appreciated securities in your brokerage account (held > 1 year, meaningful unrealized gain).
3. Initiate an **in-kind transfer** of the securities to your DAF — do **not** sell them first.
4. The DAF sells the securities internally (no capital gains to you) and invests the proceeds.
5. Claim the deduction on Schedule A in the bundle year.
6. Recommend grants to your chosen charities from the DAF over the following years.

**When Bundling Makes Sense**
- 🟢 **Strong case:** Your bundled contribution exceeds the standard deduction AND you have appreciated securities to donate.
- 🟡 **Moderate case:** Bundled contribution exceeds the standard deduction but only cash is available.
- 🔴 **Weak case:** Bundled contribution does not exceed the standard deduction — no itemizing benefit (though the CG tax avoidance on securities still applies).

**Key Risks & Considerations**
- DAF contributions are **irrevocable** — once contributed, funds must eventually go to charity.
- You control the *timing* of grants but cannot reclaim the assets for personal use.
- The DAF sponsor invests the assets; choose an investment option aligned with your time horizon for grantmaking.
- State income tax deductibility varies — check your state's rules.
                    """)

        except Exception as _h_err:
            st.error(f"⚠️ Error running tax harvesting analysis: {_h_err}")
            st.info("Ensure current market prices are accessible and portfolio data is loaded correctly.")


    # ======================================================================
    # ⚖️ PORTFOLIO REBALANCING TAB
    # ======================================================================
    with rebalance_tab:
        st.markdown("## ⚖️ Portfolio Rebalancing")
        st.caption(
            "Calculates your current **Cash / Bonds / Stocks** allocation across all accounts "
            "and flags when any asset class drifts more than the threshold from its target. "
            "Rebalancing suggestions prioritise tax-advantaged accounts first (no tax event), "
            "then use tax-loss harvesting in Brokerage, and finally redirect new contributions."
        )

        # ── Target allocation inputs ────────────────────────────────────────
        st.markdown("#### 🎯 Target Allocation & Drift Threshold")
        _rb_col1, _rb_col2, _rb_col3, _rb_col4 = st.columns(4)
        with _rb_col1:
            _rb_cash_tgt = st.number_input(
                "Target Cash %",
                min_value=0, max_value=100, value=10, step=1,
                help="Target percentage of total portfolio held as cash / money-market.",
                key="rb_cash_tgt",
            )
        with _rb_col2:
            _rb_bonds_tgt = st.number_input(
                "Target Bonds %",
                min_value=0, max_value=100, value=10, step=1,
                help="Target percentage of total portfolio held in bonds / fixed income.",
                key="rb_bonds_tgt",
            )
        with _rb_col3:
            _rb_stocks_tgt = st.number_input(
                "Target Stocks %",
                min_value=0, max_value=100, value=80, step=1,
                help="Target percentage of total portfolio held in equities.",
                key="rb_stocks_tgt",
            )
        with _rb_col4:
            _rb_drift = st.number_input(
                "Drift Threshold %",
                min_value=1, max_value=20, value=5, step=1,
                help="Trigger rebalancing when any asset class drifts this many percentage points from its target.",
                key="rb_drift",
            )

        # Validate weights sum to 100
        _rb_total = _rb_cash_tgt + _rb_bonds_tgt + _rb_stocks_tgt
        if _rb_total != 100:
            st.error(
                f"⚠️ Target weights must sum to 100% — currently {_rb_total}%. "
                "Adjust Cash, Bonds, or Stocks targets."
            )
        else:
            st.markdown("---")

            try:
                with st.spinner("Fetching current prices and computing rebalancing plan…"):
                    _rb_report = compute_rebalance_plan(
                        month=curr_month,
                        year=curr_year,
                        target_cash_pct=float(_rb_cash_tgt),
                        target_bonds_pct=float(_rb_bonds_tgt),
                        target_stocks_pct=float(_rb_stocks_tgt),
                        drift_threshold_pct=float(_rb_drift),
                    )

                # ── Top-level status banner ─────────────────────────────────
                if _rb_report.drift_triggered:
                    st.warning(
                        f"🔴 **Rebalancing Required** — one or more asset classes have drifted "
                        f"more than {_rb_report.drift_threshold_pct:.0f}% from their targets."
                    )
                else:
                    st.success(
                        f"✅ **Portfolio is balanced** — all asset classes are within "
                        f"{_rb_report.drift_threshold_pct:.0f}% of their targets."
                    )

                # ── Asset-class summary metrics ─────────────────────────────
                st.markdown(f"#### 📊 Asset Class Allocation  (Total Portfolio: ${_rb_report.total_portfolio_value:,.0f})")
                _rb_sum_df = build_rebalance_display_df(_rb_report)

                _rb_mc1, _rb_mc2, _rb_mc3 = st.columns(3)
                for _rb_col_idx, (_rb_mc, _rb_ac) in enumerate(
                    zip([_rb_mc1, _rb_mc2, _rb_mc3], ["Cash", "Bonds", "Stocks"])
                ):
                    _rb_row = _rb_sum_df[_rb_sum_df["Asset Class"] == _rb_ac]
                    if not _rb_row.empty:
                        _rb_r = _rb_row.iloc[0]
                        with _rb_mc:
                            _rb_drift_val = float(_rb_r["Drift %"])
                            _rb_delta_str = f"{_rb_drift_val:+.1f}% vs {_rb_r['Target %']:.0f}% target"
                            _rb_delta_clr = "normal" if abs(_rb_drift_val) < float(_rb_drift) else "inverse"
                            st.metric(
                                label=f"{_rb_ac}",
                                value=f"{_rb_r['Current %']:.1f}%  (${_rb_r['Current Value']:,.0f})",
                                delta=_rb_delta_str,
                                delta_color=_rb_delta_clr,
                                help=f"Target: {_rb_r['Target %']:.0f}%  |  Delta: ${_rb_r['Delta $']:,.0f}",
                            )

                # ── Allocation bar chart ────────────────────────────────────
                _rb_fig_cols = st.columns([2, 1])
                with _rb_fig_cols[0]:
                    import plotly.graph_objects as _go_rb
                    _rb_bar = _go_rb.Figure()
                    _rb_colors = {"Cash": "#f6cf71", "Bonds": "#8be0a4", "Stocks": "#b497e7"}
                    for _rb_ac in ["Cash", "Bonds", "Stocks"]:
                        _rb_row = _rb_sum_df[_rb_sum_df["Asset Class"] == _rb_ac]
                        if not _rb_row.empty:
                            _rb_r = _rb_row.iloc[0]
                            _rb_bar.add_trace(_go_rb.Bar(
                                name=_rb_ac,
                                x=["Current", "Target"],
                                y=[float(_rb_r["Current %"]), float(_rb_r["Target %"])],
                                marker_color=_rb_colors.get(_rb_ac, "#aaa"),
                                text=[f"{float(_rb_r['Current %']):.1f}%", f"{float(_rb_r['Target %']):.1f}%"],
                                textposition="auto",
                            ))
                    _rb_bar.update_layout(
                        barmode="stack",
                        title="Current vs Target Allocation",
                        yaxis_title="Allocation %",
                        plot_bgcolor="white", paper_bgcolor="white",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                        margin=dict(t=50, l=10, r=10, b=10),
                        yaxis=dict(range=[0, 105]),
                    )
                    st.plotly_chart(_rb_bar, width="stretch")

                with _rb_fig_cols[1]:
                    # Pie chart of current allocation
                    _rb_pie = _go_rb.Figure(_go_rb.Pie(
                        labels=_rb_sum_df["Asset Class"].tolist(),
                        values=_rb_sum_df["Current Value"].tolist(),
                        marker_colors=[_rb_colors.get(ac, "#aaa") for ac in _rb_sum_df["Asset Class"].tolist()],
                        textinfo="label+percent",
                        hole=0.35,
                    ))
                    _rb_pie.update_layout(
                        title="Current Mix",
                        plot_bgcolor="white", paper_bgcolor="white",
                        margin=dict(t=50, l=10, r=10, b=10),
                        showlegend=False,
                    )
                    st.plotly_chart(_rb_pie, width="stretch")

                st.markdown("---")

                # ── Brokerage cash cushion ──────────────────────────────────
                st.markdown("#### 💵 Brokerage Cash Cushion")
                _rb_brok_pct = _rb_report.brokerage_cash_pct * 100
                if _rb_report.brokerage_cash_ok:
                    st.success(
                        f"✅ Brokerage cash cushion: **{_rb_brok_pct:.1f}%** "
                        f"(target ≥ 10%) — adequate liquidity maintained."
                    )
                else:
                    st.warning(
                        f"⚠️ Brokerage cash cushion: **{_rb_brok_pct:.1f}%** "
                        f"(target ≥ 10%) — consider adding MF:CASH to the Brokerage account."
                    )

                st.markdown("---")

                # ── Account-location issues ─────────────────────────────────
                if _rb_report.location_issues:
                    st.markdown("#### 🏦 Account Location Recommendations")
                    st.caption(
                        "Optimal asset location reduces taxes over time. "
                        "Bonds → Traditional IRA (ordinary income anyway). "
                        "Stocks → Roth (tax-free growth) or Brokerage (LTCG rates). "
                        "Municipal bonds & Treasuries may stay in Brokerage."
                    )
                    for _rb_issue in _rb_report.location_issues:
                        if _rb_issue.startswith("⚠️"):
                            st.warning(_rb_issue)
                        elif _rb_issue.startswith("💡"):
                            st.info(_rb_issue)
                        else:
                            st.write(_rb_issue)
                    st.markdown("---")

                # ── Holdings by asset class ─────────────────────────────────
                with st.expander("📋 Holdings Classified by Asset Class", expanded=False):
                    _rb_hold_df = build_holdings_by_class_df(_rb_report)
                    if not _rb_hold_df.empty:
                        _rb_hold_df["Current Value"] = _rb_hold_df["Current Value"].map(lambda x: f"${x:,.0f}")
                        _rb_hold_df["Cost Basis"]    = _rb_hold_df["Cost Basis"].map(lambda x: f"${x:,.0f}")
                        _rb_hold_df["Unrealized G/L"]= _rb_hold_df["Unrealized G/L"].map(lambda x: f"${x:,.0f}")
                        _rb_hold_df["Current Price"] = _rb_hold_df["Current Price"].map(lambda x: f"${x:,.2f}")
                        st.dataframe(_rb_hold_df, hide_index=True, width="stretch")

                # ── Rebalancing action plan ─────────────────────────────────
                st.markdown("#### 🔄 Rebalancing Action Plan")
                if not _rb_report.drift_triggered and _rb_report.brokerage_cash_ok and not _rb_report.location_issues:
                    st.info("No rebalancing actions required at this time.")
                else:
                    _rb_act_df = build_actions_display_df(_rb_report)
                    if _rb_act_df.empty:
                        st.info("No specific actions generated.")
                    else:
                        st.caption(
                            "Actions are ordered by priority. "
                            "**Priority 1** = rebalance inside tax-advantaged accounts (no tax event). "
                            "**Brokerage sells** may trigger a taxable event — check LTCG rate first. "
                            "**Redirect Contributions** = direct new money / dividends to under-weight classes."
                        )
                        # Display each action as a styled card
                        for _, _rb_act in _rb_act_df.iterrows():
                            _rb_action_str = str(_rb_act["Action"])
                            _rb_tax_str    = str(_rb_act["Tax Impact"])
                            _rb_is_sell    = "Sell" in _rb_action_str
                            _rb_is_buy     = "Buy" in _rb_action_str
                            _rb_is_redir   = "Redirect" in _rb_action_str

                            if _rb_is_sell and "Brokerage" in _rb_action_str:
                                _rb_card_bg     = "#fff8f0"
                                _rb_card_border = "#f58518"
                            elif _rb_is_sell:
                                _rb_card_bg     = "#f0f8ff"
                                _rb_card_border = "#4c78a8"
                            elif _rb_is_buy:
                                _rb_card_bg     = "#f0fff4"
                                _rb_card_border = "#21c354"
                            else:
                                _rb_card_bg     = "#f8f9fa"
                                _rb_card_border = "#6c757d"

                            st.markdown(
                                f'<div style="border-left:4px solid {_rb_card_border};'
                                f'background:{_rb_card_bg};padding:12px 16px;'
                                f'border-radius:6px;margin-bottom:10px;">'
                                f'<div style="font-size:14px;font-weight:700;">'
                                f'#{int(_rb_act["Priority"])} — {_rb_action_str} '
                                f'<span style="color:#555;font-weight:400;">'
                                f'[{_rb_act["Asset Class"]}]</span> '
                                f'<span style="font-size:13px;color:#1a73e8;">{_rb_act["Symbol"]}</span>'
                                f'</div>'
                                f'<div style="font-size:12px;margin-top:4px;">'
                                f'Account: <b>{_rb_act["Account"]}</b> | '
                                f'Amount: <b>${float(_rb_act["Amount"]):,.0f}</b> | '
                                f'Tax Impact: <b>{_rb_tax_str}</b>'
                                f'</div>'
                                f'<div style="font-size:12px;color:#444;margin-top:6px;">'
                                f'{_rb_act["Rationale"]}</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                st.markdown("---")

                # ── Educational expander ────────────────────────────────────
                with st.expander("📚 Rebalancing Strategy Guide", expanded=False):
                    st.markdown("""
**Why Rebalance?**
Over time, asset classes grow at different rates, causing your portfolio to drift from its target allocation.
A portfolio that started at 10% Cash / 10% Bonds / 80% Stocks might drift to 5% / 12% / 83% after a strong
equity run — increasing risk beyond your intended level.

**The 5% Drift Rule**
Rebalance when any asset class deviates more than **5 percentage points** from its target.
This balances transaction costs against the risk of staying too far off-target.

**Rebalancing Priority (Tax-Efficient Order)**
1. **Inside Traditional or Roth accounts first** — no tax event. Sell over-weight assets and buy under-weight ones within the same account.
2. **Tax-Loss Harvesting in Brokerage** — if you must sell in a taxable account, prioritise positions with unrealized losses. Book the loss, buy a wash-sale-safe replacement in the target asset class.
3. **Redirect new contributions & dividends** — direct new money to under-weight asset classes to restore balance without selling anything.
4. **Sell appreciated Brokerage positions last** — only if necessary, and check your LTCG rate first (0% if income is low enough).

**Optimal Asset Location**
| Asset Class | Best Account | Why |
|---|---|---|
| Bonds (general) | Traditional IRA | Interest is ordinary income — deferred until withdrawal |
| Municipal Bonds | Brokerage | Interest is federally tax-exempt |
| Treasuries | Brokerage | State-tax-exempt; acceptable in taxable accounts |
| Stocks (growth) | Roth IRA | Tax-free growth on highest-return assets |
| Stocks (dividend) | Brokerage | Qualified dividends taxed at LTCG rates |
| Cash / Money Market | Brokerage (≥ 10%) | Liquidity cushion for rebalancing trades |

**Brokerage Cash Cushion**
Keep at least **10% of your Brokerage account** in MF:CASH (money market).
This provides liquidity for rebalancing trades, tax payments, and opportunistic purchases without forcing a sale.
                    """)

            except ValueError as _rb_ve:
                st.error(f"⚠️ Configuration error: {_rb_ve}")
            except Exception as _rb_err:
                st.error(f"⚠️ Error computing rebalancing plan: {_rb_err}")
                st.info("Ensure current market prices are accessible and portfolio data is loaded correctly.")


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
        except (ValueError, TypeError):
            ssi_age_s = 70; conv_tax_rate_s = 12; annual_expenses_s = 50000
            expense_multiplier_s = 4; rate_of_return_s = 0.06

        # Parameters summary bar
        param_col1, param_col2, param_col3 = st.columns(3)
        with param_col1:
            st.metric("Social Security Age", ssi_age_s)
            st.metric("Annual Expenses", f"${annual_expenses_s:,.0f}")
        with param_col2:
            st.metric("Max Roth Conv Rate", f"{conv_tax_rate_s}%")
            st.metric("Expense Multiplier", f"{expense_multiplier_s}x")
        with param_col3:
            st.metric("Rate of Return", f"{rate_of_return_s*100:.1f}%")

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

        col_daf_type, col_daf_note, _col_daf3, _col_daf4, _col_daf5 = st.columns(5)
        with col_daf_type:
            daf_contribution_type = st.selectbox(
                "DAF Contribution Type",
                ["cash", "securities"],
                key="tp_daf_type",
                on_change=clear_submit,
                help=(
                    "**Cash:** deductible up to 60% of AGI (IRC §170). "
                    "**Securities:** donate appreciated long-term stock directly — "
                    "deductible up to 30% of AGI, and you avoid capital gains tax on the embedded gain."
                ),
            )
        with col_daf_note:
            _daf_limit_pct = "60%" if daf_contribution_type == "cash" else "30%"
            st.info(
                f"ℹ️ **{daf_contribution_type.title()} limit:** {_daf_limit_pct} of AGI. "
                + ("Excess carries forward 5 years." if maxdaf == "Y" else ""),
                icon=None,
            )

        col14b, col15, _col16, _col17, _col18 = st.columns(5)
        with col14b:
            roth_amount = st.number_input("Roth Conversion Amount", key="tp_roth_amt", on_change=clear_submit)
        with col15:
            pd_tax_amount = st.number_input("Estimated prepaid Fed taxes", key="tp_prepaid", on_change=clear_submit)
        summarize_button = st.button("Project this years changes!", key="tp_summarize")

    if summarize_button:
        try:
            taxratedf  = cast(pd.DataFrame, get_income_tax_brackets(year))
            cgdf       = cast(pd.DataFrame, get_cap_gains_brackets(year))
            irmaadf    = get_medicare_costs(year)
            stddectdf  = get_std_deduction(year)
            atmdf      = get_atm_costs(year)
        except Exception as e:
            st.error(f"Error loading tax data for year {year}: {e}")
            st.stop()

        try:
            calc_daf = calc_daf_value(
                deferred_distribution + wages,
                interest,
                daf1,
                maxdaf,
                contribution_type=daf_contribution_type,
                stddectdf=stddectdf,
            )
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

with tab_mc:
    st.header("🎲 Monte Carlo Simulation")
    st.markdown(
        "Run 10,000+ retirement simulations to estimate the probability your portfolio "
        "survives your lifetime under realistic market volatility."
    )
    st.markdown("---")

    (
        mc_sim_tab,
        mc_stress_tab,
        mc_longevity_tab,
        mc_heatmap_tab,
        mc_compare_tab,
    ) = st.tabs([
        "🎯 Run Simulation",
        "⚠️ Stress Tests",
        "🕐 Longevity Risk",
        "🗺️ Success Heatmap",
        "📊 Scenario Comparison",
    ])

    # -----------------------------------------------------------------------
    # Shared sidebar inputs (stored in session state for reuse across sub-tabs)
    # -----------------------------------------------------------------------
    with st.sidebar.expander("🎲 Monte Carlo Settings", expanded=False):
        _mc_portfolio = st.number_input(
            "Starting Portfolio ($)", min_value=10_000, value=1_500_000,
            step=50_000, key="mc_portfolio"
        )
        _mc_withdrawal = st.number_input(
            "Annual Withdrawal ($)", min_value=1_000, value=80_000,
            step=5_000, key="mc_withdrawal"
        )
        _mc_start_age = st.number_input(
            "Retirement Age", min_value=40, max_value=80, value=62, key="mc_start_age"
        )
        _mc_end_age = st.number_input(
            "Plan To Age", min_value=70, max_value=110, value=90, key="mc_end_age"
        )
        _mc_ss = st.number_input(
            "Annual Social Security ($)", min_value=0, value=40_000,
            step=1_000, key="mc_ss"
        )
        _mc_ss_age = st.number_input(
            "SS Start Age", min_value=62, max_value=70, value=70, key="mc_ss_age"
        )
        _mc_inflation = st.slider(
            "Inflation Rate", min_value=0.01, max_value=0.10,
            value=0.029, step=0.001, format="%.1f%%", key="mc_inflation"
        )
        _mc_allocation = st.selectbox(
            "Portfolio Allocation", list(PORTFOLIO_PRESETS.keys()),
            index=1, key="mc_allocation"
        )
        _mc_n_sims = st.select_slider(
            "Simulations", options=[1_000, 2_000, 5_000, 10_000, 20_000],
            value=10_000, key="mc_n_sims"
        )

    def _build_mc_inputs() -> MonteCarloInputs:
        return MonteCarloInputs(
            initial_portfolio=float(st.session_state.get("mc_portfolio", 1_500_000)),
            annual_withdrawal=float(st.session_state.get("mc_withdrawal", 80_000)),
            start_age=int(st.session_state.get("mc_start_age", 62)),
            end_age=int(st.session_state.get("mc_end_age", 90)),
            portfolio_allocation=PORTFOLIO_PRESETS[
                st.session_state.get("mc_allocation", "Moderate (70/30)")
            ],
            inflation_rate=float(st.session_state.get("mc_inflation", 0.029)),
            withdrawal_growth_rate=float(st.session_state.get("mc_inflation", 0.029)),
            social_security_annual=float(st.session_state.get("mc_ss", 40_000)),
            ss_start_age=int(st.session_state.get("mc_ss_age", 70)),
            n_simulations=int(st.session_state.get("mc_n_sims", 10_000)),
            random_seed=42,
        )

    # -----------------------------------------------------------------------
    # SUB-TAB 1: Run Simulation
    # -----------------------------------------------------------------------
    with mc_sim_tab:
        st.subheader("🎯 Monte Carlo Simulation")
        st.markdown(
            "Configure inputs in the **Monte Carlo Settings** sidebar panel, then click Run."
        )

        # Quick input summary
        _mc_c1, _mc_c2, _mc_c3, _mc_c4 = st.columns(4)
        _mc_c1.metric("Starting Portfolio", f"${st.session_state.get('mc_portfolio', 1_500_000):,.0f}")
        _mc_c2.metric("Annual Withdrawal", f"${st.session_state.get('mc_withdrawal', 80_000):,.0f}")
        _mc_c3.metric("Retirement Age", str(st.session_state.get("mc_start_age", 62)))
        _mc_c4.metric("Plan To Age", str(st.session_state.get("mc_end_age", 90)))

        if st.button("▶️ Run Monte Carlo Simulation", key="mc_run", type="primary"):
            with st.spinner(f"Running {st.session_state.get('mc_n_sims', 10_000):,} simulations…"):
                try:
                    _mc_inputs = _build_mc_inputs()
                    _mc_result = run_monte_carlo(_mc_inputs)
                    st.session_state["_mc_result"] = _mc_result
                    st.session_state["_mc_inputs"] = _mc_inputs
                except Exception as _mc_err:
                    st.error(f"Simulation error: {_mc_err}")
                    st.session_state.pop("_mc_result", None)

        if "_mc_result" in st.session_state:
            _r = st.session_state["_mc_result"]

            # Success probability gauge
            _sp = _r.success_probability
            _sp_color = "🟢" if _sp >= 0.90 else ("🟡" if _sp >= 0.75 else "🔴")
            st.markdown(f"## {_sp_color} Success Probability: **{_sp:.1%}**")
            st.caption(
                "Probability the portfolio survives to the plan end age across all simulations. "
                "Target: ≥ 90% for high confidence."
            )

            # Key metrics
            _rm1, _rm2, _rm3, _rm4 = st.columns(4)
            _rm1.metric("Median Final Portfolio", f"${_r.median_final_portfolio:,.0f}")
            _rm2.metric("10th Pct Final Portfolio", f"${_r.p10_final_portfolio:,.0f}")
            _rm3.metric("90th Pct Final Portfolio", f"${_r.p90_final_portfolio:,.0f}")
            _rm4.metric(
                "P10 Depletion Age",
                str(_r.years_to_depletion_p10) if _r.years_to_depletion_p10 else "Never ✅"
            )

            # Safe withdrawal rate
            with st.spinner("Calculating safe withdrawal rate…"):
                try:
                    _swr = get_safe_withdrawal_rate(st.session_state["_mc_inputs"])
                    _swr_pct = _swr / float(st.session_state.get("mc_portfolio", 1_500_000)) * 100
                    st.info(
                        f"💡 **Safe Withdrawal Rate at 90% confidence:** "
                        f"${_swr:,.0f}/year ({_swr_pct:.2f}% of portfolio)"
                    )
                except Exception:
                    pass

            # Fan chart
            st.markdown("#### 📈 Portfolio Outcome Fan Chart")
            st.caption(
                "Shaded bands show the range of outcomes across all simulations. "
                "The dark line is the median (50th percentile)."
            )
            _fan_df = build_fan_chart_df(_r)
            if not _fan_df.empty:
                _fan_fig = go.Figure()

                # Shaded bands (outermost to innermost)
                _band_pairs = [(5, 95, "rgba(99,110,250,0.08)"),
                               (10, 90, "rgba(99,110,250,0.12)"),
                               (25, 75, "rgba(99,110,250,0.20)")]
                for _lo, _hi, _color in _band_pairs:
                    _fan_fig.add_trace(go.Scatter(
                        x=list(_fan_df["age"]) + list(_fan_df["age"])[::-1],
                        y=list(_fan_df[f"p{_hi}"]) + list(_fan_df[f"p{_lo}"])[::-1],
                        fill="toself",
                        fillcolor=_color,
                        line=dict(color="rgba(0,0,0,0)"),
                        name=f"P{_lo}–P{_hi}",
                        showlegend=True,
                    ))

                # Median line
                _fan_fig.add_trace(go.Scatter(
                    x=_fan_df["age"], y=_fan_df["p50"],
                    mode="lines", name="Median (P50)",
                    line=dict(color="rgb(99,110,250)", width=2.5),
                ))

                # P10 line (danger zone)
                _fan_fig.add_trace(go.Scatter(
                    x=_fan_df["age"], y=_fan_df["p10"],
                    mode="lines", name="P10 (Pessimistic)",
                    line=dict(color="rgb(239,85,59)", width=1.5, dash="dash"),
                ))

                _fan_fig.update_layout(
                    title="Portfolio Value Distribution by Age",
                    xaxis_title="Age",
                    yaxis_title="Portfolio Value ($)",
                    yaxis_tickformat="$,.0f",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    hovermode="x unified",
                )
                st.plotly_chart(_fan_fig, use_container_width=True)

            # Success rate by age
            st.markdown("#### ✅ Probability of Success by Age")
            _sr_fig = go.Figure()
            _sr_fig.add_trace(go.Scatter(
                x=_fan_df["age"], y=_fan_df["success_rate"] * 100,
                mode="lines+markers",
                name="Success Rate",
                line=dict(color="rgb(0,204,150)", width=2),
                fill="tozeroy",
                fillcolor="rgba(0,204,150,0.15)",
            ))
            _sr_fig.add_hline(y=90, line_dash="dash", line_color="orange",
                              annotation_text="90% Target")
            _sr_fig.update_layout(
                title="Probability of Portfolio Survival by Age",
                xaxis_title="Age",
                yaxis_title="Success Rate (%)",
                yaxis_range=[0, 105],
            )
            st.plotly_chart(_sr_fig, use_container_width=True)

            # Sequence of returns risk
            st.markdown("#### 🔀 Sequence-of-Returns Risk Analysis")
            with st.spinner("Analyzing sequence risk…"):
                try:
                    _sor = analyze_sequence_of_returns_risk(st.session_state["_mc_inputs"])
                    _sor_c1, _sor_c2, _sor_c3 = st.columns(3)
                    _sor_c1.metric(
                        "Worst-Sequence Success Rate",
                        f"{_sor.get('worst_paths_success_rate', 0):.1%}",
                        delta=f"{(_sor.get('worst_paths_success_rate', 0) - _sor.get('overall_success_probability', 0)):.1%}",
                        delta_color="inverse",
                    )
                    _sor_c2.metric(
                        "Avg First-5yr Return (Worst)",
                        f"{_sor.get('avg_first5yr_return_worst', 0):.1%}"
                    )
                    _sor_c3.metric(
                        "Depletion Age (Worst Median)",
                        str(_sor.get("depletion_age_worst_median", "N/A"))
                    )
                    st.caption(
                        "Sequence risk: retiring into a bear market dramatically reduces success. "
                        "The worst 1% of sequences are shown above."
                    )
                except Exception as _sor_err:
                    st.caption(f"Sequence analysis unavailable: {_sor_err}")

            # Notes
            with st.expander("ℹ️ Simulation Notes", expanded=False):
                for _note in _r.notes:
                    st.caption(_note)

            # Download report
            st.markdown("---")
            _csv_bytes = generate_monte_carlo_report_csv(_r)
            st.download_button(
                label="📥 Download Monte Carlo Report (CSV)",
                data=_csv_bytes,
                file_name=f"monte_carlo_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                key="mc_download",
            )

    # -----------------------------------------------------------------------
    # SUB-TAB 2: Stress Tests
    # -----------------------------------------------------------------------
    with mc_stress_tab:
        st.subheader("⚠️ Stress Test Scenarios")
        st.markdown(
            "Test your portfolio against historical market crises and adverse scenarios."
        )

        _st_scenarios = st.multiselect(
            "Select Stress Scenarios",
            list(STRESS_SCENARIOS.keys()),
            default=list(STRESS_SCENARIOS.keys()),
            key="mc_stress_scenarios",
        )

        if st.button("▶️ Run Stress Tests", key="mc_stress_run", type="primary"):
            with st.spinner("Running stress scenarios…"):
                try:
                    _st_inputs = _build_mc_inputs()
                    _st_results = run_stress_tests(_st_inputs, _st_scenarios)
                    st.session_state["_mc_stress_results"] = _st_results
                    st.session_state["_mc_stress_inputs"] = _st_inputs
                except Exception as _st_err:
                    st.error(f"Stress test error: {_st_err}")

        if "_mc_stress_results" in st.session_state:
            _st_res = st.session_state["_mc_stress_results"]

            # Summary table
            st.markdown("#### Stress Test Summary")
            _st_rows = []
            for _s in _st_res:
                _sp_icon = "🟢" if _s.success_probability >= 0.90 else ("🟡" if _s.success_probability >= 0.75 else "🔴")
                _st_rows.append({
                    "Scenario": _s.scenario_name,
                    "Description": _s.description,
                    "Success": f"{_sp_icon} {_s.success_probability:.1%}",
                    "Median Final": f"${_s.median_final_portfolio:,.0f}",
                    "P10 Final": f"${_s.p10_final_portfolio:,.0f}",
                    "Depletion Age": str(_s.years_to_depletion_median) if _s.years_to_depletion_median else "Never",
                })
            st.dataframe(pd.DataFrame(_st_rows), use_container_width=True, hide_index=True)

            # Median path comparison chart
            st.markdown("#### Median Portfolio Path by Scenario")
            _path_fig = go.Figure()
            _ages = list(range(
                int(st.session_state.get("mc_start_age", 62)),
                int(st.session_state.get("mc_end_age", 90)),
            ))
            _colors = px.colors.qualitative.Plotly
            for _i, _s in enumerate(_st_res):
                if _s.portfolio_path_median:
                    _path_fig.add_trace(go.Scatter(
                        x=_ages[:len(_s.portfolio_path_median)],
                        y=_s.portfolio_path_median,
                        mode="lines",
                        name=_s.scenario_name,
                        line=dict(color=_colors[_i % len(_colors)], width=2),
                    ))
            _path_fig.update_layout(
                title="Median Portfolio Path — Stress Scenarios",
                xaxis_title="Age",
                yaxis_title="Portfolio Value ($)",
                yaxis_tickformat="$,.0f",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(_path_fig, use_container_width=True)

            # Download
            _st_csv = generate_monte_carlo_report_csv(
                st.session_state.get("_mc_result", run_monte_carlo(_build_mc_inputs())),
                stress_results=_st_res,
            )
            st.download_button(
                label="📥 Download Stress Test Report (CSV)",
                data=_st_csv,
                file_name=f"stress_test_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                key="mc_stress_download",
            )

    # -----------------------------------------------------------------------
    # SUB-TAB 3: Longevity Risk
    # -----------------------------------------------------------------------
    with mc_longevity_tab:
        st.subheader("🕐 Longevity Risk Analysis")
        st.markdown(
            "How does your portfolio hold up if you live longer than expected? "
            "Model outcomes to age 85, 90, 95, 100, and 105."
        )

        _lon_ages_selected = st.multiselect(
            "Longevity Scenarios",
            list(LONGEVITY_SCENARIOS.keys()),
            default=list(LONGEVITY_SCENARIOS.keys()),
            key="mc_longevity_scenarios",
        )

        if st.button("▶️ Run Longevity Analysis", key="mc_lon_run", type="primary"):
            with st.spinner("Running longevity scenarios…"):
                try:
                    _lon_inputs = _build_mc_inputs()
                    _lon_ages = {k: v for k, v in LONGEVITY_SCENARIOS.items() if k in _lon_ages_selected}
                    _lon_results = run_longevity_analysis(_lon_inputs, _lon_ages)
                    st.session_state["_mc_lon_results"] = _lon_results
                except Exception as _lon_err:
                    st.error(f"Longevity analysis error: {_lon_err}")

        if "_mc_lon_results" in st.session_state:
            _lon_res = st.session_state["_mc_lon_results"]

            # Summary table
            st.markdown("#### Longevity Scenario Summary")
            _lon_rows = []
            for _label, _mc in _lon_res.items():
                _sp_icon = "🟢" if _mc.success_probability >= 0.90 else ("🟡" if _mc.success_probability >= 0.75 else "🔴")
                _lon_rows.append({
                    "Scenario": _label,
                    "Plan To Age": _mc.inputs.end_age,
                    "Success": f"{_sp_icon} {_mc.success_probability:.1%}",
                    "Median Final": f"${_mc.median_final_portfolio:,.0f}",
                    "P10 Final": f"${_mc.p10_final_portfolio:,.0f}",
                    "P10 Depletion Age": str(_mc.years_to_depletion_p10) if _mc.years_to_depletion_p10 else "Never ✅",
                })
            st.dataframe(pd.DataFrame(_lon_rows), use_container_width=True, hide_index=True)

            # Success probability by longevity chart
            _lon_fig = go.Figure()
            _lon_labels = list(_lon_res.keys())
            _lon_success = [_lon_res[k].success_probability * 100 for k in _lon_labels]
            _lon_colors = [
                "rgb(0,204,150)" if s >= 90 else ("rgb(255,165,0)" if s >= 75 else "rgb(239,85,59)")
                for s in _lon_success
            ]
            _lon_fig.add_trace(go.Bar(
                x=_lon_labels,
                y=_lon_success,
                marker_color=_lon_colors,
                text=[f"{s:.1f}%" for s in _lon_success],
                textposition="outside",
            ))
            _lon_fig.add_hline(y=90, line_dash="dash", line_color="orange",
                               annotation_text="90% Target")
            _lon_fig.update_layout(
                title="Success Probability by Longevity Scenario",
                xaxis_title="Longevity Scenario",
                yaxis_title="Success Probability (%)",
                yaxis_range=[0, 110],
            )
            st.plotly_chart(_lon_fig, use_container_width=True)

            # Median fan chart overlay for all longevity scenarios
            st.markdown("#### Median Portfolio Path by Longevity")
            _lon_path_fig = go.Figure()
            _lon_colors_list = px.colors.qualitative.Plotly
            for _i, (_label, _mc) in enumerate(_lon_res.items()):
                _fan = build_fan_chart_df(_mc)
                if not _fan.empty:
                    _lon_path_fig.add_trace(go.Scatter(
                        x=_fan["age"], y=_fan["p50"],
                        mode="lines",
                        name=_label,
                        line=dict(color=_lon_colors_list[_i % len(_lon_colors_list)], width=2),
                    ))
            _lon_path_fig.update_layout(
                title="Median Portfolio Path — Longevity Scenarios",
                xaxis_title="Age",
                yaxis_title="Portfolio Value ($)",
                yaxis_tickformat="$,.0f",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(_lon_path_fig, use_container_width=True)

            # Download
            _lon_csv = generate_monte_carlo_report_csv(
                st.session_state.get("_mc_result", run_monte_carlo(_build_mc_inputs())),
                longevity_results=_lon_res,
            )
            st.download_button(
                label="📥 Download Longevity Report (CSV)",
                data=_lon_csv,
                file_name=f"longevity_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                key="mc_lon_download",
            )

    # -----------------------------------------------------------------------
    # SUB-TAB 4: Success Heatmap
    # -----------------------------------------------------------------------
    with mc_heatmap_tab:
        st.subheader("🗺️ Success Probability Heatmap")
        st.markdown(
            "See how success probability changes across different withdrawal amounts "
            "and portfolio allocations. Green = high confidence, Red = at risk."
        )

        _hm_col1, _hm_col2 = st.columns(2)
        with _hm_col1:
            _hm_base_withdrawal = st.number_input(
                "Base Annual Withdrawal ($)", min_value=10_000, value=80_000,
                step=5_000, key="hm_withdrawal"
            )
        with _hm_col2:
            _hm_n_sims = st.select_slider(
                "Simulations per Cell", options=[500, 1_000, 2_000],
                value=1_000, key="hm_n_sims",
                help="More simulations = more accurate but slower."
            )

        if st.button("▶️ Build Heatmap", key="mc_heatmap_run", type="primary"):
            with st.spinner("Building heatmap (this may take 30–60 seconds)…"):
                try:
                    _hm_inputs = MonteCarloInputs(
                        initial_portfolio=float(st.session_state.get("mc_portfolio", 1_500_000)),
                        annual_withdrawal=float(_hm_base_withdrawal),
                        start_age=int(st.session_state.get("mc_start_age", 62)),
                        end_age=int(st.session_state.get("mc_end_age", 90)),
                        portfolio_allocation=PORTFOLIO_PRESETS["Moderate (70/30)"],
                        inflation_rate=float(st.session_state.get("mc_inflation", 0.029)),
                        withdrawal_growth_rate=float(st.session_state.get("mc_inflation", 0.029)),
                        social_security_annual=float(st.session_state.get("mc_ss", 40_000)),
                        ss_start_age=int(st.session_state.get("mc_ss_age", 70)),
                        n_simulations=int(_hm_n_sims),
                        random_seed=42,
                    )
                    _hm_df = build_success_heatmap_df(_hm_inputs)
                    st.session_state["_mc_heatmap_df"] = _hm_df
                except Exception as _hm_err:
                    st.error(f"Heatmap error: {_hm_err}")

        if "_mc_heatmap_df" in st.session_state:
            _hm_df = st.session_state["_mc_heatmap_df"]
            st.markdown("#### Success Probability (%) by Withdrawal × Allocation")
            st.caption("Values are success probability %. Green ≥ 90%, Yellow 75–90%, Red < 75%.")

            # Style the dataframe
            _hm_display = _hm_df.set_index("Annual Withdrawal")

            def _color_success(val):
                try:
                    v = float(val)
                    if v >= 90:
                        return "background-color: rgba(0,204,150,0.4)"
                    elif v >= 75:
                        return "background-color: rgba(255,165,0,0.4)"
                    else:
                        return "background-color: rgba(239,85,59,0.4)"
                except (ValueError, TypeError):
                    return ""

            st.dataframe(
                _hm_display.style.applymap(_color_success),
                use_container_width=True,
            )

            # Heatmap chart
            _hm_fig = go.Figure(data=go.Heatmap(
                z=_hm_display.values,
                x=list(_hm_display.columns),
                y=list(_hm_display.index),
                colorscale=[
                    [0.0, "rgb(239,85,59)"],
                    [0.75, "rgb(255,165,0)"],
                    [0.90, "rgb(0,204,150)"],
                    [1.0, "rgb(0,150,100)"],
                ],
                zmin=0, zmax=100,
                text=_hm_display.values,
                texttemplate="%{text:.0f}%",
                colorbar=dict(title="Success %"),
            ))
            _hm_fig.update_layout(
                title="Success Probability Heatmap",
                xaxis_title="Portfolio Allocation",
                yaxis_title="Annual Withdrawal",
            )
            st.plotly_chart(_hm_fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # SUB-TAB 5: Scenario Comparison
    # -----------------------------------------------------------------------
    with mc_compare_tab:
        st.subheader("📊 Full Scenario Comparison")
        st.markdown(
            "Run baseline + all stress tests + all longevity scenarios in one shot "
            "and compare results side-by-side."
        )

        _cmp_stress = st.multiselect(
            "Stress Scenarios to Include",
            list(STRESS_SCENARIOS.keys()),
            default=list(STRESS_SCENARIOS.keys())[:3],
            key="mc_cmp_stress",
        )
        _cmp_longevity = st.multiselect(
            "Longevity Scenarios to Include",
            list(LONGEVITY_SCENARIOS.keys()),
            default=["Average (age 85)", "Long-Lived (age 95)", "Exceptional (age 105)"],
            key="mc_cmp_longevity",
        )

        if st.button("▶️ Run Full Comparison", key="mc_compare_run", type="primary"):
            with st.spinner("Running full scenario comparison…"):
                try:
                    _cmp_inputs = _build_mc_inputs()
                    _cmp_lon_ages = {k: v for k, v in LONGEVITY_SCENARIOS.items() if k in _cmp_longevity}
                    _cmp_result = run_full_scenario_comparison(
                        _cmp_inputs,
                        stress_scenarios=_cmp_stress,
                        longevity_ages=_cmp_lon_ages,
                    )
                    st.session_state["_mc_cmp_result"] = _cmp_result
                except Exception as _cmp_err:
                    st.error(f"Comparison error: {_cmp_err}")

        if "_mc_cmp_result" in st.session_state:
            _cmp = st.session_state["_mc_cmp_result"]
            _cmp_df = build_scenario_comparison_df(_cmp)

            st.markdown("#### All Scenarios — Side-by-Side")
            st.dataframe(_cmp_df, use_container_width=True, hide_index=True)

            # Success probability bar chart
            _cmp_fig = go.Figure()
            _cmp_labels = _cmp_df["Scenario"].tolist()
            _cmp_success_vals = []
            for _row in _cmp_df["Success Probability"]:
                try:
                    _cmp_success_vals.append(float(_row.replace("%", "").strip()))
                except (ValueError, AttributeError):
                    _cmp_success_vals.append(0.0)

            _cmp_bar_colors = [
                "rgb(0,204,150)" if v >= 90 else ("rgb(255,165,0)" if v >= 75 else "rgb(239,85,59)")
                for v in _cmp_success_vals
            ]
            _cmp_fig.add_trace(go.Bar(
                x=_cmp_labels,
                y=_cmp_success_vals,
                marker_color=_cmp_bar_colors,
                text=[f"{v:.1f}%" for v in _cmp_success_vals],
                textposition="outside",
            ))
            _cmp_fig.add_hline(y=90, line_dash="dash", line_color="orange",
                               annotation_text="90% Target")
            _cmp_fig.update_layout(
                title="Success Probability — All Scenarios",
                xaxis_title="Scenario",
                yaxis_title="Success Probability (%)",
                yaxis_range=[0, 115],
                xaxis_tickangle=-30,
            )
            st.plotly_chart(_cmp_fig, use_container_width=True)

            # Full download
            _cmp_csv = generate_monte_carlo_report_csv(
                _cmp.baseline,
                stress_results=_cmp.stress_tests,
                longevity_results=_cmp.longevity_results,
            )
            st.download_button(
                label="📥 Download Full Comparison Report (CSV)",
                data=_cmp_csv,
                file_name=f"mc_full_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                key="mc_cmp_download",
            )

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
                    st.dataframe(_type_data[['account_name', 'symbol', 'name', 'qty', 'purchase_price']], hide_index=True, width='stretch')
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

with tab_advanced:
    st.header("🎯 Advanced Strategies")
    st.markdown(
        "Multi-year tax planning, backdoor Roth, NUA, QCD, and 72(t) SEPP calculators."
    )
    st.markdown("---")

    (
        adv_tax_tab,
        adv_backdoor_tab,
        adv_nua_tab,
        adv_qcd_tab,
        adv_sepp_tab,
        adv_harvest_tab,
    ) = st.tabs([
        "📅 Multi-Year Tax Planning",
        "🔄 Backdoor & Mega Backdoor Roth",
        "📈 NUA Analysis",
        "🎁 QCD Optimizer",
        "⏱️ 72(t) SEPP Calculator",
        "🌾 Capital Loss Harvesting",
    ])

    # -----------------------------------------------------------------------
    # SUB-TAB 1: Multi-Year Tax Planning
    # -----------------------------------------------------------------------
    with adv_tax_tab:
        st.subheader("📅 5-Year Rolling Tax Optimization Window")
        st.markdown(
            "Project your taxes across a 5-year window to identify Roth conversion "
            "opportunities, bracket headroom, QBI deductions, and capital loss harvesting."
        )

        _myt_col1, _myt_col2, _myt_col3 = st.columns(3)
        with _myt_col1:
            _myt_start_year = st.selectbox(
                "Start Year", list(range(curr_year, curr_year + 6)),
                key="myt_start_year"
            )
            _myt_filing = st.selectbox(
                "Filing Status",
                ["married_filing_jointly", "single"],
                key="myt_filing",
            )
        with _myt_col2:
            _myt_income = st.number_input(
                "Annual Ordinary Income ($)", min_value=0, value=150_000,
                step=5_000, key="myt_income",
                help="Wages, IRA distributions, and other ordinary income."
            )
            _myt_cg_lt = st.number_input(
                "Annual Long-Term Cap Gains ($)", min_value=0, value=0,
                step=1_000, key="myt_cg_lt"
            )
        with _myt_col3:
            _myt_conversion = st.number_input(
                "Annual Roth Conversion ($)", min_value=0, value=0,
                step=5_000, key="myt_conversion",
                help="Planned Roth conversion amount per year."
            )
            _myt_qbi = st.number_input(
                "Annual QBI Income ($)", min_value=0, value=0,
                step=5_000, key="myt_qbi",
                help="Qualified Business Income from pass-through entities."
            )

        _myt_col4, _myt_col5, _ = st.columns(3)
        with _myt_col4:
            _myt_loss_cf = st.number_input(
                "Capital Loss Carryforward ($)", min_value=0, value=0,
                step=1_000, key="myt_loss_cf"
            )
        with _myt_col5:
            _myt_window = st.slider(
                "Window (years)", min_value=3, max_value=10, value=5,
                key="myt_window"
            )

        if st.button("📊 Run 5-Year Tax Projection", key="myt_run"):
            try:
                _myt_result = build_rolling_tax_window(
                    start_year=int(_myt_start_year),
                    income_by_year={
                        int(_myt_start_year) + i: float(_myt_income)
                        for i in range(_myt_window)
                    },
                    cg_lt_by_year={
                        int(_myt_start_year) + i: float(_myt_cg_lt)
                        for i in range(_myt_window)
                    },
                    conversion_by_year={
                        int(_myt_start_year) + i: float(_myt_conversion)
                        for i in range(_myt_window)
                    },
                    qbi_by_year={
                        int(_myt_start_year) + i: float(_myt_qbi)
                        for i in range(_myt_window)
                    },
                    loss_carryforward=float(_myt_loss_cf),
                    filing_status=_myt_filing,
                    window=_myt_window,
                )

                # Summary metrics
                _mc1, _mc2, _mc3, _mc4 = st.columns(4)
                _mc1.metric(
                    f"Total Tax ({_myt_window}yr)",
                    f"${_myt_result.total_tax_5yr:,.0f}"
                )
                _mc2.metric(
                    "Avg Effective Rate",
                    f"{_myt_result.avg_effective_rate:.1%}"
                )
                _mc3.metric(
                    "Total Bracket Headroom",
                    f"${_myt_result.total_bracket_headroom:,.0f}"
                )
                _mc4.metric(
                    "Optimization Opportunities",
                    str(len(_myt_result.optimization_opportunities))
                )

                # Year-by-year table
                st.markdown("#### Year-by-Year Projection")
                _myt_rows = []
                for _p in _myt_result.years:
                    _myt_rows.append({
                        "Year": _p.year,
                        "Ordinary Income": f"${_p.ordinary_income:,.0f}",
                        "Roth Conversion": f"${_p.roth_conversion:,.0f}",
                        "QBI Deduction": f"${_p.qbi_deduction:,.0f}",
                        "AGI": f"${_p.agi:,.0f}",
                        "Federal Tax": f"${_p.federal_tax:,.0f}",
                        "Effective Rate": f"{_p.effective_rate:.1%}",
                        "Marginal Rate": f"{_p.marginal_rate:.0%}",
                        "Bracket Headroom": f"${_p.bracket_headroom:,.0f}",
                    })
                st.dataframe(pd.DataFrame(_myt_rows), use_container_width=True, hide_index=True)

                # Tax chart
                _myt_chart_df = pd.DataFrame({
                    "Year": [p.year for p in _myt_result.years],
                    "Federal Tax": [p.federal_tax for p in _myt_result.years],
                    "Bracket Headroom": [p.bracket_headroom for p in _myt_result.years],
                })
                _myt_fig = go.Figure()
                _myt_fig.add_bar(
                    x=_myt_chart_df["Year"], y=_myt_chart_df["Federal Tax"],
                    name="Federal Tax", marker_color="rgb(239, 85, 59)"
                )
                _myt_fig.add_bar(
                    x=_myt_chart_df["Year"], y=_myt_chart_df["Bracket Headroom"],
                    name="Bracket Headroom", marker_color="rgb(99, 110, 250)"
                )
                _myt_fig.update_layout(
                    barmode="group", title="Federal Tax vs. Bracket Headroom by Year",
                    xaxis_title="Year", yaxis_title="Amount ($)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02)
                )
                st.plotly_chart(_myt_fig, use_container_width=True)

                # Bracket fill visualization
                st.markdown("#### 🎯 Bracket Fill Analysis")
                st.caption(
                    "Shows how much of each tax bracket is filled each year. "
                    "Green = headroom available for Roth conversions."
                )
                _bracket_fig = go.Figure()
                for _pi, _p in enumerate(_myt_result.years):
                    _filled = _p.agi - (_p.bracket_headroom if _p.bracket_headroom > 0 else 0)
                    _headroom = _p.bracket_headroom
                    _bracket_fig.add_bar(
                        x=[str(_p.year)],
                        y=[max(0.0, _filled)],
                        name="Bracket Used" if _pi == 0 else None,
                        marker_color="rgb(239, 85, 59)",
                        showlegend=_pi == 0,
                    )
                    _bracket_fig.add_bar(
                        x=[str(_p.year)],
                        y=[max(0.0, _headroom)],
                        name="Bracket Headroom" if _pi == 0 else None,
                        marker_color="rgb(0, 204, 150)",
                        showlegend=_pi == 0,
                    )
                _bracket_fig.update_layout(
                    barmode="stack",
                    title="Tax Bracket Fill by Year",
                    xaxis_title="Year",
                    yaxis_title="Taxable Income ($)",
                    yaxis_tickformat="$,.0f",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(_bracket_fig, use_container_width=True)

                # Optimization opportunities
                if _myt_result.optimization_opportunities:
                    st.markdown("#### 💡 Optimization Opportunities")
                    for _opp in _myt_result.optimization_opportunities:
                        st.info(_opp)

                # Recommended conversions
                if _myt_result.recommended_conversions:
                    st.markdown("#### 📈 Recommended Roth Conversions")
                    _conv_rows = [
                        {"Year": yr, "Recommended Conversion": f"${amt:,.0f}"}
                        for yr, amt in _myt_result.recommended_conversions.items()
                    ]
                    st.dataframe(pd.DataFrame(_conv_rows), use_container_width=True, hide_index=True)

            except Exception as _myt_err:
                st.error(f"Error running tax projection: {_myt_err}")

        # QBI Deduction Calculator
        st.markdown("---")
        st.subheader("🏢 QBI Deduction Calculator (IRC §199A)")
        with st.expander("Calculate your Qualified Business Income deduction", expanded=False):
            _qbi_col1, _qbi_col2 = st.columns(2)
            with _qbi_col1:
                _qbi_income = st.number_input(
                    "QBI Income ($)", min_value=0, value=100_000, step=5_000, key="qbi_income"
                )
                _qbi_total = st.number_input(
                    "Total Taxable Income ($)", min_value=0, value=200_000, step=5_000, key="qbi_total"
                )
                _qbi_filing = st.selectbox(
                    "Filing Status", ["married_filing_jointly", "single"], key="qbi_filing"
                )
            with _qbi_col2:
                _qbi_w2 = st.number_input(
                    "W-2 Wages Paid by Business ($)", min_value=0, value=0, step=5_000, key="qbi_w2"
                )
                _qbi_ubia = st.number_input(
                    "UBIA of Qualified Property ($)", min_value=0, value=0, step=10_000, key="qbi_ubia"
                )
                _qbi_sstb = st.checkbox(
                    "Specified Service Trade or Business (SSTB)?", key="qbi_sstb",
                    help="Law, accounting, consulting, financial services, etc."
                )

            if st.button("Calculate QBI Deduction", key="qbi_calc"):
                _qbi_result = calculate_qbi_deduction_full(
                    qbi_income=float(_qbi_income),
                    total_taxable_income=float(_qbi_total),
                    w2_wages=float(_qbi_w2),
                    ubia_qualified_property=float(_qbi_ubia),
                    is_sstb=bool(_qbi_sstb),
                    filing_status=_qbi_filing,
                )
                _qbi_c1, _qbi_c2, _qbi_c3 = st.columns(3)
                _qbi_c1.metric("QBI Deduction", f"${_qbi_result['deduction']:,.0f}")
                _qbi_c2.metric("Base Deduction (20%)", f"${_qbi_result['base_deduction']:,.0f}")
                _qbi_c3.metric("Phase-Out %", f"{_qbi_result['phase_out_pct']:.1%}")
                for _note in _qbi_result["notes"]:
                    st.caption(_note)

    # -----------------------------------------------------------------------
    # SUB-TAB 2: Backdoor & Mega Backdoor Roth
    # -----------------------------------------------------------------------
    with adv_backdoor_tab:
        st.subheader("🔄 Backdoor Roth IRA")
        st.markdown(
            "For high-income earners who exceed the Roth IRA income limits. "
            "Make a non-deductible Traditional IRA contribution, then convert to Roth."
        )

        _bd_col1, _bd_col2, _bd_col3 = st.columns(3)
        with _bd_col1:
            _bd_year = st.selectbox(
                "Tax Year", list(range(curr_year, curr_year + 3)), key="bd_year"
            )
            _bd_age = st.number_input(
                "Your Age", min_value=18, max_value=80, value=45, key="bd_age"
            )
        with _bd_col2:
            _bd_magi = st.number_input(
                "MAGI ($)", min_value=0, value=250_000, step=5_000, key="bd_magi",
                help="Modified Adjusted Gross Income"
            )
            _bd_trad_bal = st.number_input(
                "Pre-Tax IRA Balance ($)", min_value=0, value=0, step=10_000, key="bd_trad_bal",
                help="Existing Traditional IRA pre-tax balance (triggers pro-rata rule if > 0)"
            )
        with _bd_col3:
            _bd_basis = st.number_input(
                "Existing After-Tax IRA Basis ($)", min_value=0, value=0, step=1_000, key="bd_basis"
            )
            _bd_filing = st.selectbox(
                "Filing Status", ["married_filing_jointly", "single"], key="bd_filing"
            )

        if st.button("Analyze Backdoor Roth", key="bd_run"):
            _bd_result = calculate_backdoor_roth(
                year=int(_bd_year),
                age=int(_bd_age),
                magi=float(_bd_magi),
                traditional_ira_balance=float(_bd_trad_bal),
                after_tax_ira_basis=float(_bd_basis),
                filing_status=_bd_filing,
            )
            if not _bd_result.eligible and _bd_result.ineligible_reason:
                st.info(_bd_result.ineligible_reason)
            else:
                _bd_c1, _bd_c2, _bd_c3 = st.columns(3)
                _bd_c1.metric("Contribution Amount", f"${_bd_result.contribution_amount:,.0f}")
                _bd_c2.metric("Pro-Rata Tax", f"${_bd_result.pro_rata_tax:,.0f}")
                _bd_c3.metric("20-Year Net Benefit", f"${_bd_result.net_benefit:,.0f}")

                if _bd_result.warnings:
                    for _w in _bd_result.warnings:
                        st.warning(_w)

                st.markdown("#### Step-by-Step Instructions")
                for _step in _bd_result.steps:
                    st.markdown(f"- {_step}")

        # BETR Analysis
        st.markdown("---")
        st.subheader("📐 BETR — Break-Even Tax Rate Analysis")
        st.markdown(
            "The **Break-Even Tax Rate (BETR)** shows how far your future tax rate would have to "
            "fall to make a Roth conversion undesirable. Based on Vanguard Research (July 2025). "
            "If BETR > current marginal rate, conversion is beneficial even if future rates decline."
        )

        _betr_col1, _betr_col2, _betr_col3 = st.columns(3)
        with _betr_col1:
            _betr_conv_amt = st.number_input(
                "Conversion Amount ($)", min_value=1_000, value=50_000,
                step=5_000, key="betr_conv_amt",
                help="Amount to convert from Traditional IRA to Roth IRA."
            )
            _betr_trad_bal = st.number_input(
                "Traditional IRA Balance ($)", min_value=1_000, value=500_000,
                step=10_000, key="betr_trad_bal"
            )
            _betr_basis = st.number_input(
                "Nontaxable Basis in IRA ($)", min_value=0, value=0,
                step=1_000, key="betr_basis",
                help="After-tax (non-deductible) contributions already in the Traditional IRA."
            )
        with _betr_col2:
            _betr_curr_rate = st.slider(
                "Current Marginal Rate", min_value=0.10, max_value=0.37,
                value=0.24, step=0.01, format="%.0%%", key="betr_curr_rate"
            )
            _betr_future_rate = st.slider(
                "Expected Future Rate", min_value=0.10, max_value=0.37,
                value=0.22, step=0.01, format="%.0%%", key="betr_future_rate"
            )
            _betr_return = st.slider(
                "Expected Annual Return", min_value=0.02, max_value=0.12,
                value=0.07, step=0.005, format="%.1f%%", key="betr_return"
            )
        with _betr_col3:
            _betr_years = st.number_input(
                "Years to Withdrawal", min_value=1, max_value=40, value=20,
                key="betr_years"
            )
            _betr_pay_source = st.radio(
                "Pay Conversion Tax From",
                ["Taxable Account", "IRA Assets"],
                key="betr_pay_source",
                help="Paying from taxable account is generally more efficient."
            )
            _betr_taxable_bal = st.number_input(
                "Taxable Account Balance ($)", min_value=0, value=200_000,
                step=10_000, key="betr_taxable_bal"
            )

        if st.button("📐 Calculate BETR", key="betr_run", type="primary"):
            try:
                _betr_inputs = BETRInputs(
                    current_marginal_rate=float(_betr_curr_rate),
                    expected_future_rate=float(_betr_future_rate),
                    conversion_amount=float(_betr_conv_amt),
                    traditional_ira_balance=float(_betr_trad_bal),
                    nontaxable_basis=float(_betr_basis),
                    pay_from_taxable=(_betr_pay_source == "Taxable Account"),
                    taxable_account_balance=float(_betr_taxable_bal),
                    years_to_withdrawal=int(_betr_years),
                    annual_return=float(_betr_return),
                )
                _betr_result = calculate_betr(_betr_inputs)

                # Recommendation banner
                if _betr_result.conversion_recommended:
                    st.success(
                        f"✅ **Conversion Recommended** — BETR ({_betr_result.betr:.1%}) > "
                        f"Expected Future Rate ({_betr_future_rate:.0%}). "
                        "Converting now is advantageous."
                    )
                else:
                    st.warning(
                        f"⚠️ **Conversion May Not Be Optimal** — BETR ({_betr_result.betr:.1%}) ≤ "
                        f"Expected Future Rate ({_betr_future_rate:.0%}). "
                        "Staying in Traditional IRA may be better."
                    )

                # Key metrics
                _bc1, _bc2, _bc3, _bc4 = st.columns(4)
                _bc1.metric(
                    "Break-Even Tax Rate (BETR)",
                    f"{_betr_result.betr:.1%}",
                    delta=f"{(_betr_result.betr - _betr_future_rate):.1%} vs future rate",
                    delta_color="normal" if _betr_result.conversion_recommended else "inverse",
                )
                _bc2.metric("Conversion Tax", f"${_betr_result.conversion_tax:,.0f}")
                _bc3.metric("Roth Future Value", f"${_betr_result.roth_future_value:,.0f}")
                _bc4.metric(
                    "Net Benefit vs Traditional",
                    f"${_betr_result.net_benefit:,.0f}",
                    delta_color="normal" if _betr_result.net_benefit > 0 else "inverse",
                )

                # Future value comparison chart
                _betr_fig = go.Figure()
                _betr_fig.add_bar(
                    x=["Traditional IRA\n(no conversion)", "Roth IRA\n(after conversion)"],
                    y=[_betr_result.traditional_future_value, _betr_result.roth_future_value],
                    marker_color=[
                        "rgb(239, 85, 59)" if _betr_result.roth_future_value > _betr_result.traditional_future_value
                        else "rgb(99, 110, 250)",
                        "rgb(0, 204, 150)" if _betr_result.roth_future_value > _betr_result.traditional_future_value
                        else "rgb(239, 85, 59)",
                    ],
                    text=[
                        f"${_betr_result.traditional_future_value:,.0f}",
                        f"${_betr_result.roth_future_value:,.0f}",
                    ],
                    textposition="outside",
                )
                _betr_fig.update_layout(
                    title=f"After-Tax Future Value Comparison ({_betr_years}-Year Horizon)",
                    yaxis_title="After-Tax Future Value ($)",
                    yaxis_tickformat="$,.0f",
                )
                st.plotly_chart(_betr_fig, use_container_width=True)

                # Analysis notes
                if _betr_result.analysis_notes:
                    st.markdown("#### Analysis Notes")
                    for _note in _betr_result.analysis_notes:
                        st.caption(_note)

            except Exception as _betr_err:
                st.error(f"BETR calculation error: {_betr_err}")

        st.markdown("---")
        st.subheader("🚀 Mega Backdoor Roth (401k After-Tax)")
        st.markdown(
            "Contribute after-tax dollars to your 401(k) beyond the employee elective "
            "deferral limit, then convert to Roth. Requires plan support."
        )

        _mb_col1, _mb_col2, _mb_col3 = st.columns(3)
        with _mb_col1:
            _mb_year = st.selectbox(
                "Tax Year", list(range(curr_year, curr_year + 3)), key="mb_year"
            )
            _mb_age = st.number_input(
                "Your Age", min_value=18, max_value=80, value=45, key="mb_age"
            )
        with _mb_col2:
            _mb_elective = st.number_input(
                "Employee Elective Deferral ($)", min_value=0, value=23_500,
                step=500, key="mb_elective",
                help="Your pre-tax or Roth 401(k) contributions"
            )
            _mb_match = st.number_input(
                "Employer Match ($)", min_value=0, value=5_000,
                step=500, key="mb_match"
            )
        with _mb_col3:
            _mb_after_tax = st.checkbox(
                "Plan allows after-tax contributions?", value=True, key="mb_after_tax"
            )
            _mb_in_plan = st.checkbox(
                "Plan allows in-plan Roth conversion?", value=True, key="mb_in_plan"
            )

        if st.button("Analyze Mega Backdoor Roth", key="mb_run"):
            _mb_result = calculate_mega_backdoor_roth(
                year=int(_mb_year),
                age=int(_mb_age),
                employee_elective_deferral=float(_mb_elective),
                employer_match=float(_mb_match),
                plan_allows_after_tax=bool(_mb_after_tax),
                plan_allows_in_plan_conversion=bool(_mb_in_plan),
            )
            if not _mb_result.eligible:
                st.warning(_mb_result.ineligible_reason)
            else:
                _mb_c1, _mb_c2, _mb_c3 = st.columns(3)
                _mb_c1.metric("After-Tax Contribution", f"${_mb_result.after_tax_contribution:,.0f}")
                _mb_c2.metric(
                    "In-Plan Conversion" if _mb_result.in_plan_conversion > 0 else "Rollover to Roth IRA",
                    f"${max(_mb_result.in_plan_conversion, _mb_result.rollover_to_roth_ira):,.0f}"
                )
                _mb_c3.metric("20-Year Net Benefit", f"${_mb_result.net_benefit:,.0f}")

                st.markdown("#### Step-by-Step Instructions")
                for _step in _mb_result.steps:
                    st.markdown(f"- {_step}")

    # -----------------------------------------------------------------------
    # SUB-TAB 3: NUA Analysis
    # -----------------------------------------------------------------------
    with adv_nua_tab:
        st.subheader("📈 Net Unrealized Appreciation (NUA) Analysis")
        st.markdown(
            "If you hold company stock in a 401(k), the NUA strategy lets you pay "
            "ordinary income tax only on the cost basis, with the appreciation taxed "
            "at the lower long-term capital gains rate when you sell."
        )

        _nua_col1, _nua_col2, _nua_col3 = st.columns(3)
        with _nua_col1:
            _nua_ticker = st.text_input("Company Stock Ticker", value="AAPL", key="nua_ticker")
            _nua_shares = st.number_input(
                "Shares in 401(k)", min_value=0.0, value=1_000.0, step=100.0, key="nua_shares"
            )
        with _nua_col2:
            _nua_cost = st.number_input(
                "Cost Basis per Share ($)", min_value=0.01, value=20.0, step=1.0, key="nua_cost"
            )
            _nua_price = st.number_input(
                "Current Price per Share ($)", min_value=0.01, value=150.0, step=1.0, key="nua_price"
            )
        with _nua_col3:
            _nua_ord_rate = st.slider(
                "Ordinary Income Tax Rate", min_value=0.10, max_value=0.37,
                value=0.24, step=0.01, format="%.0%%", key="nua_ord_rate"
            )
            _nua_ltcg_rate = st.slider(
                "LTCG Tax Rate", min_value=0.0, max_value=0.20,
                value=0.15, step=0.05, format="%.0%%", key="nua_ltcg_rate"
            )

        _nua_col4, _nua_col5, _ = st.columns(3)
        with _nua_col4:
            _nua_future_rate = st.slider(
                "Future IRA Withdrawal Rate", min_value=0.10, max_value=0.37,
                value=0.24, step=0.01, format="%.0%%", key="nua_future_rate"
            )
        with _nua_col5:
            _nua_years = st.slider(
                "Years Until Sale (IRA comparison)", min_value=1, max_value=30,
                value=10, key="nua_years"
            )

        if st.button("Analyze NUA Strategy", key="nua_run"):
            _nua_result = calculate_nua_analysis(
                ticker=_nua_ticker,
                shares=float(_nua_shares),
                cost_basis_per_share=float(_nua_cost),
                current_price_per_share=float(_nua_price),
                ordinary_income_tax_rate=float(_nua_ord_rate),
                ltcg_tax_rate=float(_nua_ltcg_rate),
                future_tax_rate=float(_nua_future_rate),
                years_to_sale=int(_nua_years),
            )

            _nua_c1, _nua_c2, _nua_c3, _nua_c4 = st.columns(4)
            _nua_c1.metric("Current Value", f"${_nua_result.current_value:,.0f}")
            _nua_c2.metric("NUA Amount", f"${_nua_result.nua_amount:,.0f}",
                           delta=f"{_nua_result.nua_pct:.0%} gain")
            _nua_c3.metric("NUA Strategy Tax", f"${_nua_result.total_nua_tax:,.0f}")
            _nua_c4.metric(
                "Tax Savings vs IRA Rollover",
                f"${_nua_result.tax_savings:,.0f}",
                delta="✅ Recommended" if _nua_result.strategy_recommended else "⚠️ Not Recommended",
                delta_color="normal" if _nua_result.strategy_recommended else "inverse",
            )

            # Tax comparison chart
            _nua_fig = go.Figure(go.Bar(
                x=["NUA Strategy", "IRA Rollover (est.)"],
                y=[_nua_result.total_nua_tax, _nua_result.tax_if_distributed_as_cash],
                marker_color=["rgb(99, 110, 250)", "rgb(239, 85, 59)"],
                text=[f"${_nua_result.total_nua_tax:,.0f}", f"${_nua_result.tax_if_distributed_as_cash:,.0f}"],
                textposition="outside",
            ))
            _nua_fig.update_layout(
                title=f"NUA Strategy vs. IRA Rollover Tax Comparison — {_nua_ticker}",
                yaxis_title="Estimated Tax ($)",
            )
            st.plotly_chart(_nua_fig, use_container_width=True)

            st.markdown("#### Analysis Notes")
            for _note in _nua_result.notes:
                st.caption(_note)

    # -----------------------------------------------------------------------
    # SUB-TAB 4: QCD Optimizer
    # -----------------------------------------------------------------------
    with adv_qcd_tab:
        st.subheader("🎁 Qualified Charitable Distribution (QCD) Optimizer")
        st.markdown(
            "Age 70½+: Donate directly from your IRA to charity. The distribution "
            "counts toward your RMD but is excluded from AGI — better than a cash donation."
        )

        _qcd_col1, _qcd_col2, _qcd_col3 = st.columns(3)
        with _qcd_col1:
            _qcd_year = st.selectbox(
                "Tax Year", list(range(curr_year, curr_year + 3)), key="qcd_year"
            )
            _qcd_age = st.number_input(
                "Your Age", min_value=60, max_value=95, value=73, key="qcd_age"
            )
            _qcd_rmd = st.number_input(
                "RMD Amount ($)", min_value=0, value=25_000, step=1_000, key="qcd_rmd"
            )
        with _qcd_col2:
            _qcd_ira_bal = st.number_input(
                "IRA Balance ($)", min_value=0, value=500_000, step=10_000, key="qcd_ira_bal"
            )
            _qcd_giving = st.number_input(
                "Planned Charitable Giving ($)", min_value=0, value=10_000,
                step=1_000, key="qcd_giving"
            )
            _qcd_agi = st.number_input(
                "AGI Before RMD ($)", min_value=0, value=80_000, step=5_000, key="qcd_agi"
            )
        with _qcd_col3:
            _qcd_rate = st.slider(
                "Marginal Tax Rate", min_value=0.10, max_value=0.37,
                value=0.22, step=0.01, format="%.0%%", key="qcd_rate"
            )
            _qcd_irmaa = st.number_input(
                "IRMAA MAGI Threshold ($)", min_value=0, value=206_000,
                step=1_000, key="qcd_irmaa"
            )
            _qcd_ss = st.number_input(
                "Annual SS Benefits ($)", min_value=0, value=0,
                step=1_000, key="qcd_ss"
            )

        if st.button("Optimize QCD", key="qcd_run"):
            _qcd_result = calculate_qcd_optimization(
                year=int(_qcd_year),
                age=int(_qcd_age),
                rmd_amount=float(_qcd_rmd),
                ira_balance=float(_qcd_ira_bal),
                planned_charitable_giving=float(_qcd_giving),
                agi_before_rmd=float(_qcd_agi),
                marginal_tax_rate=float(_qcd_rate),
                irmaa_magi_threshold=float(_qcd_irmaa),
                ss_benefits=float(_qcd_ss),
            )

            if not _qcd_result.eligible:
                st.warning(_qcd_result.notes[0] if _qcd_result.notes else "Not eligible for QCD.")
            else:
                _qcd_c1, _qcd_c2, _qcd_c3, _qcd_c4 = st.columns(4)
                _qcd_c1.metric("QCD Amount", f"${_qcd_result.qcd_amount:,.0f}")
                _qcd_c2.metric("AGI Reduction", f"${_qcd_result.agi_reduction:,.0f}")
                _qcd_c3.metric("Direct Tax Savings", f"${_qcd_result.tax_savings:,.0f}")
                _qcd_c4.metric(
                    "Total QCD Advantage",
                    f"${_qcd_result.qcd_advantage:,.0f}",
                    help="Tax savings + IRMAA savings + SS torpedo reduction vs. cash donation"
                )

                if _qcd_result.irmaa_impact > 0:
                    st.success(f"✅ IRMAA savings: ${_qcd_result.irmaa_impact:,.0f}")
                if _qcd_result.ss_torpedo_reduction > 0:
                    st.success(f"✅ SS torpedo reduction: ${_qcd_result.ss_torpedo_reduction:,.0f}")

                st.markdown("#### Analysis Notes")
                for _note in _qcd_result.notes:
                    st.caption(_note)

    # -----------------------------------------------------------------------
    # SUB-TAB 5: 72(t) SEPP Calculator
    # -----------------------------------------------------------------------
    with adv_sepp_tab:
        st.subheader("⏱️ 72(t) SEPP Calculator")
        st.markdown(
            "Substantially Equal Periodic Payments allow penalty-free IRA withdrawals "
            "before age 59½ under IRC §72(t). Payments must continue for the longer of "
            "5 years or until age 59½."
        )

        _sepp_col1, _sepp_col2, _sepp_col3 = st.columns(3)
        with _sepp_col1:
            _sepp_balance = st.number_input(
                "IRA Account Balance ($)", min_value=1_000, value=500_000,
                step=10_000, key="sepp_balance"
            )
            _sepp_age = st.number_input(
                "Your Age", min_value=18, max_value=59, value=50, key="sepp_age"
            )
        with _sepp_col2:
            _sepp_method = st.selectbox(
                "SEPP Method", SEPP_METHODS, key="sepp_method",
                help=(
                    "**RMD**: Lowest payment, variable each year. "
                    "**Fixed Amortization**: Highest fixed payment. "
                    "**Fixed Annuitization**: Mid-range fixed payment."
                )
            )
            _sepp_afr = st.number_input(
                "Applicable Federal Rate (AFR %)", min_value=0.1, max_value=10.0,
                value=5.5, step=0.1, key="sepp_afr",
                help="120% of mid-term AFR. Check IRS.gov for current rate. Max 5% per IRS Notice 2022-6."
            ) / 100.0
        with _sepp_col3:
            _sepp_tax_rate = st.slider(
                "Marginal Tax Rate", min_value=0.10, max_value=0.37,
                value=0.22, step=0.01, format="%.0%%", key="sepp_tax_rate"
            )

        if st.button("Calculate SEPP", key="sepp_run"):
            _sepp_result = calculate_sepp(
                account_balance=float(_sepp_balance),
                age=int(_sepp_age),
                method=_sepp_method,
                afr=float(_sepp_afr),
                marginal_tax_rate=float(_sepp_tax_rate),
            )

            if _sepp_result.warnings and _sepp_result.annual_payment == 0.0:
                for _w in _sepp_result.warnings:
                    st.warning(_w)
            else:
                _sepp_c1, _sepp_c2, _sepp_c3, _sepp_c4 = st.columns(4)
                _sepp_c1.metric("Annual Payment", f"${_sepp_result.annual_payment:,.0f}")
                _sepp_c2.metric("Monthly Payment", f"${_sepp_result.monthly_payment:,.0f}")
                _sepp_c3.metric("Required Duration", f"{_sepp_result.years_required} years")
                _sepp_c4.metric(
                    "Penalty Avoided",
                    f"${_sepp_result.early_withdrawal_penalty_avoided:,.0f}"
                )

                _sepp_c5, _sepp_c6, _ = st.columns(3)
                _sepp_c5.metric("Total Distributions", f"${_sepp_result.total_distributions:,.0f}")
                _sepp_c6.metric("Est. Annual Tax", f"${_sepp_result.estimated_annual_tax:,.0f}")

                # Payment schedule chart
                _sepp_years_list = list(range(curr_year, curr_year + _sepp_result.years_required))
                _sepp_fig = go.Figure()
                _sepp_fig.add_bar(
                    x=_sepp_years_list,
                    y=[_sepp_result.annual_payment] * _sepp_result.years_required,
                    name="Annual Payment",
                    marker_color="rgb(99, 110, 250)",
                )
                _sepp_fig.add_bar(
                    x=_sepp_years_list,
                    y=[_sepp_result.estimated_annual_tax] * _sepp_result.years_required,
                    name="Est. Annual Tax",
                    marker_color="rgb(239, 85, 59)",
                )
                _sepp_fig.update_layout(
                    barmode="overlay",
                    title=f"SEPP Payment Schedule — {_sepp_method}",
                    xaxis_title="Year",
                    yaxis_title="Amount ($)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(_sepp_fig, use_container_width=True)

                st.markdown("#### Calculation Notes")
                for _note in _sepp_result.notes:
                    st.caption(_note)

                if _sepp_result.warnings:
                    st.markdown("#### ⚠️ Important Warnings")
                    for _w in _sepp_result.warnings:
                        st.warning(_w)

        # Method comparison
        st.markdown("---")
        st.markdown("#### Compare All Three SEPP Methods")
        if st.button("Compare Methods", key="sepp_compare"):
            _compare_rows = []
            for _m in SEPP_METHODS:
                try:
                    _cr = calculate_sepp(
                        account_balance=float(_sepp_balance),
                        age=int(_sepp_age),
                        method=_m,
                        afr=float(_sepp_afr),
                        marginal_tax_rate=float(_sepp_tax_rate),
                    )
                    _compare_rows.append({
                        "Method": _m,
                        "Annual Payment": f"${_cr.annual_payment:,.0f}",
                        "Monthly Payment": f"${_cr.monthly_payment:,.0f}",
                        "Years Required": _cr.years_required,
                        "Total Distributions": f"${_cr.total_distributions:,.0f}",
                        "Est. Annual Tax": f"${_cr.estimated_annual_tax:,.0f}",
                        "Penalty Avoided": f"${_cr.early_withdrawal_penalty_avoided:,.0f}",
                    })
                except Exception:
                    pass
            if _compare_rows:
                st.dataframe(pd.DataFrame(_compare_rows), use_container_width=True, hide_index=True)

    # -----------------------------------------------------------------------
    # SUB-TAB 6: Capital Loss Harvesting
    # -----------------------------------------------------------------------
    with adv_harvest_tab:
        st.subheader("🌾 Multi-Year Capital Loss Harvesting Plan")
        st.markdown(
            "Identify positions with unrealized losses and plan harvesting across multiple years "
            "to maximize tax savings. Capital losses offset gains first, then up to $3,000 of "
            "ordinary income per year (IRC §1211(b)). Unused losses carry forward indefinitely."
        )

        st.markdown("#### Portfolio Positions")
        st.caption(
            "Enter positions with unrealized losses. Leave blank rows unused. "
            "Holding period ≥ 365 days = long-term loss."
        )

        # Dynamic position entry
        _harv_n = st.number_input(
            "Number of positions to analyze", min_value=1, max_value=20, value=3,
            key="harv_n_positions"
        )

        _harv_positions = []
        _harv_pos_cols = st.columns(5)
        _harv_pos_cols[0].markdown("**Ticker**")
        _harv_pos_cols[1].markdown("**Shares**")
        _harv_pos_cols[2].markdown("**Cost Basis/Share ($)**")
        _harv_pos_cols[3].markdown("**Current Price ($)**")
        _harv_pos_cols[4].markdown("**Holding Days**")

        for _hi in range(int(_harv_n)):
            _hc = st.columns(5)
            _hticker = _hc[0].text_input(
                f"Ticker {_hi+1}", value=["AAPL", "MSFT", "AMZN"][_hi] if _hi < 3 else "",
                key=f"harv_ticker_{_hi}", label_visibility="collapsed"
            )
            _hshares = _hc[1].number_input(
                f"Shares {_hi+1}", min_value=0.0, value=[100.0, 50.0, 200.0][_hi] if _hi < 3 else 0.0,
                step=10.0, key=f"harv_shares_{_hi}", label_visibility="collapsed"
            )
            _hcost = _hc[2].number_input(
                f"Cost {_hi+1}", min_value=0.0, value=[180.0, 420.0, 200.0][_hi] if _hi < 3 else 0.0,
                step=1.0, key=f"harv_cost_{_hi}", label_visibility="collapsed"
            )
            _hprice = _hc[3].number_input(
                f"Price {_hi+1}", min_value=0.0, value=[150.0, 380.0, 175.0][_hi] if _hi < 3 else 0.0,
                step=1.0, key=f"harv_price_{_hi}", label_visibility="collapsed"
            )
            _hdays = _hc[4].number_input(
                f"Days {_hi+1}", min_value=0, value=[400, 200, 500][_hi] if _hi < 3 else 365,
                step=30, key=f"harv_days_{_hi}", label_visibility="collapsed"
            )
            if _hticker and _hshares > 0 and _hcost > 0 and _hprice > 0:
                _harv_positions.append({
                    "ticker": _hticker,
                    "shares": float(_hshares),
                    "cost_basis": float(_hcost),
                    "current_price": float(_hprice),
                    "holding_period_days": int(_hdays),
                })

        st.markdown("---")
        _harv_col1, _harv_col2, _harv_col3 = st.columns(3)
        with _harv_col1:
            _harv_start_year = st.selectbox(
                "Start Year", list(range(curr_year, curr_year + 6)),
                key="harv_start_year"
            )
            _harv_window = st.slider(
                "Planning Window (years)", min_value=2, max_value=10, value=5,
                key="harv_window"
            )
        with _harv_col2:
            _harv_income = st.number_input(
                "Annual Ordinary Income ($)", min_value=0, value=150_000,
                step=5_000, key="harv_income"
            )
            _harv_filing = st.selectbox(
                "Filing Status", ["married_filing_jointly", "single"],
                key="harv_filing"
            )

        if st.button("🌾 Build Harvesting Plan", key="harv_run", type="primary"):
            if not _harv_positions:
                st.warning("Please enter at least one position with valid data.")
            else:
                try:
                    _harv_result = build_multi_year_loss_harvesting_plan(
                        start_year=int(_harv_start_year),
                        portfolio_positions=_harv_positions,
                        income_by_year={
                            int(_harv_start_year) + i: float(_harv_income)
                            for i in range(int(_harv_window))
                        },
                        filing_status=_harv_filing,
                        window=int(_harv_window),
                    )

                    # Summary metrics
                    _hm1, _hm2, _hm3 = st.columns(3)
                    _hm1.metric(
                        "Total Tax Savings",
                        f"${_harv_result.total_tax_savings:,.0f}"
                    )
                    _total_losses = sum(
                        _harv_result.harvest_amounts.get(yr, 0)
                        for yr in _harv_result.years
                    )
                    _hm2.metric("Total Losses to Harvest", f"${_total_losses:,.0f}")
                    _hm3.metric(
                        "Final Year Carryforward",
                        f"${_harv_result.carryforward_by_year.get(_harv_result.years[-1], 0):,.0f}"
                        if _harv_result.years else "$0"
                    )

                    # Year-by-year table
                    st.markdown("#### Year-by-Year Harvesting Schedule")
                    _harv_rows = []
                    for _yr in _harv_result.years:
                        _harv_rows.append({
                            "Year": _yr,
                            "Harvest Amount": f"${_harv_result.harvest_amounts.get(_yr, 0):,.0f}",
                            "Tax Savings": f"${_harv_result.tax_savings_by_year.get(_yr, 0):,.0f}",
                            "Loss Carryforward": f"${_harv_result.carryforward_by_year.get(_yr, 0):,.0f}",
                        })
                    st.dataframe(pd.DataFrame(_harv_rows), use_container_width=True, hide_index=True)

                    # Harvesting chart
                    _harv_fig = go.Figure()
                    _harv_fig.add_bar(
                        x=_harv_result.years,
                        y=[_harv_result.harvest_amounts.get(yr, 0) for yr in _harv_result.years],
                        name="Harvest Amount",
                        marker_color="rgb(99, 110, 250)",
                    )
                    _harv_fig.add_bar(
                        x=_harv_result.years,
                        y=[_harv_result.tax_savings_by_year.get(yr, 0) for yr in _harv_result.years],
                        name="Tax Savings",
                        marker_color="rgb(0, 204, 150)",
                    )
                    _harv_fig.add_scatter(
                        x=_harv_result.years,
                        y=[_harv_result.carryforward_by_year.get(yr, 0) for yr in _harv_result.years],
                        name="Loss Carryforward",
                        mode="lines+markers",
                        line=dict(color="rgb(239, 85, 59)", width=2, dash="dash"),
                        yaxis="y2",
                    )
                    _harv_fig.update_layout(
                        barmode="group",
                        title="Multi-Year Capital Loss Harvesting Plan",
                        xaxis_title="Year",
                        yaxis_title="Amount ($)",
                        yaxis_tickformat="$,.0f",
                        yaxis2=dict(
                            title="Carryforward ($)",
                            overlaying="y",
                            side="right",
                            tickformat="$,.0f",
                        ),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    )
                    st.plotly_chart(_harv_fig, use_container_width=True)

                    # Position summary
                    st.markdown("#### Position Analysis")
                    _pos_rows = []
                    for _pos in _harv_positions:
                        _cost = _pos["cost_basis"]
                        _price = _pos["current_price"]
                        _shares = _pos["shares"]
                        _unrealized = (_price - _cost) * _shares
                        _is_lt = _pos["holding_period_days"] >= 365
                        _pos_rows.append({
                            "Ticker": _pos["ticker"],
                            "Shares": f"{_shares:,.0f}",
                            "Cost Basis/Share": f"${_cost:,.2f}",
                            "Current Price": f"${_price:,.2f}",
                            "Unrealized P&L": f"${_unrealized:,.0f}",
                            "Holding": "Long-Term" if _is_lt else "Short-Term",
                            "Harvestable": "✅ Yes" if _unrealized < 0 else "❌ No (gain)",
                        })
                    st.dataframe(pd.DataFrame(_pos_rows), use_container_width=True, hide_index=True)

                    # Notes and warnings
                    if _harv_result.notes:
                        st.markdown("#### ⚠️ Important Notes")
                        for _note in _harv_result.notes:
                            st.warning(_note)

                except Exception as _harv_err:
                    st.error(f"Error building harvesting plan: {_harv_err}")

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
    st.info("⚙️ Open the [Configuration page](2_configuration) to edit personal information, healthcare settings, Social Security, tax strategy, and portfolio data.")
    st.markdown("---")

# ---------------------------------------------------------------------------
# Auto-rerun while portfolio cache is warming up
# ---------------------------------------------------------------------------
# This block runs AFTER all tabs have been rendered so the full Dashboard
# is visible to the user before any rerun is triggered.  Once the background
# thread sets the Event (i.e. build_portfolio_display has finished), this
# block stops scheduling reruns and the portfolio charts appear on the next
# (and final) refresh.
#
# We wait on the threading.Event with a 2-second timeout so the render thread
# yields briefly (preventing a tight CPU-spinning rerun loop) while still
# allowing the page to be fully rendered and interactive.  The wait() call
# returns True as soon as the background thread finishes, or False after 2 s —
# either way we rerun so the UI picks up the completed cache.
if not _portfolio_cache_ready:
    _done_ev: "_threading.Event" = st.session_state["_portfolio_done_event"]
    _done_ev.wait(timeout=2)   # Yields for up to 2 s; returns early if done
    st.rerun()
