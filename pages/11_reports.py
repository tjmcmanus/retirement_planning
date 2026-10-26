"""
pages/11_reports.py
===================
Report Generation Page

Provides UI for generating PDF reports, scheduling automated reports,
and viewing report history.
"""
import streamlit as st
import os
import csv
from datetime import datetime
from pathlib import Path
import time

# Import reporting components
from components.reporting import (
    ReportBuilder,
    get_template_manager,
)
from components.shared import init_page_minimal

# Try to import navbar if available
try:
    from components.navbar import render_navbar  # type: ignore
    HAS_NAVBAR = True
    def _render_navbar():
        render_navbar()  # type: ignore
except ImportError:
    HAS_NAVBAR = False
    def _render_navbar():
        pass

# Initialize page (sets page config + CSS; no data fetching needed here)
init_page_minimal(title="Report Generation", icon="📄")

# Render navigation if available
_render_navbar()

# Page title
st.title("📄 Report Generation")
st.markdown("Generate professional PDF reports for your retirement plan")

# Create tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📝 Generate Report",
    "📅 Scheduled Reports",
    "📊 Report History",
    "📋 Expense & Healthcare",
])

# ============================================================================
# TAB 1: Generate Report
# ============================================================================
with tab1:
    st.header("Generate New Report")
    
    # Get template manager
    template_mgr = get_template_manager()
    templates = template_mgr.list_templates()
    
    if not templates:
        st.error("No report templates found. Please check your installation.")
        st.stop()
    
    # Two-column layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("1. Select Report Template")
        
        # Template selection
        template_options = {t['name']: t['template_id'] for t in templates}
        selected_template_name = st.radio(
            "Choose a template:",
            options=list(template_options.keys()),
            help="Select the type of report you want to generate"
        )
        
        selected_template_id = template_options[selected_template_name]
        
        # Show template description
        selected_template_info = next(t for t in templates if t['template_id'] == selected_template_id)
        st.info(f"ℹ️ {selected_template_info['description']}")
        
        st.divider()
        
        # Section customization
        st.subheader("2. Customize Sections")
        
        try:
            template = template_mgr.get_template(selected_template_id)
            
            if template:
                st.markdown("**Select sections to include:**")
                
                # Get all sections
                all_sections = template.sections
                
                # Create checkboxes for each section
                section_states = {}
                for section in all_sections:
                    section_id = section.get('section_id')
                    section_title = section.get('title')
                    default_enabled = section.get('enabled', True)
                    
                    # Skip title page (always included)
                    if section_id == 'title_page':
                        section_states[section_id] = True
                        continue
                    
                    section_states[section_id] = st.checkbox(
                        section_title,
                        value=default_enabled,
                        key=f"section_{section_id}"
                    )
                
                # Update template with user selections
                for section in all_sections:
                    section_id = section.get('section_id')
                    if section_id in section_states:
                        section['enabled'] = section_states[section_id]
        
        except Exception as e:
            st.error(f"Error loading template: {e}")
            template = None
        
        st.divider()
        
        # Report options
        st.subheader("3. Report Options")
        
        report_title = st.text_input(
            "Report Title",
            value=selected_template_name,
            help="Custom title for the report"
        )
        
        # Get default names from configuration
        from config import get_config_manager
        config = get_config_manager()
        p1_name = config.get("personal_info", "person1_name", "")
        p2_name = config.get("personal_info", "person2_name", "")
        is_single = config.get("personal_info", "is_single_person", False)
        
        # Build default "Prepared For" value
        if is_single and p1_name:
            default_prepared_for = p1_name
        elif p1_name and p2_name:
            default_prepared_for = f"{p1_name} & {p2_name}"
        elif p1_name:
            default_prepared_for = p1_name
        else:
            default_prepared_for = ""
        
        prepared_for = st.text_input(
            "Prepared For",
            value=default_prepared_for,
            placeholder="e.g., John & Jane Doe",
            help="Optional: Name(s) to appear on the title page"
        )
        
        # File name - use report title to create a meaningful filename
        # Convert title to snake_case for filename
        title_for_filename = report_title.lower().replace(' ', '_').replace('-', '_')
        # Remove special characters
        title_for_filename = ''.join(c for c in title_for_filename if c.isalnum() or c == '_')
        default_filename = f"{title_for_filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filename = st.text_input(
            "File Name",
            value=default_filename,
            help="Name for the generated PDF file (auto-generated from report title)"
        )
        
        # Ensure .pdf extension
        if not filename.endswith('.pdf'):
            filename += '.pdf'
    
    with col2:
        st.subheader("Preview")
        
        # Show section preview
        if template:
            enabled_sections = [s for s in template.sections if s.get('enabled', True)]
            
            st.markdown(f"**Sections to include:** {len(enabled_sections)}")
            
            with st.expander("📋 Section List", expanded=True):
                for idx, section in enumerate(enabled_sections, 1):
                    st.markdown(f"{idx}. {section.get('title')}")
            
            # Estimated pages
            estimated_pages = len(enabled_sections) * 2  # Rough estimate
            st.metric("Estimated Pages", f"~{estimated_pages}")
        
        st.divider()
        
        # Generate button
        st.markdown("### Ready to Generate?")
        
        generate_button = st.button(
            "🚀 Generate Report",
            type="primary",
            width='stretch',
            help="Click to generate your PDF report"
        )
    
    # Generate report when button clicked
    if generate_button:
        if not template:
            st.error("Please select a valid template")
        else:
            # Create output directory
            output_dir = Path("data/generated_reports")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / filename
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def progress_callback(message: str, progress: float):
                """Update progress bar and status"""
                progress_bar.progress(progress)
                status_text.text(message)
            
            try:
                # Create report builder
                builder = ReportBuilder(selected_template_id)
                
                # Update template with custom title
                if report_title != selected_template_name:
                    builder.data['report_title'] = report_title
                
                # Generate report
                status_text.text("Starting report generation...")
                
                result_path = builder.generate_report(
                    output_path=str(output_path),
                    prepared_for=prepared_for if prepared_for else None,
                    progress_callback=progress_callback
                )
                
                # Success!
                progress_bar.progress(1.0)
                status_text.empty()
                
                st.success(f"✅ Report generated successfully!")
                
                # Download button
                with open(result_path, 'rb') as f:
                    pdf_data = f.read()
                
                st.download_button(
                    label="📥 Download Report",
                    data=pdf_data,
                    file_name=filename,
                    mime="application/pdf",
                    width='stretch'
                )
                
                # Show file info
                file_size = os.path.getsize(result_path) / 1024  # KB
                st.info(f"📄 File: {filename} ({file_size:.1f} KB)")
                
            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f"❌ Error generating report: {e}")
                st.exception(e)

