#!/usr/bin/env python3
"""
FocusGuardian — полная версия.
Видео + MediaPipe (поза + лицо) + аналитика + уведомления + отчёты.
"""

import cv2
import time
import json
import threading
from datetime import datetime
from flask import Flask, Response, jsonify, render_template_string

# MediaPipe
import mediapipe as mp

# ==================== КОНФИГУРАЦИЯ ====================
CAMERA_ID = 2
PORT = 5000
HOST = '0.0.0.0'

# ==================== ИНИЦИАЛИЗАЦИЯ ====================
print("📷 Запуск камеры...")
cap = cv2.VideoCapture(CAMERA_ID)
if not cap.isOpened():
    print(f"❌ Камера {CAMERA_ID} не открылась")
    exit(1)

print("🧠 Загрузка MediaPipe...")
mp_pose = mp.solutions.pose
mp_face = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils

pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=0,
    enable_segmentation=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

face_mesh = mp_face.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# ==================== СОСТОЯНИЕ ====================
class State:
    def __init__(self):
        self.frame = None
        self.frame_lock = threading.Lock()
        
        # Поза
        self.spine_angle = 0.0
        self.is_slouching = False
        self.slouch_severity = 'good'  # good, warning, critical
        
        # Глаза
        self.blink_count = 0
        self.ear = 0.0
        self.is_eyes_closed = False
        
        # Сессия
        self.session_start = datetime.now()
        self.total_slouches = 0
        self.total_blinks = 0
        self.fps = 0
        
        # Уведомления
        self.last_notification = 0
        self.notification_cooldown = 5  # секунд

state = State()

# ==================== ФУНКЦИИ АНАЛИТИКИ ====================
def calculate_angle(a, b, c):
    """Угол между тремя точками."""
    import numpy as np
    a = np.array([a.x, a.y])
    b = np.array([b.x, b.y])
    c = np.array([c.x, c.y])
    
    ba = a - b
    bc = c - b
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
    return np.degrees(angle)

def calculate_ear(eye_points):
    """Eye Aspect Ratio."""
    import numpy as np
    p1, p2, p3, p4, p5, p6 = eye_points
    ear = (np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)) / (2.0 * np.linalg.norm(p1 - p4) + 1e-6)
    return ear

