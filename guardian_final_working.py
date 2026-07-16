#!/usr/bin/env python3
"""
FocusGuardian — финальная рабочая версия.
Без детекции морганий (только осанка).
"""

import cv2
import time
import threading
import numpy as np
from flask import Flask, Response, jsonify
import mediapipe as mp

print("📷 Запуск камеры...")
cap = cv2.VideoCapture(1)
if not cap.isOpened():
    print("❌ Камера не открылась")
    exit(1)

print("🧠 Загрузка MediaPipe...")
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=0,
    enable_segmentation=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

frame = None
frame_lock = threading.Lock()
last_angle = 0
angle_lock = threading.Lock()

total_slouches = 0
was_slouching = False
last_notification = 0

def capture_loop():
    global frame, last_angle, total_slouches, was_slouching, last_notification
    
    while True:
        ret, raw = cap.read()
        if not ret:
            time.sleep(0.01)
            continue
        
        rgb = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
        pose_results = pose.process(rgb)
        
        output = raw.copy()
        
        if pose_results.pose_landmarks:
            mp_drawing.draw_landmarks(
                output, pose_results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                mp_drawing.DrawingSpec(color=(0, 255, 255), thickness=2)
            )
            
            landmarks = pose_results.pose_landmarks.landmark
            try:
                left_shoulder = landmarks[11]
                right_shoulder = landmarks[12]
                left_hip = landmarks[23]
                right_hip = landmarks[24]
                
                shoulder_center = [(left_shoulder.x + right_shoulder.x)/2,
                                  (left_shoulder.y + right_shoulder.y)/2]
                hip_center = [(left_hip.x + right_hip.x)/2,
                             (left_hip.y + right_hip.y)/2]
                
                dx = shoulder_center[0] - hip_center[0]
                dy = shoulder_center[1] - hip_center[1]
                angle = abs(dy / (dx + 0.001))
                angle = min(90, max(0, angle * 90))
                
                with angle_lock:
                    last_angle = angle
                
                is_slouching = angle > 15
                if is_slouching and not was_slouching:
                    total_slouches += 1
                    now = time.time()
                    if now - last_notification > 3:
                        last_notification = now
                        print(f"[УВЕДОМЛЕНИЕ] Сутулость #{total_slouches}! Угол: {angle:.1f}°")
                was_slouching = is_slouching
                
                color = (0, 255, 0) if not is_slouching else (0, 0, 255)
                cv2.putText(output, f'Angle: {angle:.1f}°', (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                cv2.putText(output, f'Slouches: {total_slouches}', (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            except:
                pass
        
        with frame_lock:
            frame = output
        
        time.sleep(0.01)

threading.Thread(target=capture_loop, daemon=True).start()

app = Flask(__name__)

@app.route('/')
def index():
    return '''
    <html>
        <head><title>FocusGuardian</title></head>
        <body style="background:#0f0f1a; color:#e0e0e0; font-family:Arial; text-align:center;">
            <h1 style="color:#00ff88;">🧘 FocusGuardian</h1>
            <p>Угол: <span id="angle">--</span>°</p>
            <p>Сутулости: <span id="slouches">--</span></p>
            <img src="/video" style="max-width:90%; border-radius:12px;">
            <script>
                setInterval(() => {
                    fetch('/api/status')
                        .then(r => r.json())
                        .then(d => {
                            document.getElementById('angle').textContent = d.angle.toFixed(1);
                            document.getElementById('slouches').textContent = d.slouches;
                        });
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

@app.route('/api/status')
def api_status():
    with angle_lock:
        return jsonify({
            'angle': last_angle,
            'slouches': total_slouches
        })

print("🚀 Сервер: http://localhost:5000")
app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
