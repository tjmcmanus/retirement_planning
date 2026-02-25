import streamlit as st
import datetime
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from streamlit_card import card
from streamlit_extras.metric_cards import style_metric_cards 
from streamlit_extras.add_vertical_space import add_vertical_space
from load_data import get_month_account_values,get_cap_gains_brackets, get_income_tax_brackets, get_net_worth, get_medicare_costs, get_atm_costs, get_std_deduction, get_networth_by_month
from withdrawal_strategy import build_withdrawal_strategy_display
from calculations import calc_roth_conversions_tax, getlower_atm_amount_n_deduction,calc_roth_conversions,calc_agi,calc_daf_value,getUpperIncomeRate,calculate_atm, calculate_std_deduction,get_std_deduction_by_year, calculate_irmma_penalty, calculate_cap_gains, calculate_taxable_income
from portfolio import get_portfolio_dividend_total,get_current_dividend,get_current_price,get_entry_in_portfolio,get_list_of_tickers,get_purchase_price,get_qty,getPortfolioData,calculate_cost_basis,calculate_current_value, get_ticker_name,get_sector,color_negative_positive,build_portfolio_display
from portfolio_data_entry import validate_ticker_symbol, validate_portfolio_dataframe, save_portfolio_data, create_empty_entry_template, load_previous_month_data, start_from_scratch, revert_to_last_backup
from income_expense import build_income_expenses_display,calculate_taxes
from components.sidebar import sidebar
st.set_page_config(page_title="Retirement Planner", page_icon="😊", layout="wide")

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

def clear_submit():
    st.session_state["submit"] = False

@st.cache_data(ttl=300)  # Cache for 5 minutes
def build_historical_networth(num_months=12):
    """
    Build historical net worth DataFrame using get_networth_by_month.
    
    Args:
        num_months: Number of months of historical data to fetch (default: 12)
    
    Returns:
        pd.DataFrame: Historical net worth with columns: date, cash, taxable, tax_deferred, tax_free, total
    """
    currentDate = datetime.date.today()
    curr_year = currentDate.year
    curr_month = currentDate.month
    
    # Build list of (month, year) tuples for the last num_months
    months_data = []
    for i in range(num_months, 0, -1):
        # Calculate month and year going backwards
        target_month = curr_month - i + 1
        target_year = curr_year
        
        # Handle year rollover
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        
        months_data.append((target_month, target_year))
    
    # Fetch net worth for each month
    networth_rows = []
    for month, year in months_data:
        try:
            _, summary_df = get_networth_by_month(month, year)
            
            if not summary_df.empty:
                # Extract values by account_type
                cash = summary_df[summary_df['account_type'] == 'Cash']['market_value'].sum()
                taxable = summary_df[summary_df['account_type'] == 'Brokerage']['market_value'].sum()
                tax_deferred = summary_df[summary_df['account_type'] == 'Traditional']['market_value'].sum()
                tax_free = summary_df[summary_df['account_type'] == 'Roth']['market_value'].sum()
                
                # Get total (excluding the 'Total' row to avoid double counting)
                total = summary_df[summary_df['account_type'] != 'Total']['market_value'].sum()
                
                # Create date string (using first day of month for consistency)
                date_str = f"{month:02d}/01/{year}"
                
                networth_rows.append({
                    'date': date_str,
                    'cash': cash,
                    'taxable': taxable,
                    'tax_deferred': tax_deferred,
                    'tax_free': tax_free,
                    'total': total
                })
        except Exception as e:
            st.warning(f"Could not fetch data for {month}/{year}: {e}")
            continue
    
    # Create DataFrame
    if networth_rows:
        networth_df = pd.DataFrame(networth_rows)
        return networth_df
    else:
        # Return empty DataFrame with correct structure if no data
        return pd.DataFrame(columns=['date', 'cash', 'taxable', 'tax_deferred', 'tax_free', 'total'])

currentDate = datetime.date.today()
curr_year = currentDate.year
curr_month = currentDate.month

st.header("Retirement planner")
##############################################################################################

sidebar()

##############################################################################################


