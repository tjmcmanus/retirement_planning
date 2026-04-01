"""
components/reporting/report_templates.py
=========================================
Report template management system.

Handles loading, validation, and management of report templates.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ReportTemplate:
    """
    Represents a single report template.
    
    A template defines the structure and configuration of a report,
    including which sections to include and how to format them.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize template from configuration dictionary.
        
        Args:
            config: Template configuration dictionary
        """
        self.template_id = config.get('template_id', 'unknown')
        self.name = config.get('name', 'Unnamed Template')
        self.description = config.get('description', '')
        self.version = config.get('version', '1.0')
        
        # Page settings
        self.page_size = config.get('page_size', 'letter')
        self.orientation = config.get('orientation', 'portrait')
        
        # Margins (in inches)
        margins = config.get('margins', {})
        self.margin_top = margins.get('top', 0.75)
        self.margin_bottom = margins.get('bottom', 0.75)
        self.margin_left = margins.get('left', 0.75)
        self.margin_right = margins.get('right', 0.75)
        
        # Branding
        branding = config.get('branding', {})
        self.show_logo = branding.get('show_logo', False)
        self.logo_path = branding.get('logo_path')
        self.footer_text = branding.get('footer_text', 'Confidential - For Personal Use Only')
        self.show_page_numbers = branding.get('show_page_numbers', True)
        
        # Sections
        self.sections = config.get('sections', [])
        
        # Sort sections by order
        self.sections.sort(key=lambda s: s.get('order', 999))
    
    def get_enabled_sections(self) -> List[Dict[str, Any]]:
        """Get list of enabled sections in order."""
        return [s for s in self.sections if s.get('enabled', True)]
    
    def get_section(self, section_id: str) -> Optional[Dict[str, Any]]:
        """Get specific section by ID."""
        for section in self.sections:
            if section.get('section_id') == section_id:
                return section
        return None
    
    def enable_section(self, section_id: str):
        """Enable a section."""
        section = self.get_section(section_id)
        if section:
            section['enabled'] = True
    
    def disable_section(self, section_id: str):
        """Disable a section."""
        section = self.get_section(section_id)
        if section:
            section['enabled'] = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary."""
        return {
            'template_id': self.template_id,
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'page_size': self.page_size,
            'orientation': self.orientation,
            'margins': {
                'top': self.margin_top,
                'bottom': self.margin_bottom,
                'left': self.margin_left,
                'right': self.margin_right,
            },
            'branding': {
                'show_logo': self.show_logo,
                'logo_path': self.logo_path,
                'footer_text': self.footer_text,
                'show_page_numbers': self.show_page_numbers,
            },
            'sections': self.sections,
        }


