import streamlit as st
import datetime
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from streamlit_card import card
from streamlit_extras.metric_cards import style_metric_cards 
from streamlit_extras.add_vertical_space import add_vertical_space
from load_data import get_month_account_values,load_financial_accounts,get_cap_gains_brackets, get_income_tax_brackets, get_net_worth, get_medicare_costs, get_atm_costs, get_std_deduction, load_net_worth
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
    
currentDate = datetime.date.today()
curr_year = currentDate.year
curr_month = currentDate.month    

st.header("Retirement planner")
##############################################################################################

sidebar()

##############################################################################################


tab1, tab2, tab3, tab4 = st.tabs(["Dashboard","Tax planner", "Portfolio planner", "Retirement planner"])
with tab1:
   networth = load_net_worth()
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
       st.markdown('#### Total Net Worth')
       fig2 = px.histogram(networth, x='date', y='total', nbins=10, color="total", color_discrete_sequence=color_palette)
       fig2.update_layout( 
                    autosize=True,
                    plot_bgcolor='#0f4c75', 
                    paper_bgcolor='#0f4c75',
                    xaxis=dict(title='Date',
                                tickfont=dict(color='white'),
                                #titlefont=dict(color='white')
                                ),
                    yaxis=dict(title='Net Worth',
                                tickfont=dict(color='white'),
                                #titlefont=dict(color='white')
                                ), 
                    legend=dict(orientation="h", yanchor='bottom',y=1.1, font=dict(color="white"),),  
                    )
       fig2.update_layout(showlegend=False)
       st.plotly_chart(fig2, use_container_width = True)

   with row2_col2:
      # Create traces for each group
      st.markdown('#### Net Worth by Account')
      trace1 = go.Bar(x=networth.date, y=networth.cash, name='Cash', legendgroup='1',marker_color='rgb(246, 207, 113)')
      trace2 = go.Bar(x=networth.date, y=networth.taxable, name='Broker', legendgroup='2',marker_color='rgb(254, 136, 177)')
      trace3 = go.Bar(x=networth.date, y=networth.tax_deferred, name='Traditional', legendgroup='3',marker_color='rgb(139, 224, 164)')
      trace4 = go.Bar(x=networth.date, y=networth.tax_free, name='Roth', legendgroup='4',marker_color='rgb(180, 151, 231)')
      #trace5 = go.Bar(x=networth.date, y=networth.total, name='Total', legendgroup='1',marker_color='rgb(102, 197, 204)')
      # Layout configuration with grouped legend
      layout = go.Layout(
          autosize=True,
          #color_scale=color_palette
          plot_bgcolor='#0f4c75',
          paper_bgcolor='#0f4c75',
          barmode='stack',  # Group bars together
          xaxis=dict(title='Dates',
                    tickfont=dict(color='white'),
                   # titlefont=dict(color='white')
                    ),
          yaxis=dict(title='Amount',
                    tickfont=dict(color='white'),
                    #titlefont=dict(color='white')
                    ),
        legend=dict(title='Account Type', orientation="h",yanchor='bottom',y=1.1, groupclick = 'togglegroup',font=dict(color="white"))  # Legend title
        )
      # Create the figure
      fig = go.Figure(data=[trace3, trace4, trace2,trace1], layout=layout,)
      #fig.update_layout(showlegend=True)
      # Display the plotly chart
      chart = st.plotly_chart(fig, use_container_width=True, key='selection')
   
   with row2_col3:
       st.markdown('#### Asset mix')
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
                  title_font=dict(color="white"),
                  hoverinfo='label+percent+value',
                  insidetextfont=dict(color='black')) # Custom colors
       title_text=''
       fig.update_layout( 
           autosize=True,
           plot_bgcolor='#0f4c75', 
           paper_bgcolor='#0f4c75',
           title_font=dict(color="white"),
           legend=dict(title='Account Type', orientation="h",yanchor='bottom',y=1.1, groupclick = 'togglegroup',font=dict(color="white")), 
           margin=dict(l=1,r=1,b=1,t=1)
        )
       st.plotly_chart(fig, use_container_width=True)
   
   add_vertical_space(2)
   tab1_row2_col1,tab1_row2_col2 = st.columns(2)
   with tab1_row2_col1:
       st.markdown('#### Account Mix Breakdown')
    # CURRENT MONTH SPEND BY CATEGORY [TREEMAP CHART]
    
    # CURRENT MONTH SPEND BY CATEGORY [TREEMAP CHART]
       # 2. Select the specific row to plot

       mtd_spend = get_month_account_values(curr_month,curr_year)
       print(mtd_spend)
      # monthly_balance = account_data.iloc[-1,1:15] # Select the first row
       fig_mtd_spend_by_cateogry = px.treemap(mtd_spend, path=['type','account'],
                     values='amount',color='amount', color_continuous_scale='tealrose',color_continuous_midpoint=np.average(mtd_spend['amount'], weights=mtd_spend['amount']), title="")
       fig_mtd_spend_by_cateogry.data[0].textinfo = "label+text+value+percent root"

       #fig_mtd_spend_by_cateogry.update_layout(margin=dict(l=0,r=0,t=0,b=0))
       fig_mtd_spend_by_cateogry.update_layout(margin = dict(t=50, l=25, r=25, b=25))

       st.plotly_chart(fig_mtd_spend_by_cateogry, use_container_width=True)

   with tab1_row2_col2:
       st.markdown('#### Account mix')
       
