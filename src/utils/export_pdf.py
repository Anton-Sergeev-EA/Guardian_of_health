"""
PDF report generation.
"""

import os
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Force Matplotlib to use a non-interactive backend (Agg) BEFORE importing pyplot.
# This prevents GUI/X11 initialization errors when running inside Docker or background threads.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

logger = logging.getLogger('focus_guardian.reporter')


class PDFReporter:
    """Generate PDF analysis reports from FocusGuardian session history."""
    
    def __init__(self, guardian):
        self.guardian = guardian
    
    def _get_history(self) -> List[Any]:
        """Fetch history securely from the guardian instance."""
        try:
            if hasattr(self.guardian, 'get_history'):
                return self.guardian.get_history()
            elif hasattr(self.guardian, 'db') and self.guardian.db:
                return self.guardian.db.get_history()
        except Exception as e:
            logger.error(f"Failed to retrieve history for PDF generation: {e}")
        return []
        
    def generate(self, output_path: Optional[Path] = None) -> Path:
        """
        Generate a multi-page PDF report containing statistical data and charts.
        """
        if output_path is None:
            output_dir = Path.home() / '.focus_guardian' / 'reports'
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        history = self._get_history()
        
        # Safe write using context manager
        try:
            with PdfPages(output_path) as pdf:
                # Page 1: Title
                self._create_title_page(pdf)
                
                # Pages 2+: Content or Placeholder
                if history and len(history) > 0:
                    self._create_summary_page(pdf, history)
                    self._create_posture_chart(pdf, history)
                    self._create_eye_chart(pdf, history)
                else:
                    self._create_no_data_page(pdf)
                    
            logger.info(f"PDF Report generated successfully at: {output_path}")
        except Exception as e:
            logger.error(f"Critical error during PDF compilation: {e}")
            raise e
            
        return output_path
    
    def _create_title_page(self, pdf: PdfPages):
        """Draw the main cover page of the report."""
        fig, ax = plt.subplots(figsize=(8.27, 11.69))  # Standard A4 size in inches
        try:
            ax.axis('off')
            
            # Decorative Header accent
            ax.axhline(y=0.85, color='#2C3E50', linewidth=4)
            
            # Title texts
            ax.text(0.5, 0.7, 'FocusGuardian', fontsize=32, weight='bold', 
                    color='#2C3E50', ha='center', va='center')
            ax.text(0.5, 0.62, 'Personal Health & Posture Analysis Report', fontsize=18, 
                    color='#7F8C8D', ha='center', va='center')
            
            # Metadata
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            meta_text = (
                f"Generated on: {current_time}\n"
                f"App Version: 2.0.0\n"
                f"Status: Compiled successfully"
            )
            ax.text(0.5, 0.35, meta_text, fontsize=11, color='#34495E',
                    ha='center', va='center', bbox=dict(boxstyle="round,pad=1", fc='#F8F9F9', ec='#BDC3C7'))
            
            # Footer
            ax.text(0.5, 0.05, '© FocusGuardian AI Team. Confidential Document.', 
                    fontsize=8, color='#BDC3C7', ha='center')
            
            pdf.savefig(fig)
        finally:
            plt.close(fig)
            
    def _create_summary_page(self, pdf: PdfPages, history: list):
        """Generate static text-based metrics summary table."""
        fig, ax = plt.subplots(figsize=(8.27, 11.69))
        try:
            ax.axis('off')
            
            ax.text(0.1, 0.9, 'Session Summary Statistics', fontsize=22, weight='bold', color='#2C3E50')
            
            total_records = len(history)
            
            # Safeguards against missing indices in raw DB arrays
            try:
                slouches = sum(1 for h in history if len(h) > 2 and h[2])  # Assuming index 2 is is_slouching
                avg_angle = np.mean([h[1] for h in history if len(h) > 1])  # Assuming index 1 is angle
            except (IndexError, TypeError, ValueError):
                slouches = "N/A"
                avg_angle = "N/A"
                
            summary_box = (
                f"• Total monitoring checkpoints: {total_records}\n\n"
                f"• Registered slouching events: {slouches}\n\n"
                f"• Average Measured Spine Angle: {f'{avg_angle:.2f}°' if isinstance(avg_angle, float) else avg_angle}\n\n"
            )
            
            ax.text(0.1, 0.5, summary_box, fontsize=14, color='#2C3E50',
                    linespacing=1.8, va='center')
            
            pdf.savefig(fig)
        finally:
            plt.close(fig)

    def _create_posture_chart(self, pdf: PdfPages, history: list):
        """Generate line plot visualization of user spine & neck angles over time."""
        fig, ax = plt.subplots(figsize=(8.27, 6))
        try:
            # Safely extract data series
            timestamps = [str(h[0]) if len(h) > 0 else str(i) for i, h in enumerate(history)]
            spine_angles = [float(h[1]) if len(h) > 1 else 0.0 for h in history]
            
            # Check if neck angles are present, else fallback
            neck_angles = [float(h[3]) if len(h) > 3 else 0.0 for h in history]
            
            # Downsample if history is too dense for clear visualization
            step = max(1, len(history) // 100)
            x_ticks_labels = timestamps[::step]
            
            ax.plot(timestamps, spine_angles, color='#2980B9', label='Spine Angle (deg)', linewidth=2)
            if any(neck_angles):
                ax.plot(timestamps, neck_angles, color='#F1C40F', label='Neck Angle (deg)', linewidth=1, alpha=0.7)
                
            ax.axhline(y=15.0, color='#E67E22', linestyle='--', alpha=0.5, label='Slouch Threshold (15°)')
            ax.axhline(y=25.0, color='#C0392B', linestyle='--', alpha=0.5, label='Critical Threshold (25°)')
            
            ax.set_xlabel('Timeline / Frames')
            ax.set_ylabel('Measured Angle (degrees)')
            ax.set_title('Posture Biometric Analysis Timeline')
            ax.legend(loc='upper right')
            ax.grid(True, alpha=0.3)
            
            # Format X-Axis ticks gracefully
            ax.set_xticks(range(0, len(timestamps), step))
            ax.set_xticklabels(x_ticks_labels, rotation=45, ha='right', fontsize=8)
            
            plt.tight_layout()
            pdf.savefig(fig)
        finally:
            plt.close(fig)
            
    def _create_eye_chart(self, pdf: PdfPages, history: list):
        """Generate bar chart representing blink and eye-closure distribution."""
        fig, ax = plt.subplots(figsize=(8.27, 6))
        try:
            # Safely collect values
            blink_rates = []
            for h in history:
                if len(h) > 4:
                    try:
                        blink_rates.append(float(h[4]))
                    except (ValueError, TypeError):
                        blink_rates.append(0.0)
                else:
                    blink_rates.append(0.0)
                    
            ax.bar(range(len(blink_rates)), blink_rates, color='#3498DB', alpha=0.6, label='Blinks / Min')
            ax.set_xlabel('Checkpoint Intervals')
            ax.set_ylabel('Registered Blinks Count')
            ax.set_title('Eye Blink Dynamics and Fatigue Monitoring')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            plt.tight_layout()
            pdf.savefig(fig)
        finally:
            plt.close(fig)

    def _create_no_data_page(self, pdf: PdfPages):
        """Fallback page for empty sessions."""
        fig, ax = plt.subplots(figsize=(8.27, 11.69))
        try:
            ax.axis('off')
            ax.text(0.5, 0.5, "No session monitoring logs found.\n\n"
                             "Please ensure the camera analytics thread is running\n"
                             "and data is being saved to the database.", 
                    fontsize=16, color='#7F8C8D', ha='center', va='center')
            pdf.savefig(fig)
        finally:
            plt.close(fig)
