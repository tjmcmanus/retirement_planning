# IBM Passport Advantage RPA Scraper

Automated data collection tool for IBM Passport Advantage DSW Price Book Quote Status Search system.

## 🎯 Overview

This RPA (Robotic Process Automation) script automates the process of:
- Logging into IBM Passport Advantage with w3id credentials
- Searching for quote status information
- Extracting data from search results
- Handling pagination automatically
- Exporting data to CSV or Excel format

## 📋 Prerequisites

- Python 3.8 or higher
- Google Chrome browser installed
- IBM w3id credentials with access to Passport Advantage
- Authorization to automate access to IBM internal systems

## 🚀 Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements_rpa.txt
```

This will install:
- `selenium` - Browser automation
- `webdriver-manager` - Automatic ChromeDriver management
- `pandas` - Data manipulation and export
- `python-dotenv` - Environment variable management
- `openpyxl` - Excel file support

### 2. Configure Credentials

Copy the template and add your credentials:

```bash
cp .env.rpa.template .env
```

Edit `.env` and add your IBM w3id credentials:

```
IBM_W3ID_USERNAME=your_email@ibm.com
IBM_W3ID_PASSWORD=your_password
```

**⚠️ Security Note:** Never commit the `.env` file to version control. It's already in `.gitignore`.

## 📖 Usage

### Basic Usage

Run the scraper with default settings:

```bash
python ibm_passport_advantage_scraper.py
```

### Customizing Search Criteria

Edit the `main()` function in `ibm_passport_advantage_scraper.py`:

```python
# Example: Search by quote number
search_criteria = {
    'quote_number': '12345',
}

# Example: Search by customer name
search_criteria = {
    'customer_name': 'Acme Corporation',
}

# Example: Search by date range
search_criteria = {
    'date_from': '01/01/2024',
    'date_to': '12/31/2024',
}

# Example: Multiple criteria
search_criteria = {
    'customer_name': 'Acme Corp',
    'date_from': '01/01/2024',
    'date_to': '12/31/2024',
}
```

### Programmatic Usage

```python
from ibm_passport_advantage_scraper import IBMPassportAdvantageScraper
from dotenv import load_dotenv

# Load credentials
load_dotenv()

# Initialize scraper
scraper = IBMPassportAdvantageScraper(headless=False)

# Define search criteria
search_criteria = {
    'quote_number': '12345',
}

# Run scraper
scraper.run(search_criteria, output_format='csv')
```

## 🎛️ Configuration Options

### Headless Mode

Run without opening a visible browser window:

```python
scraper = IBMPassportAdvantageScraper(headless=True)
```

### Output Formats

Choose between CSV and Excel:

```python
# CSV output (default)
scraper.run(search_criteria, output_format='csv')

