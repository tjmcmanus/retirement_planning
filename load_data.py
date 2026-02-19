import pandas as pd
import streamlit as st

#@st.cache(allow_output_mutation=True, show_spinner=True)
@st.cache_data()
def get_income_tax_brackets(year):
   dfyear = pd.read_csv('income_rates.csv')
   df = dfyear[dfyear['year'] == year]
   #print(df.head())
   return df

#@st.cache_data(allow_output_mutation=True, show_spinner=True)
@st.cache_data()
def get_cap_gains_brackets(year):
   cgdfyear= pd.read_csv('cap_gains.csv')
   cgdf = cgdfyear[cgdfyear['year'] == year]
   #print(cgdf.head())
   return cgdf
 
#@st.cache_data(allow_output_mutation=True, show_spinner=True)
@st.cache_data()
def get_std_deduction(year):
    stddectdfyear =pd.read_csv('standard.csv')
    stddectdf = stddectdfyear[stddectdfyear['year'] == year]
    return stddectdf
    
    
#@st.cache_data(allow_output_mutation=True, show_spinner=True)    
@st.cache_data()
def get_medicare_costs(year):
   irmaadfyear =pd.read_csv('irmaa.csv')
   irmaadf= irmaadfyear[irmaadfyear['year'] == year]
   #print(irmaadf.head())
   return irmaadf

#@st.cache_data(allow_output_mutation=True, show_spinner=True)
@st.cache_data()
def get_atm_costs(year):
   atmdfyear =pd.read_csv('atm.csv')
   atmdf = atmdfyear[atmdfyear['year'] == year]
   #print(atmdf.head())
   return atmdf

#@st.cache_data(allow_output_mutation=True, show_spinner=True)
@st.cache_data()
def get_net_worth(ret_date):
   networth_data =load_net_worth()
   cash = networth_data[networth_data['date'] == ret_date]['cash'].squeeze()
   taxable = networth_data[networth_data['date'] == ret_date]['taxable'].squeeze()
   tax_deferred = networth_data[networth_data['date'] == ret_date]['tax_deferred'].squeeze()
   tax_free = networth_data[networth_data['date'] == ret_date]['tax_free'].squeeze()
   total = networth_data[networth_data['date'] == ret_date]['total'].squeeze()
   expenses = networth_data[networth_data['date'] == ret_date]['expenses'].squeeze()
   daf = networth_data[networth_data['date'] == ret_date]['daf'].squeeze()
   return cash,taxable,tax_deferred,tax_free,total,expenses,daf

#@st.cache_data(allow_output_mutation=True, show_spinner=True)
@st.cache_data()
def load_net_worth():
   networth_data =pd.read_csv('financial_data.csv')
   return  networth_data

#@st.cache_data()
def load_financial_accounts():
   account_data =pd.read_csv('financial_account.csv')
   return  account_data

def get_month_account_values(month, year):
   account_data =load_financial_accounts()
   print(account_data)
   ytd_spend = account_data[account_data['year']==year]
   print(ytd_spend)
   mtd_spend = ytd_spend[ytd_spend['month']== month]
   print(mtd_spend)
   return mtd_spend

def load_ssi_data():
   ssi_data =pd.read_csv('ssincome.csv')
   return  ssi_data

def get_annual_ssi_data(year):
   ssi_data = load_ssi_data()
   year_df = ssi_data[ssi_data['year']==year]
   return year_df


