# Guardian of Health - Architecture

## Project Structure
Guardian_of_health/
├── start.py # Web UI (video only, no ML)
├── guardian_final_working.py # Full ML: posture + slouch detection
├── guardian_web.py # ML via web interface
├── final_video.py # Video stream only
├── main.py # CLI with args (--web, --status, etc.)
├── config.yaml # App settings
├── requirements.txt # Python dependencies
├── src/
│ ├── core/
│ │ └── video_engine.cpp # C++ video capture (high perf)
│ ├── analytics/
│ │ ├── posture.py # MediaPipe pose + angle calc
│ │ ├── eye_tracker.py # Blink detection
│ │ └── fatigue.py # Fatigue level
│ ├── web/
│ │ └── server.py # Flask routes /video, /api/status
│ ├── ui/
│ │ └── tray_app.py # System tray (PyQt6)
│ ├── voice/
│ │ └── commands.py # Vosk offline STT
│ ├── config/
│ │ └── config_loader.py # YAML parser
│ └── logging/
│ └── logger.py # Logging setup
└── tests/
└── test_*.py # Unit tests
## Data Flow
Webcam → OpenCV → MediaPipe Pose → Angle Calculation → Slouch Detection → UI (Web/Console/Tray)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Video Capture | OpenCV, C++ |
| Pose Estimation | MediaPipe |
| Web Server | Flask |
| UI | PyQt6 (tray), HTML/CSS (web) |
| Voice | Vosk (offline) |
| Config | YAML |

---

## Key Modules

| Module | File | Purpose |
|--------|------|---------|
| Camera init | `guardian_final_working.py` | Auto-detects camera (0-4) |
| Pose processing | `src/analytics/posture.py` | 33 keypoints → angle |
| Slouch logic | `guardian_final_working.py` | angle > 15° → alert |
| Video streaming | `/video` route | MJPEG stream |
| Status API | `/api/status` | JSON with angle + slouches |

---

## License

MIT © Sergeev Anton Valentinovich (kavery@mail.ru)