def process_frame(frame):
    """Обработка одного кадра."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Поза
    pose_results = pose.process(rgb)
    face_results = face_mesh.process(rgb)
    
    output = frame.copy()
    
    # === ПОЗА ===
    if pose_results.pose_landmarks:
        landmarks = pose_results.pose_landmarks.landmark
        
        # Рисуем скелет
        mp_drawing.draw_landmarks(
            output, pose_results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
            mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
            mp_drawing.DrawingSpec(color=(0, 255, 255), thickness=2)
        )
        
        # Анализ осанки
        try:
            # Плечи (11, 12) и бёдра (23, 24)
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            left_hip = landmarks[23]
            right_hip = landmarks[24]
            
            # Центры
            shoulder_center = mp_pose.PoseLandmark(
                x=(left_shoulder.x + right_shoulder.x)/2,
                y=(left_shoulder.y + right_shoulder.y)/2,
                z=0
            )
            hip_center = mp_pose.PoseLandmark(
                x=(left_hip.x + right_hip.x)/2,
                y=(left_hip.y + right_hip.y)/2,
                z=0
            )
            
            # Угол позвоночника (от вертикали)
            angle = calculate_angle(
                shoulder_center,
                hip_center,
                mp_pose.PoseLandmark(x=shoulder_center.x, y=0, z=0)
            )
            
            state.spine_angle = angle
            state.is_slouching = angle > 15
            
            if angle > 25:
                state.slouch_severity = 'critical'
            elif angle > 15:
                state.slouch_severity = 'warning'
            else:
                state.slouch_severity = 'good'
            
            if state.is_slouching:
                state.total_slouches += 1
                
                # Уведомление
                now = time.time()
                if now - state.last_notification > state.notification_cooldown:
                    state.last_notification = now
                    msg = f"⚠️ Сутулость! Угол: {angle:.1f}°"
                    if state.slouch_severity == 'critical':
                        msg += " — СРОЧНО ВЫПРЯМИСЬ!"
                    print(f"[УВЕДОМЛЕНИЕ] {msg}")
            
            # Показываем угол
            color = (0, 255, 0) if not state.is_slouching else (0, 0, 255)
            cv2.putText(output, f"Угол: {angle:.1f}°", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            
            # Статус
            status = "✅ Хорошо" if not state.is_slouching else "⚠️ Сутулишься!"
            if state.slouch_severity == 'critical':
                status = "🚨 КРИТИЧЕСКИ!"
            cv2.putText(output, status, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
        except Exception as e:
            pass
    
    # === ГЛАЗА ===
    if face_results.multi_face_landmarks:
        face = face_results.multi_face_landmarks[0]
        landmarks = face.landmark
        
        # Индексы глаз (MediaPipe Face Mesh)
        LEFT_EYE = [33, 133, 157, 158, 159, 160, 161, 246]
        RIGHT_EYE = [362, 263, 387, 386, 385, 384, 398, 466]
        
        try:
            # Левый глаз
            left_pts = [(landmarks[i].x, landmarks[i].y) for i in LEFT_EYE[:6]]
            left_ear = calculate_ear([np.array(p) for p in left_pts])
            
            # Правый глаз
            right_pts = [(landmarks[i].x, landmarks[i].y) for i in RIGHT_EYE[:6]]
            right_ear = calculate_ear([np.array(p) for p in right_pts])
            
            ear = (left_ear + right_ear) / 2
            state.ear = ear
            
            # Детекция моргания
            if ear < 0.2:
                state.is_eyes_closed = True
                state.total_blinks += 1
            else:
                state.is_eyes_closed = False
            
            cv2.putText(output, f"EAR: {ear:.2f}", (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            cv2.putText(output, f"Моргания: {state.total_blinks}", (10, 120),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
        except Exception as e:
            pass
    
    return output

# ==================== ПОТОК ЗАХВАТА ====================
def capture_loop():
    frame_count = 0
    fps_start = time.time()
    
    while True:
        ret, raw = cap.read()
        if not ret:
            time.sleep(0.01)
            continue
        
        # Обработка
        processed = process_frame(raw)
        
        # FPS
        frame_count += 1
        if time.time() - fps_start >= 1.0:
            state.fps = frame_count
            frame_count = 0
            fps_start = time.time()
        
        # Сохраняем кадр
        with state.frame_lock:
            state.frame = processed
        
        time.sleep(0.01)

# Запускаем захват
threading.Thread(target=capture_loop, daemon=True).start()

# ==================== ВЕБ-СЕРВЕР ====================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>FocusGuardian</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial; background: #0f0f1a; color: #e0e0e0; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #00ff88; }
        .video-container { background: #1a1a2e; border-radius: 16px; padding: 20px; margin: 20px 0; }
        .video-container img { width: 100%; border-radius: 8px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 20px 0; }
        .stat-card { background: #1a1a2e; padding: 15px; border-radius: 12px; text-align: center; border: 1px solid #2a2a3e; }
        .stat-value { font-size: 28px; font-weight: bold; color: #00ff88; }
        .stat-label { color: #8888aa; font-size: 12px; text-transform: uppercase; }
        .badge-good { background: #00ff88; color: #000; padding: 4px 12px; border-radius: 20px; }
        .badge-warning { background: #ffdd00; color: #000; padding: 4px 12px; border-radius: 20px; }
        .badge-critical { background: #ff0044; color: #fff; padding: 4px 12px; border-radius: 20px; }
        button { background: #2a2a3e; color: #e0e0e0; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; }
        button:hover { background: #3a3a5e; }
        .report { background: #1a1a2e; padding: 20px; border-radius: 12px; margin-top: 20px; border: 1px solid #2a2a3e; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧘 FocusGuardian</h1>
        <p>AI-ассистент для контроля осанки и усталости глаз</p>
        
        <div class="video-container">
            <img src="/video" alt="Video stream">
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value" id="angle">--</div>
                <div class="stat-label">Угол (°)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="status">--</div>
                <div class="stat-label">Статус</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="blinks">--</div>
                <div class="stat-label">Моргания</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="slouches">--</div>
                <div class="stat-label">Сутулости</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="fps">--</div>
                <div class="stat-label">FPS</div>
            </div>
        </div>
        
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            <button onclick="generateReport()">📊 Отчёт</button>
            <button onclick="resetSession()">🔄 Сброс</button>
        </div>
        
        <div id="report-container"></div>
        
        <div style="margin-top: 20px; font-size: 12px; color: #666;">
            🔒 Все вычисления производятся локально. Данные не передаются в облако.
        </div>
    </div>
    
    <script>
        function updateStats() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('angle').textContent = data.spine_angle?.toFixed(1) || '--';
                    document.getElementById('blinks').textContent = data.total_blinks || '--';
                    document.getElementById('slouches').textContent = data.total_slouches || '--';
                    document.getElementById('fps').textContent = data.fps || '--';
                    
                    const statusEl = document.getElementById('status');
                    if (data.is_slouching) {
                        if (data.slouch_severity === 'critical') {
                            statusEl.textContent = '🚨 КРИТИЧЕСКИ!';
                            statusEl.style.color = '#ff0044';
                        } else {
                            statusEl.textContent = '⚠️ Сутулишься!';
                            statusEl.style.color = '#ffdd00';
                        }
                    } else {
                        statusEl.textContent = '✅ Хорошо';
                        statusEl.style.color = '#00ff88';
                    }
                })
                .catch(() => {});
        }
        
        function generateReport() {
            fetch('/api/report')
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById('report-container');
                    container.innerHTML = `
                        <div class="report">
                            <h3>📊 Отчёт за сессию</h3>
                            <p>⏱️ Длительность: ${data.duration} мин</p>
                            <p>🧘 Сутулостей: ${data.total_slouches}</p>
                            <p>👁️ Морганий: ${data.total_blinks}</p>
                            <p>📈 Средний угол: ${data.avg_angle?.toFixed(1)}°</p>
                            <p>📊 Статус: ${data.status}</p>
                        </div>
                    `;
                });
        }
        
        function resetSession() {
            fetch('/api/reset', { method: 'POST' })
                .then(() => {
                    document.getElementById('blinks').textContent = '0';
                    document.getElementById('slouches').textContent = '0';
                    document.getElementById('report-container').innerHTML = '';
                });
        }
        
        setInterval(updateStats, 500);
        updateStats();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/video')
def video():
    def gen():
        while True:
            with state.frame_lock:
                f = state.frame.copy() if state.frame is not None else None
            if f is not None:
                _, jpg = cv2.imencode('.jpg', f)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + 
                       jpg.tobytes() + b'\r\n')
            time.sleep(0.05)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/status')
def api_status():
    return jsonify({
        'spine_angle': state.spine_angle,
        'is_slouching': state.is_slouching,
        'slouch_severity': state.slouch_severity,
        'total_blinks': state.total_blinks,
        'total_slouches': state.total_slouches,
        'fps': state.fps,
        'ear': state.ear,
        'is_eyes_closed': state.is_eyes_closed
    })

@app.route('/api/report')
def api_report():
    duration = (datetime.now() - state.session_start).seconds // 60
    return jsonify({
        'duration': duration,
        'total_slouches': state.total_slouches,
        'total_blinks': state.total_blinks,
        'avg_angle': state.spine_angle,
        'status': '✅ Хорошо' if not state.is_slouching else '⚠️ Требуется внимание'
    })

@app.route('/api/reset', methods=['POST'])
def api_reset():
    state.total_slouches = 0
    state.total_blinks = 0
    state.session_start = datetime.now()
    return jsonify({'status': 'ok'})

# ==================== ЗАПУСК ====================
print("🚀 Сервер: http://localhost:5000")
app.run(host=HOST, port=PORT, debug=False, threaded=True)
