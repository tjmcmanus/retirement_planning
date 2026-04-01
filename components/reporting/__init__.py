"""
components/reporting/__init__.py
=================================
Report generation module for creating PDF reports and email automation.

This module provides comprehensive report generation capabilities including:
- PDF generation with charts, tables, and formatted text
- Multiple report templates (comprehensive, executive summary, tax planning, etc.)
- Email scheduling and automated delivery
- Report history tracking
"""

from .chart_exporter import ChartExporter
from .pdf_generator import PDFGenerator
from .report_builder import ReportBuilder
from .report_templates import ReportTemplateManager, get_template_manager

# Email scheduler and report history will be implemented in Phase 4
# from .email_scheduler import EmailScheduler
# from .report_history import ReportHistory

__all__ = [
    'ChartExporter',
    'PDFGenerator',
    'ReportBuilder',
    'ReportTemplateManager',
    'get_template_manager',
    # 'EmailScheduler',
    # 'ReportHistory',
]

__version__ = '1.0.0'

# Made with Bob
