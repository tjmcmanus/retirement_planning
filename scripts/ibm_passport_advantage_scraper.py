#!/usr/bin/env python3
"""
IBM Passport Advantage Quote Status RPA Scraper

This script automates data collection from IBM Passport Advantage DSW Price Book
Quote Status Search system using Selenium WebDriver.

Requirements:
    pip install selenium pandas python-dotenv webdriver-manager

Usage:
    python ibm_passport_advantage_scraper.py

Configuration:
    Create a .env file with:
    IBM_W3ID_USERNAME=your_username
    IBM_W3ID_PASSWORD=your_password
"""

import os
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'ibm_scraper_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class IBMPassportAdvantageScraper:
    """RPA bot for scraping IBM Passport Advantage quote status data."""
    
    def __init__(self, headless: bool = False):
        """
        Initialize the scraper.
        
        Args:
            headless: Run browser in headless mode (no GUI)
        """
        self.base_url = "https://w3-314.ibm.com/software/sales/passportadvantage/dswpricebook/quotestatus/statussearch.wss"
        self.username = os.getenv('IBM_W3ID_USERNAME')
        self.password = os.getenv('IBM_W3ID_PASSWORD')
        self.headless = headless
        self.driver = None
        self.wait = None
        
        if not self.username or not self.password:
            raise ValueError("IBM_W3ID_USERNAME and IBM_W3ID_PASSWORD must be set in .env file")
    
    def setup_driver(self):
        """Configure and initialize Chrome WebDriver."""
        logger.info("Setting up Chrome WebDriver...")
        
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        
        # Additional options for stability
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
        
        # Initialize driver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 20)
        
        logger.info("WebDriver setup complete")
    
    def login(self) -> bool:
        """
        Authenticate with IBM w3id credentials.
        
        Returns:
            True if login successful, False otherwise
        """
        try:
            logger.info("Navigating to IBM Passport Advantage...")
            self.driver.get(self.base_url)
            
            # Wait for login page to load
            time.sleep(3)
            
            # Check if we're on IBM SSO login page
            if "w3id" in self.driver.current_url.lower() or "login" in self.driver.current_url.lower():
                logger.info("IBM SSO login page detected")
                
                # Find and fill username field
                username_field = self.wait.until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                username_field.clear()
                username_field.send_keys(self.username)
                logger.info(f"Entered username: {self.username}")
                
                # Find and click continue/next button
                continue_button = self.driver.find_element(By.ID, "continue-button")
                continue_button.click()
                time.sleep(2)
                
                # Find and fill password field
                password_field = self.wait.until(
                    EC.presence_of_element_located((By.ID, "password"))
                )
                password_field.clear()
                password_field.send_keys(self.password)
                logger.info("Entered password")
                
                # Find and click sign in button
                signin_button = self.driver.find_element(By.ID, "signinbutton")
                signin_button.click()
                
                # Wait for redirect to main page
                time.sleep(5)
                
                logger.info("Login successful")
                return True
            else:
                logger.info("Already authenticated or no login required")
                return True
                
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            self.take_screenshot("login_error")
            return False
    
    def search_quotes(self, search_criteria: Dict[str, str]) -> bool:
        """
        Perform search with given criteria.
        
        Args:
            search_criteria: Dictionary with search parameters
                Examples:
                - {'quote_number': '12345'}
                - {'customer_name': 'Acme Corp'}
                - {'date_from': '01/01/2024', 'date_to': '12/31/2024'}
        
        Returns:
            True if search executed successfully
        """
        try:
            logger.info(f"Executing search with criteria: {search_criteria}")
            
            # Wait for search form to be available
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
            
            # Fill in search fields based on criteria
            for field_name, field_value in search_criteria.items():
                try:
                    # Try to find field by name, id, or other attributes
                    field = self.driver.find_element(By.NAME, field_name)
                    field.clear()
                    field.send_keys(field_value)
                    logger.info(f"Filled field '{field_name}' with '{field_value}'")
                except NoSuchElementException:
                    logger.warning(f"Field '{field_name}' not found")
            
            # Find and click search button
            search_button = self.driver.find_element(By.XPATH, "//input[@type='submit' or @value='Search']")
            search_button.click()
            
            # Wait for results to load
            time.sleep(3)
            logger.info("Search executed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            self.take_screenshot("search_error")
            return False
    
    def extract_table_data(self) -> List[Dict[str, str]]:
        """
        Extract data from results table.
        
        Returns:
            List of dictionaries containing row data
        """
        try:
            logger.info("Extracting table data...")
            
            # Wait for results table
            table = self.wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            
            # Extract headers
            headers = []
            header_row = table.find_element(By.TAG_NAME, "thead").find_element(By.TAG_NAME, "tr")
            for th in header_row.find_elements(By.TAG_NAME, "th"):
                headers.append(th.text.strip())
            
            logger.info(f"Found {len(headers)} columns: {headers}")
            
            # Extract data rows
            data = []
            tbody = table.find_element(By.TAG_NAME, "tbody")
            rows = tbody.find_elements(By.TAG_NAME, "tr")
            
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if cells:
                    row_data = {}
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            row_data[headers[i]] = cell.text.strip()
                    data.append(row_data)
            
            logger.info(f"Extracted {len(data)} rows of data")
            return data
            
        except Exception as e:
            logger.error(f"Data extraction failed: {str(e)}")
            self.take_screenshot("extraction_error")
            return []
    
    def handle_pagination(self) -> List[Dict[str, str]]:
        """
        Handle pagination and extract data from all pages.
        
        Returns:
            Combined data from all pages
        """
        all_data = []
        page_num = 1
        
        while True:
            logger.info(f"Processing page {page_num}...")
            
            # Extract data from current page
            page_data = self.extract_table_data()
            all_data.extend(page_data)
            
            # Check for next page button
            try:
                next_button = self.driver.find_element(
                    By.XPATH, 
                    "//a[contains(text(), 'Next') or contains(@class, 'next')]"
                )
                
                if next_button.is_enabled():
                    next_button.click()
                    time.sleep(2)
                    page_num += 1
                else:
                    break
            except NoSuchElementException:
                logger.info("No more pages to process")
                break
        
        logger.info(f"Total records extracted: {len(all_data)}")
        return all_data
    
    def save_to_csv(self, data: List[Dict[str, str]], filename: Optional[str] = None):
        """
        Save extracted data to CSV file.
        
        Args:
            data: List of dictionaries to save
            filename: Output filename (default: auto-generated with timestamp)
        """
        if not data:
            logger.warning("No data to save")
            return
        
        if filename is None:
            filename = f"ibm_passport_advantage_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        logger.info(f"Data saved to {filename}")
        logger.info(f"Columns: {list(df.columns)}")
        logger.info(f"Rows: {len(df)}")
    
    def save_to_excel(self, data: List[Dict[str, str]], filename: Optional[str] = None):
        """
        Save extracted data to Excel file.
        
        Args:
            data: List of dictionaries to save
            filename: Output filename (default: auto-generated with timestamp)
        """
        if not data:
            logger.warning("No data to save")
            return
        
        if filename is None:
            filename = f"ibm_passport_advantage_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        df = pd.DataFrame(data)
        df.to_excel(filename, index=False, engine='openpyxl')
        logger.info(f"Data saved to {filename}")
    
    def take_screenshot(self, name: str):
        """Take screenshot for debugging."""
        if self.driver:
            filename = f"screenshot_{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            self.driver.save_screenshot(filename)
            logger.info(f"Screenshot saved: {filename}")
    
    def close(self):
        """Clean up and close browser."""
        if self.driver:
            logger.info("Closing browser...")
            self.driver.quit()
            logger.info("Browser closed")
    
    def run(self, search_criteria: Dict[str, str], output_format: str = 'csv'):
        """
        Main execution method.
        
        Args:
            search_criteria: Search parameters
            output_format: 'csv' or 'excel'
        """
        try:
            # Setup
            self.setup_driver()
            
            # Login
            if not self.login():
                raise Exception("Login failed")
            
            # Search
            if not self.search_quotes(search_criteria):
                raise Exception("Search failed")
            
            # Extract data (with pagination)
            data = self.handle_pagination()
            
            # Save data
            if output_format.lower() == 'excel':
                self.save_to_excel(data)
            else:
                self.save_to_csv(data)
            
            logger.info("RPA process completed successfully")
            
        except Exception as e:
            logger.error(f"RPA process failed: {str(e)}")
            self.take_screenshot("final_error")
            raise
        finally:
            self.close()


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()
    
    # Initialize scraper
    scraper = IBMPassportAdvantageScraper(headless=False)
    
    # Example search criteria - customize as needed
    search_criteria = {
        # 'quote_number': '12345',
        # 'customer_name': 'Customer Name',
        # 'date_from': '01/01/2024',
        # 'date_to': '12/31/2024',
    }
    
    # Run the scraper
    scraper.run(search_criteria, output_format='csv')


if __name__ == "__main__":
    main()

# Made with Bob
