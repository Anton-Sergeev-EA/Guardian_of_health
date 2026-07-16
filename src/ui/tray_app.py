"""
System Tray Application using PyQt6 with dynamic localization and optimized UI rendering.
"""

import sys
from pathlib import Path
from typing import Optional, Dict

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidget
from PyQt6.QtGui import QIcon, QAction, QColor, QPainter, QPixmap, QPen
from PyQt6.QtCore import QTimer, Qt


class TrayApp(QWidget):
    """System tray application for FocusGuardian with optimized layout updates."""
    
    def __init__(self, guardian, web_port: Optional[int] = None, language: str = 'ru'):
        super().__init__()
        self.guardian = guardian
        self.web_port = web_port
        self.paused = False
        self.language = language
        
        # Localized UI string dictionary.
        self._translations: Dict[str, Dict[str, str]] = {
            'ru': {
                'tooltip_active': "🧘 FocusGuardian - Мониторинг",
                'tooltip_paused': "⏸️ Мониторинг приостановлен",
                'tooltip_no_face': "👤 Лицо не обнаружено",
                'tooltip_slouch': "⚠️ Внимание: Вы сутулитесь",
                'tooltip_critical': "🚨 КРИТИЧЕСКАЯ осанка!",
                'tooltip_good': "✅ Осанка в норме!",
                'init': "🔵 Инициализация",
                'no_face': "👤 Нет лица",
                'slouching': "🟡 Сутулость",
                'critical': "🔴 Критическая сутулость!",
                'good': "🟢 Отличная осанка",
                'pause': "⏸️ Пауза",
                'resume': "▶️ Продолжить",
                'report': "📊 Сформировать отчет",
                'open_web': "🌐 Открыть Веб-интерфейс",
                'quit': "✖️ Выход",
                'toast_paused': "⏸️ Мониторинг приостановлен",
                'toast_resumed': "▶️ Мониторинг возобновлен",
                'toast_report_title': "📊 Отчет сформирован!",
                'toast_report_body': "Проверьте консоль программы.",
                'stats_pattern': "📊 Моргнул: {blinks} | Сутулость: {slouches} | Угол: {angle:.1f}°"
            },
            'en': {
                'tooltip_active': "🧘 FocusGuardian - Monitoring",
                'tooltip_paused': "⏸️ Monitoring paused",
                'tooltip_no_face': "👤 No face detected",
                'tooltip_slouch': "⚠️ Warning: Slouching detected",
                'tooltip_critical': "🚨 CRITICAL slouching!",
                'tooltip_good': "✅ Posture good!",
                'init': "🔵 Initializing",
                'no_face': "👤 No face",
                'slouching': "🟡 Slouching",
                'critical': "🔴 Critical slouch!",
                'good': "🟢 Good posture",
                'pause': "⏸️ Pause",
                'resume': "▶️ Resume",
                'report': "📊 Generate Report",
                'open_web': "🌐 Open Web Interface",
                'quit': "✖️ Quit",
                'toast_paused': "⏸️ Monitoring paused",
                'toast_resumed': "▶️ Monitoring resumed",
                'toast_report_title': "📊 Report generated!",
                'toast_report_body': "Check application console output.",
                'stats_pattern': "📊 Blinks: {blinks} | Slouches: {slouches} | Angle: {angle:.1f}°"
            }
        }
        
        # Safe fallback for language selection.
        if self.language not in self._translations:
            self.language = 'ru'
            
        self.t = self._translations[self.language]
        
        # Create state indicators.
        self.green_icon = self._create_icon(QColor(0, 255, 136))
        self.yellow_icon = self._create_icon(QColor(255, 221, 0))
        self.red_icon = self._create_icon(QColor(255, 0, 68))
        self.gray_icon = self._create_icon(QColor(128, 128, 128))
        
        # Initialize System Tray
        self.tray = QSystemTrayIcon(self.gray_icon, self)
        self.tray.setToolTip(self.t['tooltip_active'])
        self.tray.activated.connect(self._on_tray_click)
        
        # Build structure once (prevents GUI thread memory leaks and recursive loops).
        self.menu = QMenu()
        self._init_menu_structure()
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        
        # Update thread loop timer (1 second interval).
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_ui)
        self.timer.start(1000)
        
        print(f"[TRAY] System tray initialized successfully in '{self.language}' language mode.")
    
    def _create_icon(self, color: QColor, size: int = 32) -> QIcon:
        """Create a vector colored circle layout."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(QPen(Qt.GlobalColor.transparent))
        painter.drawEllipse(4, 4, size - 8, size - 8)
        painter.end()
        
        return QIcon(pixmap)
    
    def _init_menu_structure(self):
        """Create QAction objects once and map events during initialization."""
        self.menu.clear()
        
        # Status field placeholder.
        self.status_action = QAction(self.t['init'], self)
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)
        self.menu.addSeparator()
        
        # Control actions.
        self.pause_action = QAction(self.t['pause'], self)
        self.pause_action.triggered.connect(self._toggle_pause)
        self.menu.addAction(self.pause_action)
        
        self.report_action = QAction(self.t['report'], self)
        self.report_action.triggered.connect(self._generate_report)
        self.menu.addAction(self.report_action)
        
        if self.web_port:
            self.web_action = QAction(f"{self.t['open_web']} (:{self.web_port})", self)
            self.web_action.triggered.connect(self._open_web)
            self.menu.addAction(self.web_action)
        
        self.menu.addSeparator()
        
        # Counters and statistics action placeholder.
        self.stats_action = QAction("", self)
        self.stats_action.setEnabled(False)
        self.menu.addAction(self.stats_action)
        
        self.menu.addSeparator()
        
        # Quit option.
        self.quit_action = QAction(self.t['quit'], self)
        self.quit_action.triggered.connect(self._quit)
        self.menu.addAction(self.quit_action)
    
    def _update_ui(self):
        """Safely refresh the text values of existing elements to avoid recursion."""
        try:
            status = self.guardian.get_status()
            
            # State evaluation and Icon/Tooltip update logic.
            if self.paused:
                self.tray.setIcon(self.gray_icon)
                self.tray.setToolTip(self.t['tooltip_paused'])
                self.status_action.setText(self.t['tooltip_paused'])
            elif not status.get('face_detected', False):
                self.tray.setIcon(self.gray_icon)
                self.tray.setToolTip(self.t['tooltip_no_face'])
                self.status_action.setText(self.t['no_face'])
            elif status.get('posture', {}).get('is_slouching', False):
                severity = status.get('posture', {}).get('severity', 'warning')
                if severity == 'critical':
                    self.tray.setIcon(self.red_icon)
                    self.tray.setToolTip(self.t['tooltip_critical'])
                    self.status_action.setText(self.t['critical'])
                else:
                    self.tray.setIcon(self.yellow_icon)
                    self.tray.setToolTip(self.t['tooltip_slouch'])
                    self.status_action.setText(self.t['slouching'])
            else:
                self.tray.setIcon(self.green_icon)
                self.tray.setToolTip(self.t['tooltip_good'])
                self.status_action.setText(self.t['good'])
            
            # Extract current session variables.
            eyes = status.get('eyes', {})
            session = status.get('session', {})
            posture = status.get('posture', {})
            
            # Format and apply statistics updates dynamically.
            stats_text = self.t['stats_pattern'].format(
                blinks=eyes.get('blinks', 0),
                slouches=session.get('slouches', 0),
                angle=posture.get('angle', 0.0)
            )
            self.stats_action.setText(stats_text)
            
        except Exception as e:
            print(f"[TRAY] Interface refresh error: {e}")
    
    def _toggle_pause(self):
        """Toggle core tracking algorithms and update context button text."""
        self.paused = not self.paused
        if self.paused:
            self.guardian.pause_monitoring()
            self.pause_action.setText(self.t['resume'])
            self.tray.showMessage(
                "FocusGuardian",
                self.t['toast_paused'],
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
        else:
            self.guardian.resume_monitoring()
            self.pause_action.setText(self.t['pause'])
            self.tray.showMessage(
                "FocusGuardian",
                self.t['toast_resumed'],
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
    
    def _generate_report(self):
        """Invoke report generator on background guardian thread."""
        self.guardian._generate_report()
        self.tray.showMessage(
            "FocusGuardian",
            f"{self.t['toast_report_title']} {self.t['toast_report_body']}",
            QSystemTrayIcon.MessageIcon.Information,
            3000
        )
    
    def _open_web(self):
        """Open web client interface using system's default browser."""
        import webbrowser
        webbrowser.open(f"http://localhost:{self.web_port}")
    
    def _on_tray_click(self, reason):
        """Intercept click events and double-click shortcuts."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._open_web()
    
    def _quit(self):
        """Gracefully release stream resources and terminate Qt loops."""
        self.guardian.stop()
        self.tray.hide()
        QApplication.quit()
        sys.exit(0)
