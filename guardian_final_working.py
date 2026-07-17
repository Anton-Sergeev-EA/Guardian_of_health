"""
FocusGuardian — рабочая версия с гарантированной передачей видео.
"""

import cv2
import time
import threading
import numpy as np
from flask import Flask, Response, jsonify
import mediapipe as mp

print("📷 Запуск камеры...")

# Автоматический поиск камеры
cap = None
for i in range(5):
    test = cv2.VideoCapture(i)
    if test.isOpened():
        cap = test
        print(f"✅ Камера {i} работает")
        break
    test.release()

if cap is None:
    print("❌ Камера не найдена")
    exit(1)

# Устанавливаем разрешение для ускорения
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

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

# Глобальные переменные
current_frame = None
frame_lock = threading.Lock()
last_angle = 0
angle_lock = threading.Lock()
total_slouches = 0
was_slouching = False
last_notification = 0
running = True

def capture_loop():
    global current_frame, last_angle, total_slouches, was_slouching, last_notification, running
    
    while running:
        ret, raw = cap.read()
        if not ret:
            time.sleep(0.01)
            continue
        
        # Обработка через MediaPipe
        rgb = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
        results = pose.process(rgb)
        
        # Создаём выходной кадр
        output = raw.copy()
        
        if results.pose_landmarks:
            # Рисуем скелет
            mp_drawing.draw_landmarks(
                output, 
                results.pose_landmarks, 
                mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                mp_drawing.DrawingSpec(color=(0, 255, 255), thickness=2)
            )
            
            # Расчёт угла
            landmarks = results.pose_landmarks.landmark
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
                
                # Проверка сутулости
                is_slouching = angle > 15
                if is_slouching and not was_slouching:
                    total_slouches += 1
                    now = time.time()
                    if now - last_notification > 3:
                        last_notification = now
                        print(f"[УВЕДОМЛЕНИЕ] Сутулость #{total_slouches}! Угол: {angle:.1f}°")
                was_slouching = is_slouching
                
                # Отображение информации
                color = (0, 255, 0) if not is_slouching else (0, 0, 255)
                cv2.putText(output, f'Angle: {angle:.1f}°', (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                cv2.putText(output, f'Slouches: {total_slouches}', (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            except Exception as e:
                pass
        
        # Сохраняем кадр
        with frame_lock:
            current_frame = output
        
        time.sleep(0.01)

# Запускаем поток
thread = threading.Thread(target=capture_loop, daemon=True)
thread.start()

# Даём время на инициализацию
time.sleep(1)

app = Flask(__name__)

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>FocusGuardian</title>
        <style>
            body { background: #0f0f1a; color: #e0e0e0; font-family: Arial; text-align: center; margin: 0; padding: 20px; }
            h1 { color: #00ff88; }
            .container { max-width: 800px; margin: 0 auto; }
            .video-container { background: #1a1a2e; border-radius: 12px; padding: 10px; border: 2px solid #00ff88; }
            img { width: 100%; border-radius: 8px; }
            .metrics { display: flex; justify-content: center; gap: 40px; margin: 20px 0; font-size: 18px; }
            .metric { background: #1a1a2e; padding: 10px 30px; border-radius: 8px; border: 1px solid #333; }
            .metric span { color: #00ff88; font-weight: bold; font-size: 24px; }
            .status { color: #888; font-size: 14px; margin-top: 10px; }
            .green { color: #00ff88; }
            .red { color: #ff4444; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧘 FocusGuardian</h1>
            <div class="metrics">
                <div class="metric">Угол: <span id="angle">--</span>°</div>
                <div class="metric">Сутулости: <span id="slouches">--</span></div>
            </div>
            <div class="video-container">
                <img src="/video" alt="Видео с камеры">
            </div>
            <p class="status">✅ Камера работает • Анализ осанки активен</p>
        </div>
        <script>
            setInterval(() => {
                fetch('/api/status')
                    .then(r => r.json())
                    .then(d => {
                        document.getElementById('angle').textContent = d.angle.toFixed(1);
                        document.getElementById('slouches').textContent = d.slouches;
                    })
                    .catch(e => console.log('Ошибка API:', e));
            }, 500);
        </script>
    </body>
    </html>
    '''

@app.route('/video')
def video():
    def generate():
        while True:
            with frame_lock:
                frame_copy = current_frame.copy() if current_frame is not None else None
            
            if frame_copy is not None:
                try:
                    ret, jpg = cv2.imencode('.jpg', frame_copy, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    if ret:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + 
                               jpg.tobytes() + b'\r\n')
                except Exception as e:
                    print(f"Ошибка отправки: {e}")
            
            time.sleep(0.03)
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/status')
def api_status():
    with angle_lock:
        return jsonify({
            'angle': last_angle,
            'slouches': total_slouches
        })

if __name__ == '__main__':
    print("🚀 Сервер запущен на http://localhost:5000")
    print("📱 Откройте этот адрес в браузере")
    print("⏹ Для остановки нажмите Ctrl+C")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
