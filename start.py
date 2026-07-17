import cv2
import time
import threading
from flask import Flask, Response, render_template_string

# ========== КАМЕРА ==========
print("Открываем камеру")

camera_indexes = [0, 1]  # пробуем камеры 0 и 1 по очереди.
cap = None

for idx in camera_indexes:
    print(f"Пробуем камеру {idx}...")
    test_cap = cv2.VideoCapture(idx)
    if test_cap.isOpened():
        cap = test_cap
        print(f"✅ Камера {idx} работает")
        break
    else:
        test_cap.release()

if cap is None or not cap.isOpened():
    print("❌ Ни одна камера не открылась. Проверьте подключение камеры.")
    exit(1)

# ========== ПОТОК ВИДЕО ==========
def generate_frames():
    while True:
        ret, frame = cap.read()
        if ret:
            # Добавляем небольшое сообщение на кадр (опционально)
            cv2.putText(frame, "FocusGuardian", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
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
    <!DOCTYPE html>
    <html>
    <head>
        <title>FocusGuardian</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 20px; background: #f0f0f0; }
            h1 { color: #2c3e50; }
            .container { background: white; padding: 20px; border-radius: 10px; max-width: 800px; margin: 0 auto; }
            img { max-width: 100%; border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .status { color: #27ae60; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Guardian_of_health</h1>
            <p>Видео с камеры:</p>
            <img src="/video" alt="Видео с камеры">
            <p class="status">✅ Камера работает</p>
        </div>
    </body>
    </html>
    '''

@app.route('/video')
def video():
    return Response(generate_frames(), 
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("Запуск сервера на http://localhost:5000")
    print("Откройте этот адрес в браузере")
    print("Для остановки нажмите Ctrl+C")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
