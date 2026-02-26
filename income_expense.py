from matplotlib.pylab import f
import streamlit as st
import pandas as pd
import numpy as np
import datetime
import logging
import os
from load_data import load_ssi_data,get_annual_ssi_data,get_std_deduction, get_income_tax_brackets,get_networth_by_month
from calculations import calculate_taxable_income, calculate_std_deduction,get_rmd_value
from ssibenefits import get_monthly_benefit,get_age, get_claiming_age,get_year

# Configure logging to match calculations.py pattern
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Distribution configuration constants
YEAR_2026_CONVERSION = 100000
YEAR_2027_DAF_RATIO = 0.33
PRE_SSI_CONVERSION = 375000


def _calculate_year_distributions(year: int, ssi_year: int,
                                  planned_dist_2027: float,
                                  convert_at: int) -> tuple:
    """
    Calculate planned distributions, DAF contributions, and conversions for a given year.
    
    Args:
        year: The year to calculate distributions for
        ssi_year: The year SSI benefits begin
        planned_dist_2027: Planned distribution amount for 2027
        convert_at: Conversion amount to use at SSI age
        
    Returns:
        tuple: (planned_dist, daf, conversions) as floats
        
    Raises:
        ValueError: If ssi_year <= 2027
    """
    # Input validation
    if year < 2026:
        logger.warning(f"Year {year} is before 2026, returning zero distributions")
        return (0.0, 0.0, 0.0)
    
    if ssi_year <= 2027:
        logger.error(f"Invalid ssi_year {ssi_year}, must be > 2027")
        raise ValueError(f"ssi_year must be greater than 2027, got {ssi_year}")
    
    # Year-specific distribution logic
    if year == 2026:
        return (0.0, 0.0, float(YEAR_2026_CONVERSION))
    
    if year == 2027:
        daf = planned_dist_2027 * YEAR_2027_DAF_RATIO
        return (planned_dist_2027, daf, 0.0)
    
    if 2027 < year < ssi_year:
        return (0.0, 0.0, float(PRE_SSI_CONVERSION))
    
    # Default case: year >= ssi_year
    return (0.0, 0.0, float(convert_at))


def calculate_taxes(income, daf, year):
    """
    Calculate taxes based on income, donor advised fund contributions, and year.
    
    Args:
        income: Total taxable income
        daf: Donor Advised Fund contribution amount
        year: Tax year for calculation
        
    Returns:
        float: Calculated tax amount (returns 0.0 on error)
        
    Raises:
        No exceptions raised - errors are logged and 0.0 is returned
    """
    try:
        logger.debug(f"calculate_taxes inputs: income={income:,.2f}, daf={daf:,.2f}, year={year}")
        
        # Validate inputs
        if income < 0:
            logger.warning(f"Negative income provided: {income:,.2f}, setting to 0")
            income = 0
        
        if daf < 0:
            logger.warning(f"Negative DAF provided: {daf:,.2f}, setting to 0")
            daf = 0
            
        if not isinstance(year, int) or year < 1900 or year > 2100:
            logger.error(f"Invalid year provided: {year}, must be integer between 1900-2100")
            return 0.0
        
        # Get standard deduction data
        stddectdf = get_std_deduction(year)
        if stddectdf is None or stddectdf.empty:
            logger.error(f"Failed to retrieve standard deduction data for year {year}")
            return 0.0
        logger.debug(f"Retrieved standard deduction data for year {year}")
        
        # Get tax bracket data
        taxratedf = get_income_tax_brackets(year)
        if taxratedf is None or taxratedf.empty:
            logger.error(f"Failed to retrieve tax brackets for year {year}")
            return 0.0
        logger.debug(f"Retrieved tax bracket data for year {year}")
        
        # Calculate standard deduction
        std_dect = calculate_std_deduction(income, stddectdf)
        logger.debug(f"Standard deduction calculated: {std_dect:,.2f}")
        
        # Calculate AGI
        agi = (income - std_dect) - daf
        logger.debug(f"AGI calculated: {agi:,.2f} (income={income:,.2f} - std_dect={std_dect:,.2f} - daf={daf:,.2f})")
        
        # Calculate taxes
        taxes, maxrate, uppermax = calculate_taxable_income(agi, taxratedf)
        logger.debug(f"Taxes calculated: {taxes:,.2f}, maxrate={maxrate}, uppermax={uppermax:,.2f}")
        
        return taxes
        
    except TypeError as e:
        logger.error(f"Type error in calculate_taxes: {e}. Inputs - income: {income}, daf: {daf}, year: {year}")
        return 0.0
    except ValueError as e:
        logger.error(f"Value error in calculate_taxes: {e}. Inputs - income: {income}, daf: {daf}, year: {year}")
        return 0.0
    except KeyError as e:
        logger.error(f"Key error in calculate_taxes (missing data): {e}. Year: {year}")
        return 0.0
    except Exception as e:
        logger.error(f"Unexpected error in calculate_taxes: {type(e).__name__}: {e}. Inputs - income: {income}, daf: {daf}, year: {year}")
        return 0.0