tab1, tab3, tab4, tab5 = st.tabs(["Dashboard", "Portfolio planner", "Retirement planner", "Withdrawal Strategy"])
with tab1:
   # Build historical net worth using optimized portfolio truth data
   networth = build_historical_networth(num_months=12)
   
   # Check if we have enough data
   if networth.empty or len(networth) < 2:
       st.error("Insufficient historical data. Need at least 2 months of portfolio data.")
       st.stop()
   
   color_palette = px.colors.qualitative.Pastel
   cg_income_lt=0
   cg_income_st=0
   interest=0
   agi=0
   col1row3, col1row4, col1row5, col1row6,col1row7 = st.columns(5)
   with col1row3:
       st.header(" ")
       cash_value=networth["cash"].values[-1]
       cash_value2=networth["cash"].values[-2]
       change_last_month=(networth["cash"].values[-1]-networth["cash"].values[-2])
       fcash_value=f"${cash_value:,.2f}"
       fchange_last_month=f"{change_last_month:,.2f}"
       st.metric(label="Cash", value=fcash_value, delta= fchange_last_month + " Monthly Change" )
       #st.metric(label="Change from Last Month", value=fchange_last_month)
   with col1row4:  
       st.header(" ")
       taxable_value=networth["taxable"].values[-1]
       taxable_last_month=networth["taxable"].values[-1]-networth["taxable"].values[-2]
       ftaxable_value=f"${taxable_value:,.2f}"
       ftaxable_last_month=f"{taxable_last_month:,.2f}"    
       st.metric(label="Brokerage", value=ftaxable_value, delta=ftaxable_last_month + " Monthly Change"  )
       # st.metric(label="Change from Last Month", value=ftaxable_last_month)
   with col1row5:   
       st.header(" ")
       roth_value=networth["tax_free"].values[-1]
       roth_last_month=networth["tax_free"].values[-1]-networth["tax_free"].values[-2]
       froth_value=f"${roth_value:,.2f}"
       froth_last_month=f"{roth_last_month:,.2f}"
       st.metric(label="Roth", value=froth_value, delta=froth_last_month+ " Monthly Change" )
       #st.metric(label="Change from Last Month", value=froth_last_month)
   with col1row6:   
       st.header(" ")
       trad_value=networth["tax_deferred"].values[-1]
       trad_last_month=networth["tax_deferred"].values[-1]-networth["tax_deferred"].values[-2]
       ftrad_value=f"${trad_value:,.2f}"
       ftrad_last_month=f"{trad_last_month:,.2f}"
       st.metric(label="Traditional", value=ftrad_value, delta=ftrad_last_month+ "Monthly Change" )
       #st.metric(label="Change from Last Month", value=ftrad_last_month)
   with col1row7:   
       st.header(" ")
       total_value=networth["total"].values[-1]
       total_last_month=networth["total"].values[-1]-networth["total"].values[-2]
       ftotal_value=f"${total_value:,.2f}"
       ftotal_last_month=f"{total_last_month:,.2f}"
       st.metric(label="Total Net Worth", value=ftotal_value, delta=ftotal_last_month+ " Monthly Change" )
       #st.metric(label="Change from Last Month", value=ftotal_last_month)  
   
   add_vertical_space(2)
   row2_col1, row2_col2, row2_col3 = st.columns(3)
   with row2_col1:
       st.markdown('<h4 style="text-align: center;">Total Net Worth</h4>', unsafe_allow_html=True)
       fig2 = px.histogram(networth, x='date', y='total', nbins=10, color="total", color_discrete_sequence=color_palette)
       
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
          x=networth.date,
          y=networth.cash,
          name='Cash',
          legendgroup='1',
          marker_color='rgb(246, 207, 113)'
      )
      trace2 = go.Bar(
          x=networth.date,
          y=networth.taxable,
          name='Broker',
          legendgroup='2',
          marker_color='rgb(254, 136, 177)'
      )
      trace3 = go.Bar(
          x=networth.date,
          y=networth.tax_deferred,
          name='Traditional',
          legendgroup='3',
          marker_color='rgb(139, 224, 164)'
      )
      trace4 = go.Bar(
          x=networth.date,
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
           color_discrete_sequence=color_palette,
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
   
   add_vertical_space(2)
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
                     values='market_value',color='market_value', color_continuous_scale=color_palette,color_continuous_midpoint=np.average(mtd_spend['market_value'], weights=mtd_spend['market_value']), title="")
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
        values='Current value',color='Current value', color_continuous_scale=color_palette,color_continuous_midpoint=np.average(portdf_no_totals['Current value'], weights=portdf_no_totals['Current value']), title="")
        #values='Current value',color='Current value', title="")
        portfolio_by_sector.data[0].textinfo = "label+text+value+percent root"
        portfolio_by_sector.update_traces(texttemplate="%{label}<br>$%{value:,.2f}")
        portfolio_by_sector.update_layout(margin = dict(t=50, l=25, r=25, b=25))

        st.plotly_chart(portfolio_by_sector, width='stretch')
       
