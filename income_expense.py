from matplotlib.pylab import f
import streamlit as st
import pandas as pd
import numpy as np
import datetime
from load_data import load_ssi_data,get_annual_ssi_data,get_std_deduction, get_income_tax_brackets,load_net_worth
from calculations import calculate_taxable_income, calculate_std_deduction,get_rmd_value
from ssibenefits import get_monthly_benefit,get_age, get_claiming_age,get_year


def calculate_taxes(income,daf,year):
    stddectdf = get_std_deduction(year)
   # print(stddectdf)
    taxratedf = get_income_tax_brackets(year)
    std_dect = calculate_std_deduction(income,stddectdf)
    #print(std_dect)
    agi=(income-std_dect)-daf
    taxes,maxrate,uppermax = calculate_taxable_income(agi,taxratedf)
    return taxes

def build_income_expenses_display():
    #getPortfolioData()
    cash=0
    tax_free=0
    current_year = datetime.date.today().year
    networth = load_net_worth()
    cash_in=networth["cash"].values[-1]
    brokerage=networth["taxable"].values[-1]
    trad_value=networth["tax_deferred"].values[-1]
    tax_free_in =networth["tax_free"].values[-1]
   
    
    # The end year (range() is exclusive of the stop value, so we use 2051 to include 2050)
    end_year = 2051 
    trad_value_new = np.zeros(len(range(current_year, end_year)))
    expenses = float(st.session_state["EXPENSE"])
    ssi_year = int(get_year(get_claiming_age(),"Tom"))
    rate = 1+float(st.session_state["RATE"])/100
    daf_rate = float(st.session_state["DAF_RATE"])/100
    expense_multiplier = int(st.session_state["EXPENSE_MULITPLIER"])
    daf_in=0
    #print(f"rate is {rate}")
    #print(f"Looping from {current_year} to 2050:")
    # Iterate through the years
    #i_e_df = pd.DataFrame(columns=['Year', 'Age', 'Income Flows', 'Planned Distribution', "Dividends", "Total Inflows","Expenses","Tax payment","Total Outflows"])
    i_e_df = pd.DataFrame(columns=['Year', 'Age', 'SSI Flows', 'Planned Distribution','Roth Conversions','RMD','Total Inflows','Taxes Owed',"Expenses",'Portfolio Withdrawl']) 
    #print("i_e_df")
    port_draw_df = pd.DataFrame(columns=['Year', 'Cash','Taxable','Tax Deferred', 'Tax Free','Donor Advised Fund'])
    #print("port_draw_df")
    for year in range(current_year, end_year):
       #print(year)
       rmd=0
       conversions = 0
       planned_dist = 0
       
       
       s_age = get_age(year, "Sarah")
       t_age = get_age(year, "Tom")
       age = str(s_age) + "/" + str(t_age)
       
       int_s_age = int(s_age)
       if get_claiming_age() <= int_s_age:
          s_monthly_benefit =  get_monthly_benefit(year, "Sarah")
       else:
           s_monthly_benefit =  0
       if get_claiming_age() <= int(t_age):      
           t_monthly_benefit =  get_monthly_benefit(year, "Tom")
       else:
           t_monthly_benefit =  0  
       monthly_benefit = (s_monthly_benefit + t_monthly_benefit) * 12

       
       #print(ssi_year)
       convert_at = int(st.session_state["CONV_AMOUNT_AT_SSI_AGE"])
       
       if year == 2026:
          planned_dist = 0
          daf=0
          conversions = 100000
       elif year == 2027:
          planned_dist = 575000
          daf = planned_dist*0.33
          conversions = 0
       elif year >2027 and year < ssi_year:
          planned_dist = 0
          daf=0
          conversions = 375000
       else:
           planned_dist = 0
           daf=0
           conversions = convert_at
       
       rmd_distribution = get_rmd_value(t_age)
       if rmd_distribution > 0:
          rmd=trad_value/rmd_distribution 
          rmd=int(rmd)
          #print(f"RMD is post conversion {rmd}") 
          #print(f" rmd distribution is {rmd_distribution}")
          if rmd > conversions+planned_dist:
             # print(f"rmd greater before {rmd}")
              rmd = rmd-conversions-planned_dist
             # print(f"ELse conversions {conversions} planned dist {planned_dist} RMD {rmd}")  
          elif rmd < (planned_dist+conversions):
              rmd = 0 
            #  print(f"RMD is greater than conversions {conversions} planned dist {planned_dist} RMD {rmd}")  
          else:
              rmd = 0     

      # print(f"RMD is {rmd}")  
            
       trad_value_new = trad_value-planned_dist-conversions-rmd
       #print(f"New Trad Value is: {trad_value_new}; Old is {trad_value}")
       if trad_value < trad_value_new or trad_value < 0 or trad_value_new <0 :
         #  print("trad_value > trad_value_new or trad_value < 0 or trad_value_new <0")
           planned_dist=0
           conversions=0
           rmd = 0
           daf=0
           #tot_inflows = monthly_benefit+rmd
       else:  
          # tot_inflows = monthly_benefit+rmd
           trad_value=trad_value_new*rate
          # print(f"Trad value is {trad_value}")
           
       taxable_inflows = (monthly_benefit*0.85)+planned_dist+conversions+rmd-daf
           
       taxes=calculate_taxes(taxable_inflows,0,year)
       expenses = expenses * 0.993
       tot_inflows=monthly_benefit
       port_withdrawl = (expenses+taxes) - tot_inflows
       #print(f"total inflows: {tot_inflows} Portfolio withdrawl : {port_withdrawl} Expenses : {expenses} Taxes: {taxes}")
       if port_withdrawl < 0:
           port_withdrawl=0
       tot_inflows= port_withdrawl+tot_inflows
       #print(f"Total Inflows : {tot_inflows}")
       #print(f"Taxes are ${taxes}")
       #print( year, age, s_monthly_benefit, t_monthly_benefit, conversions, taxes)   
       #print(f"cash in: {cash_in} Cash: {cash} SSI: {monthly_benefit} Port withdrawl : {port_withdrawl} Expense: {expenses} Taxes: {taxes}")


            
       if cash>0:
            cash = cash+monthly_benefit+port_withdrawl-expenses-taxes
            cash_rate = ((rate-1)/3)
            cash = cash + cash*cash_rate
       else:     
            cash = cash_in+monthly_benefit+port_withdrawl-expenses-taxes
            cash_rate = ((rate-1)/3)
            cash = cash + cash*cash_rate
       #print(year)     
       
       compare = (expenses+taxes)*expense_multiplier
       #print(f"Compare is : {compare} and brokerage is {brokerage}")
     

       if brokerage < compare:
           planned_dist=planned_dist+conversions/2
           conversions=conversions/2
           brokerage = (brokerage+planned_dist+rmd-daf-port_withdrawl)*rate
           #print(f"If: Brokerage : {brokerage}")
       elif brokerage<=0:
          # print(f"Elif: Brokerage : {brokerage}")
           brokerage = (brokerage+planned_dist+rmd-daf-port_withdrawl)*rate
       else:
           # print(f"Else: Brokerage : {brokerage}")
            brokerage = (brokerage+planned_dist+rmd-daf-port_withdrawl)*rate
           # print(f"Brokerage with rate : {brokerage}")
       
       if tax_free >0:    
            tax_free =(tax_free+conversions)*rate
       else :
            tax_free =(tax_free_in+tax_free+conversions)*rate
            
       if daf_in == 0:
           daf_in = daf
       elif daf_in >= (daf_in*daf_rate):
           daf_in = daf_in - (daf_in*daf_rate) + daf
       else:
           daf_in=daf    
           #daf_in  
       
       #print(year,cash,brokerage,trad_value_new,tax_free,daf_in)
       i_e_df.loc[len(i_e_df)] = [year,age,monthly_benefit,planned_dist,conversions,rmd,tot_inflows,taxes,expenses,port_withdrawl] 
       port_draw_df.loc[len(port_draw_df)] = [year,cash,brokerage,trad_value,tax_free,daf_in]
    
    return i_e_df, port_draw_df