with tab2:
    st.header("Withdrawl and Conversion calculator")
   # add_vertical_space(2)
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
       st.metric(label="Traditional", value=ftrad_value, delta=ftrad_last_month+ " Monthly Change" )
       #st.metric(label="Change from Last Month", value=ftrad_last_month)
    with col1row7:   
       st.header(" ")
       total_value=networth["total"].values[-1]
       total_last_month=networth["total"].values[-1]-networth["total"].values[-2]
       ftotal_value=f"${total_value:,.2f}"
       ftotal_last_month=f"{total_last_month:,.2f}"
       st.metric(label="Total Net Worth", value=ftotal_value, delta=ftotal_last_month+ " Monthly Change" )
       #st.metric(label="Change from Last Month", value=ftotal_last_month)    



    if "visibility" not in st.session_state:
       st.session_state.visibility = "visible"
       st.session_state.disabled = False
  
    with st.expander("Create estimated taxes for next year"):
        col5, col6, col7, col8, col14 = st.columns(5)    
        with col5: 
            wages = st.number_input("Wages",  on_change=clear_submit)
            # wages = st.number_input("Wages",step=None)
        with col6:     
            deferred_distribution = st.number_input("Trad IRA Distribution", on_change=clear_submit)
        with col14:    
            interest=st.number_input("Interest", on_change=clear_submit)
            #print(f"Input interest is {interest:.6f}")
        with col7:     
            cg_income_lt = st.number_input("Long Term Cap Gains", on_change=clear_submit)
            #print(f"Input LTCG is {cg_income_lt:.6f}")
        with col8:
            cg_income_st = st.number_input("Short Term Cap Gains", on_change=clear_submit)
            #print(f"Input STCG is {cg_income_st:.6f}")
      
        col9, col10, col12, col11, col13 = st.columns(5)  
        with col9:
           people = st.selectbox("Medicare Eligible" ,[0,1,2], on_change=clear_submit)
        with col10:
           year =st.selectbox("Tax Year" ,[2023,2024,2025,2026,2027], on_change=clear_submit,index=3)
        with col12:    
           maxdaf=st.selectbox("Max Donor Advisor Fund" ,['N','Y'], on_change=clear_submit)
        with col11:
          if maxdaf == 'Y':
             daf1 =st.number_input("Charitable Contrib", disabled=True )
          else:   
             daf1 =st.number_input("Charitable Contrib", on_change=clear_submit)
        with col13:
             headroom_rate = (st.selectbox("Max Conversion Rate" ,[10,12,22,24,32,35,37], on_change=clear_submit,index=3)/100)
        col14,col15,col16,col17,col18= st.columns(5) 
        with col14:
             roth_amount = st.number_input("Roth Conversion Amount" , on_change=clear_submit)
        with col15:    
             pd_tax_amount = st.number_input("Estimated prepaid Fed taxes" , on_change=clear_submit)
        summarize_button = st.button("Project this years changes!")
   

    if summarize_button:
        taxratedf = get_income_tax_brackets(year)
        cgdf = get_cap_gains_brackets(year)
        irmaadf= get_medicare_costs(year)
        stddectdf = get_std_deduction(year)
        atmdf = get_atm_costs(year)
    
  
        #calc_roth_conversions(maxrate,headroom_rate,uppermax,agi,headroom_max)
        #inc=deferred_distribution+wages
        #print(f"Income to DAF Calc is: ${deferred_distribution+wages:,.2f}")
        calc_daf = calc_daf_value(deferred_distribution+wages,interest,daf1,maxdaf)
        #st.write("Calculated DAF is : ",calc_daf )

        #income=deferred_distribution+wages+cg_income_st
        #st.write("AGI values : " ,deferred_distribution+wages+cg_income_st,interest,stddectdf,calc_daf)
        agi = calc_agi(deferred_distribution+wages+cg_income_st,interest,stddectdf,calc_daf)  
        #st.write("Calculated AGI (deferred_distribution+wages+cg_income_st) is : ",agi )
   
        irmaa_fees_income = calculate_irmma_penalty(agi, irmaadf, people)
        #st.write("Medicare Fees  is : ",irmaa_fees_income )
   
        #st.write("LTCG is : ",cg_tax )
        #print(f"agi to calculate taxable income is {agi}")
        taxable_income, maxrate, uppermax = calculate_taxable_income(agi, taxratedf)
        #st.write("Income Tax is : ",taxable_income,maxrate,uppermax )
   
        headroom_max = getUpperIncomeRate(headroom_rate,taxratedf)
        #st.write("Max Conversion Tax Rate is : ",headroom_max)
   
        if maxrate>headroom_rate:
            st.write("bad stuff is happening")
        lowerby=0   
        atm_lower,atm_deduction = getlower_atm_amount_n_deduction(year, atmdf)
        #print(f"ATM Values are: {atm_lower} and {atm_deduction} or {atm_lower+atm_deduction}")
        std_deduction=get_std_deduction_by_year(year)
        if uppermax>=(atm_lower+atm_deduction):
            uppermax=atm_lower+atm_deduction
            #print(f"UpperMax is: {uppermax}")
        if roth_amount>0:
            conversions=roth_amount   
            conversion_tax= calc_roth_conversions_tax(maxrate,headroom_rate,uppermax,agi,headroom_max,conversions)
            #print(f"conversio tax is: {conversion_tax}")
        else:
            #print(f"agi for roth conversion calc: {agi}")
            conversions,conversion_tax = calc_roth_conversions(maxrate,headroom_rate,uppermax,agi,headroom_max,lowerby) 
    
        #st.write("Roth Conversion is : ", conversions,conversion_tax)  
        if conversions >= 0:
            agi = calc_agi(deferred_distribution+wages+cg_income_st+conversions,interest,stddectdf,calc_daf) 
            taxable_income, maxrate, uppermax = calculate_taxable_income(agi, taxratedf)
        #    print(f"agi is is roth is >=0 {agi}")
 
        if cg_income_lt == 0:
            cg_tax=0
        else:
            cg_tax = calculate_cap_gains(agi, cgdf, cg_income_lt)
        
        if agi >=(atm_lower+atm_deduction+calc_daf+30000):
            dont_sure_if_I_can_remove=0
            #print(f"MAGI is {agi+conversions+cg_income_lt} and ATM Lower is {atm_lower+atm_deduction+calc_daf+30000}")
            #conversions=0
            #conversion_tax=0
    
        atm_tax,init_lowerby = calculate_atm(agi,cg_income_lt, atmdf)
        #print(f"ATM Tax is {atm_tax} and taxable Income is {taxable_income}")
        if taxable_income>atm_tax:
            atm_tax=0
            #print(f"ATM_tax lower MAGI is {agi+conversions+cg_income_lt} and ATM Lower is {atm_lower+atm_deduction+calc_daf+30000}")
        #else:
            #print(f"ATM_tax higher MAGI is {agi+cg_income_lt} and ATM Lower is {atm_lower+atm_deduction+calc_daf+30000}")
            # conversions,conversion_tax = calc_roth_conversions(maxrate,headroom_rate,uppermax,agi,headroom_max,init_lowerby) 
            #
            # 
            # print(f"PRE: atm_atx is {atm_tax} vs taxable_income {taxable_income} and lowerby is {lowerby} conversions are {conversions} and Conversion tax is {pre_conversion_tax}")
    
       
        irmaa_fees_income_headroom = calculate_irmma_penalty(uppermax, irmaadf, people)
        #st.write("Medicare Tax Rate is : ",irmaa_fees_income_headroom)
   
        #day_cash,day_taxable,day_tax_deferred,day_tax_free,day_total,day_expenses,day_daf =  get_net_worth('10/23/2025')

        #day_cash,day_taxable,day_tax_deferred,day_tax_free,day_total,day_expenses,day_daf = get_net_worth(formatted_date)

        #st.write(day_cash,day_taxable,day_tax_deferred,day_tax_free,day_total,day_expenses,day_daf)
            
        col1row3, col1row5, col1row6,col1row7,col1row8 = st.columns(5) 
        with col1row3:
            st.markdown('##### Ordinary Income')
            fcash_value=f"${agi:,.2f}"
            f_cgst_month=f"${cg_income_st:,.2f}" 
            fcg_taxable_value=f"${cg_income_lt:,.2f}"
            fint_value=f"${interest:,.2f}"
            if 0 < (agi+conversions):
                st.metric(label="Adjusted Gross Income", value=fcash_value)
            if 0 < (interest):
                st.metric(label="Interest", value=fint_value)
            if 0 < (cg_income_st):   
                #print(f"Input STCG is {cg_income_st:.6f}")
                st.metric(label="Short Term Capital Gains", value=f_cgst_month)
            if 0 != (cg_income_lt):
                st.metric(label="Long Term Capital Gains", value=fcg_taxable_value)

        with col1row5:   
            st.markdown('##### Taxes Owed')
           # if atm_tax>taxable_income:
            #    fincome_tax=f"${atm_tax+cg_tax-pd_tax_amount:,.2f}"
            #else:
            fincome_tax=f"${taxable_income+cg_tax-pd_tax_amount:,.2f}"
            #print(f"Income {taxable_income} minus estimated {pd_tax_amount} is {fincome_tax}")
            #print(f"ATM {atm_tax} minus estimated {pd_tax_amount} is {fincome_tax}")
            fcg_tax=f"${cg_tax:,.2f}"
            froth_conv_tax=f"${conversion_tax:,.2f}"
            if 0 == (cg_income_lt+cg_income_st+interest):
                state_tax=0
                quarterly_state_tax=0
            else: 
                 #print(f"state tax = {(cg_income_lt+cg_income_st+interest)}") 
                #print(f"LTCG: {cg_income_lt} STCG: {cg_income_st} interest: {interest}")  
                state_tax=((cg_income_lt+cg_income_st+interest)*0.03 )
                quarterly_state_tax=state_tax/4
            fstate_tax=f"${state_tax:,.2f}"
            fquarterly_state_tax=f"${quarterly_state_tax:,.2f}"
            quarterly_fed_tax=(taxable_income+cg_tax-pd_tax_amount)/4
            fquarterly_fed_tax=f"${quarterly_fed_tax:,.2f}"
            if taxable_income>0:
                st.metric(label="Income Tax", value=fincome_tax)
                st.metric(label="Quarterly Fed tax Payment", value=fquarterly_fed_tax)
            if state_tax>0: 
                st.metric(label="State tax", value=fstate_tax)
                st.metric(label="Quarterly State tax Payment", value=fquarterly_state_tax)
       
     
            st.markdown('##### Other costs')
            fdaf=f"${calc_daf:,.2f}"
            fdeferred_distribution=f"${deferred_distribution:,.2f}"
            firmaa_fees=f"${irmaa_fees_income:,.2f}"
            firmaa_headroom_month=f"${irmaa_fees_income_headroom:,.2f}"
            ftaxable_last_month=f"${cg_income_st:,.2f}" 
            fatm_tax_taxable_income=f"${atm_tax-taxable_income:,.2f}" 
            flowerby=f"${lowerby:,.2f}" 
            if calc_daf>0: 
                st.metric(label="Donor Advisory Fund", value=fdaf)
            #if deferred_distribution>0:
            #   st.metric(label="Traditional Distribution", value=fdeferred_distribution)    
            if cg_tax>0:   
                st.metric(label="Long Term Capital Gains Tax", value=fcg_tax)
            if  irmaa_fees_income >0:  
                st.metric(label="Medicare Surcharge", value=firmaa_fees)
            if irmaa_fees_income_headroom>0 and conversions>0:
                st.metric(label="Medicare cost w. Roth Conversion", value=firmaa_headroom_month)
                #st.metric(label="Roth Conversions", value=ftaxable_value)
            if atm_tax>taxable_income:
                st.metric(label="Additional ATM taxes", value=fatm_tax_taxable_income)
                st.metric(label="Decrease income or LT Capital gains by", value=flowerby)       
        with col1row6:   
            st.markdown('##### Traditional Updates')
            ftrad_value=f"${trad_value:,.2f}"
            ftrad_dist_delta=f"${trad_value-deferred_distribution-conversions:,.2f}"
            fdelta=f"{-deferred_distribution-conversions:,.2f}"
            if deferred_distribution+conversions >0:
                st.metric(label="New Traditional Balance", value=ftrad_dist_delta, delta=fdelta)
            else:
                st.metric(label="Pre Changes Traditional", value=ftrad_value)         
        with col1row7:   
            st.markdown('##### Roth Updates')
            fconversions_amt=f"{conversions:,.2f}"
            fconversions=f"${conversions:,.2f}"
            fconversions_total=f"${(roth_value+conversions):,.2f}"
            if conversions > 0:
                st.metric(label="New Roth Account Balance", value=fconversions_total, delta=fconversions_amt) 
                st.metric(label="Roth Conversion",value=fconversions)    
                st.metric(label="Estimated Roth Conversion tax", value=froth_conv_tax)
            else:
                st.metric(label="Pre Changes Roth", value=froth_value) 
                #st.write("Wages: ", wages, "Trad IRA Distribution: ", deferred_distribution, "Interest: ",interest, "Long Term Cap Gains: ",cg_income_lt, "Max Conversion Rate: ", headroom_rate, "Max Charitable", maxdaf  )
        with col1row8:   
            st.markdown('##### Broker & Cash Updates')
            fcash_value=f"${cash_value:,.2f}"
            #print(f"Cash Value {cash_value} minus Comnversion tax: {conversion_tax} minus Income Tax: {taxable_income} minus LT CG {cg_tax} minus State Tax {state_tax} ")
            new_cash_value=(cash_value-state_tax-cg_tax-taxable_income+pd_tax_amount)
            new_broker_value =(taxable_value-calc_daf+deferred_distribution)
            fnew_cash_delta=f"{new_cash_value-cash_value:,.2f}"
            f_new_broker_value=f"${new_broker_value:,.2f}"
            f_new_broker_delta_value=f"{new_broker_value-taxable_value:,.2f}"
            f_new_cash_value=f"${new_cash_value:,.2f}"
            #ftotal_last_month=f"${f_new_broker_value:,.2f}"
            if new_cash_value != cash_value:
                st.metric(label="New Cash Balance", value=f_new_cash_value, delta=fnew_cash_delta)
                #st.metric(label="Delta", value=fnew_cash_delta)
            else:   
                st.metric(label="Pre Changes Cash Balance", value=fcash_value)
            if new_broker_value != taxable_value:
                st.metric(label="New Broker Balance", value=f_new_broker_value, delta=f_new_broker_delta_value) 
            else:
                    st.metric(label="Pre Changes Broker Balance", value=ftaxable_value)  

            #st.write("Wages: ", wages, "Trad IRA Distribution: ", deferred_distribution, "Interest: ",interest, "Long Term Cap Gains: ",cg_income_lt, "Max Conversion Rate: ", headroom_rate, "Max Charitable", maxdaf  )