portdf = build_portfolio_display()



with tab3:
    
    st.header("Portfolio")
    #add_vertical_space(2)
    portdf = build_portfolio_display()
    
    # Note: build_portfolio_display() already includes a totals row at the bottom
    #print(portdf)
    
    # Exclude the totals row (last row where Account == 'Portfolio Totals')
    portdf_no_totals = portdf[portdf['Account'] != 'Portfolio Totals'].copy()
    
    # Define styles for center alignment of headers and specific columns
    styles = [
        dict(selector="th", props=[('text-align', 'center')]),
        dict(selector="td", props=[('text-align', 'center')])
    ]
    
    # Apply styles and color formatting
    styled_portdf = portdf.style.set_table_styles(styles).map(color_negative_positive)
    styled_portdf_no_total = portdf_no_totals.style.set_table_styles(styles).map(color_negative_positive)
    
    map_tab,details_tab,update_tab = st.tabs(["Map Of Portfolio", "Details", "Update Securities"])
    with map_tab:
        st.markdown('<h4 style="text-align: center;">Account Mix Breakdown</h4>', unsafe_allow_html=True)

        portfolio_by_sector = px.treemap(portdf_no_totals, path=['Tax Type','Sector', 'Ticker'],
            values='Current value',color='Current value', color_continuous_scale=color_palette,color_continuous_midpoint=np.average(portdf_no_totals['Current value'], weights=portdf_no_totals['Current value']), title="")
                    #values='Current value',color='Current value', title="")
        portfolio_by_sector.data[0].textinfo = "label+text+value+percent root"
        portfolio_by_sector.update_traces(texttemplate="%{label}<br>$%{value:,.2f}")
        portfolio_by_sector.update_layout(margin = dict(t=50, l=25, r=25, b=25))

        st.plotly_chart(portfolio_by_sector, width='stretch')
        
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

    with update_tab:
        st.title('Manual Portfolio Data Entry')
        st.markdown("Enter your monthly portfolio holdings below. The system will validate ticker symbols against Yahoo Finance and save to portfolio_data_truth.csv")
        
        # Month/Year selection
        col1, col2 = st.columns(2)
        with col1:
            entry_month = st.number_input("Month", min_value=1, max_value=12, value=curr_month, step=1)
        with col2:
            entry_year = st.number_input("Year", min_value=2000, max_value=2100, value=curr_year, step=1)
        
        # Initialize session state for the data editor
        if 'portfolio_entries' not in st.session_state:
            st.session_state.portfolio_entries = load_previous_month_data(entry_month, entry_year)
            st.session_state.last_loaded_month = entry_month
            st.session_state.last_loaded_year = entry_year
        
        # Reload data if month/year changed
        if 'last_loaded_month' not in st.session_state or 'last_loaded_year' not in st.session_state or \
           st.session_state.last_loaded_month != entry_month or \
           st.session_state.last_loaded_year != entry_year:
            st.session_state.portfolio_entries = load_previous_month_data(entry_month, entry_year)
            st.session_state.last_loaded_month = entry_month
            st.session_state.last_loaded_year = entry_year
        
        st.markdown("### Enter Portfolio Data")
        
        # Show info about data source
        prev_month = entry_month - 1 if entry_month > 1 else 12
        prev_year = entry_year if entry_month > 1 else entry_year - 1
        
        if len(st.session_state.portfolio_entries) > 1 or \
           (len(st.session_state.portfolio_entries) == 1 and st.session_state.portfolio_entries['symbol'].iloc[0] != ''):
            st.info(f"📋 Loaded {len(st.session_state.portfolio_entries)} entries from {prev_month}/{prev_year}. You can add, update, or delete rows as needed.")
        else:
            st.info("💡 No previous month data found. Add rows using the '+' button. For ticker symbols, use standard symbols (e.g., AAPL, GOOGL) or MF:CASH for cash holdings.")
        
        # Data editor with proper column configuration
        edited_df = st.data_editor(
            st.session_state.portfolio_entries,
            num_rows="dynamic",
            width='stretch',
            column_config={
                "month": st.column_config.NumberColumn(
                    "Month",
                    min_value=1,
                    max_value=12,
                    step=1,
                    format="%d"
                ),
                "year": st.column_config.NumberColumn(
                    "Year",
                    min_value=2000,
                    max_value=2100,
                    step=1,
                    format="%d"
                ),
                "account_name": st.column_config.TextColumn(
                    "Account Name",
                    help="e.g., PNC, Schwab, Fidelity",
                    required=True
                ),
                "account_type": st.column_config.SelectboxColumn(
                    "Account Type",
                    options=["Cash", "Brokerage", "Traditional", "Roth"],
                    required=True
                ),
                "symbol": st.column_config.TextColumn(
                    "Ticker Symbol",
                    help="Stock ticker or MF:CASH for cash",
                    required=True
                ),
                "name": st.column_config.TextColumn(
                    "Security Name",
                    help="Will be auto-filled during validation"
                ),
                "sector": st.column_config.SelectboxColumn(
                    "Sector",
                    options=[
                        "MF:Cash",
                        "Stock/ETF",
                        "MF:Large-Cap",
                        "MF:Mid-Cap",
                        "MF:Small-Cap",
                        "MF:Reit",
                        "MF:Global",
                        "MF:Asia",
                        "MF:Europe",
                        "MF:Latin America",
                        "Automotive",
                        "Technology",
                        "Communication Services",
                        "Healthcare",
                        "Consumer Defensive",
                        "Financial Services",
                        "Energy",
                        "Industrials",
                        "Real Estate",
                        "Utilities",
                        "Basic Materials",
                        "Consumer Cyclical"
                    ],
                    help="Will be auto-filled during validation"
                ),
                "qty": st.column_config.NumberColumn(
                    "Quantity",
                    min_value=0,
                    step=0.01,
                    format="%.2f",
                    required=True
                ),
                "purchase_price": st.column_config.NumberColumn(
                    "Purchase Price",
                    min_value=0,
                    step=0.01,
                    format="$%.2f",
                    required=True
                )
            },
            hide_index=True
        )
        
        # Update session state
        st.session_state.portfolio_entries = edited_df
        
        # Action buttons
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            if st.button('🔍 Validate & Lookup Tickers', type="primary", width='stretch'):
                with st.spinner("Validating ticker symbols with Yahoo Finance..."):
                    # Filter out empty rows
                    non_empty_df = edited_df[edited_df['symbol'].str.strip() != ''].copy()
                    
                    if non_empty_df.empty:
                        st.warning("No entries to validate. Please add at least one row with a ticker symbol.")
                    else:
                        validation_results = []
                        
                        # Validate each ticker and auto-fill name/sector
                        for idx, row in non_empty_df.iterrows():
                            symbol = row['symbol'].strip().upper()
                            is_valid, name, sector, error = validate_ticker_symbol(symbol)
                            
                            if is_valid:
                                # Update name and sector in the dataframe
                                non_empty_df.at[idx, 'name'] = name
                                non_empty_df.at[idx, 'sector'] = sector
                                validation_results.append({
                                    'Symbol': symbol,
                                    'Status': '✅ Valid',
                                    'Name': name,
                                    'Sector': sector
                                })
                            else:
                                validation_results.append({
                                    'Symbol': symbol,
                                    'Status': '❌ Invalid',
                                    'Name': '',
                                    'Sector': error
                                })
                        
                        # Update session state with validated data
                        st.session_state.portfolio_entries = non_empty_df
                        
                        # Display validation results
                        st.markdown("### Validation Results")
                        results_df = pd.DataFrame(validation_results)
                        st.dataframe(results_df, width='stretch', hide_index=True)
                        
                        # Check if all valid
                        invalid_count = sum(1 for r in validation_results if '❌' in r['Status'])
                        if invalid_count == 0:
                            st.success(f"✅ All {len(validation_results)} ticker symbols validated successfully!")
                        else:
                            st.error(f"❌ {invalid_count} invalid ticker symbol(s). Please correct them before saving.")
        
        with col2:
            if st.button('💾 Save to CSV', type="secondary", width='stretch'):
                # Filter out empty rows
                non_empty_df = edited_df[edited_df['symbol'].str.strip() != ''].copy()
                
                if non_empty_df.empty:
                    st.warning("No entries to save. Please add at least one row.")
                else:
                    # Validate the dataframe
                    valid_df, invalid_df = validate_portfolio_dataframe(non_empty_df)
                    
                    if not invalid_df.empty:
                        st.error(f"❌ Found {len(invalid_df)} invalid entries. Please fix errors before saving:")
                        st.dataframe(invalid_df[['symbol', 'account_name', 'validation_error']], width='stretch', hide_index=True)
                    elif valid_df.empty:
                        st.warning("No valid entries to save.")
                    else:
                        # Save to CSV
                        success, message = save_portfolio_data(valid_df, append=True)
                        
                        if success:
                            st.success(f"✅ {message}")
                            st.info("🔄 Refreshing portfolio data and switching to Map view...")
                            
                            # Clear ALL caches to force reload of portfolio data
                            st.cache_data.clear()
                            
                            # Reset the entry form
                            st.session_state.portfolio_entries = create_empty_entry_template(entry_month, entry_year)
                            
                            # Force a complete page refresh to reload all data
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
        
        with col3:
            if st.button('🔄 Reload Previous Month', width='stretch'):
                st.session_state.portfolio_entries = load_previous_month_data(entry_month, entry_year)
                st.rerun()
        
        with col4:
            if st.button('🆕 Start from Scratch', type="secondary", width='stretch'):
                # Show confirmation dialog
                if 'confirm_scratch' not in st.session_state:
                    st.session_state.confirm_scratch = False
                
                if not st.session_state.confirm_scratch:
                    st.session_state.confirm_scratch = True
                    st.warning("⚠️ This will backup your current data and create a blank file. Click again to confirm.")
                    st.rerun()
                else:
                    with st.spinner("Creating backup and blank file..."):
                        success, message = start_from_scratch()
                        
                        if success:
                            st.success(f"✅ {message}")
                            st.info("🔄 Refreshing data...")
                            
                            # Clear caches and reset
                            st.cache_data.clear()
                            st.session_state.portfolio_entries = create_empty_entry_template(entry_month, entry_year)
                            st.session_state.confirm_scratch = False
                            
                            # Force refresh
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                            st.session_state.confirm_scratch = False
        
        with col5:
            if st.button('⏮️ Revert to Last Backup', type="secondary", width='stretch'):
                # Show confirmation dialog
                if 'confirm_revert' not in st.session_state:
                    st.session_state.confirm_revert = False
                
                if not st.session_state.confirm_revert:
                    st.session_state.confirm_revert = True
                    st.warning("⚠️ This will restore the most recent backup. Click again to confirm.")
                    st.rerun()
                else:
                    with st.spinner("Reverting to last backup..."):
                        success, message = revert_to_last_backup()
                        
                        if success:
                            st.success(f"✅ {message}")
                            st.info("🔄 Refreshing data...")
                            
                            # Clear caches and reload
                            st.cache_data.clear()
                            st.session_state.portfolio_entries = load_previous_month_data(entry_month, entry_year)
                            st.session_state.confirm_revert = False
                            
                            # Force refresh
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")
                            st.session_state.confirm_revert = False
        
        # Display current data preview
        st.markdown("---")
        st.markdown("### Current Entries Preview")
        non_empty_preview = edited_df[edited_df['symbol'].str.strip() != '']
        if not non_empty_preview.empty:
            st.dataframe(non_empty_preview, width='stretch', hide_index=True)
        else:
            st.info("No entries yet. Add rows above to get started.")
        


