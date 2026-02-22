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
from calculations import calc_roth_conversions_tax, getlower_atm_amount_n_deduction,calc_roth_conversions,calc_agi,calc_daf_value,getUpperIncomeRate,calculate_atm, calculate_std_deduction,get_std_deduction_by_year, calculate_irmma_penalty, calculate_cap_gains, calculate_taxable_income
from portfolio import get_portfolio_dividend_total,get_current_dividend,get_current_price,get_entry_in_portfolio,get_list_of_tickers,get_purchase_price,get_qty,getPortfolioData,calculate_cost_basis,calculate_current_value, get_ticker_name,get_sector,color_negative_positive,build_portfolio_display
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


tab1, tab3, tab4 = st.tabs(["Dashboard", "Portfolio planner", "Retirement planner"])
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
        },hide_index=True)

    with update_tab:  
        st.title('Editable Data Entry Table(not functional - roadmap)')

        initial_data = pd.DataFrame(getPortfolioData())
        # Ensure numeric columns are properly typed to prevent Arrow serialization errors
        numeric_columns = ['qty', 'purchase_price', 'Price']
        for col in numeric_columns:
            if col in initial_data.columns:
                # Replace empty strings with NaN, then convert to numeric
                initial_data[col] = initial_data[col].replace('', np.nan)
                initial_data[col] = pd.to_numeric(initial_data[col], errors='coerce').fillna(0)
        
        st.markdown("### Update Data Below")
        edited_df = st.data_editor(initial_data, num_rows="dynamic",
        column_config={
            "account_type": st.column_config.SelectboxColumn(
            "Type of Account",
            options=[
                "Brokerage",
                "Traditional",
                "Roth",
            ],
            required=True,
            ),
            "sector": st.column_config.SelectboxColumn(
            "Sector",
            options=[
                "Stock/ETF",
                "MF:Large-Cap",
                "MF:Mid-Cap",
                "MF:Small-Cap",
                "MF:Reit",
                "MF:Cash",
                "MF:Global",
                "MF:Asia",
                "MF:Europe",
                "MF:Latin America",
            ],
            ),
        },
        hide_index=True)

        if st.button('Validate Data'):
            st.success(f'Validate Data. Total entries: {len(edited_df)}.')
            st.write(edited_df)
            # Further processing of the 'edited_df' can be done here.    
        # 3. The 'edited_df' variable automatically contains the current state of the table
        # after user interactions (editing cells, adding/deleting rows).

        st.markdown("### Extracted DataFrame (After Editing)")

        # 4. Display the extracted DataFrame for verification
        #st.write(edited_df)

        # You can also use the data in other parts of your application, for example:
        if st.button('Process Data'):
            st.success(f'Data processed. Total entries: {len(edited_df)}.')
            # Further processing of the 'edited_df' can be done here.    
        


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
        hide_index=True)
        
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
        hide_index=True)