# ============================================================================
# TAB 2: Scheduled Reports
# ============================================================================
with tab2:
    st.header("Scheduled Reports")
    st.info("📅 Email scheduling feature coming soon!")
    
    st.markdown("""
    ### Planned Features:
    
    - **Automated Report Generation**: Schedule reports to be generated automatically
    - **Email Delivery**: Receive reports via email on a schedule
    - **Multiple Recipients**: Send reports to family members or advisors
    - **Flexible Scheduling**: Daily, weekly, monthly, quarterly, or annually
    - **Custom Templates**: Use different templates for different schedules
    
    This feature will be available in the next update.
    """)
    
    # Placeholder for future implementation
    with st.expander("🔧 Configuration Preview"):
        st.selectbox("Report Template", ["Comprehensive", "Executive Summary"])
        st.selectbox("Frequency", ["Monthly", "Quarterly", "Annually"])
        st.multiselect("Recipients", ["user@example.com"])
        st.button("Save Schedule", disabled=True)

# ============================================================================
# TAB 3: Report History
# ============================================================================
with tab3:
    st.header("Report History")
    
    # Check for generated reports
    output_dir = Path("data/generated_reports")
    
    if output_dir.exists():
        pdf_files = list(output_dir.glob("*.pdf"))
        
        if pdf_files:
            st.markdown(f"**Found {len(pdf_files)} generated report(s)**")
            
            # Sort by modification time (newest first)
            pdf_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Display reports in a table
            report_data = []
            for pdf_file in pdf_files:
                stat = pdf_file.stat()
                report_data.append({
                    'File Name': pdf_file.name,
                    'Size (KB)': f"{stat.st_size / 1024:.1f}",
                    'Generated': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                })
            
            import pandas as pd
            df = pd.DataFrame(report_data)
            st.dataframe(df, width='stretch', hide_index=True)
            
            # Download buttons for each report
            st.divider()
            st.subheader("Download Reports")
            
            cols = st.columns(3)
            for idx, pdf_file in enumerate(pdf_files[:9]):  # Show up to 9 most recent
                col = cols[idx % 3]
                with col:
                    with open(pdf_file, 'rb') as f:
                        pdf_data = f.read()
                    
                    st.download_button(
                        label=f"📥 {pdf_file.name[:20]}...",
                        data=pdf_data,
                        file_name=pdf_file.name,
                        mime="application/pdf",
                        key=f"download_{idx}",
                        width='stretch'
                    )
            
            # Cleanup option
            st.divider()
            if st.button("🗑️ Clear All Reports", type="secondary"):
                for pdf_file in pdf_files:
                    try:
                        pdf_file.unlink()
                    except Exception as e:
                        st.error(f"Error deleting {pdf_file.name}: {e}")
                st.success("All reports cleared!")
                st.rerun()
        else:
            st.info("No reports generated yet. Generate your first report in the 'Generate Report' tab!")
    else:
        st.info("No reports generated yet. Generate your first report in the 'Generate Report' tab!")

