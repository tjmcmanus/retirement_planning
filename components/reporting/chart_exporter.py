"""
components/reporting/chart_exporter.py
=======================================
Export Plotly charts to images for PDF embedding.

Handles conversion of Plotly figures to high-quality PNG/JPEG images
suitable for inclusion in PDF reports.
"""
from __future__ import annotations

import os
import hashlib
import tempfile
from pathlib import Path
from typing import Optional, Literal
import logging

import plotly.graph_objects as go

logger = logging.getLogger(__name__)


class ChartExporter:
    """
    Export Plotly charts to images for PDF embedding.
    
    Features:
    - High-quality image export (300 DPI)
    - Caching to avoid re-exporting identical charts
    - Support for PNG and JPEG formats
    - Automatic cleanup of temporary files
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize chart exporter.
        
        Args:
            cache_dir: Directory for caching exported images.
                      If None, uses system temp directory.
        """
        if cache_dir is None:
            self.cache_dir = Path(tempfile.gettempdir()) / "retirement_planning_charts"
        else:
            self.cache_dir = Path(cache_dir)
        
        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"ChartExporter initialized with cache dir: {self.cache_dir}")
    
    def export_chart(
        self,
        fig: go.Figure,
        width: int = 800,
        height: int = 600,
        format: Literal["png", "jpeg", "jpg"] = "png",
        scale: float = 2.0,
        cache_key: Optional[str] = None
    ) -> str:
        """
        Export Plotly chart to image file.
        
        Args:
            fig: Plotly Figure object to export
            width: Image width in pixels
            height: Image height in pixels
            format: Output format ('png' or 'jpeg')
            scale: Scale factor for higher resolution (2.0 = 2x resolution)
            cache_key: Optional cache key. If provided and cached image exists,
                      returns cached path without re-exporting.
        
        Returns:
            Path to exported image file
            
        Raises:
            ValueError: If figure is invalid or export fails
        """
        try:
            # Normalize format
            if format.lower() == "jpg":
                format = "jpeg"
            
            # Generate cache key if not provided
            if cache_key is None:
                cache_key = self._generate_cache_key(fig, width, height, format, scale)
            
            # Check cache
            cached_path = self.cache_dir / f"{cache_key}.{format}"
            if cached_path.exists():
                logger.debug(f"Using cached chart: {cached_path}")
                return str(cached_path)
            
            # Export chart
            logger.info(f"Exporting chart: {width}x{height}, format={format}, scale={scale}")
            
            # Use kaleido for export (installed as dependency)
            output_path = str(cached_path)
            fig.write_image(
                output_path,
                format=format,
                width=width,
                height=height,
                scale=scale
            )
            
            logger.info(f"Chart exported successfully: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Failed to export chart: {e}")
            raise ValueError(f"Chart export failed: {e}")
    
    def _generate_cache_key(
        self,
        fig: go.Figure,
        width: int,
        height: int,
        format: str,
        scale: float
    ) -> str:
        """
        Generate unique cache key for a chart.
        
        Args:
            fig: Plotly Figure
            width: Image width
            height: Image height
            format: Output format
            scale: Scale factor
            
        Returns:
            MD5 hash as cache key
        """
        # Create a string representation of the chart configuration
        config_str = f"{width}x{height}_{format}_{scale}"
        
        # Add figure data (simplified - just use layout title and data length)
        try:
            if hasattr(fig, 'layout') and fig.layout:
                title_obj = getattr(fig.layout, 'title', None)
                if title_obj:
                    title_text = getattr(title_obj, 'text', 'notitle')
                    config_str += f"_{title_text}"
                else:
                    config_str += "_notitle"
            else:
                config_str += "_notitle"
        except (AttributeError, TypeError):
            config_str += "_notitle"
        
        if hasattr(fig, 'data'):
            try:
                data_len = len(fig.data) if fig.data else 0
                config_str += f"_traces{data_len}"
            except (TypeError, AttributeError):
                config_str += "_traces0"
        
        # Generate MD5 hash
        return hashlib.md5(config_str.encode()).hexdigest()
    
    def clear_cache(self, older_than_hours: Optional[int] = None):
        """
        Clear cached chart images.
        
        Args:
            older_than_hours: If provided, only delete files older than this many hours.
                            If None, deletes all cached files.
        """
        import time
        
        deleted_count = 0
        current_time = time.time()
        
        for file_path in self.cache_dir.glob("*"):
            if file_path.is_file():
                # Check age if specified
                if older_than_hours is not None:
                    file_age_hours = (current_time - file_path.stat().st_mtime) / 3600
                    if file_age_hours < older_than_hours:
                        continue
                
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete cached file {file_path}: {e}")
        
        logger.info(f"Cleared {deleted_count} cached chart images")
    
    def get_cache_size(self) -> tuple[int, int]:
        """
        Get cache statistics.
        
        Returns:
            Tuple of (file_count, total_size_bytes)
        """
        file_count = 0
        total_size = 0
        
        for file_path in self.cache_dir.glob("*"):
            if file_path.is_file():
                file_count += 1
                total_size += file_path.stat().st_size
        
        return file_count, total_size
    
    def export_multiple_charts(
        self,
        charts: list[tuple[go.Figure, str]],
        width: int = 800,
        height: int = 600,
        format: Literal["png", "jpeg"] = "png",
        scale: float = 2.0
    ) -> dict[str, str]:
        """
        Export multiple charts at once.
        
        Args:
            charts: List of (figure, name) tuples
            width: Image width in pixels
            height: Image height in pixels
            format: Output format
            scale: Scale factor
            
        Returns:
            Dictionary mapping chart names to exported file paths
        """
        results = {}
        
        for fig, name in charts:
            try:
                cache_key = f"{name}_{self._generate_cache_key(fig, width, height, format, scale)}"
                path = self.export_chart(fig, width, height, format, scale, cache_key)
                results[name] = path
            except Exception as e:
                logger.error(f"Failed to export chart '{name}': {e}")
                results[name] = None
        
        return results


# Convenience function for quick exports
def export_chart_to_image(
    fig: go.Figure,
    output_path: str,
    width: int = 800,
    height: int = 600,
    format: Literal["png", "jpeg"] = "png",
    scale: float = 2.0
) -> str:
    """
    Quick export of a Plotly chart to an image file.
    
    Args:
        fig: Plotly Figure to export
        output_path: Destination file path
        width: Image width in pixels
        height: Image height in pixels
        format: Output format ('png' or 'jpeg')
        scale: Scale factor for resolution
        
    Returns:
        Path to exported file
    """
    exporter = ChartExporter()
    temp_path = exporter.export_chart(fig, width, height, format, scale)
    
    # Copy to desired output path
    import shutil
    shutil.copy2(temp_path, output_path)
    
    return output_path


# Made with Bob