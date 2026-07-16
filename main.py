"""
Guardian of health - Main Entry Point.
"""


import sys
import os
import argparse
import threading
import subprocess
import time
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.traceback import install

# Install rich traceback for clear debugging inside terminal.
install(show_locals=True)

# Add src to python path securely.
sys.path.insert(0, str(Path(__file__).parent))

from src.app import FocusGuardian
from src.config.config_loader import get_config, reload_config
from src.logging.logger import get_logger
from src.utils.daemon import DaemonInstaller
from src.utils.performance import get_monitor

console = Console()
logger = get_logger("focus_guardian.main")


def show_banner():
    """Show application banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║   "Guardian of health"                                    ║
    ║   AI Health Assistant for Posture & Eye Health                ║
    ║                                                               ║
    ║   🔒 100% Local  |  🎙️ Voice Commands  |  🌐 Web UI         ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(Panel(banner, border_style="green"))


def make_status_table(guardian) -> Table:
    """Generate real-time status table from current guardian metrics."""
    status = guardian.get_status()
    posture = status.get('posture', {})
    eyes = status.get('eyes', {})
    fatigue = status.get('fatigue', {})
    session = status.get('session', {})
    
    table = Table(show_header=False, border_style="dim")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("FPS", f"{status.get('fps', 0)}")
    table.add_row("Face", "Detected" if status.get('face_detected') else "❌ Not detected")
    
    angle = posture.get('angle', 0.0)
    severity = posture.get('severity', 'Unknown')
    table.add_row("Posture", f"{angle:.1f}° ({severity})")
    table.add_row("Slouching", "Yes" if posture.get('is_slouching') else "✅ No")
    
    table.add_row("Blinks", f"{eyes.get('blinks', 0)}")
    table.add_row("Eyes", "Closed" if eyes.get('is_closed') else "👀 Open")
    table.add_row("Fatigue", f"{fatigue.get('level', 'Low')} ({fatigue.get('score', 0.0):.2f})")
    table.add_row("Session", f"{session.get('duration', 0)} min")
    
    return table


def show_status(guardian):
    """Show real-time status in console without screen flickering."""
    try:
        # Use rich Live rendering to keep status in one place smoothly.
        with Live(make_status_table(guardian), console=console, refresh_per_second=2) as live:
            while True:
                time.sleep(0.5)
                live.update(make_status_table(guardian))
    except KeyboardInterrupt:
        pass


def is_gui_available() -> bool:
    """Check if the operating system currently supports GUI environment rendering."""
    if sys.platform == 'win32':
        return True
    if sys.platform == 'darwin':
        # macOS launchd or SSH headless checks.
        return "SSH_CONNECTION" not in os.environ
    # Linux DISPLAY check
    return os.environ.get('DISPLAY') is not None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Guardian of health - AI Health Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                     # Console mode with TUI.
  python main.py --web               # With web interface.
  python main.py --status            # Show status once.
  python main.py --daemon install    # Install as service.
  python main.py --config reload     # Reload configuration.
  python main.py --perf              # Show performance stats.
        """
    )
    
    # Core options.
    parser.add_argument('--web', action='store_true', help='Enable web interface')
    parser.add_argument('--host', default='0.0.0.0', help='Web server host')
    parser.add_argument('--port', type=int, default=5000, help='Web server port')
    parser.add_argument('--no-tray', action='store_true', help='Disable system tray')
    parser.add_argument('--no-voice', action='store_true', help='Disable voice commands')
    parser.add_argument('--cam', type=int, default=0, help='Camera ID')
    parser.add_argument('--width', type=int, default=640, help='Camera width')
    parser.add_argument('--height', type=int, default=480, help='Camera height')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    
    # Action modes.
    parser.add_argument('--status', action='store_true', help='Show status once and exit')
    parser.add_argument('--perf', action='store_true', help='Show performance stats')
    parser.add_argument('--daemon', choices=['install', 'uninstall', 'status'], help='Manage daemon/service')
    parser.add_argument('--config-reload', action='store_true', help='Reload configuration')
    parser.add_argument('--test', action='store_true', help='Run tests')
    
    args = parser.parse_args()
    
    # Show banner.
    show_banner()
    
    # Handle daemon commands.
    if args.daemon:
        if args.daemon == 'install':
            console.print("[yellow]Installing system service...[/yellow]")
            if DaemonInstaller.install():
                console.print("[green] Service installed successfully![/green]")
            else:
                console.print("[red] Failed to install service[/red]")
            return 0
        elif args.daemon == 'uninstall':
            console.print("[yellow]Removing system service...[/yellow]")
            if DaemonInstaller.uninstall():
                console.print("[green] Service removed[/green]")
            else:
                console.print("[red] Failed to completely remove service[/red]")
            return 0
        elif args.daemon == 'status':
            if sys.platform == 'linux':
                subprocess.run(['systemctl', 'status', 'focus-guardian'])
            else:
                console.print("[yellow]Systemd service status check is only available on Linux.[/yellow]")
            return 0
    
    # Handle tests.
    if args.test:
        console.print("[yellow]Running tests...[/yellow]")
        import pytest
        sys.exit(pytest.main(['tests/']))
    
    # Load config.
    config_path = Path(args.config)
    if config_path.exists():
        console.print(f"[green] Loaded config: {config_path}[/green]")
    else:
        console.print(f"[yellow] Config not found, using defaults[/yellow]")
    
    # Initialize Core Application securely inside a try block
    guardian = None
    web_server = None
    try:
        guardian = FocusGuardian(
            cam_id=args.cam,
            width=args.width,
            height=args.height,
            enable_voice=not args.no_voice
        )
        
        # Start core background camera loop.
        capture_thread = threading.Thread(target=guardian.capture_loop, daemon=True)
        capture_thread.start()
        logger.info("Guardian camera analytics thread started.")
        
    except Exception as e:
        console.print(f"[red] Failed to initialize FocusGuardian: {e}[/red]")
        logger.critical(f"Initialization failure: {e}", exc_info=True)
        return 1
    
    # Global execution wrap to guarantee hardware and server resource cleanup.
    try:
        # Start web interface if requested.
        if args.web:
            from src.web.server import create_web_interface
            web_server = create_web_interface(guardian, host=args.host, port=args.port)
            web_thread = threading.Thread(target=web_server.start, daemon=True)
            web_thread.start()
            console.print(f"[green]Web interface: http://{args.host}:{args.port}[/green]")
        
        # Handle status mode (snapshot).
        if args.status:
            time.sleep(1.0)  # Wait for first few camera analysis iterations.
            status = guardian.get_status()
            from rich import print as rprint
            rprint(status)
            return 0
        
        # Handle performance benchmarking mode.
        if args.perf:
            console.print("[yellow]Gathering Performance Metrics (waiting 2 seconds).[/yellow]")
            time.sleep(2.0)
            report = get_monitor().report()
            table = Table(title="Performance Statistics")
            table.add_column("Component", style="cyan")
            table.add_column("Count", style="white")
            table.add_column("Avg (ms)", style="green")
            table.add_column("Min (ms)", style="blue")
            table.add_column("Max (ms)", style="red")
            
            for name, stats in report.items():
                if 'avg' in stats:
                    table.add_row(
                        name,
                        str(stats.get('count', 0)),
                        f"{stats.get('avg', 0):.2f}",
                        f"{stats.get('min', 0):.2f}",
                        f"{stats.get('max', 0):.2f}"
                    )
                else:
                    table.add_row(name, str(stats.get('count', 0)), "-", "-", "-")
            
            console.print(table)
            return 0
        
        # Detect headless environments to avoid PyQt crashes.
        force_console = args.no_tray
        if not force_console and not is_gui_available():
            console.print("[yellow]GUI/Display environment not detected. Forcing console-only mode.[/yellow]")
            force_console = True
            
        # Try starting PyQt6 Tray app.
        if not force_console:
            try:
                from PyQt6.QtWidgets import QApplication
                from src.ui.tray_app import TrayApp
                
                app = QApplication(sys.argv)
                app.setQuitOnLastWindowClosed(False)
                
                tray = TrayApp(guardian, web_port=args.port if args.web else None)
                console.print("[green]System tray active[/green]")
                console.print("[dim]Press Ctrl+C inside terminal to quit[/dim]")
                
                # Execute Qt loop
                sys.exit(app.exec())
                
            except ImportError:
                console.print("[yellow]PyQt6 not installed, falling back to console mode.[/yellow]")
                force_console = True
            except Exception as qt_err:
                console.print(f"[yellow]Failed to load system tray UI: {qt_err}. Falling back to console.[/yellow]")
                force_console = True
                
        # Console Mode TUI loop if tray is explicitly disabled or failed to load.
        if force_console:
            console.print("[green]Monitoring active (Console Mode)[/green]")
            show_status(guardian)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user. Cleaning up.[/yellow]")
    finally:
        # Guarantee resources are liberated securely.
        console.print("[yellow]Shutting down modules.[/yellow]")
        if guardian:
            guardian.stop()
        if web_server:
            try:
                web_server.stop()
            except Exception as ws_err:
                logger.error(f"Failed to cleanly stop web-server: {ws_err}")
        console.print("[green]Clean shutdown completed.[/green]")
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