# ============================================================================
# TAB 4: Expense & Healthcare Report
# ============================================================================
with tab4:
    st.header("📋 Expense & Healthcare Report")
    st.markdown("A printable summary of all configured expenses and healthcare costs. Use your browser's **Print** (Ctrl/⌘ + P) to save as PDF.")

    # ------------------------------------------------------------------
    # Load live config values
    # ------------------------------------------------------------------
    from config import get_config_manager
    _cfg = get_config_manager()

    p1_name   = _cfg.get("personal_info", "person1_name", "Person 1")
    p2_name   = _cfg.get("personal_info", "person2_name", "Person 2")
    p1_bd     = _cfg.get("personal_info", "person1_birth_date", "1966-01-01")
    p2_bd     = _cfg.get("personal_info", "person2_birth_date", "1967-01-01")
    p1_ret    = _cfg.get("personal_info", "person1_retirement_date", "2026-01-01")
    p2_ret    = _cfg.get("personal_info", "person2_retirement_date", "2027-01-01")
    state     = _cfg.get("personal_info", "retirement_state", "")
    is_single = _cfg.get("personal_info", "is_single_person", False)

    living    = _cfg.get_section("expenses").get("living_expenses", {})
    entertain = _cfg.get_section("expenses").get("entertainment_expenses", {})
    fin       = _cfg.get_section("financial_assumptions")
    hc        = _cfg.get_section("healthcare")
    char      = _cfg.get_section("charitable_giving")
    ss        = _cfg.get_section("social_security")

    total_exp      = fin.get("expected_annual_expenses", 0)
    exp_inflation  = fin.get("expense_inflation_rate", 3.0)
    ror            = fin.get("expected_rate_of_return", 6.0)
    cash_yrs       = fin.get("years_of_expenses_in_cash", 2)
    cash_buf_mo    = fin.get("accumulation_cash_buffer_months", 6)

    # Retirement age / year helpers
    def _ret_age_year(ret_date_str, birth_date_str):
        try:
            by = int(birth_date_str.split("-")[0])
            ry = int(ret_date_str.split("-")[0])
            return ry - by, ry
        except Exception:
            return "?", "?"

    p1_ret_age, p1_ret_yr = _ret_age_year(p1_ret, p1_bd)
    p2_ret_age, p2_ret_yr = _ret_age_year(p2_ret, p2_bd)

    p1_med_age = hc.get("person1_medicare_start_age", 65)
    p2_med_age = hc.get("person2_medicare_start_age", 65)
    p1_med_yr  = int(p1_bd.split("-")[0]) + p1_med_age
    p2_med_yr  = int(p2_bd.split("-")[0]) + p2_med_age

    def _fmt(v):
        """Format number as $X,XXX"""
        try:
            return f"${int(v):,}"
        except Exception:
            return str(v)

    def _fmtm(v):
        try:
            return f"${int(v):,}"
        except Exception:
            return str(v)

    # ------------------------------------------------------------------
    # Load IRMAA and medicare_premiums CSVs
    # ------------------------------------------------------------------
    def _load_csv_as_dicts(filepath):
        rows = []
        try:
            with open(filepath, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(row)
        except Exception:
            pass
        return rows

    irmaa_rows     = _load_csv_as_dicts("irmaa.csv")
    medicare_rows  = _load_csv_as_dicts("medicare_premiums.csv")

    # Index IRMAA by year → list of tiers
    irmaa_by_year = {}
    for r in irmaa_rows:
        yr = r.get("year", "")
        irmaa_by_year.setdefault(yr, []).append(r)

    # Medicare premiums indexed by year
    med_by_year = {r["year"]: r for r in medicare_rows}

    current_year = datetime.now().year
    filing = "Married Filing Jointly" if not is_single else "Single"
    names  = f"{p1_name} & {p2_name}" if not is_single else p1_name

    # ------------------------------------------------------------------
    # Build living-expense rows
    # ------------------------------------------------------------------
    living_labels = {
        "property_tax": "Property Tax",
        "homeowners_insurance": "Homeowners Insurance",
        "auto_insurance": "Auto Insurance",
        "food_groceries": "Food & Groceries",
        "utilities_phone": "Phone / Telecom",
        "utilities_internet": "Internet",
        "utilities_cable": "Cable / Streaming",
        "utilities_electric": "Electric",
        "utilities_gas": "Natural Gas",
        "utilities_water": "Water / Sewer",
        "gifts_donations": "Gifts & Donations",
        "other_living": "Other Living",
    }
    living_total = sum(living.get(k, 0) for k in living_labels)

    entertain_labels = {
        "travel_vacations": "Travel & Vacations",
        "dining_out": "Dining Out",
        "clothing": "Clothing",
        "hobbies": "Hobbies",
        "entertainment_other": "Entertainment — Other",
    }
    entertain_total = sum(entertain.get(k, 0) for k in entertain_labels)
    decline_enabled = entertain.get("retirement_decline_enabled", False)
    decline_pct     = entertain.get("retirement_decline_percent", 20)
    decline_age     = entertain.get("retirement_decline_start_age", 72)

    # Build IRMAA tier rows for the most-current year in the CSV
    latest_irmaa_yr = max((k for k in irmaa_by_year), key=lambda y: int(y), default=str(current_year))
    irmaa_tiers = irmaa_by_year.get(latest_irmaa_yr, [])

    # Medicare cost snapshot rows — pick 5-year window from first Medicare year
    first_med_yr = min(p1_med_yr, p2_med_yr)
    snap_years = [str(y) for y in range(first_med_yr, first_med_yr + 6) if str(y) in med_by_year]

    # ------------------------------------------------------------------
    # Helper: render an HTML table row
    # ------------------------------------------------------------------
    def _tr(cells, cls=""):
        tds = "".join(f'<td class="num">{c}</td>' if i > 0 else f"<td>{c}</td>" for i, c in enumerate(cells))
        return f'<tr class="{cls}">{tds}</tr>' if cls else f"<tr>{tds}</tr>"

    # ------------------------------------------------------------------
    # Assemble report HTML (self-contained, print-friendly)
    # ------------------------------------------------------------------
    living_rows_html = "".join(
        _tr([label, _fmt(living.get(k, 0)), _fmtm(living.get(k, 0) // 12)])
        for k, label in living_labels.items()
    )
    entertain_rows_html = "".join(
        _tr([label, _fmt(entertain.get(k, 0)), _fmtm(entertain.get(k, 0) // 12)])
        for k, label in entertain_labels.items()
    )

    irmaa_rows_html = ""
    for tier in irmaa_tiers:
        lower = int(float(tier.get("lower", 0)))
        upper = int(float(tier.get("upper", 0)))
        pb    = float(tier.get("part_b_monthly", 0))
        pd_b  = float(tier.get("part_d_base_monthly", 0))
        pd_i  = float(tier.get("part_d_irmaa_monthly", 0))
        pd_total = pd_b + pd_i
        annual_2 = round((pb + pd_total) * 12 * (2 if not is_single else 1))
        rng = f"${lower:,} – ${upper:,}" if upper < 4000000 else f"Over ${lower:,}"
        irmaa_rows_html += _tr([rng, f"${pb:,.2f}", f"${pd_total:,.2f}", f"${annual_2:,}"])

    med_snap_rows_html = ""
    for yr_s in snap_years:
        row = med_by_year[yr_s]
        mg  = int(float(row.get("medigap_annual", 0)))
        oop_h = int(float(row.get("oop_healthy", 0)))
        oop_a = int(float(row.get("oop_average", 0)))
        oop_c = int(float(row.get("oop_chronic", 0)))
        ltc   = int(float(row.get("ltc_annual_per_person", 0)))
        factor = 2 if not is_single else 1
        med_snap_rows_html += _tr([
            yr_s,
            f"${mg * factor:,}", f"${oop_h * factor:,}",
            f"${oop_a * factor:,}", f"${oop_c * factor:,}", f"${ltc:,}"
        ])

    # --- IRMAA note for 2-year lookback ---
    roth_2yr_note = ""
    if not is_single and p1_ret_yr != "?":
        lookback_yr = int(latest_irmaa_yr) - 2
        roth_2yr_note = (
            f"Roth conversions in {lookback_yr} affect {latest_irmaa_yr} Medicare premiums "
            f"(2-year lookback rule)."
        )

    # --- Healthcare phase descriptions ---
    p1_cov_pre  = hc.get("person1_preretirement_coverage_type", "Employer")
    p1_cov_post = hc.get("person1_retirement_coverage_type", "Employer Retiree")
    p1_aca_mo   = hc.get("person1_aca_insurance_monthly", 0)
    p1_aca_s    = hc.get("person1_aca_start_age", 62)
    p1_aca_e    = hc.get("person1_aca_end_age", 65)
    p1_pre_mo   = hc.get("person1_preretirement_insurance_monthly", 0)
    p1_cond     = hc.get("person1_conditions", [])

    p2_cov_pre  = hc.get("person2_preretirement_coverage_type", "Employer")
    p2_cov_post = hc.get("person2_retirement_coverage_type", "Employer Retiree")
    p2_aca_mo   = hc.get("person2_aca_insurance_monthly", 0)
    p2_aca_s    = hc.get("person2_aca_start_age", 62)
    p2_aca_e    = hc.get("person2_aca_end_age", 65)
    p2_pre_mo   = hc.get("person2_preretirement_insurance_monthly", 0)
    p2_cond     = hc.get("person2_conditions", [])

    # Charitable
    char_annual = char.get("annual_charitable_giving", 0)
    char_start  = char.get("charitable_giving_start_age", 65)
    char_end    = char.get("charitable_giving_end_age", 90)
    char_inf    = char.get("charitable_giving_inflation_rate", 2.0)
    has_daf     = char.get("has_daf", False)
    daf_prov    = char.get("daf_provider", "")
    daf_init    = char.get("daf_initial_contribution", 0)
    daf_ann     = char.get("daf_annual_contribution", 0)
    daf_start   = char.get("daf_contribution_start_year", "")
    daf_end     = char.get("daf_contribution_end_year", "")
    daf_prefund = char.get("daf_trad_prefund_enabled", False)
    daf_pf_amt  = char.get("daf_trad_prefund_amount", 0)
    daf_pf_yr   = char.get("daf_trad_prefund_start_year", "")

    # ------------------------------------------------------------------
    # Pre-build conditional HTML snippets (avoids nested f-strings and
    # double-quote conflicts inside the outer f-string, which Python 3.11
    # does not support).
    # ------------------------------------------------------------------
    _p1_cond_html = "<span class='pill g'>None</span>" if not p1_cond else ", ".join(p1_cond)
    _p2_cond_html = "<span class='pill g'>None</span>" if not p2_cond else ", ".join(p2_cond)

    if is_single:
        _p2_card_html = ""
    else:
        _p2_card_html = (
            f'<div class="card">'
            f'<h3>{p2_name} (born {p2_bd})</h3>'
            f'<div class="kv"><span class="l">Pre-Retirement Coverage</span>'
            f'<span class="v"><span class="pill">{p2_cov_pre}</span></span></div>'
            f'<div class="kv"><span class="l">Pre-Ret. Monthly Premium</span>'
            f'<span class="v">{_fmt(p2_pre_mo)}/mo</span></div>'
            f'<div class="kv"><span class="l">Retires</span>'
            f'<span class="v">{p2_ret} (age {p2_ret_age})</span></div>'
            f'<div class="kv"><span class="l">Post-Retirement Coverage</span>'
            f'<span class="v"><span class="pill o">{p2_cov_post}</span></span></div>'
            f'<div class="kv"><span class="l">ACA Monthly Premium</span>'
            f'<span class="v">{_fmt(p2_aca_mo)}/mo</span></div>'
            f'<div class="kv"><span class="l">ACA Coverage Ages</span>'
            f'<span class="v">{p2_aca_s} \u2013 {p2_aca_e}</span></div>'
            f'<div class="kv"><span class="l">Medicare Starts</span>'
            f'<span class="v">Age {p2_med_age} (est. {p2_med_yr})</span></div>'
            f'<div class="kv"><span class="l">Conditions</span>'
            f'<span class="v">{_p2_cond_html}</span></div>'
            f'</div>'
        )

    _person_count     = 1 if is_single else 2
    _person_count_lbl = "person" if is_single else "people"

    _irmaa_warn_html = (
        f"<div class='warn'><strong>IRMAA Note:</strong> {roth_2yr_note} "
        f"Managing MAGI below the first threshold preserves base-tier Medicare pricing.</div>"
    ) if roth_2yr_note else ""

    _decline_note_html = (
        f"<div class='note'><strong>Retirement Decline:</strong> Entertainment spending reduced by "
        f"{decline_pct}% starting at age {decline_age}. Post-decline entertainment subtotal: "
        f"{_fmt(round(entertain_total * (1 - decline_pct / 100)))}/yr.</div>"
    ) if decline_enabled else ""

    _decline_row_html = (
        f"<tr><td>Entertainment Decline</td><td>{decline_pct}% at age {decline_age} "
        f"(~{_fmt(round(entertain_total * decline_pct / 100))}/yr reduction)</td></tr>"
    ) if decline_enabled else ""

    if has_daf:
        _daf_rows_html = (
            f"<tr><td>DAF Provider</td><td>{daf_prov}</td></tr>"
            f"<tr><td>DAF Initial Contribution</td><td><strong>{_fmt(daf_init)}</strong></td></tr>"
            f"<tr><td>DAF Annual Contribution</td><td><strong>{_fmt(daf_ann)}/yr</strong></td></tr>"
            f"<tr><td>DAF Contribution Window</td><td>{daf_start} \u2013 {daf_end}</td></tr>"
        )
    else:
        _daf_rows_html = "<tr><td>DAF</td><td>Not configured</td></tr>"

    _daf_prefund_row_html = (
        f"<tr><td>DAF Traditional Prefund</td><td><strong>{_fmt(daf_pf_amt)}</strong> starting {daf_pf_yr}</td></tr>"
    ) if daf_prefund else ""

    report_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Expense &amp; Healthcare Report</title>
<style>
@media print {{
  .no-print {{ display: none; }}
  body {{ margin: 0; font-size: 12px; }}
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
  font-size: 13.5px;
  line-height: 1.55;
  color: #1f2328;
  background: #fff;
  padding: 28px 20px;
}}
.container {{ max-width: 760px; margin: 0 auto; }}
.hdr {{ border-bottom: 2px solid #e5e7eb; padding-bottom: 12px; margin-bottom: 24px; }}
.hdr h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; }}
.meta {{ font-size: 11.5px; color: #57606a; display: flex; gap: 18px; flex-wrap: wrap; margin-top: 6px; }}
.meta span::before {{ content: "• "; color: #3b82d4; }}
h2 {{ font-size: 14px; font-weight: 700; margin: 24px 0 8px;
     padding-bottom: 4px; border-bottom: 1px solid #e5e7eb;
     display: flex; justify-content: space-between; align-items: center; }}
h2 .badge {{ font-size: 10.5px; font-weight: 500; background: #f0f1f3;
              border: 1px solid #e5e7eb; border-radius: 10px; padding: 1px 8px; color: #57606a; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; margin-bottom: 2px; }}
thead th {{ background: #f7f8fa; border: 1px solid #e5e7eb; padding: 5px 9px;
            text-align: left; font-weight: 600; color: #57606a;
            font-size: 10.5px; text-transform: uppercase; letter-spacing: .04em; }}
tbody td {{ border: 1px solid #e5e7eb; padding: 5px 9px; vertical-align: top; }}
tbody tr:nth-child(even) td {{ background: #fafafa; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.sub td {{ font-weight: 600; background: #f7f8fa !important; border-top: 1px solid #d0d7de; }}
.tot td {{ font-weight: 700; background: #e8f0fe !important; border-top: 2px solid #3b82d4; }}
.note {{ font-size: 11.5px; color: #57606a; margin-top: 6px; padding: 7px 10px;
         background: #f7f8fa; border-left: 3px solid #e5e7eb; border-radius: 0 4px 4px 0; }}
.warn {{ background: #fff8e1; border: 1px solid #ffe082; border-radius: 4px;
         padding: 9px 11px; font-size: 11.5px; color: #57606a; margin-top: 10px; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 8px 0; }}
.card {{ background: #f7f8fa; border: 1px solid #e5e7eb; border-radius: 6px; padding: 12px; }}
.card h3 {{ font-size: 12.5px; font-weight: 700; color: #3b82d4; margin-bottom: 8px;
            padding-bottom: 5px; border-bottom: 1px solid #e5e7eb; }}
.kv {{ display: flex; justify-content: space-between; padding: 2px 0; font-size: 12.5px; }}
.kv .l {{ color: #57606a; }} .kv .v {{ font-weight: 600; }}
.pill {{ display:inline-block; border-radius:10px; padding:1px 7px;
         font-size:11px; font-weight:600; background:#e8f0fe; color:#3b82d4; }}
.pill.g {{ background:#e6f4ea; color:#2a7a3e; }}
.pill.o {{ background:#fff3e0; color:#b45309; }}
footer {{ margin-top: 36px; padding-top: 12px; border-top: 1px solid #e5e7eb;
          text-align: center; font-size: 11.5px; color: #57606a; }}
</style>
</head>
<body>
<div class="container">

<div class="hdr">
  <h1>Retirement Expense &amp; Healthcare Report</h1>
  <div class="meta">
    <span>{names}</span>
    <span>State: {state}</span>
    <span>Filing: {filing}</span>
    <span>Inflation: {exp_inflation}% / yr</span>
    <span>Base Year: {current_year}</span>
    <span>Generated: {datetime.now().strftime('%B %Y')}</span>
  </div>
</div>

<!-- LIVING EXPENSES -->
<h2>🏠 Living Expenses <span class="badge">Annual · Today's Dollars</span></h2>
<table>
  <thead><tr><th>Category</th><th class="num">Annual</th><th class="num">Monthly</th></tr></thead>
  <tbody>
    {living_rows_html}
    <tr class="sub"><td>Subtotal — Living</td><td class="num">{_fmt(living_total)}</td><td class="num">{_fmt(living_total // 12)}</td></tr>
  </tbody>
</table>

<!-- ENTERTAINMENT EXPENSES -->
<h2>🎭 Entertainment &amp; Lifestyle <span class="badge">Annual · Today's Dollars</span></h2>
<table>
  <thead><tr><th>Category</th><th class="num">Annual</th><th class="num">Monthly</th></tr></thead>
  <tbody>
    {entertain_rows_html}
    <tr class="sub"><td>Subtotal — Entertainment</td><td class="num">{_fmt(entertain_total)}</td><td class="num">{_fmt(entertain_total // 12)}</td></tr>
  </tbody>
</table>
{_decline_note_html}

<!-- TOTAL BUDGET -->
<h2>📋 Total Annual Expense Budget</h2>
<table>
  <thead><tr><th>Category</th><th class="num">Annual</th><th class="num">Monthly</th></tr></thead>
  <tbody>
    <tr><td>Living Expenses</td><td class="num">{_fmt(living_total)}</td><td class="num">{_fmt(living_total // 12)}</td></tr>
    <tr><td>Entertainment &amp; Lifestyle</td><td class="num">{_fmt(entertain_total)}</td><td class="num">{_fmt(entertain_total // 12)}</td></tr>
    <tr class="tot"><td>Configured Total (financial_assumptions)</td><td class="num">{_fmt(total_exp)}</td><td class="num">{_fmt(total_exp // 12)}</td></tr>
  </tbody>
</table>
<div class="note">Healthcare costs are modeled separately and added on top during simulation. Rate of return: {ror}% · Cash buffer: {cash_yrs} yrs retirement / {cash_buf_mo} mo accumulation.</div>

<!-- HEALTHCARE PER PERSON -->
<h2>🏥 Healthcare Configuration</h2>
<div class="two-col">
  <div class="card">
    <h3>{p1_name} (born {p1_bd})</h3>
    <div class="kv"><span class="l">Pre-Retirement Coverage</span><span class="v"><span class="pill">{p1_cov_pre}</span></span></div>
    <div class="kv"><span class="l">Pre-Ret. Monthly Premium</span><span class="v">{_fmt(p1_pre_mo)}/mo</span></div>
    <div class="kv"><span class="l">Retires</span><span class="v">{p1_ret} (age {p1_ret_age})</span></div>
    <div class="kv"><span class="l">Post-Retirement Coverage</span><span class="v"><span class="pill o">{p1_cov_post}</span></span></div>
    <div class="kv"><span class="l">ACA Monthly Premium</span><span class="v">{_fmt(p1_aca_mo)}/mo</span></div>
    <div class="kv"><span class="l">ACA Coverage Ages</span><span class="v">{p1_aca_s} – {p1_aca_e}</span></div>
    <div class="kv"><span class="l">Medicare Starts</span><span class="v">Age {p1_med_age} (est. {p1_med_yr})</span></div>
    <div class="kv"><span class="l">Conditions</span><span class="v">{_p1_cond_html}</span></div>
  </div>
  {_p2_card_html}
</div>

<!-- IRMAA TIERS -->
<h2>⚠️ IRMAA Surcharge Tiers — {latest_irmaa_yr} <span class="badge">{filing}</span></h2>
<table>
  <thead><tr><th>MAGI Range</th><th class="num">Part B / mo</th><th class="num">Part D Total / mo</th><th class="num">Annual ({_person_count} {_person_count_lbl})</th></tr></thead>
  <tbody>{irmaa_rows_html}</tbody>
</table>
{_irmaa_warn_html}

<!-- MEDIGAP + OOP -->
<h2>🔵 Medigap &amp; Out-of-Pocket Costs <span class="badge">From Medicare Start · {_person_count} {_person_count_lbl}</span></h2>
<table>
  <thead>
    <tr>
      <th>Year</th>
      <th class="num">Medigap</th>
      <th class="num">OOP Healthy</th>
      <th class="num">OOP Average</th>
      <th class="num">OOP Chronic</th>
      <th class="num">LTC / person / yr</th>
    </tr>
  </thead>
  <tbody>{med_snap_rows_html}</tbody>
</table>
<div class="note">LTC escalates at 5%/yr. LTC cost is per person — double if both require care concurrently.</div>

<!-- CHARITABLE -->
<h2>❤️ Charitable Giving &amp; DAF</h2>
<table>
  <thead><tr><th>Parameter</th><th>Value</th></tr></thead>
  <tbody>
    <tr><td>Annual Charitable Giving</td><td><strong>{_fmt(char_annual)}/yr</strong></td></tr>
    <tr><td>Giving Window</td><td>Age {char_start} – {char_end}</td></tr>
    <tr><td>Charitable Inflation Rate</td><td>{char_inf}% / yr</td></tr>
    {_daf_rows_html}
    {_daf_prefund_row_html}
  </tbody>
</table>

<!-- KEY ASSUMPTIONS -->
<h2>⚙️ Key Financial Assumptions</h2>
<table>
  <thead><tr><th>Parameter</th><th>Value</th></tr></thead>
  <tbody>
    <tr><td>Configured Total Annual Expenses</td><td><strong>{_fmt(total_exp)}</strong></td></tr>
    <tr><td>Expense Inflation Rate</td><td>{exp_inflation}% / yr</td></tr>
    <tr><td>Expected Rate of Return</td><td>{ror}% / yr</td></tr>
    <tr><td>Cash Buffer — Retirement</td><td>{cash_yrs} years (~{_fmt(total_exp * cash_yrs)} today's $)</td></tr>
    <tr><td>Cash Buffer — Accumulation</td><td>{cash_buf_mo} months</td></tr>
    {_decline_row_html}
  </tbody>
</table>

<footer>Made with IBM Bob</footer>
</div>
</body>
</html>"""

    st.components.v1.html(report_html, height=1800, scrolling=True)

    st.divider()
    st.caption("💡 Use **Ctrl / ⌘ + P** inside the report frame, or right-click → Print, to save as PDF.")


# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9em;'>
    <p>💡 <strong>Tip:</strong> Reports are saved locally and can be downloaded anytime from the Report History tab.</p>
    <p>For questions or issues, please refer to the documentation.</p>
</div>
""", unsafe_allow_html=True)

# Made with Bob