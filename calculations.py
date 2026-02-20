from matplotlib.pylab import f
import pandas as pd
import numpy as np
import streamlit as st
import sys
import argparse
from datetime import date
from datetime import datetime
from load_data import get_cap_gains_brackets, get_income_tax_brackets, get_net_worth, get_medicare_costs, get_atm_costs, get_std_deduction, load_net_worth

def calc_roth_conversions_tax(maxrate,headroom_rate,uppermax,agi,headroom_max,conversion):
    if (maxrate <=headroom_rate):
       conversion_max = (uppermax-agi)
       headroom_conv = (headroom_max-uppermax)
       #print(f"headroom conversion is {headroom_max},uppermax is {uppermax} ")
       delta_conversion = conversion_max-conversion
      # print(f"delta conversion is {delta_conversion}")
       if delta_conversion < 0:
           headroom_conv = delta_conversion*-1
           conversion_tax =(conversion_max*maxrate)+(headroom_conv*headroom_rate)
       else:
           conversion_tax =(conversion*maxrate)
             
      # print(f"Conversion tax breakdown {conversion_tax:,.2f} ")
  #     print(f" Roth conversion total is ${headroom_max-agi:,.2f}")
  #     print(f" Headroom tax ${headroom_conv*headroom_rate:,.2f} conversion tax ${conversion*maxrate:,.2f}")
  #     print(f" Conversion_tax ${conversion_tax:,.2f} conversion ${conversion:,.2f} and headroom conversion ${headroom_conv:,.2f}")
       conversions=conversion+headroom_conv
   #    print(f"Combined {headroom_conv}")
    else:       
       conversions = 0
       conversion_tax=0
   # print(f"Conversion and Conversion_tax are {conversions} and {conversion_tax}")   
    return conversion_tax

def calc_roth_conversions(maxrate,headroom_rate,uppermax,agi,headroom_max,lowerby):
    if (maxrate <=headroom_rate):
       conversion = (uppermax-agi)
       headroom_conv = (headroom_max-uppermax)
#       print(f"Lowerby value is {lowerby}")
       #print(f"MaxRate is {maxrate} and Headroom is {headroom_rate}")
       #print(f"Headroom_conv is {headroom_conv}")
       if lowerby>0:
          # print(f"Lowerby value is {lowerby}")
           lower_headroom_conv=headroom_conv-lowerby
           conversion_tax =(conversion*maxrate)+(lower_headroom_conv*headroom_rate)
           headroom_conv=lower_headroom_conv
          # print(f"Reduce Headroom {lower_headroom_conv}")
       else: 
          conversion_tax =(conversion*maxrate)+(headroom_conv*headroom_rate)
         # print(f"Keep Headroom {headroom_conv} + {conversion}")
  #     print(f" Roth conversion total is ${headroom_max-agi:,.2f}")
  #     print(f" Headroom tax ${headroom_conv*headroom_rate:,.2f} conversion tax ${conversion*maxrate:,.2f}")
  #     print(f" Conversion_tax ${conversion_tax:,.2f} conversion ${conversion:,.2f} and headroom conversion ${headroom_conv:,.2f}")
       conversions=conversion+headroom_conv
   #    print(f"Combined {headroom_conv}")
    else:       
       conversions = 0
       conversion_tax=0
   # print(f"Conversion and Conversion_tax are {conversions} and {conversion_tax}")   
    return conversions,conversion_tax
    
def calc_agi(joint_gross_income,div,stddectdf,daf):
    #print(joint_gross_income,div,stddectdf,daf)
    if(calculate_std_deduction(joint_gross_income+div,stddectdf) < daf):
        agi = joint_gross_income+div-daf-(calculate_std_deduction(joint_gross_income,stddectdf))
        #print(agi)
        #print("Daf Route")
    elif(0 == (calculate_std_deduction(joint_gross_income+div,stddectdf))):
        agi = 0
        #print("0 income Route")
    else:
        agi = (joint_gross_income +div- calculate_std_deduction(joint_gross_income,stddectdf))
       # print("std Route")
    return agi    
        
