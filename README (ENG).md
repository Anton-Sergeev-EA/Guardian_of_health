# Guardian of Health.
A local, private AI assistant that analyzes your webcam video stream in real-time to prevent digital 
fatigue (eye strain, slouching) and burnout without sending your video to the cloud.

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

---
## Features.
- Real-time video analysis — uses your webcam to track posture.
- AI-powered pose estimation — MediaPipe detects 33 body keypoints.
- Posture angle calculation — measures slouching in real-time.
- Smart notifications — alerts when you slouch (console + visual).
- 100% private — all processing is done locally, no data leaves your computer.
- Web interface — view your posture stats in any browser.
- Voice commands (optional) — control the app hands-free.
- Slouch counter — track how many times you've slouched.

---
## Quick Start.
### Prerequisites.

- Python 3.12+ ([Download](https://www.python.org/downloads/))
- Webcam (built-in or external)
- Git ([Download](https://git-scm.com/downloads))

### Installation.
# 1. Clone the repository.
git clone https://github.com/Anton-Sergeev-EA/Guardian_of_health.git
cd Guardian_of_health
# 2. Create and activate virtual environment.
python -m venv venv
source venv/bin/activate      # On Linux/macOS
venv\Scripts\activate         # On Windows
# 3. Install dependencies.
pip install -r requirements.txt
# 4. Run the application.
python guardian_final_working.py

# Usage.
1. Open your browser and go to http://localhost:5000.
2. Allow camera access when prompted.
3. Sit in front of your webcam.
4. View your posture angle and slouch count in real-time.

# Available Versions.
File	                      Description	                                        Command
guardian_final_working.py	  Full ML version — posture analysis + notifications	python guardian_final_working.py
guardian_web.py	              ML version with web interface	                        python guardian_web.py
start.py	                  Simple video stream (no ML)	                        python start.py
final_video.py	              Minimal video stream	                                python final_video.py
main.py	                      CLI with arguments (--web, --status, etc.)	        python main.py --web

# Screenshots.
Web Interface
+------------------------------------------+
|        Guardian_of_health                    |
|        Angle: 23.5°  Slouches: 3           |
|        +------------------------------+    |
|        |    [Live Video Feed]         |    |
|        |    ⚠️ Slouch detected!       |    |
|        +------------------------------+    |
|        ✅ Camera working                   |
+------------------------------------------+
# Console Notifications.

[УВЕДОМЛЕНИЕ] Сутулость #1! Угол: 25.3°
[УВЕДОМЛЕНИЕ] Сутулость #2! Угол: 30.1°

# Architecture.
Webcam → OpenCV → MediaPipe Pose → Angle Calculation → Slouch Detection → UI (Web/Console)

# Key components:
- Video Capture: OpenCV (C++ engine for performance)
- Pose Estimation: MediaPipe (33 keypoints)
- Web Server: Flask (MJPEG streaming + REST API)
- UI: HTML/CSS + JavaScript (auto-updating stats)

# Configuration.
Edit config.yaml to adjust:
yaml
posture:
  slouch_threshold: 15      # Angle in degrees
  notification_cooldown: 3  # Seconds between alerts

camera:
  width: 640
  height: 480
  fps: 30

# Dependencies.
- opencv-python — video capture and processing.
- mediapipe — pose estimation.
- flask — web server.
- numpy — calculations.
- pyyaml — configuration.
- pytest — testing.
Full list: requirements.txt.

# Contributing.
1. Fork the repository.
2. Create your feature branch (git checkout -b feature/amazing-feature).
3. Commit your changes (git commit -m 'Add some amazing feature').
4. Push to the branch (git push origin feature/amazing-feature).
5. Open a Pull Request.

# License.
Distributed under the MIT License.

Author: Sergeev Anton Valentinovich
Email: kavery@mail.ru

# Disclaimer.
This application is for informational and wellness purposes only. It is not a medical device and should not be used as a substitute for professional medical advice, diagnosis, or treatment.

# Acknowledgments.
- MediaPipe — pose estimation library.
- OpenCV — computer vision.
- Flask — web framework.
- Made with for better posture and health.