class ReportTemplateManager:
    """
    Manage report templates.
    
    Handles loading templates from JSON files, validation,
    and providing access to available templates.
    """
    
    def __init__(self, templates_dir: str = "data/report_templates"):
        """
        Initialize template manager.
        
        Args:
            templates_dir: Directory containing template JSON files
        """
        self.templates_dir = Path(templates_dir)
        self.templates: Dict[str, ReportTemplate] = {}
        
        # Create templates directory if it doesn't exist
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # Load templates
        self.load_templates()
        
        logger.info(f"ReportTemplateManager initialized with {len(self.templates)} templates")
    
    def load_templates(self):
        """Load all templates from the templates directory."""
        self.templates.clear()
        
        # Load JSON files
        for template_file in self.templates_dir.glob("*.json"):
            try:
                with open(template_file, 'r') as f:
                    config = json.load(f)
                
                template = ReportTemplate(config)
                self.templates[template.template_id] = template
                
                logger.info(f"Loaded template: {template.name} ({template.template_id})")
                
            except Exception as e:
                logger.error(f"Failed to load template {template_file}: {e}")
    
    def get_template(self, template_id: str) -> Optional[ReportTemplate]:
        """
        Get template by ID.
        
        Args:
            template_id: Template identifier
            
        Returns:
            ReportTemplate or None if not found
        """
        return self.templates.get(template_id)
    
    def list_templates(self) -> List[Dict[str, str]]:
        """
        List all available templates.
        
        Returns:
            List of template info dictionaries
        """
        return [
            {
                'template_id': t.template_id,
                'name': t.name,
                'description': t.description,
            }
            for t in self.templates.values()
        ]
    
    def create_custom_template(
        self,
        template_id: str,
        name: str,
        base_template_id: Optional[str] = None,
        **kwargs
    ) -> ReportTemplate:
        """
        Create a custom template.
        
        Args:
            template_id: Unique template identifier
            name: Template name
            base_template_id: Optional base template to copy from
            **kwargs: Additional template configuration
            
        Returns:
            New ReportTemplate instance
        """
        if base_template_id and base_template_id in self.templates:
            # Copy from base template
            config = self.templates[base_template_id].to_dict()
            config['template_id'] = template_id
            config['name'] = name
            config.update(kwargs)
        else:
            # Create from scratch
            config = {
                'template_id': template_id,
                'name': name,
                'description': kwargs.get('description', ''),
                'version': '1.0',
                'page_size': kwargs.get('page_size', 'letter'),
                'orientation': kwargs.get('orientation', 'portrait'),
                'margins': kwargs.get('margins', {
                    'top': 0.75,
                    'bottom': 0.75,
                    'left': 0.75,
                    'right': 0.75,
                }),
                'branding': kwargs.get('branding', {
                    'show_logo': False,
                    'footer_text': 'Confidential - For Personal Use Only',
                    'show_page_numbers': True,
                }),
                'sections': kwargs.get('sections', []),
            }
        
        template = ReportTemplate(config)
        self.templates[template_id] = template
        
        return template
    
    def save_template(self, template: ReportTemplate):
        """
        Save template to JSON file.
        
        Args:
            template: ReportTemplate to save
        """
        filepath = self.templates_dir / f"{template.template_id}.json"
        
        try:
            with open(filepath, 'w') as f:
                json.dump(template.to_dict(), f, indent=2)
            
            logger.info(f"Saved template: {template.name} to {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save template {template.template_id}: {e}")
            raise
    
    def delete_template(self, template_id: str):
        """
        Delete a template.
        
        Args:
            template_id: Template identifier
        """
        if template_id in self.templates:
            del self.templates[template_id]
            
            # Delete file
            filepath = self.templates_dir / f"{template_id}.json"
            if filepath.exists():
                filepath.unlink()
            
            logger.info(f"Deleted template: {template_id}")
    
    def validate_template(self, template: ReportTemplate) -> List[str]:
        """
        Validate template configuration.
        
        Args:
            template: ReportTemplate to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Check required fields
        if not template.template_id:
            errors.append("Template ID is required")
        
        if not template.name:
            errors.append("Template name is required")
        
        # Check page size
        valid_page_sizes = ['letter', 'a4', 'legal']
        if template.page_size not in valid_page_sizes:
            errors.append(f"Invalid page size: {template.page_size}")
        
        # Check orientation
        valid_orientations = ['portrait', 'landscape']
        if template.orientation not in valid_orientations:
            errors.append(f"Invalid orientation: {template.orientation}")
        
        # Check sections
        if not template.sections:
            errors.append("Template must have at least one section")
        
        # Check for duplicate section IDs
        section_ids = [s.get('section_id') for s in template.sections]
        if len(section_ids) != len(set(section_ids)):
            errors.append("Duplicate section IDs found")
        
        # Check section order
        for section in template.sections:
            if 'order' not in section:
                errors.append(f"Section {section.get('section_id')} missing order")
        
        return errors


# Singleton instance
_template_manager_instance: Optional[ReportTemplateManager] = None


def get_template_manager() -> ReportTemplateManager:
    """Get singleton template manager instance."""
    global _template_manager_instance
    if _template_manager_instance is None:
        _template_manager_instance = ReportTemplateManager()
    return _template_manager_instance


# Made with Bob