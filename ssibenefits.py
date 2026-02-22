import pandas as pd
import streamlit as st
import numpy as np
import logging
import os
from load_data import get_annual_ssi_data, load_ssi_data

# Configure logging
log_level = logging.getLevelName(os.getenv('LOG_LEVEL', 'WARNING'))
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)



def get_age(year, name):
    """
    Get the claiming age for a person in a specific year.
    
    Args:
        year: The year to query
        name: The person's name
        
    Returns:
        The claiming age for the person in that year
    """
    logger.debug(f"get_age called with year={year}, name={name}")
    
    try:
        datadf = get_annual_ssi_data(year)
        # Filter by year and person in one operation
        person_data = datadf[(datadf['year'] == year) & (datadf['person'] == name)]
        
        if person_data.empty:
            logger.warning(f"No data found for person={name} in year={year}")
            raise ValueError(f"No data found for person '{name}' in year {year}")
        
        age = person_data['claiming_age'].iloc[0]
        logger.debug(f"Retrieved age={age} for person={name} in year={year}")
        return age
        
    except Exception as e:
        logger.error(f"Error in get_age for year={year}, name={name}: {str(e)}")
        raise

def get_year(age, name):
    """
    Get the year when a person claims benefits at a specific age.
    
    Args:
        age: The claiming age
        name: The person's name
        
    Returns:
        The year when the person claims at that age
    """
    logger.debug(f"get_year called with age={age}, name={name}")
    
    try:
        datadf = load_ssi_data()
        # Filter by age and person in one operation
        person_data = datadf[(datadf['claiming_age'] == age) & (datadf['person'] == name)]
        
        if person_data.empty:
            logger.warning(f"No data found for person={name} at age={age}")
            raise ValueError(f"No data found for person '{name}' at age {age}")
        
        year = person_data['year'].iloc[0]
        logger.debug(f"Retrieved year={year} for person={name} at age={age}")
        return year
        
    except Exception as e:
        logger.error(f"Error in get_year for age={age}, name={name}: {str(e)}")
        raise


def get_monthly_benefit(year, name):
    """
    Get the monthly benefit amount for a person in a specific year.
    
    Args:
        year: The year to query
        name: The person's name
        
    Returns:
        The monthly benefit amount for the person in that year
    """
    logger.debug(f"get_monthly_benefit called with year={year}, name={name}")
    
    try:
        datadf = get_annual_ssi_data(year)
        # Filter by year and person in one operation
        person_data = datadf[(datadf['year'] == year) & (datadf['person'] == name)]
        
        if person_data.empty:
            logger.warning(f"No benefit data found for person={name} in year={year}")
            raise ValueError(f"No benefit data found for person '{name}' in year {year}")
        
        monthly_person_benefit = person_data['monthly_benefit'].iloc[0]
        logger.debug(f"Retrieved monthly_benefit=${monthly_person_benefit:,.2f} for person={name} in year={year}")
        return monthly_person_benefit
        
    except Exception as e:
        logger.error(f"Error in get_monthly_benefit for year={year}, name={name}: {str(e)}")
        raise

def get_claiming_age():
    """
    Get the claiming age from Streamlit session state.
    
    Returns:
        The claiming age as an integer
    """
    logger.debug("get_claiming_age called")
    
    try:
        if "SSI_AGE" not in st.session_state:
            logger.warning("SSI_AGE not found in session state")
            raise KeyError("SSI_AGE not found in session state")
        
        ss_age = st.session_state["SSI_AGE"]
        age = int(ss_age)
        logger.debug(f"Retrieved claiming age={age} from session state")
        return age
        
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Error in get_claiming_age: {str(e)}")
        raise