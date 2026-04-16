"""
pages/9_admin_tax_data.py — 🔧 Tax Data Administration

Administrative interface for updating IRS tax data lookup tables.
Provides a user-friendly interface to update CSV files with annual IRS adjustments.
"""
from __future__ import annotations
import pandas as pd
import streamlit as st
from datetime import datetime
import os
import shutil
from typing import Dict, List, Tuple, Any

from components.navbar import navbar
from components.shared import init_page

# Initialize page
init_page("🔧 Tax Data Admin", "🔧")
navbar("🔧 Tax Data Admin")

# Get current year for filtering
CURRENT_YEAR = datetime.now().year

st.header("🔧 Tax Data Administration")
st.markdown("""
Update IRS tax data lookup tables for annual cost-of-living adjustments.
All changes are saved immediately to CSV files.

⚠️ **Important**: Always verify data against official IRS publications before updating.
""")
st.markdown("---")

# File mapping
TAX_DATA_FILES = {
    "Standard Deduction": "standard.csv",
    "Income Tax Brackets": "income_rates.csv",
    "Capital Gains Brackets": "cap_gains.csv",
    "IRA & 401(k) Limits": "ira_limits.csv",
    "IRMAA (Medicare Surcharges)": "irmaa.csv",
    "RMD Life Expectancy": "rmd.csv",
    "Social Security Income": "ssincome.csv",
    "ATM (Alternative Minimum Tax)": "atm.csv",
}

# Define expected schemas for validation
TAX_DATA_SCHEMAS = {
    "standard.csv": {
        "required_columns": ["year", "filing_status", "deduction"],
        "numeric_columns": ["year", "deduction"],
        "filing_status_values": ["married_filing_jointly", "single"],
    },
    "income_rates.csv": {
        "required_columns": ["year", "filing_status", "lower", "upper", "rate"],
        "numeric_columns": ["year", "lower", "upper", "rate"],
        "filing_status_values": ["married_filing_jointly", "single"],
    },
    "cap_gains.csv": {
        "required_columns": ["year", "filing_status", "lower", "upper", "rate"],
        "numeric_columns": ["year", "lower", "upper", "rate"],
        "filing_status_values": ["married_filing_jointly", "single"],
    },
    "ira_limits.csv": {
        "required_columns": ["year"],
        "numeric_columns": ["year"],
        "filing_status_values": None,
    },
    "irmaa.csv": {
        "required_columns": ["year", "filing_status"],
        "numeric_columns": ["year"],
        "filing_status_values": ["married_filing_jointly", "single"],
    },
    "rmd.csv": {
        "required_columns": ["age"],
        "numeric_columns": ["age"],
        "filing_status_values": None,
    },
    "ssincome.csv": {
        "required_columns": ["year"],
        "numeric_columns": ["year"],
        "filing_status_values": None,
    },
    "atm.csv": {
        "required_columns": ["year", "filing_status"],
        "numeric_columns": ["year"],
        "filing_status_values": ["married_filing_jointly", "single"],
    },
}

