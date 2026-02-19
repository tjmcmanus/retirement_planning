import pandas as pd
import numpy as np
import sys
import argparse
from datetime import date
from datetime import datetime

def calc_roth_conversions(maxrate,headroom_rate,uppermax,agi,headroom_max):
    if (maxrate <=headroom_rate):
       conversion = (uppermax-agi)
       headroom_conv = (headroom_max-uppermax)
       conversion_tax =(conversion*maxrate)+(headroom_conv*headroom_rate)
       #print(f" Roth conversion total is ${headroom_max-agi:,.2f}")
       #print(f" Headroom tax ${headroom_conv*headroom_rate:,.2f} conversion tax ${conversion*maxrate:,.2f}")
       #print(f" Conversion_tax ${conversion_tax:,.2f} conversion ${conversion:,.2f} and headroom conversion ${headroom_conv:,.2f}")
       conversions=conversion+headroom_conv
    else:    
       conversions = 0
       conversion_tax=0
    return conversions,conversion_tax
    
def calc_agi(joint_gross_income,div,stddectdf,daf):
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
    if ("Y" == maxdaf):
        daf=(joint_gross_income+div)*0.3
    elif (0 <= daf1 and daf1 <= ((joint_gross_income+div)*0.3)):
        daf=daf1
    elif("N" == maxdaf):
        daf=0
    else:   
        daf=0
    #print(f"Donor Advised Funds Contribution is calculated at ${daf:,.2F}")    
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
    uppervalue = df.query(f"rate == {rate_to_query}")['upper'].squeeze()
    #print(f"Upper value for {taxrate:.0%} rate is ${uppervalue:.2f}")
    return uppervalue
       
    
def calculate_atm(total_income,cap_gains,atmdf):
    tax=0
    #print(f"ATM MAGI is ${total_income+cap_gains:.2f}")
    tax_owed = np.zeros(len(atmdf))
    for i, (year, deduction, lower, upper, phase_out, rate) in enumerate(atmdf[['year','deduction','lower','upper','phase_out','rate']].values):
        amount=0
        if total_income+cap_gains <= phase_out:      
            income= round((total_income+cap_gains)-deduction,0)
            #print(f"Income is below Phase out include deduction ${income:.2f}")
        else:    
            income= round(total_income+cap_gains,0)
            #print(f"Income, with phase out, no deduction, is ${income:,.2f}")
        if income >= lower and income <= upper: 
            tax_owed [i] = round(income*rate,0)
            lowerby = income-lower
            #print(f"Income is ${income:.2f} which is above ${lower:,.2f} tween Rate is {rate:.0%}: Tax is ${tax_owed [i]:.2f}")
        tax += tax_owed[i]
    #print(f"tax owed ${tax:,.2f}")
    return tax,lowerby
    
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
    # Calculate tax owed for each bracket
    tax=0
    for i, (lower, upper, rate) in enumerate(cg_range[['lower', 'upper', 'rate']].values):
          amount=0
          if cg_income <= 0:
              tax_owed[i] = 0
          elif income+cg_income<lower:
              tax_owed[i] = 0
          elif income+cg_income >= lower and income <= upper: 
              tax_owed[i] = round(cg_income * rate,0)
          elif income+cg_income >= upper:      
              tax_owed[i] = 0
              
          tax += tax_owed[i]
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
          if income<lower:
              tax_owed[i] = 0
          if income >= lower and income <= upper: 
              tax_owed[i] = round((min(income, upper) - lower) * rate,0)
              amount = (min(income, upper) - lower)
              maxrate = rate
              uppermax = upper
          if income >= upper:      
              tax_owed[i] = round((min(income, upper) - lower) * rate,0)
              amount = (min(income, upper) - lower)
          tax += tax_owed[i]
          #print(f"total tax  ${tax:,.2f}  Tax Rate {rate:.0%}  Income  ${income:,.2f} Upper Range ${upper:,.2f} income taxed ${amount:,.2f}, Tax Calculated  ${tax_owed[i]:,.2f}")

    return tax, maxrate,uppermax

# Hypothetical married filing jointly tax brackets for illustration (replace with actual 2025 rates)
# Example usage        
#joint_total_income = 220000
#cg_income = 100000
#people = 2

if len(sys.argv) <= 1:
    print("No arguments provided. Provide Income, Cap Gains and People medicare in that order")
    sys.exit(1)
    
parser = argparse.ArgumentParser(description="A simple script with named arguments.")
 # 2. Add arguments
# --name is a named argument. You can also use -n as a short form.
parser.add_argument("--deferred_distribution", type=float, default=0,required=True,
                        help="Specify a income.")
# --age is another named argument, requiring an integer input.
parser.add_argument("--cap_gains_lt", type=float, default=0, required=False,
                        help="Specify an Long Term Gap Gains.")
parser.add_argument("--cap_gains_st", type=float, default=0, required=False,
                        help="Specify an Short Term Gap Gains.")
