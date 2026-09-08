from flask import Flask, render_template, Response, request, jsonify
from flask_cors import CORS
import cv2
import csv
import io
import time
from datetime import datetime


class WebServer:
    def __init__(self, guardian, host='0.0.0.0', port=5000):
        self.guardian = guardian
        self.host = host
        self.port = port
        
        self.app = Flask(__name__, template_folder='templates', static_folder='static')
        CORS(self.app)
        
        @self.app.route('/')
        def index():
            return render_template('dashboard.html')
        
        @self.app.route('/api/stream')
        def video():
            return Response(self._generate(), 
                          mimetype='multipart/x-mixed-replace; boundary=frame')

        @self.app.route('/api/status')
        def status():
            return jsonify(self._status_payload())

        @self.app.route('/api/history')
        def history():
            limit = request.args.get('limit', 50, type=int)
            return jsonify(self._history_rows(limit))

        @self.app.route('/api/command', methods=['POST'])
        def command():
            body = request.get_json(silent=True) or {}
            cmd = body.get('command')
            if cmd == 'pause':
                self.guardian.pause_monitoring()
                return jsonify({'status': 'paused'})
            elif cmd == 'resume':
                self.guardian.resume_monitoring()
                return jsonify({'status': 'resumed'})
            elif cmd == 'report':
                self.guardian._generate_report()
                return jsonify({'status': 'report_generated'})
            return jsonify({'error': f'Unknown command: {cmd}'}), 400

        @self.app.route('/api/voice/command', methods=['POST'])
        def voice_command():
            # Drives the dashboard's manual command buttons through the same
            # actions the real voice commands trigger (see
            # FocusGuardian._handle_voice_command in src/app.py) - not tied
            # to the microphone, so these work even with voice unavailable.
            body = request.get_json(silent=True) or {}
            cmd_name = body.get('command')
            handlers = {
                'status': lambda: self.guardian.get_status(),
                'pause': self.guardian.pause_monitoring,
                'resume': self.guardian.resume_monitoring,
                'report': self.guardian._generate_report,
                'reset': self.guardian.reset_session,
                'help': lambda: None,
            }
            handler = handlers.get(cmd_name)
            if handler is None:
                return jsonify({'error': f'Unknown command: {cmd_name}'}), 400
            handler()
            return jsonify({'status': 'command_processed', 'command': cmd_name})

        @self.app.route('/api/export')
        def export():
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['timestamp', 'spine_angle', 'neck_angle', 'shoulder_angle',
                              'is_slouching', 'severity', 'blink_rate', 'fatigue_level'])
            if self.guardian.conn:
                cursor = self.guardian.conn.execute(
                    '''SELECT timestamp, spine_angle, neck_angle, shoulder_angle,
                              is_slouching, severity, blink_rate, fatigue_level
                       FROM posture_logs WHERE session_id = ? ORDER BY id''',
                    (self.guardian.session_id,)
                )
                writer.writerows(cursor.fetchall())
            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=session_{self.guardian.session_id}.csv'}
            )
        
        print(f'[WEB] Сервер готов: http://{host}:{port}')

    def _status_payload(self):
        data = self.guardian.get_status()
        # dashboard.js reads a top-level `session_id`, and treats `timestamp`
        # as the session's *start* time (it computes uptime as
        # Date.now() - timestamp*1000) rather than the current server time
        # get_status() puts there under that same key.
        data['session_id'] = data['session']['id']
        data['timestamp'] = data['session_start_ts']
        return data

    def _history_rows(self, limit: int):
        rows = []
        if not self.guardian.conn:
            return rows
        cursor = self.guardian.conn.execute(
            '''SELECT timestamp, spine_angle, neck_angle FROM posture_logs
               WHERE session_id = ? ORDER BY id DESC LIMIT ?''',
            (self.guardian.session_id, limit)
        )
        for ts, spine_angle, neck_angle in cursor.fetchall():
            # Stored as datetime.now().isoformat() text (see
            # FocusGuardian._queue_db_log), but the dashboard chart expects a
            # numeric Unix epoch (it does `item.timestamp * 1000`).
            try:
                epoch = datetime.fromisoformat(ts).timestamp()
            except (TypeError, ValueError):
                epoch = time.time()
            rows.append({
                'timestamp': epoch,
                'spine_angle': spine_angle,
                'neck_angle': neck_angle,
            })
        return rows

    def _generate(self):
        while True:
            frame = self.guardian.last_frame
            if frame is not None and frame.size > 0:
                try:
                    bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    _, jpg = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    yield (b'--frame\r\n'
                          b'Content-Type: image/jpeg\r\n\r\n' + 
                          jpg.tobytes() + b'\r\n')
                except Exception as e:
                    print(f'[VIDEO] Ошибка: {e}')
            time.sleep(0.05)
    
    def start(self):
        print(f'[WEB] Запуск на http://{self.host}:{self.port}')
        self.app.run(host=self.host, port=self.port, debug=False, threaded=True)

def create_web_interface(guardian, host='0.0.0.0', port=5000):
    return WebServer(guardian, host, port)
