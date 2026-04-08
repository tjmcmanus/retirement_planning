"""
components/reporting/pdf_generator.py
======================================
Core PDF generation engine using ReportLab.

Provides low-level PDF creation capabilities including:
- Multi-page documents
- Headers and footers
- Tables and charts
- Table of contents
- Page numbering
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
import logging

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, legal
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    Image, KeepTogether, ListFlowable, ListItem
)
from reportlab.pdfgen import canvas

from .chart_exporter import ChartExporter

logger = logging.getLogger(__name__)


class PDFGenerator:
    """
    Core PDF generation engine.
    
    Features:
    - Multi-page document generation
    - Custom page layouts (portrait/landscape)
    - Header and footer management
    - Table of contents generation
    - Page numbering
    - Watermarks and branding
    """
    
    # Page size mapping
    PAGE_SIZES = {
        'letter': letter,
        'a4': A4,
        'legal': legal,
    }
    
    def __init__(
        self,
        filename: str,
        page_size: Literal['letter', 'a4', 'legal'] = 'letter',
        orientation: Literal['portrait', 'landscape'] = 'portrait',
        title: str = "Retirement Planning Report",
        author: str = "Retirement Planning System",
        subject: str = "Financial Planning Report"
    ):
        """
        Initialize PDF generator.
        
        Args:
            filename: Output PDF filename
            page_size: Page size ('letter', 'a4', or 'legal')
            orientation: Page orientation ('portrait' or 'landscape')
            title: Document title (metadata)
            author: Document author (metadata)
            subject: Document subject (metadata)
        """
        self.filename = filename
        self.title = title
        self.author = author
        self.subject = subject
        
        # Get page size
        page_size_tuple = self.PAGE_SIZES.get(page_size.lower(), letter)
        if orientation == 'landscape':
            page_size_tuple = (page_size_tuple[1], page_size_tuple[0])
        
        self.page_size = page_size_tuple
        self.page_width = page_size_tuple[0]
        self.page_height = page_size_tuple[1]
        
        # Initialize document
        self.doc = SimpleDocTemplate(
            filename,
            pagesize=page_size_tuple,
            title=title,
            author=author,
            subject=subject,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=1.0 * inch,
            bottomMargin=0.75 * inch
        )
        
        # Story (content) list
        self.story: List[Any] = []
        
        # Styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        
        # Chart exporter
        self.chart_exporter = ChartExporter()
        
        # TOC tracking
        self.toc_entries: List[Dict[str, Any]] = []
        
        # Header/footer configuration
        self.header_text: Optional[str] = None
        self.footer_text: Optional[str] = "Confidential - For Personal Use Only"
        self.show_page_numbers = True
        self.logo_path: Optional[str] = None
        
        logger.info(f"PDFGenerator initialized: {filename}")
    
    def _setup_custom_styles(self):
        """Set up custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a2e'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        # Heading 1
        self.styles.add(ParagraphStyle(
            name='CustomHeading1',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a2e'),
            spaceAfter=12,
            spaceBefore=12,
            keepWithNext=True
        ))
        
        # Heading 2
        self.styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=10,
            spaceBefore=10,
            keepWithNext=True
        ))
        
        # Body text
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['BodyText'],
            fontSize=11,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=10
        ))
        
        # Caption
        self.styles.add(ParagraphStyle(
            name='Caption',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=TA_CENTER,
            spaceAfter=10
        ))
    
    def add_title_page(
        self,
        title: str,
        subtitle: Optional[str] = None,
        prepared_for: Optional[str] = None,
        date: Optional[str] = None,
        disclaimer: Optional[str] = None
    ):
        """
        Add title page with branding.
        
        Args:
            title: Main title
            subtitle: Optional subtitle
            prepared_for: Optional "Prepared for" text
            date: Optional date (defaults to today)
            disclaimer: Optional disclaimer text
        """
        # Add logo if available
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                logo = Image(self.logo_path, width=2*inch, height=1*inch)
                logo.hAlign = 'CENTER'
                self.story.append(logo)
                self.story.append(Spacer(1, 0.5*inch))
            except Exception as e:
                logger.warning(f"Could not add logo: {e}")
        
        # Title
        self.story.append(Spacer(1, 2*inch))
        self.story.append(Paragraph(title, self.styles['CustomTitle']))
        
        # Subtitle
        if subtitle:
            self.story.append(Spacer(1, 0.2*inch))
            self.story.append(Paragraph(subtitle, self.styles['Heading2']))
        
        # Prepared for
        if prepared_for:
            self.story.append(Spacer(1, 0.5*inch))
            self.story.append(Paragraph(f"Prepared for: {prepared_for}", self.styles['Heading3']))
        
        # Date
        if date is None:
            date = datetime.now().strftime("%B %d, %Y")
        self.story.append(Spacer(1, 0.3*inch))
        self.story.append(Paragraph(date, self.styles['Normal']))
        
        # Disclaimer
        if disclaimer:
            self.story.append(Spacer(1, 1*inch))
            disclaimer_style = ParagraphStyle(
                name='Disclaimer',
                parent=self.styles['Normal'],
                fontSize=9,
                textColor=colors.grey,
                alignment=TA_CENTER
            )
            self.story.append(Paragraph(disclaimer, disclaimer_style))
        
        self.story.append(PageBreak())
        logger.debug("Added title page")
    
    def add_section(
        self,
        title: str,
        content: str,
        level: int = 1,
        keep_with_next: bool = False
    ):
        """
        Add text section with heading.
        
        Args:
            title: Section title
            content: Section content (can include HTML tags)
            level: Heading level (1, 2, or 3)
            keep_with_next: If True, keeps this section with the next element (prevents page break between them)
        """
        # Add to TOC
        self.toc_entries.append({
            'title': title,
            'level': level,
            'page': len(self.story)  # Approximate page number
        })
        
        # Add heading
        if level == 1:
            style = self.styles['CustomHeading1']
        elif level == 2:
            style = self.styles['CustomHeading2']
        else:
            style = self.styles['Heading3']
        
        # Build section elements
        section_elements = []
        if title:
            section_elements.append(Paragraph(title, style))
        
        # Add content
        if content:
            paragraphs = content.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    section_elements.append(Paragraph(para, self.styles['CustomBody']))
        
        # If keep_with_next is True, store elements to be combined with next item
        if keep_with_next and section_elements:
            # Store for combining with next element
            if not hasattr(self, '_pending_keep_together'):
                self._pending_keep_together = []
            self._pending_keep_together.extend(section_elements)
        else:
            # Add any pending elements first
            if hasattr(self, '_pending_keep_together') and self._pending_keep_together:
                section_elements = self._pending_keep_together + section_elements
                self._pending_keep_together = []
            
            # Add to story
            for elem in section_elements:
                self.story.append(elem)
        
        logger.debug(f"Added section: {title} (keep_with_next={keep_with_next})")
    
    def add_table(
        self,
        data: pd.DataFrame,
        title: Optional[str] = None,
        col_widths: Optional[List[float]] = None,
        style: Optional[str] = 'default'
    ):
        """
        Add formatted table with smart column alignment.
        
        Text columns are left-aligned, numeric columns are right-aligned.
        
        Args:
            data: DataFrame to display
            title: Optional table title
            col_widths: Optional column widths in inches
            style: Table style ('default', 'minimal', or 'colorful')
        """
        # Collect elements for this table
        table_elements = []
        
        if title:
            table_elements.append(Paragraph(title, self.styles['Heading3']))
            table_elements.append(Spacer(1, 0.1*inch))
        
        # Convert DataFrame to list of lists
        table_data = [data.columns.tolist()] + data.values.tolist()
        
        # Create table
        if col_widths:
            col_widths = [w * inch for w in col_widths]
        
        table = Table(table_data, colWidths=col_widths)
        
        # Detect column types for alignment
        col_alignments = []
        for col_idx, col_name in enumerate(data.columns):
            col_data = data[col_name]
            # Check if column is numeric or contains currency-formatted strings
            is_numeric = False
            if pd.api.types.is_numeric_dtype(col_data):
                is_numeric = True
            elif col_data.dtype == 'object':
                # Check if most values look like numbers or currency
                sample = col_data.dropna().head(5).astype(str)
                if len(sample) > 0:
                    numeric_count = sum(1 for val in sample if val.replace('$', '').replace(',', '').replace('.', '').replace('-', '').replace('(', '').replace(')', '').strip().isdigit())
                    is_numeric = numeric_count >= len(sample) * 0.8
            
            col_alignments.append('RIGHT' if is_numeric else 'LEFT')
        
        # Apply style
        if style == 'default':
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                # Header row centered
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ])
        elif style == 'minimal':
            table_style = TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),
                ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
                # Header row centered
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ])
        else:  # colorful
            table_style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')]),
                # Header row centered
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ])
        
        # Apply column-specific alignments to data rows
        for col_idx, alignment in enumerate(col_alignments):
            table_style.add('ALIGN', (col_idx, 1), (col_idx, -1), alignment)
        
        table.setStyle(table_style)
        table_elements.append(table)
        table_elements.append(Spacer(1, 0.2*inch))
        
        # Check if there are pending keep_together elements (e.g., a header)
        if hasattr(self, '_pending_keep_together') and self._pending_keep_together:
            # Combine header with table using KeepTogether
            combined_elements = self._pending_keep_together + table_elements
            self.story.append(KeepTogether(combined_elements))
            self._pending_keep_together = []
            logger.debug(f"Added table with {len(data)} rows (kept with header), alignments: {col_alignments}")
        elif title:
            # If table has its own title, always keep title with table
            self.story.append(KeepTogether(table_elements))
            logger.debug(f"Added table with {len(data)} rows (title kept with table), alignments: {col_alignments}")
        else:
            # Add table elements normally (no title, no pending header)
            for elem in table_elements:
                self.story.append(elem)
            logger.debug(f"Added table with {len(data)} rows, alignments: {col_alignments}")
    
    def add_chart(
        self,
        fig,
        title: Optional[str] = None,
        width: int = 6,
        height: int = 4,
        caption: Optional[str] = None
    ):
        """
        Add Plotly chart as image.
        
        Args:
            fig: Plotly Figure object
            title: Optional chart title
            width: Chart width in inches
            height: Chart height in inches
            caption: Optional caption text
        """
        # Collect elements for this chart
        chart_elements = []
        
        if title:
            chart_elements.append(Paragraph(title, self.styles['Heading3']))
            chart_elements.append(Spacer(1, 0.1*inch))
        
        try:
            # Export chart to image
            img_path = self.chart_exporter.export_chart(
                fig,
                width=int(width * 100),
                height=int(height * 100),
                format='png',
                scale=2.0
            )
            
            # Add image to PDF
            img = Image(img_path, width=width*inch, height=height*inch)
            img.hAlign = 'CENTER'
            chart_elements.append(img)
            
            # Add caption
            if caption:
                chart_elements.append(Spacer(1, 0.05*inch))
                chart_elements.append(Paragraph(caption, self.styles['Caption']))
            
            chart_elements.append(Spacer(1, 0.2*inch))
            
            # Check if there are pending keep_together elements (e.g., a header)
            if hasattr(self, '_pending_keep_together') and self._pending_keep_together:
                # Combine header with chart using KeepTogether
                combined_elements = self._pending_keep_together + chart_elements
                self.story.append(KeepTogether(combined_elements))
                self._pending_keep_together = []
                logger.debug(f"Added chart: {title or 'Untitled'} (kept with header)")
            elif title:
                # If chart has its own title, always keep title with chart
                self.story.append(KeepTogether(chart_elements))
                logger.debug(f"Added chart: {title or 'Untitled'} (title kept with chart)")
            else:
                # Add chart elements normally (no title, no pending header)
                for elem in chart_elements:
                    self.story.append(elem)
                logger.debug(f"Added chart: {title or 'Untitled'}")
            
        except Exception as e:
            logger.error(f"Failed to add chart: {e}")
            error_elem = Paragraph(f"[Chart could not be rendered: {e}]", self.styles['Normal'])
            
            # Handle pending elements even on error
            if hasattr(self, '_pending_keep_together') and self._pending_keep_together:
                self.story.extend(self._pending_keep_together)
                self._pending_keep_together = []
            
            self.story.append(error_elem)
    
    def add_page_break(self):
        """Force new page."""
        self.story.append(PageBreak())
    
    def add_spacer(self, height: float = 0.2):
        """
        Add vertical space.
        
        Args:
            height: Space height in inches
        """
        self.story.append(Spacer(1, height * inch))
    
    def add_bullet_list(self, items: List[str], style_name: Optional[str] = None, compact: bool = False):
        """
        Add bullet list.
        
        Args:
            items: List of items
            style_name: Optional paragraph style name
            compact: If True, use minimal spacing between items (like Shift+Enter)
        """
        if style_name is None:
            para_style = self.styles['CustomBody']
        else:
            para_style = self.styles.get(style_name, self.styles['CustomBody'])
        
        # Create bullet list using simple paragraphs with bullet prefix
        for i, item in enumerate(items):
            bullet_para = Paragraph(f"• {item}", para_style)
            self.story.append(bullet_para)
            
            # Add minimal spacer between items if compact mode
            if compact and i < len(items) - 1:
                self.story.append(Spacer(1, 0.02*inch))  # Minimal spacing (like Shift+Enter)
        
        # Add normal spacer after the list
        if not compact:
            self.story.append(Spacer(1, 0.1*inch))
        else:
            self.story.append(Spacer(1, 0.1*inch))  # Normal space after compact list
    
    def add_toc(self):
        """Generate and add table of contents."""
        if not self.toc_entries:
            return
        
        self.story.append(Paragraph("Table of Contents", self.styles['CustomHeading1']))
        self.story.append(Spacer(1, 0.2*inch))
        
        for entry in self.toc_entries:
            indent = "    " * (entry['level'] - 1)
            toc_text = f"{indent}{entry['title']}"
            self.story.append(Paragraph(toc_text, self.styles['Normal']))
        
        self.story.append(PageBreak())
        logger.debug("Added table of contents")
    
    def _header_footer(self, canvas_obj, doc):
        """Draw header and footer on each page."""
        canvas_obj.saveState()
        
        # Header
        if self.header_text:
            canvas_obj.setFont('Helvetica', 9)
            canvas_obj.setFillColor(colors.grey)
            canvas_obj.drawString(
                0.75 * inch,
                self.page_height - 0.5 * inch,
                self.header_text
            )
        
        # Footer
        if self.footer_text:
            canvas_obj.setFont('Helvetica', 8)
            canvas_obj.setFillColor(colors.grey)
            canvas_obj.drawCentredString(
                self.page_width / 2,
                0.5 * inch,
                self.footer_text
            )
        
        # Page number
        if self.show_page_numbers:
            canvas_obj.setFont('Helvetica', 9)
            canvas_obj.drawRightString(
                self.page_width - 0.75 * inch,
                0.5 * inch,
                f"Page {doc.page}"
            )
        
        canvas_obj.restoreState()
    
    def save(self) -> str:
        """
        Save PDF and return filepath.
        
        Returns:
            Path to saved PDF file
        """
        try:
            # Build PDF
            self.doc.build(
                self.story,
                onFirstPage=self._header_footer,
                onLaterPages=self._header_footer
            )
            
            logger.info(f"PDF saved successfully: {self.filename}")
            return self.filename
            
        except Exception as e:
            logger.error(f"Failed to save PDF: {e}")
            raise


# Made with Bob