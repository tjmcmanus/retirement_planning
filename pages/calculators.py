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
from tabs import clear_submit

networth = load_net_worth()
conversion_tab, something_tab = st.tabs(["Tax planner","something"])
with conversion_tab:
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
        print(f"agi to calculate taxable income is {agi}")
        taxable_income, maxrate, uppermax = calculate_taxable_income(agi, taxratedf)
        #st.write("Income Tax is : ",taxable_income,maxrate,uppermax )
   
        headroom_max = getUpperIncomeRate(headroom_rate,taxratedf)
        #st.write("Max Conversion Tax Rate is : ",headroom_max)
   
        if maxrate>headroom_rate:
            st.write("bad stuff is happening")
        lowerby=0   
        atm_lower,atm_deduction = getlower_atm_amount_n_deduction(year, atmdf)
        print(f"ATM Values are: {atm_lower} and {atm_deduction} or {atm_lower+atm_deduction}")
        std_deduction=get_std_deduction_by_year(year)
        if uppermax>=(atm_lower+atm_deduction):
            uppermax=atm_lower+atm_deduction
            print(f"UpperMax is: {uppermax}")
        if roth_amount>0:
            conversions=roth_amount   
            conversion_tax= calc_roth_conversions_tax(maxrate,headroom_rate,uppermax,agi,headroom_max,conversions)
            print(f"conversio tax is: {conversion_tax}")
        else:
            print(f"agi for roth conversion calc: {agi}")
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
            print(f"MAGI is {agi+conversions+cg_income_lt} and ATM Lower is {atm_lower+atm_deduction+calc_daf+30000}")
            #conversions=0
            #conversion_tax=0
    
        atm_tax,init_lowerby = calculate_atm(agi,cg_income_lt, atmdf)
        print(f"ATM Tax is {atm_tax} and taxable Income is {taxable_income}")
        if taxable_income>atm_tax:
            atm_tax=0
            print(f"ATM_tax lower MAGI is {agi+conversions+cg_income_lt} and ATM Lower is {atm_lower+atm_deduction+calc_daf+30000}")
        else:
            print(f"ATM_tax higher MAGI is {agi+cg_income_lt} and ATM Lower is {atm_lower+atm_deduction+calc_daf+30000}")
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
                print(f"Input STCG is {cg_income_st:.6f}")
                st.metric(label="Short Term Capital Gains", value=f_cgst_month)
            if 0 != (cg_income_lt):
                st.metric(label="Long Term Capital Gains", value=fcg_taxable_value)

        with col1row5:   
            st.markdown('##### Taxes Owed')
           # if atm_tax>taxable_income:
            #    fincome_tax=f"${atm_tax+cg_tax-pd_tax_amount:,.2f}"
            #else:
            fincome_tax=f"${taxable_income+cg_tax-pd_tax_amount:,.2f}"
            print(f"Income {taxable_income} minus estimated {pd_tax_amount} is {fincome_tax}")
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
with something_tab:
    st.header("something calculator")