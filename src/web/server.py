from flask import Flask, render_template, Response
from flask_cors import CORS
import cv2
import time

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
        
        print(f'[WEB] Сервер готов: http://{host}:{port}')
    
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