def calc_daf_value(joint_gross_income,div,daf1,maxdaf):
    #print(joint_gross_income,div,daf1,maxdaf)
    if ("Y" == maxdaf):
        daf=(joint_gross_income+div)*0.3
        #print("DAF is : ${daf:,.2f}")
    elif (0 <= daf1 and daf1 <= ((joint_gross_income+div)*0.3)):
        daf=daf1
        #print("Between DAF is : ${daf:,.2f}")
    elif("N" == maxdaf):
        daf=0
    else:   
        daf=0
    #print("Donor Advised Funds Contribution is calculated at ${daf:,.2f}")   
    #print(daf)
    return daf
    
def get_net_worth(ret_date):
   networth_data =pd.read_csv('financial_data.csv')
   cash = networth_data[networth_data['date'] == ret_date]['cash'].squeeze()
   taxable = networth_data[networth_data['date'] == ret_date]['taxable'].squeeze()
   tax_deferred = networth_data[networth_data['date'] == ret_date]['tax_deferred'].squeeze()
   tax_free = networth_data[networth_data['date'] == ret_date]['tax_free'].squeeze()
   total = networth_data[networth_data['date'] == ret_date]['total'].squeeze()
   expenses = networth_data[networth_data['date'] == ret_date]['expenses'].squeeze()
   daf = networth_data[networth_data['date'] == ret_date]['daf'].squeeze()
   return cash,taxable,tax_deferred,tax_free,total,expenses,daf

def getUpperIncomeRate(taxrate,year_tax_brackets_df):
    df = pd.DataFrame(year_tax_brackets_df)
    #print(df)
    rate_to_query = float(taxrate)
    #print(rate_to_query)
    uppervalue = df.query(f"rate == {rate_to_query}")['upper'].squeeze()
    #print(uppervalue)
    return uppervalue
       
def calc_atm_phase_out(total_income,cap_gains,deduction,phase_out,execption_rate):
    if total_income+cap_gains <= phase_out:
       income= round(total_income-deduction,0)
       #print(f"Income is below Phase out include deduction ${income:,.2f}")
    elif total_income+cap_gains > phase_out:
        deduction=deduction - (execption_rate*(total_income+cap_gains-phase_out))
        income=round(total_income-deduction,0)
       # print(f"Income is above Phase out include deduction ${income:,.2f}")
    else:
       income= round(total_income,0)
      # print(f"Income, with phase out, no deduction, is ${income:,.2f}")
    return income
           
def calculate_atm(total_income,cap_gains,atmdf):
    tax=0
    lowerby=0
    #print(f"inside calculate: ATM MAGI is ${total_income+cap_gains:.2f}")
    
    tax_owed = np.zeros(len(atmdf))
    
    for i, (year, deduction, lower, upper, phase_out, rate, execption_rate) in enumerate(atmdf[['year','deduction','lower','upper','phase_out','rate','execption_rate']].values):
        amount=0
        #fyear=f"{year:.0f}"
        #print(f"Year is {year}")
        std_deduction=get_std_deduction_by_year(year)
        #print(f"Std Deduction is {std_deduction}")
        income =calc_atm_phase_out(total_income+std_deduction,cap_gains,deduction,phase_out,execption_rate)
        if income >= lower and income <= upper: 
            tax_owed [i] = round(income*rate,0)
            lowerby = income-lower
           # print(f"Income is ${income:.2f} which is above ${lower:,.2f} tween Rate is {rate:.0%}: Tax is ${tax_owed [i]:.2f}")
        tax += tax_owed[i]
    #print(f"tax owed ${tax:,.2f}")
    #print(f"Lowerby is {lowerby}")
    return tax,float(lowerby)