def build_income_expenses_display():
    #getPortfolioData()
    cash=0
    tax_free=0
    current_year = datetime.date.today().year
    # Load current net worth data using get_networth_by_month (replaces deprecated load_net_worth)
    try:
        # Get current month and year for latest portfolio values
        current_month = datetime.date.today().month
        
        # Get net worth with current market prices
        detailed_df, summary_df = get_networth_by_month(current_month, current_year)
        
        # Validate summary DataFrame is not empty
        if summary_df.empty:
            logger.error(f"Net worth data is empty for {current_month}/{current_year}, using default values of 0")
            cash_in = brokerage = trad_value = tax_free_in = 0.0
        else:
            # Extract values by account_type from summary DataFrame
            # Using .get() with default 0.0 for safe access
            cash_in = float(summary_df[summary_df['account_type'] == 'Cash']['market_value'].sum())
            brokerage = float(summary_df[summary_df['account_type'] == 'Brokerage']['market_value'].sum())
            trad_value = float(summary_df[summary_df['account_type'] == 'Traditional']['market_value'].sum())
            tax_free_in = float(summary_df[summary_df['account_type'] == 'Roth']['market_value'].sum())
            
            logger.debug(f"Loaded net worth for {current_month}/{current_year} - "
                       f"Cash: ${cash_in:,.2f}, Brokerage: ${brokerage:,.2f}, "
                       f"Traditional: ${trad_value:,.2f}, Tax-Free: ${tax_free_in:,.2f}")
    
    except ValueError as e:
        logger.error(f"Invalid date parameters for net worth: {e}. Using default values of 0")
        cash_in = brokerage = trad_value = tax_free_in = 0.0
    except RuntimeError as e:
        logger.error(f"Failed to load portfolio data: {e}. Using default values of 0")
        cash_in = brokerage = trad_value = tax_free_in = 0.0
    except Exception as e:
        logger.error(f"Unexpected error loading net worth: {type(e).__name__}: {e}. Using default values of 0")
        cash_in = brokerage = trad_value = tax_free_in = 0.0
   
    
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
    i_e_df = pd.DataFrame(columns=['Year', 'Age', 'SSI Flows', 'Planned Distribution','Roth Conversions','RMD','Total Inflows','Taxes Owed',"Expenses",'Portfolio Withdrawal'])
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
       planned_dist_2027 = float(st.session_state.get("PLANNED_DIST_2027", "575000"))
       
       # Calculate year-specific distributions using helper function
       planned_dist, daf, conversions = _calculate_year_distributions(
           year=year,
           ssi_year=ssi_year,
           planned_dist_2027=planned_dist_2027,
           convert_at=convert_at
       )
       
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