portdf = build_portfolio_display()
#print(portdf[['Current value','Cost Basis','Net Return','Dividend Amount','annual dividend amount']])


with tab3:
    
    st.header("Portfolio")
    #add_vertical_space(2)
    portdf_no_totals = build_portfolio_display()
    
    #portdf.loc['Total'] = portdf[['Current value','Cost Basis','Net Return','Dividend Amount','annual dividend amount']].sum()
    totals = portdf[['Current value','Cost Basis','Net Return','Dividend Amount','annual dividend amount']].sum()
    index_label = len(portdf) + 1
    total_row = pd.Series(totals, name=index_label)
    portdf = pd.concat([portdf, pd.DataFrame(total_row).T])
    #print(portdf)
    
    styles = [
    dict(selector="th", props=[('text-align', 'center')]),
    dict(selector="td", props=[('text-align', 'center')])
    ]
    styled_portdf = portdf.style.set_table_styles(styles)
    styled_portdf = portdf.style.map(color_negative_positive)
    
    #styled_portdf_no_total = portdf_no_totals.set_table_styles(styles)
    styled_portdf_no_total = portdf_no_totals.map(color_negative_positive)
    
    map_tab,details_tab,update_tab = st.tabs(["Map Of Portfolio", "Details", "Update Securities"])
    with map_tab:
        st.markdown('#### Account Mix Breakdown')

        portfolio_by_sector = px.treemap(portdf_no_totals, path=['Tax Type','Sector', 'Ticker'],
            values='Current value',color='Current value', color_continuous_scale='tealrose',color_continuous_midpoint=np.average(portdf_no_totals['Current value'], weights=portdf_no_totals['Current value']), title="")
                    #values='Current value',color='Current value', title="")
        portfolio_by_sector.data[0].textinfo = "label+text+value+percent root"
        portfolio_by_sector.update_traces(texttemplate="%{label}<br>$%{value:,.2f}")
        portfolio_by_sector.update_layout(margin = dict(t=50, l=25, r=25, b=25))

        st.plotly_chart(portfolio_by_sector, use_container_width=True)
        
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
        st.title('Editable Data Entry Table')

        initial_data = pd.DataFrame(getPortfolioData())
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