def getlower_atm_amount_n_deduction(year, atmdf):
    atm_lower = np.zeros(len(atmdf))
    atm_deduct = np.zeros(len(atmdf))
    for i, (year, deduction, lower, upper, phase_out, rate) in enumerate(atmdf[['year','deduction','lower','upper','phase_out','rate']].values):
       atm_lower [i] =lower
       atm_deduct [i] =deduction
       
    return  atm_lower[1],atm_deduct[1]
   
def calculate_atm1(total_income,cap_gains,atmdf):
    tax=0
    #print(f"ATM MAGI is ${total_income+cap_gains:.2f}")
    lowerby=0
    tax_owed = np.zeros(len(atmdf))
    for i, (year, deduction, lower, upper, phase_out, rate) in enumerate(atmdf[['year','deduction','lower','upper','phase_out','rate']].values):
        amount=0
        if total_income+cap_gains <= phase_out:      
            income= round((total_income+cap_gains)-deduction,0)
            #print(f"Income is below Phase out include deduction ${income:.2f}")
        else:    
            income= round(total_income+cap_gains,0)
           # print(f"Income, with phase out, no deduction, is ${income:,.2f}")
        if income >= lower and income <= upper: 
            tax_owed [i] = round(income*rate,0)
            lowerby = income-lower
           # print(f"Income is ${income:.2f} which is above ${lower:,.2f} tween Rate is {rate:.0%}: Tax is ${tax_owed [i]:.2f}")
        tax += tax_owed[i]
    #print(f"tax owed ${tax:,.2f}")
    return tax,float(lowerby)
    
def get_std_deduction_by_year(year_in):
    stddectdf=get_std_deduction(year_in)
    for i, (year, deduction) in enumerate(stddectdf[['year', 'deduction']].values):
        return float(deduction)
    
def calculate_std_deduction(joint_gross_income,stddectdf):
    #deduction = np.zeros(len(stddectdf))
    for i, (year, deduction) in enumerate(stddectdf[['year', 'deduction']].values):
        if (joint_gross_income >= deduction):
               return deduction
        else :
              deduction = 0
              return deduction
    
def calculate_irmma_penalty(income, irmaa_range, people):
    # Create an array of zeros with the same length as the number of tax brackets
    tax_owed = np.zeros(len(irmaa_range))
    # Calculate tax owed for each bracket
    monthly_penalty=0
    for i, (lower, upper, rate) in enumerate(irmaa_range[['lower', 'upper', 'rate']].values):
          amount=0
          if income<lower:
              tax_owed[i] = 0
          if income >= lower and income <= upper: 
              tax_owed[i] = rate
          if income >= upper:      
              tax_owed[i] = 0
          monthly_penalty += tax_owed[i]
          #print(f"total tax  ${monthly_penalty}  Tax Rate ${rate}  Income  ${income} Upper Range ${upper}   ${tax_owed[i]}")

    return monthly_penalty*12*people

