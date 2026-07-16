"""
Daemon/Service integration for auto-start
"""

import os
import sys
from pathlib import Path
import subprocess
import logging

logger = logging.getLogger('focus_guardian.daemon')


class DaemonInstaller:
    """Handles installation and uninstallation of FocusGuardian as a background system service."""
    
    @staticmethod
    def _is_root() -> bool:
        """Check if the current process has administrative privileges on Unix systems."""
        try:
            return os.geteuid() == 0
        except AttributeError:
            # Windows platform doesn't have geteuid, handle administrative check elsewhere
            return False

    @staticmethod
    def _get_python_executable() -> str:
        """Get the absolute path to the Python executable, prioritizing virtual environments (venv)."""
        cwd = Path(os.getcwd())
        # Check if local virtual environment exists
        venv_python = cwd / 'venv' / 'bin' / 'python'
        if sys.platform == 'win32':
            venv_python = cwd / 'venv' / 'Scripts' / 'python.exe'
            
        if venv_python.exists():
            logger.info(f"Detected local virtual environment Python: {venv_python}")
            return str(venv_python)
        
        logger.warning("No local virtual environment ('venv') found. Falling back to global interpreter.")
        return sys.executable

    @staticmethod
    def install_systemd() -> bool:
        """Install and enable systemd service unit on Linux platforms."""
        if not os.path.exists('/etc/systemd/system/'):
            logger.error("Systemd folder '/etc/systemd/system/' does not exist. Is this a Systemd-based Linux?")
            return False
        
        if not DaemonInstaller._is_root():
            logger.critical("Administrative privileges required. Please run this command using 'sudo'.")
            return False
        
        python_bin = DaemonInstaller._get_python_executable()
        username = os.environ.get('SUDO_USER', os.environ.get('USER', 'guardian'))
        user_home = os.path.expanduser(f"~{username}")
        
        # Display configuration forwarding to allow OpenCV/PyQt inside service if needed
        display = os.environ.get('DISPLAY', ':0')
        xauth = f"{user_home}/.Xauthority"
        
        service_content = f"""[Unit]
Description=FocusGuardian AI Health Assistant
After=network.target sound.target

[Service]
Type=simple
User={username}
WorkingDirectory={os.getcwd()}
Environment=DISPLAY={display}
Environment=XAUTHORITY={xauth}
Environment=PYTHONUNBUFFERED=1
ExecStart={python_bin} {os.path.join(os.getcwd(), 'main.py')} --web --no-tray
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        service_path = Path('/etc/systemd/system/focus-guardian.service')
        try:
            with open(service_path, 'w', encoding='utf-8') as f:
                f.write(service_content)
                
            subprocess.run(['systemctl', 'daemon-reload'], check=True, capture_output=True)
            subprocess.run(['systemctl', 'enable', 'focus-guardian'], check=True, capture_output=True)
            logger.info("FocusGuardian systemd service successfully registered and enabled.")
            return True
        except Exception as e:
            logger.error(f"Failed to install systemd service: {e}")
            return False
    
    @staticmethod
    def install_launchd() -> bool:
        """Install and load Launchd daemon on macOS."""
        if sys.platform != 'darwin':
            return False
            
        if not DaemonInstaller._is_root():
            logger.critical("Administrative privileges required. Please run this command using 'sudo'.")
            return False
            
        python_bin = DaemonInstaller._get_python_executable()
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.focusguardian.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_bin}</string>
        <string>{os.path.join(os.getcwd(), 'main.py')}</string>
        <string>--web</string>
        <string>--no-tray</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{os.getcwd()}</string>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/focus_guardian_out.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/focus_guardian_err.log</string>
</dict>
</plist>
"""
        plist_path = Path('/Library/LaunchDaemons/com.focusguardian.agent.plist')
        try:
            with open(plist_path, 'w', encoding='utf-8') as f:
                f.write(plist_content)
                
            subprocess.run(['launchctl', 'load', '-w', str(plist_path)], check=True, capture_output=True)
            logger.info("FocusGuardian launchd daemon successfully registered and loaded.")
            return True
        except Exception as e:
            logger.error(f"Failed to install launchd daemon: {e}")
            return False

    @staticmethod
    def install_windows_service() -> bool:
        """Install and register a Windows service."""
        if sys.platform != 'win32':
            return False
        try:
            import win32service
            import win32event
            # TODO: Future implementation for Windows Service registration via pywin32 utilities
            logger.warning("Windows service installation logic is defined but not yet implemented.")
            return False
        except ImportError:
            logger.error("Required package 'pywin32' is not installed. Unable to create Windows service.")
            return False
    
    @staticmethod
    def install() -> bool:
        """Auto-detect operating system platform and install appropriate background service."""
        if sys.platform == 'linux':
            return DaemonInstaller.install_systemd()
        elif sys.platform == 'darwin':
            return DaemonInstaller.install_launchd()
        elif sys.platform == 'win32':
            return DaemonInstaller.install_windows_service()
        else:
            logger.error(f"Unsupported operating system platform: {sys.platform}")
            return False
    
    @staticmethod
    def uninstall() -> bool:
        """Remove and clean up registered background services from the local system."""
        if sys.platform == 'linux':
            if not DaemonInstaller._is_root():
                logger.critical("Sudo permissions required to uninstall Linux service.")
                return False
                
            try:
                subprocess.run(['systemctl', 'stop', 'focus-guardian'], capture_output=True)
                subprocess.run(['systemctl', 'disable', 'focus-guardian'], capture_output=True)
                Path('/etc/systemd/system/focus-guardian.service').unlink(missing_ok=True)
                subprocess.run(['systemctl', 'daemon-reload'], capture_output=True)
                logger.info("Systemd service uninstalled successfully.")
                return True
            except Exception as e:
                logger.error(f"Error during systemd service cleanup: {e}")
                
        elif sys.platform == 'darwin':
            if not DaemonInstaller._is_root():
                logger.critical("Sudo permissions required to uninstall macOS daemon.")
                return False
                
            plist_path = '/Library/LaunchDaemons/com.focusguardian.agent.plist'
            try:
                subprocess.run(['launchctl', 'unload', '-w', plist_path], capture_output=True)
                Path(plist_path).unlink(missing_ok=True)
                logger.info("Launchd daemon uninstalled successfully.")
                return True
            except Exception as e:
                logger.error(f"Error during launchd daemon cleanup: {e}")
                
        elif sys.platform == 'win32':
            logger.warning("Windows service uninstallation is not yet implemented.")
            
        return False
