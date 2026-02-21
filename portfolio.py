# Source - https://stackoverflow.com/a
# Posted by Trenton McKinney, modified by community. See post 'Timeline' for change history
# Retrieved 2025-12-29, License - CC BY-SA 4.0

import yfinance as yf
import pandas as pd
import streamlit as st
import os
from datetime import datetime
from load_data import get_portfolio_truth_by_month

def color_negative_positive(value):
    """
    Colors the text red if the value is negative, and green if positive or zero.
    """
    if isinstance(value, (int, float)):
        return 'color: red' if value < 0 else 'color: green'
    return ''

@st.cache_data()
def get_current_price(symbol):
    ticker = yf.Ticker(symbol)
    todays_data = ticker.history(period='4d').tail(1)
    return todays_data['Close'].iloc[0]

#@st.cache_data()
def get_qty(symbol):
    df = getPortfolioData()
    quanity = df.loc[df['symbol'] == symbol, 'qty'].iloc[0]
    #print(f"quantity is: {quanity}")
    return quanity

#@st.cache_data()
def get_purchase_price(symbol):
    df = getPortfolioData()
    purchase_price = df.loc[df['symbol'] == symbol, 'purchase_price'].iloc[0]
    #print("Purchase price is: {purchase_price}")
    return purchase_price

#@st.cache_data()
def get_tax_type(symbol):
    df = getPortfolioData()
    tax_type = df.loc[df['symbol'] == symbol, 'account_type'].iloc[0]
    #print("tax_type price is: {tax_type}")
    return tax_type

#@st.cache_data()
def get_ticker_name(symbol):
    #df = getPortfolioData()
    #ticker_name = df.loc[df['symbol'] == symbol, 'name'].iloc[0]
    ticker = yf.Ticker(symbol)
    return ticker.info['shortName']
    #return ticker_name


def get_sector(symbol):
    #print(f"get sector {symbol}")
    df = getPortfolioData()
    if df.loc[df['symbol'] == symbol, 'sector'].iloc[0].startswith("MF:"):
       sector_in = df.loc[df['symbol'] == symbol, 'sector'].iloc[0]
       before, separator, after = sector_in.partition(':')
       sector= after.strip()
      # print(f"Sector is (else) : {sector}")
       
    else:    
        ticker = yf.Ticker(symbol)
        sector = ticker.info.get('sector')
        #print(f"Sector is (if) : {sector}")
       
    return sector

def calculate_current_value(symbol):
    current_value = get_qty(symbol) * get_current_price(symbol)
    #print(stock_value_port)
    return current_value

def calculate_cost_basis(symbol):
    cost_basis = get_qty(symbol) * get_purchase_price(symbol)
    #print(stock_value_port)
    return cost_basis

#@st.cache_data()
def get_current_dividend(symbol):
    ticker = yf.Ticker(symbol)
    dividends_data = ticker.dividends
    # Find the latest dividend payment date (ex-date) and amount
    if not dividends_data.empty:
       latest_dividend_date = dividends_data.index[-1].strftime('%D')
       latest_dividend_amount = dividends_data.iloc[-1]* get_qty(symbol)
       annual_dividend_count = get_dividend_frequency(symbol)
       annual_dividend_amount = latest_dividend_amount * annual_dividend_count
    else:
       latest_dividend_date = "na" 
       latest_dividend_amount = 0.00
       annual_dividend_amount = 0
       annual_dividend_count = 0
    #print( latest_dividend_date, latest_dividend_amount )
    return latest_dividend_date,latest_dividend_amount, annual_dividend_amount

def get_dividend_frequency(symbol):
    ticker = yf.Ticker(symbol)
    dividends_history = ticker.dividends
    if not dividends_history.empty:
        # Filter dividends for the year 2025 (from start of year to end of year)
        start_date = '2025-01-01'
        end_date = '2025-12-31'
        dividends_2025 = dividends_history.loc[start_date:end_date]
        count = len(dividends_2025)
    else:
     count =0
    
    return count
    
#@st.cache_data()
def loadPortfolio():
   portfoliodf =pd.read_csv(get_portfolio_filename())
   return portfoliodf

def get_portfolio_filename():
    filename=f"portfolio_sample.csv"
    return filename
  