def calculate_cap_gains(income, cg_range, cg_income):
    # Create an array of zeros with the same length as the number of tax brackets
    tax_owed = np.zeros(len(cg_range))
    #tobetaxed = np.zeros(len(cg_range))
    # Calculate tax owed for each bracket
    #\print(f"Income {income} cg_income {cg_income}")
    
    agi=income+cg_income
    tax=0
    tobetaxed=0
    #print(f"agi {agi} tax {tax} tobetaxed {tobetaxed}")
    for i, (lower, upper, rate) in enumerate(cg_range[['lower', 'upper', 'rate']].values):
          amount=0
          if cg_income <= 0:
             # print(f"cg_income {cg_income}")
              tax_owed[i] = 0
          elif agi<lower:
              #print(f"AGI is {agi}")
             # print(f"AGI is {agi} lowwer {lower}  rate {rate}")
              tax_owed[i] = 0
          elif agi >= lower and agi <= upper: 
              #print(f"Middle AGI is {agi} lowwer {lower} upper {upper} rate {rate}")
              taxed_cg=agi-lower-income
              tobetaxed=cg_income-taxed_cg
              tax_owed[i] = round((cg_income) * rate,0)
              
              #print(f"agi {agi} tax {tax} cg_income {cg_income} tobetaxed {tobetaxed} and tax_owed[i] {tax_owed[i]}")
              
          elif agi >= upper:  
             # print(f"Upper AGI is {agi} lowwer {lower} upper {upper} rate {rate}")
              if income > upper:
                  tax_owed[i] = 0
                  tobetaxed=cg_income
              else:
                  taxed_cg=upper-income
                  tobetaxed=cg_income-taxed_cg
                  tax_owed[i] = round((taxed_cg) * rate,0)
                 # print(f"agi {agi} tax {tax} taxed_cg {taxed_cg} tobetaxed {tobetaxed} and tax_owed[i] {tax_owed[i]}")
              
          cg_income = tobetaxed
          tax += tax_owed[i]
          #print(f"total tax  ${tax}  Tax Rate ${rate}  Income  ${income} Upper Range ${upper} , CG Amount ${cg_income} to be taxed {tobetaxed} Tax Calculated  ${tax_owed[i]}")
          #print(f"total tax  ${tax}  Tax Rate ${rate}  Income  ${income} Upper Range ${upper} , CG Amount ${cg_income} Tax Calculated  ${tax_owed[i]}")

    return tax

    
def calculate_taxable_income(income, tax_brackets_df):
    """
    Calculate taxable income based on given tax brackets and rates using NumPy and Pandas.

    :param income: Total joint income
    :param tax_brackets_df: Pandas DataFrame containing tax brackets and rates
    :return: Taxable income after applying the given tax brackets
    """
    # Create an array of zeros with the same length as the number of tax brackets
    tax_owed = np.zeros(len(tax_brackets_df))
    # Calculate tax owed for each bracket'
    uppermax=0
    maxrate=0
    tax=0
    for i, (lower, upper, rate) in enumerate(tax_brackets_df[['lower', 'upper', 'rate']].values):
          amount=0
          #print(f"income is {income}, Lower is {lower}, Upper is {upper}, rate is {rate}, i is {i}")
          if income<lower:
              tax_owed[i] = 0
              #print(f"Amount is {amount}")
          if income >= lower and income <= upper: 
              tax_owed[i] = round((min(income, upper) - lower) * rate,0)
              amount = (min(income, upper) - lower)
              maxrate = rate
              uppermax = upper
             # print(f"Amount is {amount}")
             # print(f"Tax_owed is middle {tax_owed[i]}")
          if income >= upper:      
              tax_owed[i] = round((min(income, upper) - lower) * rate,0)
              amount = (min(income, upper) - lower)
             # print(f"Amount is {amount}")
             # print(f"Tax_owed is upper {tax_owed[i]}")
          tax += tax_owed[i]
          #print(f"Amount in loop no if is {amount}")
          #print(f"Tax in loop no if is {tax}")
          #print(f"total tax  ${tax:,.2f}  Tax Rate {rate:.0%}  Income  ${income:,.2f} Upper Range ${upper:,.2f} income taxed ${amount:,.2f}, Tax Calculated  ${tax_owed[i]:,.2f}")

    return tax, maxrate,uppermax

def get_rmd_value(age):
    rmddf = load_rmd_data()
    try:
       distrm= rmddf[rmddf['Age'] == age]
       #print(distrm)
       distribution_rate = distrm.loc[distrm['Age'] == age, 'Distribution'].values[0]
       #print(f"rmd dist rate is {distribution_rate}")
    except Exception as e:   
       #print("Age not found") 
       distribution_rate = 0
    
    return distribution_rate


def load_rmd_data():
   rmd_data =pd.read_csv('rmd.csv')
   return  rmd_data
   