with tab4:
    column_1, column_2, column_3, column_4, column_5 = st.columns(5)
    with column_1:
        st.subheader("Current Value")
        #st.write("Left Subheader")
        networth=networth["total"].values[-1]
        st.metric("Current Value", "${:,.2f}".format(networth))
    with column_2:
        st.subheader("Retirement Value")
        st.metric("Retirement Value", "${:,.2f}".format(networth))
    with column_3:
        st.subheader("Progress")
        st.metric("Progress", 100)
    with column_4:
        st.subheader("Monthly Income")
        st.metric("Monthly Income", "${:,.2f}".format(12500))
    with column_5:
        st.subheader("Retirement Date")
        st.metric("Retirement Date", '12/31/2026')

    inflow_outflow_df, port_review_df = build_income_expenses_display()
    
    outflow_tab, portfolio_tab  = st.tabs(["Inflow/Outflow","Portfolio Value"])
    with outflow_tab:
        st.dataframe(inflow_outflow_df,    column_config={
            "SSI Flows": st.column_config.NumberColumn(
               "Social Security", # Column header name in UI
                format="dollar"
            ),
            "Planned Distribution": st.column_config.NumberColumn(
                "Planned Distribution", # Column header name in UI
                format="dollar"
            ),
            "Roth Conversions": st.column_config.NumberColumn(
               "Roth Conversions", # Column header name in UI
                format="dollar"
          ),
            "RMD": st.column_config.NumberColumn(
                "Req Min Distributions", # Column header name in UI
                format="dollar"
            ),
            "Portfolio Withdrawl": st.column_config.NumberColumn(
                "Cash Needs", # Column header name in UI
                 format="dollar"
            ),
            "Total Inflows": st.column_config.NumberColumn(
                "Annual Total Income", # Column header name in UI
                format="dollar"
            ),
            "Taxes Owed": st.column_config.NumberColumn(
                "Taxes Owed", # Column header name in UI
                format="dollar"
            ),
            "Expenses": st.column_config.NumberColumn(
                "Expenses", # Column header name in UI
                format="dollar"
            ),
        },
        hide_index=True,
        width='stretch')
        
    with portfolio_tab:
        st.dataframe(port_review_df,    column_config={
            "Cash": st.column_config.NumberColumn(
            "PNC Accounts", # Column header name in UI
            format="dollar"
            ),"Taxable": st.column_config.NumberColumn(
            "Total Brokerage", # Column header name in UI
            format="dollar"
            ),"Tax Deferred": st.column_config.NumberColumn(
            "Total 401k and IRAs", # Column header name in UI
            format="dollar"
            ),"Tax Free": st.column_config.NumberColumn(
            "Total Roth", # Column header name in UI
            format="dollar"
            ),"Donor Advised Fund": st.column_config.NumberColumn(
            "Remaining Donor Advised Fund", # Column header name in UI
            format="dollar"
            ),
        },
        hide_index=True,
        width='stretch')