parser.add_argument("--medicare_persons", type=int, default=0, required=False,
                        help="Specify number of people on Medicare.")
parser.add_argument("--year", type=int, required=True,
                        help="Specify 4 digit tax year")
parser.add_argument("--max_daf", type=str, default="N", required=False,
                        help="Calculate max donation to advised fund.")
parser.add_argument("--daf", type=float, default="0", required=False,
                        help="Enter donation to advised fund.")
parser.add_argument("--int_div", type=float, default="0", required=False,
                        help="Enter amount of Dividend and Interest.")
parser.add_argument("--headroom_rate", type=float, default="24", required=False,
                        help="Enter max rate to execute conversions.")
parser.add_argument("--date", type=str, default="10/23/2025", required=False,
                        help="Date to pull from.")
parser.add_argument("--wages", type=float, default="0", required=False,
                        help="Enter totals wages for the year.")

# 3. Parse the arguments
args = parser.parse_args()
       
#joint_gross_income = args.deferred_distribution
deferred_distribution = args.deferred_distribution
wages =args.wages
cg_income_lt = args.cap_gains_lt
cg_income_st = args.cap_gains_st
people = args.medicare_persons
year =args.year
daf1 =args.daf
maxdaf=args.max_daf
div=args.int_div
headroom_rate = args.headroom_rate
#print( joint_total_income, cg_income_lt, people)

#Load the tax brackets:
dfyear = pd.read_csv('income_rates.csv')
cgdfyear= pd.read_csv('cap_gains.csv')
irmaadfyear =pd.read_csv('irmaa.csv')
stddectdfyear =pd.read_csv('standard.csv')
atmdfyear =pd.read_csv('atm.csv')
# Filter for transactions in the year 
df = dfyear[dfyear['year'] == year]
cgdf = cgdfyear[cgdfyear['year'] == year]
irmaadf= irmaadfyear[irmaadfyear['year'] == year]
stddectdf = stddectdfyear[stddectdfyear['year'] == year]
atmdf = atmdfyear[atmdfyear['year'] == year]

#print(f"Upper limit for {headroom_rate} is ${getUpperIncomeRate(headroom_rate,df):,.2f}")

#Print out the filtered data sets
#print(df.head())
#print(cgdf.head())
#print(irmaadf.head())
#print(stddectdf.head())
#print(atmdf.head())

daf = calc_daf_value(deferred_distribution+wages,div,daf1,maxdaf)
agi = calc_agi(deferred_distribution+wages+cg_income_st,div,stddectdf,daf)   
        
#Calculate all of the potential taxes 
irmaa_fees_income = calculate_irmma_penalty(agi, irmaadf, people)
cg_tax = calculate_cap_gains(agi, cgdf, cg_income_lt)

agi = agi + cg_income_lt

#print(f"AGI is ${agi}")
#Calculate Taxable income
taxable_income, maxrate, uppermax = calculate_taxable_income(agi, df)

headroom_max = getUpperIncomeRate(headroom_rate,df)
#print(f"Maxrate is {maxrate} vs {headroom_rate}")
if maxrate>headroom_rate:
    print(f"Your are above your desired tax rate of {headroom_rate:.0%}") 
    print(f"Bring you Total Taxable Income down below ${headroom_max}")
    print(f"Your total Income is ${deferred_distribution+wages+div-daf:,.2f} ")
    print(f"Deferred Distribution Income is ${deferred_distribution:,.2f}; Interest income is : ${div:,.2f} them subtract Charitable giving: ${daf:,.2f}")
    sys.exit(1)
    


conversions,conversion_tax = calc_roth_conversions(maxrate,headroom_rate,uppermax,agi,headroom_max)   
atm_tax,lowerby = calculate_atm(agi+conversions,cg_income_lt, atmdf)
#Roth Conversion Options    
irmaa_fees_income_headroom = calculate_irmma_penalty(uppermax, irmaadf, people)

print(" ")
#Report all of the findings
print(f"For Adjusted Gross Income of ${deferred_distribution+wages+div+cg_income_st+cg_income_lt:,.2f}")
if (maxdaf=="Y" or daf1>0):
    print(f"Contribute to the amount Donor Advised Fund of ${daf:,.2f} which is {daf/(deferred_distribution+wages+div):.0%} of AGI")
print(f"For an Modified Adjusted Gross Income of ${agi:,.2f} and LTC Gains of ${cg_income_lt:,.2f}")
if (atm_tax > taxable_income):
    print(f"   Alternative Minimum Tax is ${atm_tax:,.2f} which is an additional ${atm_tax-taxable_income:,.2f}")
    print(f"   Avoid ATM by decreasing income (including interest/dvidends) or lower LT Capital gains by ${lowerby:,.2f}")
    ttax=atm_tax
    deltatax=atm_tax-taxable_income
else:    
    ttax=taxable_income
    deltatax=0
    print(f"   Income tax is ${ttax:,.2f} with effective rate of {ttax/agi:.0%}") 
  
