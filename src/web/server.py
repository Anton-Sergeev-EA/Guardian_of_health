"""
Web Server for FocusGuardian - Flask + Socket.IO with multi-threading protection.
"""

import os
import sys
import time
import json
import sqlite3
import threading
import csv
import io
from pathlib import Path
from typing import Optional
import cv2
import numpy as np

from flask import Flask, render_template, Response, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# Dynamic imports with fallbacks.
try:
    from commands import VoiceCommand
except ImportError:
    try:
        from src.voice.commands import VoiceCommand
    except ImportError:
        VoiceCommand = None


class WebServer:
    """Web interface server for FocusGuardian."""
    
    def __init__(self, guardian, host: str = '0.0.0.0', port: int = 5000):
        self.guardian = guardian
        self.host = host
        self.port = port
        self.is_running = False
        
        # Resolve DB path for thread-safe local connections.
        self.db_path = getattr(self.guardian, 'db_path', 'focus_guardian.db')
        
        # Flask configuration.
        self.app = Flask(
            __name__,
            template_folder=Path(__file__).parent / 'templates',
            static_folder=Path(__file__).parent / 'static'
        )
        self.app.config['SECRET_KEY'] = 'focus-guardian-secret-key-2026'
        
        # Enable Cross-Origin Resource Sharing (CORS).
        CORS(self.app, origins='*')
        
        # Socket.IO setup.
        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins='*',
            async_mode='threading',
            ping_timeout=60
        )
        
        # Video stream parameters.
        self.streaming_enabled = True
        self.frame_skip = 2
        self.frame_quality = 75
        
        # Register API end-points and WS events.
        self._register_routes()
        self._register_events()
        
        print(f"[WEB] Server initialized at http://{host}:{port}")
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Create a thread-safe database connection for the Flask pool."""
        conn = sqlite3.connect(self.db_path)
        return conn

    def _register_routes(self):
        """Register HTTP routes."""
        
        @self.app.route('/')
        def index():
            return render_template('dashboard.html')
        
        @self.app.route('/api/status')
        def api_status():
            status = self.guardian.get_status()
            status['timestamp'] = time.time()
            return jsonify(status)
        
        @self.app.route('/api/session')
        def api_session():
            duration = 0.0
            if hasattr(self.guardian, 'session_start') and self.guardian.session_start:
                duration = (time.time() - self.guardian.session_start.timestamp()) / 60.0
                
            return jsonify({
                'session_id': getattr(self.guardian, 'session_id', 'unknown'),
                'start_time': self.guardian.session_start.isoformat() if hasattr(self.guardian, 'session_start') else None,
                'duration': duration,
                'data': getattr(self.guardian, 'session_data', {})
            })
        
        @self.app.route('/api/history')
        def api_history():
            limit = request.args.get('limit', 100, type=int)
            session_id = getattr(self.guardian, 'session_id', 'unknown')
            
            # Use thread-local DB connection.
            try:
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT timestamp, spine_angle, neck_angle, is_slouching, severity, blink_rate
                        FROM posture_logs
                        WHERE session_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                    ''', (session_id, limit))
                    rows = cursor.fetchall()
            except sqlite3.Error as e:
                return jsonify({'error': f"Database access error: {e}"}), 500
            
            history = [{
                'timestamp': r[0],
                'spine_angle': r[1],
                'neck_angle': r[2],
                'is_slouching': bool(r[3]),
                'severity': r[4],
                'blink_rate': r[5]
            } for r in rows]
            
            return jsonify(history)
        
        @self.app.route('/api/command', methods=['POST'])
        def api_command():
            data = request.get_json() or {}
            command = data.get('command', '')
            
            if command == 'pause':
                self.guardian.pause_monitoring()
                return jsonify({'status': 'paused'})
            elif command == 'resume':
                self.guardian.resume_monitoring()
                return jsonify({'status': 'resumed'})
            elif command == 'reset':
                self.guardian.reset_session()
                return jsonify({'status': 'reset'})
            elif command == 'report':
                self.guardian._generate_report()
                return jsonify({'status': 'report_generated'})
            else:
                return jsonify({'error': 'Unknown command'}), 400
        
        @self.app.route('/api/voice/command', methods=['POST'])
        def api_voice_command():
            if VoiceCommand is None:
                return jsonify({'error': 'Voice modules are not loaded'}), 500
                
            data = request.get_json() or {}
            command = data.get('command', '')
            
            if self.guardian.voice and self.guardian.voice.is_available():
                cmd_map = {
                    'status': VoiceCommand.STATUS,
                    'pause': VoiceCommand.PAUSE,
                    'resume': VoiceCommand.RESUME,
                    'report': VoiceCommand.REPORT,
                    'reset': VoiceCommand.RESET,
                    'quit': VoiceCommand.QUIT,
                    'help': VoiceCommand.HELP,
                    'break': VoiceCommand.BREAK,
                    'continue': VoiceCommand.CONTINUE,
                    'calibrate': VoiceCommand.CALIBRATE,
                    'posture': VoiceCommand.POSTURE,
                    'blinks': VoiceCommand.BLINKS
                }
                
                if command in cmd_map:
                    self.guardian._handle_voice_command(cmd_map[command], command)
                    return jsonify({'status': 'command_processed', 'command': command})
            
            return jsonify({'error': 'Voice command unavailable'}), 400
        
        @self.app.route('/api/stream')
        def video_feed():
            return Response(
                self._generate_frames(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )
        
        @self.app.route('/api/export')
        def export_data():
            limit = request.args.get('limit', 1000, type=int)
            session_id = getattr(self.guardian, 'session_id', 'unknown')
            
            # Query from safe connection.
            try:
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id, timestamp, spine_angle, neck_angle, 
                               is_slouching, severity, blink_rate, session_id 
                        FROM posture_logs
                        WHERE session_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                    ''', (session_id, limit))
                    rows = cursor.fetchall()
            except sqlite3.Error as e:
                return Response(f"Database error: {e}", status=500)
            
            columns = ['id', 'timestamp', 'spine_angle', 'neck_angle', 
                       'is_slouching', 'severity', 'blink_rate', 'session_id']
            
            # Fast in-memory CSV generation without Pandas.
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)
            writer.writerows(rows)
            
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename=focus-guardian-export-{int(time.time())}.csv'
                }
            )
    
    def _register_events(self):
        """Register Socket.IO events."""
        
        @self.socketio.on('connect')
        def handle_connect():
            print(f"[WS] Client connected: {request.sid}")
            emit('connected', {'message': 'Connected to FocusGuardian'})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            print(f"[WS] Client disconnected: {request.sid}")
        
        @self.socketio.on('subscribe')
        def handle_subscribe(data):
            channels = data.get('channels', ['status'])
            emit('subscribed', {'channels': channels})
        
        @self.socketio.on('command')
        def handle_command(data):
            command = data.get('command', '')
            
            if command == 'pause':
                self.guardian.pause_monitoring()
                emit('command_result', {'status': 'paused'})
            elif command == 'resume':
                self.guardian.resume_monitoring()
                emit('command_result', {'status': 'resumed'})
            else:
                emit('command_result', {'error': 'Unknown command'})
    
    def _generate_frames(self):
        """Generate MJPEG frames with optimized CPU usage and frame-skipping."""
        frame_counter = 0
        
        while self.is_running:
            if not self.streaming_enabled:
                time.sleep(0.1)
                continue
            
            frame_counter += 1
            if frame_counter % self.frame_skip != 0:
                time.sleep(0.01)  # Balanced sleep interval to prevent high CPU loads.
                continue
            
            try:
                frame = getattr(self.guardian, 'last_frame', None)
                if frame is None or frame.size == 0:
                    time.sleep(0.03)  # Wait for a new frame from webcam loop.
                    continue
                
                # Convert to displayable BGR format safely.
                display_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # Encode frame as JPEG.
                ret, jpeg = cv2.imencode('.jpg', display_frame, [
                    cv2.IMWRITE_JPEG_QUALITY, self.frame_quality
                ])
                
                if ret:
                    yield (b'--frame\r\n'
                          b'Content-Type: image/jpeg\r\n\r\n' +
                          jpeg.tobytes() + b'\r\n')
                
            except Exception as e:
                print(f"[VIDEO] Stream generator processing error: {e}")
                time.sleep(0.1)
    
    def _emit_status(self):
        """Background thread for continuous WebSocket status updates."""
        while self.is_running:
            try:
                status = self.guardian.get_status()
                self.socketio.emit('status_update', status)
            except Exception as e:
                print(f"[WS] Emission thread error: {e}")
            time.sleep(0.5)
    
    def start(self):
        """Start Flask-SocketIO background server execution."""
        self.is_running = True
        
        # Launch websocket dispatcher daemon.
        status_thread = threading.Thread(target=self._emit_status, daemon=True)
        status_thread.start()
        
        print(f"[WEB] Starting server at http://{self.host}:{self.port}")
        self.socketio.run(
            self.app,
            host=self.host,
            port=self.port,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
    
    def stop(self):
        """Stop background execution and thread runners."""
        self.is_running = False
        print("[WEB] Server stopped")


def create_web_interface(guardian, host: str = '0.0.0.0', port: int = 5000) -> WebServer:
    """Factory builder for FocusGuardian WebServer interface."""
    return WebServer(guardian, host, port)