#!/usr/bin/env python3
"""
Example usage scenarios for IBM Passport Advantage RPA Scraper

This file demonstrates various ways to use the scraper for different use cases.
"""

from ibm_passport_advantage_scraper import IBMPassportAdvantageScraper
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_1_single_quote():
    """Example 1: Search for a specific quote number."""
    logger.info("Example 1: Searching for specific quote")
    
    scraper = IBMPassportAdvantageScraper(headless=False)
    
    search_criteria = {
        'quote_number': '12345',
    }
    
    scraper.run(search_criteria, output_format='csv')


def example_2_customer_search():
    """Example 2: Search by customer name."""
    logger.info("Example 2: Searching by customer name")
    
    scraper = IBMPassportAdvantageScraper(headless=False)
    
    search_criteria = {
        'customer_name': 'Acme Corporation',
    }
    
    scraper.run(search_criteria, output_format='excel')


def example_3_date_range():
    """Example 3: Search by date range."""
    logger.info("Example 3: Searching by date range")
    
    scraper = IBMPassportAdvantageScraper(headless=False)
    
    search_criteria = {
        'date_from': '01/01/2024',
        'date_to': '12/31/2024',
    }
    
    scraper.run(search_criteria, output_format='csv')


def example_4_multiple_criteria():
    """Example 4: Search with multiple criteria."""
    logger.info("Example 4: Searching with multiple criteria")
    
    scraper = IBMPassportAdvantageScraper(headless=False)
    
    search_criteria = {
        'customer_name': 'Acme Corp',
        'date_from': '06/01/2024',
        'date_to': '06/30/2024',
        'status': 'Active',
    }
    
    scraper.run(search_criteria, output_format='excel')


def example_5_headless_mode():
    """Example 5: Run in headless mode (no browser window)."""
    logger.info("Example 5: Running in headless mode")
    
    scraper = IBMPassportAdvantageScraper(headless=True)
    
    search_criteria = {
        'quote_number': '12345',
    }
    
    scraper.run(search_criteria, output_format='csv')


def example_6_manual_control():
    """Example 6: Manual control with step-by-step execution."""
    logger.info("Example 6: Manual step-by-step execution")
    
    scraper = IBMPassportAdvantageScraper(headless=False)
    
    try:
        # Step 1: Setup
        scraper.setup_driver()
        logger.info("✓ Driver setup complete")
        
        # Step 2: Login
        if scraper.login():
            logger.info("✓ Login successful")
        else:
            logger.error("✗ Login failed")
            return
        
        # Step 3: Search
        search_criteria = {'quote_number': '12345'}
        if scraper.search_quotes(search_criteria):
            logger.info("✓ Search executed")
        else:
            logger.error("✗ Search failed")
            return
        
        # Step 4: Extract data
        data = scraper.handle_pagination()
        logger.info(f"✓ Extracted {len(data)} records")
        
        # Step 5: Save data
        scraper.save_to_csv(data)
        logger.info("✓ Data saved")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        scraper.close()


def example_7_batch_processing():
    """Example 7: Process multiple quote numbers in batch."""
    logger.info("Example 7: Batch processing multiple quotes")
    
    quote_numbers = ['12345', '12346', '12347', '12348', '12349']
    
    for quote_num in quote_numbers:
        logger.info(f"Processing quote: {quote_num}")
        
        scraper = IBMPassportAdvantageScraper(headless=True)
        
        search_criteria = {
            'quote_number': quote_num,
        }
        
        try:
            scraper.run(search_criteria, output_format='csv')
            logger.info(f"✓ Quote {quote_num} processed successfully")
        except Exception as e:
            logger.error(f"✗ Quote {quote_num} failed: {str(e)}")


def example_8_scheduled_daily_export():
    """Example 8: Daily export of all quotes from yesterday."""
    from datetime import datetime, timedelta
    
    logger.info("Example 8: Daily export")
    
    # Calculate yesterday's date
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime('%m/%d/%Y')
    
    scraper = IBMPassportAdvantageScraper(headless=True)
    
    search_criteria = {
        'date_from': date_str,
        'date_to': date_str,
    }
    
    scraper.run(search_criteria, output_format='excel')


def example_9_error_handling():
    """Example 9: Robust error handling and retry logic."""
    logger.info("Example 9: Error handling with retries")
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            scraper = IBMPassportAdvantageScraper(headless=False)
            
            search_criteria = {
                'quote_number': '12345',
            }
            
            scraper.run(search_criteria, output_format='csv')
            logger.info("✓ Success!")
            break
            
        except Exception as e:
            retry_count += 1
            logger.warning(f"Attempt {retry_count} failed: {str(e)}")
            
            if retry_count >= max_retries:
                logger.error("✗ Max retries reached. Giving up.")
                raise
            else:
                logger.info(f"Retrying in 5 seconds...")
                import time
                time.sleep(5)


def example_10_custom_output_location():
    """Example 10: Save output to custom location."""
    import os
    from datetime import datetime
    
    logger.info("Example 10: Custom output location")
    
    # Create output directory if it doesn't exist
    output_dir = './rpa_output'
    os.makedirs(output_dir, exist_ok=True)
    
    scraper = IBMPassportAdvantageScraper(headless=False)
    
    try:
        scraper.setup_driver()
        scraper.login()
        
        search_criteria = {'quote_number': '12345'}
        scraper.search_quotes(search_criteria)
        
        data = scraper.handle_pagination()
        
        # Custom filename with path
        custom_filename = os.path.join(
            output_dir,
            f"quotes_{datetime.now().strftime('%Y%m%d')}.csv"
        )
        
        scraper.save_to_csv(data, filename=custom_filename)
        logger.info(f"✓ Data saved to {custom_filename}")
        
    finally:
        scraper.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("IBM Passport Advantage RPA Scraper - Usage Examples")
    print("="*60 + "\n")
    
    print("Available examples:")
    print("1. Single quote search")
    print("2. Customer name search")
    print("3. Date range search")
    print("4. Multiple criteria search")
    print("5. Headless mode")
    print("6. Manual step-by-step control")
    print("7. Batch processing")
    print("8. Scheduled daily export")
    print("9. Error handling with retries")
    print("10. Custom output location")
    
    choice = input("\nEnter example number to run (1-10): ")
    
    examples = {
        '1': example_1_single_quote,
        '2': example_2_customer_search,
        '3': example_3_date_range,
        '4': example_4_multiple_criteria,
        '5': example_5_headless_mode,
        '6': example_6_manual_control,
        '7': example_7_batch_processing,
        '8': example_8_scheduled_daily_export,
        '9': example_9_error_handling,
        '10': example_10_custom_output_location,
    }
    
    if choice in examples:
        print(f"\nRunning Example {choice}...\n")
        examples[choice]()
    else:
        print("Invalid choice. Please run again and select 1-10.")

# Made with Bob