with tab5:
    st.header("Withdrawal Strategy Analysis")
    
    # Get parameters from session state (set by sidebar)
    try:
        ssi_age = int(st.session_state.get("SSI_AGE", 70))
        conv_amount_at_ssi = float(st.session_state.get("CONV_AMOUNT_AT_SSI_AGE", 5000))
        conv_tax_rate = float(st.session_state.get("CONV_TAX_RATE", 12))
        annual_expenses = float(st.session_state.get("EXPENSE", 50000))
        expense_multiplier = float(st.session_state.get("EXPENSE_MULITPLIER", 4))
        rate_of_return = float(st.session_state.get("RATE", 6)) / 100
        daf_rate = float(st.session_state.get("DAF_RATE", 25)) / 100
        planned_dist_2027 = float(st.session_state.get("PLANNED_DIST_2027", 5000))
    except (ValueError, TypeError) as e:
        st.error(f"Error reading sidebar parameters: {e}. Using default values.")
        ssi_age = 70
        conv_amount_at_ssi = 5000
        conv_tax_rate = 12
        annual_expenses = 50000
        expense_multiplier = 4
        rate_of_return = 0.06
        daf_rate = 0.25
        planned_dist_2027 = 75000
    
    # Display current parameters
    st.subheader("Strategy Parameters")
    param_col1, param_col2, param_col3, param_col4 = st.columns(4)
    with param_col1:
        st.metric("Social Security Age", ssi_age)
        st.metric("Annual Expenses", f"${annual_expenses:,.0f}")
    with param_col2:
        st.metric("Roth Conv @ SSI Age", f"${conv_amount_at_ssi:,.0f}")
        st.metric("Expense Multiplier", f"{expense_multiplier}x")
    with param_col3:
        st.metric("Max Conv Tax Rate", f"{conv_tax_rate}%")
        st.metric("Rate of Return", f"{rate_of_return*100:.1f}%")
    with param_col4:
        st.metric("DAF Disbursement", f"{daf_rate*100:.0f}%")
        st.metric("2027 Planned Dist", f"${planned_dist_2027:,.0f}")
    
    add_vertical_space(2)
    
    # Calculate withdrawal strategy
    try:
        # Get max conversion rate from sidebar (convert from percentage string to decimal)
        max_conversion_rate_str = st.session_state.get("CONV_TAX_RATE", "24")
        try:
            max_conversion_rate = float(max_conversion_rate_str) / 100.0
        except (ValueError, TypeError):
            max_conversion_rate = 0.24  # Default to 24%
        
        # Get ACA marketplace enrollment and expense inflation from config
        from config import get_config_manager
        config_mgr = get_config_manager()
        aca_marketplace_enrolled = config_mgr.get("healthcare", "aca_marketplace_enrolled", False)
        expense_inflation_rate = config_mgr.get("financial_assumptions", "expense_inflation_rate", 3.0) / 100.0
        
        with st.spinner("Calculating withdrawal strategy..."):
            strategy_df, balances_df = build_withdrawal_strategy_display(
                start_year=curr_year,
                end_year=2050,
                growth_rate=1 + rate_of_return,
                expense_inflation_rate=expense_inflation_rate,
                person1_name="Tom",
                person2_name="Sarah",
                max_conversion_rate=max_conversion_rate,
                aca_optimize=aca_marketplace_enrolled,
                ss_claiming_age=ssi_age
            )
        
        # Display strategy results in tabs
        strategy_tab, balances_tab, charts_tab = st.tabs(["Annual Strategy", "Account Balances", "Visualizations"])
        
        with strategy_tab:
            st.subheader("Year-by-Year Withdrawal Strategy")
            
            # Format the strategy dataframe for display
            # Order: Wages, SS Benefits, RMD, Traditional Withdrawal, Roth Conversion, Expenses, IRMAA, Taxes, Cash Balance
            display_cols = [
                'Year', 'Age', 'Stage',
                'Wages',
                'SS Benefits',
                'RMD',
                'Traditional Withdrawal',
                'Roth Conversion',
                'Expenses',
                'IRMAA Penalty',
                'Federal Tax',
                'Cash Balance'
            ]
            
            available_cols = [col for col in display_cols if col in strategy_df.columns]
            display_df = strategy_df[available_cols].copy()
            
            # Format numeric columns: show 2 decimals only if not a whole number
            def format_currency(val):
                """Format currency: whole numbers without decimals, non-whole with 2 decimals"""
                if pd.isna(val):
                    return ""
                if val == int(val):
                    return f"${int(val):,}"
                else:
                    return f"${val:,.2f}"
            
            # Apply formatting to numeric columns (excluding Year, Age, Stage)
            numeric_cols = ['Wages', 'SS Benefits', 'RMD', 'Traditional Withdrawal', 'Roth Conversion',
                          'Expenses', 'IRMAA Penalty', 'Federal Tax', 'Cash Balance']
            for col in numeric_cols:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(format_currency)
            
            # Configure column formatting (now treating formatted columns as text)
            column_config = {
                "Year": st.column_config.NumberColumn("Year", format="%d"),
                "Age": st.column_config.TextColumn("Age"),
                "Stage": st.column_config.TextColumn("Life Stage"),
                "Wages": st.column_config.TextColumn("Wages"),
                "SS Benefits": st.column_config.TextColumn("Social Security"),
                "RMD": st.column_config.TextColumn("Required Minimum Distribution"),
                "Traditional Withdrawal": st.column_config.TextColumn("Traditional Withdrawal"),
                "Roth Conversion": st.column_config.TextColumn("Roth Conversion"),
                "Expenses": st.column_config.TextColumn("Expenses"),
                "IRMAA Penalty": st.column_config.TextColumn("Medicare (IRMAA)"),
                "Federal Tax": st.column_config.TextColumn("Taxes"),
                "Cash Balance": st.column_config.TextColumn("Cash Drawdown")
            }
            
            st.dataframe(display_df, column_config=column_config, hide_index=True, width='stretch')
        
        with balances_tab:
            st.subheader("Account Balances Over Time")
            
            # Ensure all numeric columns are properly typed
            balances_display = balances_df.copy()
            for col in ['Cash Balance', 'Taxable Balance', 'Traditional Balance', 'Roth Balance', 'DAF Balance', 'Total Portfolio']:
                if col in balances_display.columns:
                    balances_display[col] = pd.to_numeric(balances_display[col], errors='coerce').apply(format_currency)
        
            
            # Configure column formatting for balances
            balance_column_config = {
                "Year": st.column_config.NumberColumn("Year", format="%d"),
                "Cash Balance": st.column_config.TextColumn("Cash"),
                "Taxable Balance": st.column_config.TextColumn("Taxable"),
                "Traditional Balance": st.column_config.TextColumn("Traditional"),
                "Roth Balance": st.column_config.TextColumn("Roth"),
                "DAF Balance": st.column_config.TextColumn("DAF"),
                "Total Portfolio": st.column_config.TextColumn("Total Portfolio")
            }
            
            st.dataframe(balances_display, column_config=balance_column_config, hide_index=True, width='stretch')
        
        with charts_tab:
            st.subheader("Portfolio Balance Projections")
            
            # Create stacked area chart for account balances
            fig_balances = go.Figure()
            
            fig_balances.add_trace(go.Scatter(
                x=balances_df['Year'],
                y=balances_df['Cash Balance'],
                name='Cash',
                mode='lines',
                stackgroup='one',
                fillcolor='rgb(246, 207, 113)'
            ))
            
            fig_balances.add_trace(go.Scatter(
                x=balances_df['Year'],
                y=balances_df['Taxable Balance'],
                name='Taxable',
                mode='lines',
                stackgroup='one',
                fillcolor='rgb(254, 136, 177)'
            ))
            
            fig_balances.add_trace(go.Scatter(
                x=balances_df['Year'],
                y=balances_df['Traditional Balance'],
                name='Traditional',
                mode='lines',
                stackgroup='one',
                fillcolor='rgb(139, 224, 164)'
            ))
            
            fig_balances.add_trace(go.Scatter(
                x=balances_df['Year'],
                y=balances_df['Roth Balance'],
                name='Roth',
                mode='lines',
                stackgroup='one',
                fillcolor='rgb(180, 151, 231)'
            ))
            
            fig_balances.update_layout(
                title='Projected Account Balances',
                xaxis_title='Year',
                yaxis_title='Balance ($)',
                hovermode='x unified',
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            
            st.plotly_chart(fig_balances, width='stretch')
            
            # Create income sources chart
            if 'Total Income' in strategy_df.columns:
                st.subheader("Income Sources Over Time")
                
                fig_income = go.Figure()
                
                if 'Wages' in strategy_df.columns:
                    fig_income.add_trace(go.Bar(
                        x=strategy_df['Year'],
                        y=strategy_df['Wages'],
                        name='Wages',
                        marker_color='rgb(99, 110, 250)'
                    ))
                
                if 'Social Security' in strategy_df.columns:
                    fig_income.add_trace(go.Bar(
                        x=strategy_df['Year'],
                        y=strategy_df['Social Security'],
                        name='Social Security',
                        marker_color='rgb(239, 85, 59)'
                    ))
                
                if 'Portfolio Withdrawal' in strategy_df.columns:
                    fig_income.add_trace(go.Bar(
                        x=strategy_df['Year'],
                        y=strategy_df['Portfolio Withdrawal'],
                        name='Portfolio Withdrawal',
                        marker_color='rgb(0, 204, 150)'
                    ))
                
                fig_income.update_layout(
                    title='Income Sources by Year',
                    xaxis_title='Year',
                    yaxis_title='Amount ($)',
                    barmode='stack',
                    hovermode='x unified',
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                
                st.plotly_chart(fig_income, width='stretch')
    
    except Exception as e:
        st.error(f"Error calculating withdrawal strategy: {e}")
        st.info("Please ensure all sidebar parameters are properly configured and try refreshing the data.")
