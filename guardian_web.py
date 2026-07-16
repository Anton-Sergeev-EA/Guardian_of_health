#!/usr/bin/env python3
"""
FocusGuardian с MediaPipe — пошаговое добавление.
"""

import cv2
import time
import threading
from flask import Flask, Response, jsonify

# MediaPipe
import mediapipe as mp

# ==================== ИНИЦИАЛИЗАЦИЯ ====================
print("📷 Запуск камеры...")
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("❌ Камера не открылась")
    exit(1)

print("🧠 Загрузка MediaPipe...")
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=0,  # 0 = lite (быстро)
    enable_segmentation=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# ==================== ПОТОК ВИДЕО ====================
frame = None
frame_lock = threading.Lock()
last_angle = 0
angle_lock = threading.Lock()

def capture_loop():
    global frame, last_angle
    while True:
        ret, raw = cap.read()
        if not ret:
            time.sleep(0.01)
            continue
        
        # Обработка через MediaPipe
        rgb = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)
        
        # Рисуем скелет
        output = raw.copy()
        if results.pose_landmarks:
            mp.solutions.drawing_utils.draw_landmarks(
                output, results.pose_landmarks, mp_pose.POSE_CONNECTIONS)
            
            # Считаем угол (примерно)
            landmarks = results.pose_landmarks.landmark
            try:
                # Плечи (11, 12) и бёдра (23, 24)
                left_shoulder = landmarks[11]
                right_shoulder = landmarks[12]
                left_hip = landmarks[23]
                right_hip = landmarks[24]
                
                # Центр плеч и бёдер
                shoulder_center = [(left_shoulder.x + right_shoulder.x)/2,
                                  (left_shoulder.y + right_shoulder.y)/2]
                hip_center = [(left_hip.x + right_hip.x)/2,
                             (left_hip.y + right_hip.y)/2]
                
                # Угол (упрощённо)
                dx = shoulder_center[0] - hip_center[0]
                dy = shoulder_center[1] - hip_center[1]
                angle = abs(dy / (dx + 0.001))
                angle = min(90, max(0, angle * 90))
                
                with angle_lock:
                    last_angle = angle
                
                # Показываем угол на видео
                cv2.putText(output, f'Angle: {angle:.1f}°', (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            except:
                pass
        
        # Сохраняем кадр
        with frame_lock:
            frame = output
        
        time.sleep(0.01)

# Запускаем захват в фоне
threading.Thread(target=capture_loop, daemon=True).start()

# ==================== ВЕБ-СЕРВЕР ====================
app = Flask(__name__)

@app.route('/')
def index():
    return '''
    <html>
        <head><title>FocusGuardian</title></head>
        <body style="background:#0f0f1a; color:#e0e0e0; font-family:Arial; text-align:center;">
            <h1 style="color:#00ff88;">🧘 FocusGuardian</h1>
            <p>Угол: <span id="angle">--</span>°</p>
            <img src="/video" style="max-width:90%; border-radius:12px;">
            <script>
                setInterval(() => {
                    fetch('/api/angle')
                        .then(r => r.json())
                        .then(d => document.getElementById('angle').textContent = d.angle.toFixed(1));
                }, 500);
            </script>
        </body>
    </html>
    '''

@app.route('/video')
def video():
    def gen():
        while True:
            with frame_lock:
                f = frame.copy() if frame is not None else None
            if f is not None:
                _, jpg = cv2.imencode('.jpg', f)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + 
                       jpg.tobytes() + b'\r\n')
            time.sleep(0.05)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/angle')
def api_angle():
    with angle_lock:
        return jsonify({'angle': last_angle})

# ==================== ЗАПУСК ====================
print("🚀 Сервер: http://localhost:5000")
app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
