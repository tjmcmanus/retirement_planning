import pandas as pd
import streamlit as st
import numpy as np
from load_data import get_annual_ssi_data,load_ssi_data



def get_age(year, name):
   datadf = get_annual_ssi_data(year)
   #print(account_data)
   year_data = datadf[datadf['year']==year]
  # print(year_data)
   agedf = year_data.loc[year_data['person']== name]
   #agedf['claiming_age'] = agedf['claiming_age'].astype(str)
   age = agedf.loc[agedf['person'] == name, 'claiming_age'].iloc[0]
   #print(age)
   return age

def get_year(age, name):
   datadf = load_ssi_data()
   #print(account_data)
   age_data = datadf[datadf['claiming_age']==age]
  # print(year_data)
   year_data = age_data.loc[age_data['person']== name]
   #agedf['claiming_age'] = agedf['claiming_age'].astype(str)
   year = year_data.loc[year_data['person'] == name, 'year'].iloc[0]
   #print(age)
   return year


def get_monthly_benefit(year, name):
   datadf = get_annual_ssi_data(year)
   #print(account_data)
   year_data = datadf[datadf['year']==year]
   #print(ytd_spenddatadf)
   monthly_benefit = year_data[year_data['person']== name]
   monthly_person_benefit = monthly_benefit.loc[monthly_benefit['person'] == name, 'monthly_benefit'].iloc[0]
   #print(monthly_person_benefit) 
   return monthly_person_benefit

def get_claiming_age():
    ss_age = st.session_state["SSI_AGE"]
    return int(ss_age)