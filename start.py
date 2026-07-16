#!/usr/bin/env python3
"""
FocusGuardian — минимальная рабочая версия.
"""

import cv2
import time
import threading
from flask import Flask, Response, render_template_string

# ========== КАМЕРА ==========
print("📷 Открываем камеру...")
cap = cv2.VideoCapture(2)  # попробуйте 0, 1, 2
if not cap.isOpened():
    print("❌ Камера не открылась. Попробуйте другой номер.")
    exit(1)
print("✅ Камера работает")

# ========== ПОТОК ВИДЕО ==========
def generate_frames():
    while True:
        ret, frame = cap.read()
        if ret:
            _, jpg = cv2.imencode('.jpg', frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + 
                   jpg.tobytes() + b'\r\n')
        else:
            time.sleep(0.01)

# ========== ВЕБ-СЕРВЕР ==========
app = Flask(__name__)

@app.route('/')
def index():
    return '''
    <h1>🧘 FocusGuardian</h1>
    <p>Видео с камеры:</p>
    <img src="/video" style="max-width: 100%;">
    '''

@app.route('/video')
def video():
    return Response(generate_frames(), 
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    print("🚀 Запуск сервера на http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