# Excel output
scraper.run(search_criteria, output_format='excel')
```

## 📊 Output

### File Naming

Output files are automatically named with timestamps:
- CSV: `ibm_passport_advantage_data_YYYYMMDD_HHMMSS.csv`
- Excel: `ibm_passport_advantage_data_YYYYMMDD_HHMMSS.xlsx`

### Log Files

Detailed logs are saved to:
- `ibm_scraper_YYYYMMDD_HHMMSS.log`

### Screenshots

Error screenshots are saved automatically when issues occur:
- `screenshot_<error_type>_YYYYMMDD_HHMMSS.png`

## 🔧 Advanced Features

### Pagination Handling

The scraper automatically:
- Detects pagination controls
- Navigates through all pages
- Combines data from multiple pages
- Logs progress for each page

### Error Handling

Built-in error handling includes:
- Automatic screenshot capture on errors
- Detailed logging of all operations
- Graceful failure with cleanup
- Retry logic for transient failures

### Data Extraction

The scraper intelligently:
- Identifies table headers automatically
- Extracts all columns from results
- Handles missing or empty cells
- Preserves data types where possible

## 🐛 Troubleshooting

### Login Issues

**Problem:** Login fails or times out

**Solutions:**
1. Verify credentials in `.env` file
2. Check if IBM SSO requires additional authentication (2FA, certificate)
3. Try running in non-headless mode to see what's happening
4. Check logs for specific error messages

### Element Not Found Errors

**Problem:** Script can't find page elements

**Solutions:**
1. IBM may have updated their website structure
2. Check screenshots to see current page state
3. Update element selectors in the script
4. Increase timeout values if page loads slowly

### ChromeDriver Issues

**Problem:** ChromeDriver version mismatch

**Solutions:**
1. Update Chrome browser to latest version
2. Clear webdriver-manager cache: `rm -rf ~/.wdm`
3. Reinstall webdriver-manager: `pip install --upgrade webdriver-manager`

### Data Extraction Issues

**Problem:** No data extracted or incomplete data

**Solutions:**
1. Verify search criteria returns results
2. Check if table structure has changed
3. Review screenshots to see actual page content
4. Update table parsing logic if needed

## 📝 Field Mapping

The scraper will automatically detect and extract all columns from the results table. Common fields include:

- Quote Number
- Customer Name
- Status
- Date Created
- Date Modified
- Product Information
- Pricing Details
- Sales Representative

*Note: Actual fields depend on the search results and may vary.*

## 🔒 Security Best Practices

1. **Credentials:**
   - Store credentials in `.env` file only
   - Never hardcode credentials in scripts
   - Use environment variables in production
   - Rotate passwords regularly

2. **Data Handling:**
   - Ensure compliance with IBM data policies
   - Encrypt sensitive data at rest
   - Limit access to output files
   - Delete old data files regularly

3. **Access Control:**
   - Only use with authorized IBM accounts
   - Log all scraping activities
   - Monitor for unusual patterns
   - Report security concerns to IBM security team

## 📅 Scheduling

### Using Cron (Linux/Mac)

Run daily at 2 AM:

```bash
0 2 * * * cd /path/to/project && /usr/bin/python3 ibm_passport_advantage_scraper.py
```

### Using Task Scheduler (Windows)

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (daily, weekly, etc.)
4. Action: Start a program
5. Program: `python`
6. Arguments: `ibm_passport_advantage_scraper.py`
7. Start in: `C:\path\to\project`

### Using Python Schedule

```python
import schedule
import time

def job():
    scraper = IBMPassportAdvantageScraper()
    scraper.run(search_criteria)

# Run every day at 2 AM
schedule.every().day.at("02:00").do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## 🔄 Maintenance

### Regular Updates

1. **Dependencies:** Update monthly
   ```bash
   pip install --upgrade -r requirements_rpa.txt
   ```

2. **Chrome Browser:** Keep updated to latest version

3. **Script Updates:** Check for IBM website changes

### Monitoring

Monitor these metrics:
- Success/failure rate
- Execution time
- Data volume extracted
- Error patterns

## 📞 Support

### Common Issues

Check the troubleshooting section above first.

### IBM Support

For IBM Passport Advantage access issues:
- Contact IBM IT Support
- Verify account permissions
- Check system status page

### Script Issues

For script bugs or enhancements:
1. Check logs for error details
2. Review screenshots
3. Test with minimal search criteria
4. Document steps to reproduce

## 📄 License

This script is for internal IBM use only. Ensure compliance with:
- IBM Code of Conduct
- IBM Data Handling Policies
- IBM Security Guidelines
- Passport Advantage Terms of Use

## ⚠️ Disclaimer

This tool is provided as-is for authorized IBM users only. Users are responsible for:
- Ensuring proper authorization
- Complying with IBM policies
- Protecting sensitive data
- Monitoring script behavior
- Reporting issues promptly

**Use responsibly and in accordance with IBM guidelines.**

## 🎓 Learning Resources

### Selenium Documentation
- [Selenium Python Docs](https://selenium-python.readthedocs.io/)
- [WebDriver API](https://www.selenium.dev/documentation/webdriver/)

### Web Scraping Best Practices
- Respect robots.txt
- Implement rate limiting
- Handle errors gracefully
- Monitor resource usage

### Python Automation
- [Schedule Library](https://schedule.readthedocs.io/)
- [Logging Best Practices](https://docs.python.org/3/howto/logging.html)
- [Environment Variables](https://pypi.org/project/python-dotenv/)

## 🔮 Future Enhancements

Potential improvements:
- [ ] Multi-threaded execution for multiple searches
- [ ] Database storage option (SQLite, PostgreSQL)
- [ ] Email notifications on completion/errors
- [ ] Web dashboard for monitoring
- [ ] API endpoint for remote execution
- [ ] Advanced filtering and data transformation
- [ ] Integration with IBM Watson for data analysis
- [ ] Automated report generation
- [ ] Real-time progress tracking
- [ ] Custom alert rules

---

**Version:** 1.0.0  
**Last Updated:** 2026-06-23  
**Author:** Bob (AI Assistant)