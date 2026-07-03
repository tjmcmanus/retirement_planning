# 🚀 Quick Start Guide - IBM Passport Advantage RPA Scraper

Get up and running in 5 minutes!

## Step 1: Install Dependencies (2 minutes)

```bash
# Install Python packages
pip install -r requirements_rpa.txt
```

## Step 2: Configure Credentials (1 minute)

```bash
# Copy the template
cp .env.rpa.template .env

# Edit .env and add your credentials
# IBM_W3ID_USERNAME=your_email@ibm.com
# IBM_W3ID_PASSWORD=your_password
```

## Step 3: Run Your First Scrape (2 minutes)

### Option A: Interactive Examples

```bash
python example_rpa_usage.py
```

Then select an example (1-10) to run.

### Option B: Direct Execution

Edit `ibm_passport_advantage_scraper.py` and customize the search criteria in the `main()` function:

```python
search_criteria = {
    'quote_number': '12345',  # Replace with your quote number
}
```

Then run:

```bash
python ibm_passport_advantage_scraper.py
```

## What Happens Next?

1. **Browser Opens**: Chrome will launch and navigate to IBM Passport Advantage
2. **Auto-Login**: Script enters your credentials and logs in
3. **Search**: Executes your search criteria
4. **Extract**: Collects all data from results (handles pagination automatically)
5. **Save**: Exports to CSV/Excel with timestamp
6. **Done**: Browser closes, data is ready!

## Output Files

Look for these files in your project directory:

- **Data**: `ibm_passport_advantage_data_YYYYMMDD_HHMMSS.csv`
- **Logs**: `ibm_scraper_YYYYMMDD_HHMMSS.log`
- **Screenshots** (if errors): `screenshot_*.png`

## Common Search Criteria

```python
# Single quote
search_criteria = {'quote_number': '12345'}

# Customer search
search_criteria = {'customer_name': 'Acme Corp'}

# Date range
search_criteria = {
    'date_from': '01/01/2024',
    'date_to': '12/31/2024'
}

# Multiple criteria
search_criteria = {
    'customer_name': 'Acme Corp',
    'date_from': '06/01/2024',
    'date_to': '06/30/2024'
}
```

## Troubleshooting

### "Login failed"
- Check credentials in `.env` file
- Verify IBM w3id account is active
- Try running in non-headless mode to see what's happening

### "Element not found"
- IBM website may have changed
- Check screenshots to see current page
- Increase timeout in script

### "ChromeDriver error"
- Update Chrome browser
- Clear cache: `rm -rf ~/.wdm`
- Reinstall: `pip install --upgrade webdriver-manager`

## Next Steps

- Read full documentation: `IBM_RPA_SCRAPER_README.md`
- Explore examples: `example_rpa_usage.py`
- Schedule automated runs (see README)
- Customize for your specific needs

## Need Help?

1. Check the logs: `ibm_scraper_*.log`
2. Review screenshots: `screenshot_*.png`
3. Read full README: `IBM_RPA_SCRAPER_README.md`
4. Test with simple search first

---

**Ready to automate? Let's go! 🎯**