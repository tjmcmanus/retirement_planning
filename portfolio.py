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
    # For cash holdings, return 1.0 (no price lookup needed)
    if symbol == "MF:CASH":
        return 1.0
    ticker = yf.Ticker(symbol)
    todays_data = ticker.history(period='4d').tail(1)
    return todays_data['Close'].iloc[0]

#@st.cache_data()
def get_qty(symbol, month=None, year=None):
    df = getPortfolioData(month=month, year=year)
    quanity = df.loc[df['symbol'] == symbol, 'qty'].iloc[0]
    #print(f"quantity is: {quanity}")
    return quanity

#@st.cache_data()
def get_purchase_price(symbol, month=None, year=None):
    df = getPortfolioData(month=month, year=year)
    purchase_price = df.loc[df['symbol'] == symbol, 'purchase_price'].iloc[0]
    #print("Purchase price is: {purchase_price}")
    return purchase_price

#@st.cache_data()
def get_tax_type(symbol, month=None, year=None):
    df = getPortfolioData(month=month, year=year)
    tax_type = df.loc[df['symbol'] == symbol, 'account_type'].iloc[0]
    #print("tax_type price is: {tax_type}")
    return tax_type

#@st.cache_data()
def get_ticker_name(symbol, month=None, year=None):
    # For cash holdings, return "Cash"
    if symbol == "MF:CASH":
        return "Cash"
    #df = getPortfolioData(month=month, year=year)
    #ticker_name = df.loc[df['symbol'] == symbol, 'name'].iloc[0]
    ticker = yf.Ticker(symbol)
    return ticker.info['shortName']
    #return ticker_name


def get_sector(symbol, month=None, year=None):
    #print(f"get sector {symbol}")
    # For cash holdings, return "Cash"
    if symbol == "MF:CASH":
        return "Cash"
    
    df = getPortfolioData(month=month, year=year)
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

def calculate_current_value(symbol, month=None, year=None):
    current_value = get_qty(symbol, month=month, year=year) * get_current_price(symbol)
    #print(stock_value_port)
    return current_value

def calculate_cost_basis(symbol, month=None, year=None):
    cost_basis = get_qty(symbol, month=month, year=year) * get_purchase_price(symbol, month=month, year=year)
    #print(stock_value_port)
    return cost_basis

#@st.cache_data()
def get_current_dividend(symbol, month=None, year=None):
    # Cash holdings don't have dividends
    if symbol == "MF:CASH":
        return "na", 0.00, 0
    
    ticker = yf.Ticker(symbol)
    dividends_data = ticker.dividends
    # Find the latest dividend payment date (ex-date) and amount
    if not dividends_data.empty:
       latest_dividend_date = dividends_data.index[-1].strftime('%D')
       latest_dividend_amount = dividends_data.iloc[-1]* get_qty(symbol, month=month, year=year)
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
    # Cash holdings don't have dividends
    if symbol == "MF:CASH":
        return 0
    
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
    
  
@st.cache_data()
def getPortfolioData(month=None, year=None):
    """
    Get portfolio data for a specific month and year.
    If month/year not provided, defaults to current month/year.
    
    Args:
        month (int, optional): Month number (1-12). Defaults to current month.
        year (int, optional): Year (e.g., 2025, 2026). Defaults to current year.
    
    Returns:
        pd.DataFrame: Portfolio data with columns: account_name, account_type, symbol, name, sector, qty, purchase_price
    """
    # Use current month/year if not provided
    if month is None or year is None:
        now = datetime.now()
        month = month or now.month
        year = year or now.year
    
    # Get portfolio data from the truth dataset
    portdf = get_portfolio_truth_by_month(month, year)
    
    # Select the required columns, now including account_name for unique identification
    selected_columns = ['account_name', 'account_type', 'symbol', 'name', 'sector', 'qty', 'purchase_price']
    df_selected = portdf[selected_columns]
    
    # Remove duplicates based on account_name and symbol combination
    df_selected = df_selected.drop_duplicates(subset=['account_name', 'symbol'], keep='first')
    
    #print(df_selected)
    return df_selected

