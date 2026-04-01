"""
pages/11_reports.py
===================
Report Generation Page

Provides UI for generating PDF reports, scheduling automated reports,
and viewing report history.
"""
import streamlit as st
import os
from datetime import datetime
from pathlib import Path
import time

# Import reporting components
from components.reporting import (
    ReportBuilder,
    get_template_manager,
)
from components.shared import init_page

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

# Page configuration
st.set_page_config(
    page_title="Report Generation",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize page
init_page(title="Report Generation", icon="📄")

# Render navigation if available
_render_navbar()

# Page title
st.title("📄 Report Generation")
st.markdown("Generate professional PDF reports for your retirement plan")

# Create tabs
tab1, tab2, tab3 = st.tabs(["📝 Generate Report", "📅 Scheduled Reports", "📊 Report History"])

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
            use_container_width=True,
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
                    use_container_width=True
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
            st.dataframe(df, use_container_width=True, hide_index=True)
            
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
                        use_container_width=True
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

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; font-size: 0.9em;'>
    <p>💡 <strong>Tip:</strong> Reports are saved locally and can be downloaded anytime from the Report History tab.</p>
    <p>For questions or issues, please refer to the documentation.</p>
</div>
""", unsafe_allow_html=True)

# Made with Bob