def validate_uploaded_data(df: pd.DataFrame, filename: str) -> Tuple[bool, List[str]]:
    """
    Validate uploaded CSV data against expected schema.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Get schema for this file
    schema = TAX_DATA_SCHEMAS.get(filename)
    if not schema:
        # No schema defined - allow upload but warn
        return True, ["⚠️ No validation schema defined for this file"]
    
    # 1. Validate required columns exist
    required_cols = schema.get("required_columns", [])
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        errors.append(f"❌ Missing required columns: {', '.join(missing_cols)}")
    
    # 2. Validate numeric columns have correct data types
    numeric_cols = schema.get("numeric_columns", [])
    for col in numeric_cols:
        if col in df.columns:
            try:
                # Try to convert to numeric
                pd.to_numeric(df[col], errors='raise')
            except (ValueError, TypeError):
                errors.append(f"❌ Column '{col}' contains non-numeric values")
    
    # 3. Validate filing_status values if applicable
    if "filing_status" in df.columns:
        allowed_values = schema.get("filing_status_values")
        if allowed_values:
            invalid_mask = ~df["filing_status"].isin(allowed_values)
            invalid_statuses = df.loc[invalid_mask, "filing_status"].unique()
            if len(invalid_statuses) > 0:
                errors.append(
                    f"❌ Invalid filing_status values: {', '.join(map(str, invalid_statuses))}. "
                    f"Allowed: {', '.join(allowed_values)}"
                )
    
    # 4. Validate year ranges are reasonable (2020-2100)
    if "year" in df.columns:
        try:
            years_series = pd.to_numeric(df["year"], errors='coerce')
            # Type guard: ensure we have a Series
            if isinstance(years_series, pd.Series):
                year_mask = (years_series < 2020) | (years_series > 2100)
                filtered_years = years_series[year_mask]
                if isinstance(filtered_years, pd.Series):
                    invalid_years = filtered_years.dropna()
                    if len(invalid_years) > 0:
                        unique_invalid = invalid_years.astype(int).unique()
                        errors.append(
                            f"❌ Year values outside reasonable range (2020-2100): "
                            f"{', '.join(map(str, unique_invalid))}"
                        )
        except Exception:
            errors.append("❌ Unable to validate year column")
    
    is_valid = len(errors) == 0
    return is_valid, errors

def create_backup(filename: str) -> bool:
    """
    Create a backup of the file before overwriting.
    
    Returns:
        True if backup was successful, False otherwise
    """
    try:
        if os.path.exists(filename):
            backup_dir = ".backups"
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"{backup_dir}/{filename.replace('.csv', '')}_{timestamp}.csv"
            shutil.copy2(filename, backup_filename)
            return True
        return False
    except Exception:
        return False

# Create tabs for each data type
tabs = st.tabs(list(TAX_DATA_FILES.keys()))

for tab, (data_name, filename) in zip(tabs, TAX_DATA_FILES.items()):
    with tab:
        st.subheader(f"📊 {data_name}")
        
        # Check if file exists
        if not os.path.exists(filename):
            st.error(f"File not found: {filename}")
            continue
        
        try:
            # Load current data
            df = pd.read_csv(filename)
            
            # Filter for relevant years if 'year' column exists
            if 'year' in df.columns:
                # Show last year, current year, and next year
                relevant_years = [CURRENT_YEAR - 1, CURRENT_YEAR, CURRENT_YEAR + 1]
                df_display = df[df['year'].isin(relevant_years)].copy()
                
                if df_display.empty:
                    st.warning(f"No data found for years {CURRENT_YEAR-1}, {CURRENT_YEAR}, or {CURRENT_YEAR+1}")
                    df_display = df.copy()
            else:
                df_display = df.copy()
            
            # Display current data (filtered to relevant years)
            st.markdown(f"### Current Data ({CURRENT_YEAR-1}, {CURRENT_YEAR}, {CURRENT_YEAR+1})")
            # Calculate dynamic height: header (38px) + rows (35px each) + padding (10px)
            dynamic_height = min(38 + (len(df_display) * 35) + 10, 600)
            st.dataframe(df_display, use_container_width=True, height=dynamic_height)
            
            # Statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Rows Shown", len(df_display))
            with col2:
                st.metric("Total Rows", len(df))
            with col3:
                if 'year' in df.columns:
                    years = df['year'].unique()
                    st.metric("All Years", f"{min(years)}-{max(years)}")
                else:
                    st.metric("Columns", len(df.columns))
            
            st.markdown("---")
            
            # Edit interface
            st.markdown("### Add/Update Data")
            
            with st.expander("➕ Add New Row", expanded=False):
                st.markdown("Enter values for each column:")
                
                # Create input fields for each column
                new_row = {}
                cols = st.columns(min(len(df.columns), 4))
                for idx, col_name in enumerate(df.columns):
                    with cols[idx % 4]:
                        # Determine input type based on column data type
                        if df[col_name].dtype in ['int64', 'float64']:
                            new_row[col_name] = st.number_input(
                                col_name,
                                value=0.0 if df[col_name].dtype == 'float64' else 0,
                                key=f"{filename}_{col_name}_new"
                            )
                        else:
                            new_row[col_name] = st.text_input(
                                col_name,
                                value="",
                                key=f"{filename}_{col_name}_new"
                            )
                
                if st.button("Add Row", key=f"{filename}_add"):
                    # Add new row to dataframe
                    new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    new_df.to_csv(filename, index=False)
                    st.success(f"✅ Row added to {filename}")
                    st.rerun()
            
            with st.expander("📝 Edit Existing Data", expanded=False):
                st.markdown(f"**Editing {CURRENT_YEAR} data only.** Use the data editor below to modify values:")
                
                # Filter to current year only for editing
                if 'year' in df.columns:
                    df_edit = df[df['year'] == CURRENT_YEAR].copy()
                    if df_edit.empty:
                        st.warning(f"No data found for year {CURRENT_YEAR}. Add new rows first.")
                    else:
                        # Editable dataframe (current year only)
                        edited_df = st.data_editor(
                            df_edit,
                            use_container_width=True,
                            num_rows="dynamic",
                            key=f"{filename}_editor"
                        )
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("💾 Save Changes", key=f"{filename}_save", type="primary"):
                                # Merge edited current year data back into full dataframe
                                df_updated = df[df['year'] != CURRENT_YEAR].copy()
                                df_updated = pd.concat([df_updated, edited_df], ignore_index=True)
                                # Sort by year if column exists
                                if 'year' in df_updated.columns:
                                    df_updated = df_updated.sort_values(by='year')  # type: ignore
                                df_updated.to_csv(filename, index=False)
                                st.success(f"✅ Changes saved to {filename}")
                                st.rerun()
                        
                        with col2:
                            if st.button("🔄 Reset", key=f"{filename}_reset"):
                                st.rerun()
                else:
                    # No year column - edit all data
                    edited_df = st.data_editor(
                        df,
                        use_container_width=True,
                        num_rows="dynamic",
                        key=f"{filename}_editor"
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 Save Changes", key=f"{filename}_save", type="primary"):
                            edited_df.to_csv(filename, index=False)
                            st.success(f"✅ Changes saved to {filename}")
                            st.rerun()
                    
                    with col2:
                        if st.button("🔄 Reset", key=f"{filename}_reset"):
                            st.rerun()
            
            # Download current data
            st.markdown("---")
            st.markdown("### 📥 Download/Backup")
            csv_data = df.to_csv(index=False)
            st.download_button(
                label=f"Download {data_name} CSV",
                data=csv_data,
                file_name=f"{filename.replace('.csv', '')}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                key=f"{filename}_download"
            )
            
            # Upload replacement data
            with st.expander("📤 Upload Replacement Data", expanded=False):
                st.warning("⚠️ This will replace ALL existing data in this file!")
                uploaded_file = st.file_uploader(
                    f"Upload CSV file for {data_name}",
                    type=['csv'],
                    key=f"{filename}_upload"
                )
                
                if uploaded_file is not None:
                    try:
                        new_df = pd.read_csv(uploaded_file)
                        st.markdown("**Preview of uploaded data:**")
                        st.dataframe(new_df.head(10), use_container_width=True)
                        
                        # Validate uploaded data
                        is_valid, validation_errors = validate_uploaded_data(new_df, filename)
                        
                        if not is_valid:
                            st.error("**Validation Failed:**")
                            for error in validation_errors:
                                st.error(error)
                            st.info("Please fix the errors in your CSV file and try uploading again.")
                        else:
                            # Show validation success
                            if validation_errors:  # Warnings but still valid
                                for warning in validation_errors:
                                    st.warning(warning)
                            else:
                                st.success("✅ Validation passed - data looks good!")
                            
                            if st.button("✅ Confirm Upload", key=f"{filename}_confirm_upload", type="primary"):
                                # Create backup before overwriting
                                backup_created = create_backup(filename)
                                if backup_created:
                                    st.info(f"📦 Backup created in .backups/ directory")
                                
                                # Save the new data
                                new_df.to_csv(filename, index=False)
                                st.success(f"✅ {filename} has been replaced with uploaded data")
                                st.rerun()
                    except Exception as e:
                        st.error(f"Error reading uploaded file: {e}")
        
        except Exception as e:
            st.error(f"Error loading {filename}: {e}")

# Documentation section
st.markdown("---")
st.markdown("## 📚 Documentation & Resources")

with st.expander("🔗 Official IRS Resources", expanded=False):
    st.markdown("""
    ### Annual IRS Publications (typically released October-November)
    
    **Tax Brackets & Standard Deduction:**
    - [IRS Revenue Procedure - Cost-of-Living Adjustments](https://www.irs.gov/newsroom/irs-provides-tax-inflation-adjustments-for-tax-year)
    - Published annually in October/November
    
    **IRA & 401(k) Contribution Limits:**
    - [IRS Retirement Topics - Contribution Limits](https://www.irs.gov/retirement-plans/plan-participant-employee/retirement-topics-contributions)
    - [IRS Publication 590-A](https://www.irs.gov/publications/p590a) - IRA Contributions
    
    **Capital Gains:**
    - [IRS Topic No. 409 - Capital Gains and Losses](https://www.irs.gov/taxtopics/tc409)
    
    **IRMAA (Medicare Surcharges):**
    - [Medicare.gov - Part B Costs](https://www.medicare.gov/your-medicare-costs/part-b-costs)
    - [Medicare.gov - Part D Costs](https://www.medicare.gov/drug-coverage-part-d/costs-for-medicare-drug-coverage)
    
    **RMD (Required Minimum Distributions):**
    - [IRS Publication 590-B](https://www.irs.gov/publications/p590b) - Distributions from IRAs
    - Uniform Lifetime Table (Appendix B)
    
    **Social Security:**
    - [SSA - Cost-of-Living Adjustments](https://www.ssa.gov/oact/cola/colaseries.html)
    """)

with st.expander("📋 Update Checklist", expanded=False):
    st.markdown("""
    ### Annual Update Process
    
    **Timing:** October-December (after IRS announces adjustments)
    
    **Steps:**
    1. ✅ Wait for official IRS announcements (typically October/November)
    2. ✅ Download official IRS publications
    3. ✅ Backup current CSV files (use Download buttons above)
    4. ✅ Update each file with new year's data:
       - Standard Deduction
       - Income Tax Brackets (both MFJ and Single)
       - Capital Gains Brackets (both MFJ and Single)
       - IRA & 401(k) Limits
       - IRMAA thresholds
    5. ✅ Verify all entries against official sources
    6. ✅ Test calculations with sample data
    7. ✅ Clear Streamlit cache (☰ → Clear cache)
    8. ✅ Document changes in a changelog
    
    **Important Notes:**
    - Always verify data against official IRS publications
    - Keep backups of previous years' data
    - Test thoroughly before relying on new data
    - Some values may remain unchanged year-over-year
    """)

with st.expander("⚠️ Common Pitfalls", expanded=False):
    st.markdown("""
    ### Things to Watch Out For
    
    1. **Filing Status Columns**
       - Income tax brackets and capital gains have separate rows for MFJ and Single
       - Standard deduction has separate rows for MFJ and Single
       - Don't forget to update BOTH filing statuses
    
    2. **Bracket Structure**
       - Tax brackets must have a "0,0,0" row at the start
       - Upper limits should be very high (e.g., 4000000) for top bracket
       - Brackets must not overlap
    
    3. **IRMAA Thresholds**
       - IRMAA uses MAGI from 2 years prior
       - Thresholds are for MFJ (Single is typically 50%)
       - Multiple tiers with different surcharges
    
    4. **IRA Limits**
       - Catch-up contributions change at age 50
       - Special catch-up for 401(k) at age 60-63 (SECURE 2.0)
       - Roth phase-out ranges differ by filing status
    
    5. **Data Types**
       - Years should be integers (2025, not "2025")
       - Rates should be decimals (0.22, not 22)
       - Dollar amounts should be integers or floats
    """)

st.markdown("---")
st.info("""
💡 **Tip**: After making changes, clear the Streamlit cache (☰ → Clear cache) to ensure 
the application uses the updated data.
""")

# Made with Bob
