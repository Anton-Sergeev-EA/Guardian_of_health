from flask import Flask, Response
import cv2
import time

app = Flask(__name__)
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

@app.route('/')
def index():
    return '''
    <html>
        <body>
            <h1>Видео</h1>
            <img src="/video" style="max-width: 100%;">
        </body>
    </html>
    '''

@app.route('/video')
def video():
    def gen():
        while True:
            ret, frame = cap.read()
            if ret:
                _, jpg = cv2.imencode('.jpg', frame)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + 
                       jpg.tobytes() + b'\r\n')
            else:
                time.sleep(0.01)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

app.run(host='0.0.0.0', port=5000, debug=False)