def get_entry_in_portfolio(symbol, month=None, year=None):
    try:
        cols_to_extract = ['symbol', 'name','sector', 'qty', 'purchase_price']
        df = getPortfolioData(month=month, year=year)
        filtered_rows = df.loc[df['symbol'] == symbol]
        extracted_data = filtered_rows[cols_to_extract]
        return extracted_data
    except KeyError as e:
        print(f"Error: One of the specified columns was not found: {e}")
        return None



def get_list_of_tickers(month=None, year=None):
    """
    Get list of unique account_name + symbol combinations for a given month/year.
    
    Returns:
        list: List of tuples (account_name, symbol)
    """
    portdf = getPortfolioData(month=month, year=year)
    # Return list of tuples with (account_name, symbol) for unique identification
    ticker_list = list(zip(portdf['account_name'], portdf['symbol']))
    return ticker_list
    
def format_quantity(qty):
    """
    Format quantity: whole number if decimal is 0, otherwise 2 decimal places.
    
    Args:
        qty: The quantity value to format
    
    Returns:
        str: Formatted quantity string
    """
    if qty == int(qty):
        return f"{int(qty)}"
    else:
        return f"{qty:.2f}"

@st.cache_data()
def build_portfolio_display(month=None, year=None):
    """
    Build portfolio display with unique account_name + symbol combinations.
    Each row represents a unique holding in a specific account.
    Includes a totals row at the bottom.
    """
    portfolio_data = getPortfolioData(month=month, year=year)
    
    portdf = pd.DataFrame(columns=['Account','Tax Type','Ticker', 'Name','Sector', 'Quantity', 'Price', "Current value", "Cost Basis","Net Return","Dividend date","Dividend Amount","annual dividend amount","dividend yield"])
    
    # Iterate through each unique account_name + symbol combination
    for _, row in portfolio_data.iterrows():
        account_name = row['account_name']
        symbol = row['symbol']
        tax_type = row['account_type']
        qty = row['qty']
        purchase_price = row['purchase_price']
        
        # Display ticker as "Cash" if it's MF:CASH
        display_ticker = "Cash" if symbol == "MF:CASH" else symbol
        
        # Get current price and calculate values
        price = get_current_price(symbol)
        sector = get_sector(symbol, month=month, year=year)
        name = get_ticker_name(symbol, month=month, year=year)
        
        # Calculate values using the specific qty and purchase_price from this row
        current_value = qty * price
        cost_basis = qty * purchase_price
        net_return = current_value - cost_basis
        
        # Get dividend information
        divy_date, divy_amt, annual_divy_amount = get_current_dividend(symbol, month=month, year=year)
        
        # Calculate dividend yield
        divy_yield = annual_divy_amount/cost_basis if cost_basis > 0 else 0
        
        # Format quantity: whole number if no decimal, otherwise 2 decimal places
        formatted_qty = format_quantity(qty)
        
        portdf.loc[len(portdf)] = [account_name, tax_type, display_ticker, name, sector, formatted_qty, price, current_value, cost_basis, net_return, divy_date, divy_amt, annual_divy_amount, divy_yield]

    # Add totals row at the bottom
    if not portdf.empty:
        total_current_value = portdf["Current value"].sum()
        total_cost_basis = portdf["Cost Basis"].sum()
        total_net_return = portdf["Net Return"].sum()
        total_annual_dividend = portdf["annual dividend amount"].sum()
        
        # Calculate overall dividend yield
        total_dividend_yield = total_annual_dividend / total_cost_basis if total_cost_basis > 0 else 0
        
        # Add the totals row
        totals_row = pd.DataFrame([{
            'Account': 'Portfolio Totals',
            'Tax Type': '',
            'Ticker': '',
            'Name': '',
            'Sector': '',
            'Quantity': '',
            'Price': '',
            'Current value': total_current_value,
            'Cost Basis': total_cost_basis,
            'Net Return': total_net_return,
            'Dividend date': '',
            'Dividend Amount': '',
            'annual dividend amount': total_annual_dividend,
            'dividend yield': total_dividend_yield
        }])
        
        portdf = pd.concat([portdf, totals_row], ignore_index=True)

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
    
     
    
      
