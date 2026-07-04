# Standard Deduction CSV Schema Change

## Breaking Change Notice

**Version:** 2024-03-02  
**Impact:** Breaking change requiring manual intervention

## Overview

The `standard.csv` file schema has been updated from 2 columns to 3 columns to support multiple filing statuses.

## Schema Changes

### Old Format (2 columns)
```csv
year,deduction
2023,27700
2024,29200
```

### New Format (3 columns)
```csv
year,filing_status,deduction
2023,married_filing_jointly,27700
2023,single,13850
2024,married_filing_jointly,29200
2024,single,14600
```

## Why This Change Was Made

The old format only supported a single deduction value per year, which was implicitly assumed to be for married filing jointly status. The new format explicitly supports both:
- `married_filing_jointly` - Standard deduction for married couples filing jointly
- `single` - Standard deduction for single filers

This change enables proper tax calculations for different filing statuses.

## Migration Required

**If you have an existing installation**, you MUST migrate your `standard.csv` file before the application will work.

### Automatic Migration

Run the provided migration script:

```bash
python migrate_standard_csv.py
```

The script will:
1. Detect if your file is in the old format
2. Create a timestamped backup (e.g., `standard.csv.backup.20240302_143022`)
3. Convert to the new format
4. Validate the conversion

### Manual Migration

If you prefer to migrate manually:

1. **Backup your current file:**
   ```bash
   cp standard.csv standard.csv.backup
   ```

2. **Add the `filing_status` column** and duplicate each row:
   - Original row becomes `married_filing_jointly` with the same deduction
   - Add a `single` row with approximately 50% of the married value

3. **Update the header:**
   ```csv
   year,filing_status,deduction
   ```

## Error Messages

If you try to run the application with an old format file, you'll see:

```
ValueError: standard.csv schema error: Missing columns ['filing_status']. 
Expected format: year,filing_status,deduction. 
Please run migrate_standard_csv.py to update the file format.
```

## Schema Validation

The application now includes automatic schema validation in [`load_data.py::get_std_deduction()`](load_data.py:45). This function:
- Checks for required columns: `year`, `filing_status`, `deduction`
- Provides clear error messages if the schema is incorrect
- Prevents silent failures or incorrect calculations

## Backward Compatibility

**There is no backward compatibility** for this change. The old 2-column format is no longer supported. All installations must migrate to the new 3-column format.

## Testing

After migration, verify the application works correctly:

```bash
# Run the application
streamlit run planning_app.py

# Or run tests if available
pytest test_*.py
```

## Questions or Issues

If you encounter problems during migration:
1. Check that your backup file was created successfully
2. Verify the new file has 3 columns: `year,filing_status,deduction`
3. Ensure each year has entries for both `married_filing_jointly` and `single`
4. Check the application logs for detailed error messages

## Related Files

- [`standard.csv`](standard.csv:1) - The data file (new format)
- [`load_data.py`](load_data.py:45) - Schema validation code
- [`migrate_standard_csv.py`](migrate_standard_csv.py:1) - Migration script