#print(f"Max Rate is: {maxrate:.0%}  Upper limit: ${uppermax:,.2f}") 
if(0 < int(cg_income_lt)):
    print(f"   LTC Gains of ${cg_income_lt:,.2f} tax is ${cg_tax:,.2f} with effective rate of {(cg_tax+deltatax)/cg_income_lt:.0%}")
    print(f"   Total federal tax is ${ttax+cg_tax:,.2f} with a effective tax rate of {(ttax+cg_tax)/(agi+cg_income_lt):.0%}")
    print(f"   Pennsylvania state tax is ${cg_tax*0.03:,.2f}")
elif 0 == cg_income_lt:
     print(f"   LTC Gains of ${cg_income_lt:,.2f}")
else:
    max_cg_deduction=-3000
    if cg_income_lt <=max_cg_deduction:
        print(f"   Capital Gains carry forward is ${cg_income_lt-max_cg_deduction:,.2f}")
        print(f"   Capital Gains deduction is ${max_cg_deduction:,.2f}")
    else:
        print(f"   Capital Gains deduction is ${cg_income_lt:,.2f}")
#print(f"   Total tax is ${ttax+cg_tax:,.2f} with a effective tax rate of {(ttax+cg_tax)/(agi+cg_income_lt):.0%}")
    

print(f" ")
if (conversions >=  0):
    if maxrate< headroom_rate:
       print(f"Headroom Roth Conversions at marginal rate is {headroom_rate:.0%}:")
    else : 
       print(f"Headroom Roth Conversions at marginal rate is {headroom_rate:.0%}:")
    print(f"   Roth Conversion amount is ${conversions:,.2f} with a tax hit of:  ${conversion_tax:,.2f}")
    print(f"   Total tax ${ttax+cg_tax+conversion_tax:,.2f} effective rate of {(ttax+conversion_tax+cg_tax)/(conversions+agi+cg_income_lt):.0%}")
    print(f"   Pennsylvania state tax do not tax Conversions to Roth")
if people > 0:
    print(f" ")
    print(f"Medicare Costs:")
    print(f"   At 65, annual Medicare Costs will be: ${irmaa_fees_income:,.2f}")
    print(f"   At 65, annual Medicare Costs (with headroom Roth Conversions) would be: ${irmaa_fees_income_headroom:,.2f}")
    print(f"   Cost of making the Headroom Roth conversion including IRMAA penalty is ${conversion_tax+(irmaa_fees_income_headroom-irmaa_fees_income):,.2f} bringing you to an effective rate of {(taxable_income+cg_tax+conversion_tax+(irmaa_fees_income_headroom-irmaa_fees_income))/(conversions+agi+cg_income_lt):.0%}")
print(f" ")
print(f"Reducing tax deferred account by ${deferred_distribution+conversions:,.2f}")
#print(f"Adding to Donor Advised Fund of ${daf:,.2f}")
print(" ")


formatted_date = args.date
#print(formatted_date)
#day_cash,day_taxable,day_tax_deferred,day_tax_free,day_total,day_expenses,day_daf = get_net_worth(formatted_date)
#print(day_cash,day_taxable,day_tax_deferred,day_tax_free,day_total,day_expenses)

print(f"Changes to balances on the plan would be:")
#print(f"{str(day_cash)}")   
print(f"                      Starting           Ending                                    Starting             Ending ")
#print(f"  Cash on hand:       ${day_cash:,.2f}      ${day_cash-ttax-cg_tax-conversion_tax:,.2f}        Taxable Accounts:        ${day_taxable-day_cash:,.2f}        ${day_taxable+deferred_distribution-daf-day_cash:,.2f}")
#print(f"  Taxable Accounts: ${day_taxable+agi-daf-cg_income_lt:,.2f}")
#print(f"  Deferred Tax Accounts: ${day_tax_deferred-agi-conversions:,.2f}")
#
# #print(f"  Tax Free Accounts:  ${day_tax_free:,.2f}      ${day_tax_free+conversions:,.2f}        Deferred Tax Accounts: ${day_tax_deferred:,.2f}      ${day_tax_deferred-deferred_distribution-conversions:,.2f}")
#print(f"  Donor Advised Fund: ${day_daf:,.2f}      ${day_daf+daf:,.2f}")
print(f" ")
print(f"Tax Prepayments:")
print(f"  Federal return:")

print(f"    Additional Taxes owed ${(ttax+cg_tax+conversion_tax):,.2f}")
print(f"    Quarterly payment of ${(ttax+cg_tax+conversion_tax)/4:,.2f}")
print(f"  PA State return:")
print(f"    Additional Taxes owed ${(div+cg_income_st+cg_income_lt)*0.03:,.2f}")
print(f"    Quarterly payment of ${((div+cg_income_st+cg_income_lt)*0.03)/4:,.2f}")
print(f" ")