@st.cache_data()
def getPortfolioData(month=None, year=None):
    """
    Get portfolio data for a specific month and year.
    If month/year not provided, defaults to current month/year.
    
    Args:
        month (int, optional): Month number (1-12). Defaults to current month.
        year (int, optional): Year (e.g., 2025, 2026). Defaults to current year.
    
    Returns:
        pd.DataFrame: Portfolio data with columns: account_type, symbol, name, sector, qty, purchase_price
    """
    # Use current month/year if not provided
    if month is None or year is None:
        now = datetime.now()
        month = month or now.month
        year = year or now.year
    
    # Get portfolio data from the truth dataset
    portdf = get_portfolio_truth_by_month(month, year)
    
    # Select the required columns (same as before for backward compatibility)
    selected_columns = ['account_type', 'symbol', 'name', 'sector', 'qty', 'purchase_price']
    df_selected = portdf[selected_columns]
    #print(df_selected)
    return df_selected

def get_entry_in_portfolio(symbol):
    try:
        cols_to_extract = ['symbol', 'name','sector', 'qty', 'purchase_price']
        df = getPortfolioData()
        filtered_rows = df.loc[df['symbol'] == symbol]
        extracted_data = filtered_rows[cols_to_extract]
        return extracted_data
    except KeyError as e:
        print(f"Error: One of the specified columns was not found: {e}")
        return None



def get_list_of_tickers():
    portdf = loadPortfolio()
    # Extract the column data
    column_values = portdf['symbol']
        # Convert the column values to a list (optional, but makes joining clearer)
    values_list = column_values.tolist() 
        # Ensure all values are strings before joining (important for numbers, NaNs, etc.)
    string_values_list = [str(value) for value in values_list]
        # Form the comma-separated list
    comma_separated_list = ", ".join(string_values_list)
        
    return comma_separated_list
    
@st.cache_data()
def build_portfolio_display():
    getPortfolioData()
    results = get_list_of_tickers()
    
    # Initialize python_list_of_values to avoid unbound variable error
    python_list_of_values = []
    
    if isinstance(results, str) and not results.startswith("Error"):
        # Split the resulting string back into a list if needed for further Python operations
        python_list_of_values_unsorted = results.split(', ')
        python_list_of_values = sorted(python_list_of_values_unsorted)
        #print(python_list_of_values)
    
    portdf = pd.DataFrame(columns=['Tax Type','Ticker', 'Name','Sector', 'Quantity', 'Price', "Current value", "Cost Basis","Net Return","Dividend date","Dividend Amount","annual dividend amount","dividend yield"])
    
    for ticker in python_list_of_values:
        price = get_current_price(ticker)
        sector = get_sector(ticker)
        qty = get_qty(ticker)
        name=get_ticker_name(ticker)
        tax_type=get_tax_type(ticker)
        current_value = calculate_current_value(ticker)
        cost_basis = calculate_cost_basis(ticker)
        net_return = current_value - cost_basis
        divy_date, divy_amt, annual_divy_amount = get_current_dividend(ticker)
        
        #divy_yield = annual_divy_amount/get_purchase_price(ticker)
        divy_yield = annual_divy_amount/cost_basis
        
        portdf.loc[len(portdf)] = [tax_type,ticker,name,sector,qty,price,current_value,cost_basis,net_return, divy_date,divy_amt,annual_divy_amount, divy_yield]

    return portdf


def get_portfolio_dividend_total():
    portdf = build_portfolio_display()
    divy_total = portdf[['annual dividend amount']].sum()
    #print(divy_total)
    return  divy_total

def backup_file(current_file_name, backup_filename):   
    try:
        os.rename(current_file_name, backup_filename)
      #  print(f"File successfully renamed to: {backup_filename}")
    except FileNotFoundError:
        print(f"Error: The file '{current_file_name}' was not found.")
    except FileExistsError:
        print(f"Error: A file named '{backup_filename}' already exists.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        
def add_rows_to_portfolio(original_df,new_rows_df):
      df_merged = pd.concat([original_df, new_rows_df], ignore_index=True) 
      return df_merged 
  
#def update_portfolio(df):
    
     
    
      
