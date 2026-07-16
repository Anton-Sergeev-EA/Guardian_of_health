"""
Guardian of health - Main Entry Point.
"""
"""
Guardian of health - Main Entry Point.
"""

import sys
import argparse
import threading
from pathlib import Path

# Add src to path.
sys.path.insert(0, str(Path(__file__).parent))

from src.app import FocusGuardian


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Guardian of health - AI Health Assistant',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                     # Console mode.
  python main.py --web               # With web interface.
  python main.py --web --port 8080   # Custom port.
  python main.py --no-voice          # Disable voice commands.
  python main.py --cam 1             # Use second camera.
        """
    )
    
    parser.add_argument('--web', action='store_true', 
                       help='Enable web interface')
    parser.add_argument('--host', default='0.0.0.0',
                       help='Web server host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000,
                       help='Web server port (default: 5000)')
    parser.add_argument('--no-tray', action='store_true',
                       help='Disable system tray')
    parser.add_argument('--no-voice', action='store_true',
                       help='Disable voice commands')
    parser.add_argument('--cam', type=int, default=0,
                       help='Camera ID (default: 0)')
    parser.add_argument('--width', type=int, default=640,
                       help='Camera width (default: 640)')
    parser.add_argument('--height', type=int, default=480,
                       help='Camera height (default: 480)')
    
    args = parser.parse_args()
    
    # Create guardian (and automatically start internal threads)
    guardian = FocusGuardian(
        cam_id=args.cam,
        width=args.width,
        height=args.height,
        enable_voice=not args.no_voice
    )
    
    # Start web interface.
    web_server = None
    if args.web:
        from src.web.server import create_web_interface
        web_server = create_web_interface(guardian, host=args.host, port=args.port)
        web_thread = threading.Thread(target=web_server.start, daemon=True)
        web_thread.start()
        print(f"Web interface: http://{args.host}:{args.port}")
    
    # Start system tray.
    if not args.no_tray:
        try:
            from PyQt6.QtWidgets import QApplication
            from src.ui.tray_app import TrayApp
            
            app = QApplication(sys.argv)
            app.setQuitOnLastWindowClosed(False)
            
            tray = TrayApp(guardian, web_port=args.port if args.web else None)
            
            print("System tray active")
            print("Press Ctrl+C to quit")
            
            sys.exit(app.exec())
            
        except ImportError as e:
            print(f"PyQt6 not installed: {e}")
            print("Running in console mode")
        except Exception as e:
            print(f"Tray error: {e}")
            print("Running in console mode")
    
    # Console mode.
    if args.no_tray:
        try:
            print("\nMonitoring active. Press Ctrl+C to stop.\n")
            while True:
                import time
                status = guardian.get_status()
                posture = status['posture']
                eyes = status['eyes']
                fatigue = status['fatigue']
                
                print(f"\r[STATS] Posture: {posture['angle']:.1f}° | "
                      f"Slouch: {posture['is_slouching']} | "
                      f"Blinks: {eyes['blinks']} | "
                      f"Fatigue: {fatigue['level']} | "
                      f"FPS: {status['fps']}", end="")
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n[SHUTDOWN] Interrupted")
        finally:
            guardian.stop()
            if web_server:
                web_server.stop()
            print("Done!")


if __name__ == "__main__":
    main()
