#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <opencv2/opencv.hpp>
#include <opencv2/videoio.hpp>
#include <atomic>
#include <thread>
#include <mutex>
#include <chrono>
#include <vector>
#include <stdexcept>

namespace py = pybind11;

class VideoEngine {
private:
    cv::VideoCapture cap;
    cv::Mat frame_rgb;
    std::mutex mtx;
    std::atomic<bool> is_running;
    std::thread capture_thread;
    std::atomic<int> fps;
    int width;
    int height;
    int camera_id;
    
public:
    VideoEngine(int cam_id = 0, int w = 640, int h = 480) 
        : camera_id(cam_id), width(w), height(h), is_running(false), fps(0) {
        
        // Open the camera with platform-agnostic optimizations.
        cap.open(cam_id, cv::CAP_ANY);
        if (!cap.isOpened()) {
            throw std::runtime_error("Failed to open camera with ID: " + std::to_string(cam_id));
        }
        
        // Configure acquisition parameters for low latency.
        cap.set(cv::CAP_PROP_FRAME_WIDTH, w);
        cap.set(cv::CAP_PROP_FRAME_HEIGHT, h);
        cap.set(cv::CAP_PROP_FPS, 30);
        
        // Enforce MJPEG codec for high-bandwidth/high-FPS capture.
        cap.set(cv::CAP_PROP_FOURCC, cv::VideoWriter::fourcc('M', 'J', 'P', 'G'));
        
        // Pre-allocate frame buffers
        frame_rgb = cv::Mat::zeros(h, w, CV_8UC3);
        
        // Verify actual hardware-negotiated resolution.
        int actual_w = static_cast<int>(cap.get(cv::CAP_PROP_FRAME_WIDTH));
        int actual_h = static_cast<int>(cap.get(cv::CAP_PROP_FRAME_HEIGHT));
        if (actual_w > 0 && actual_h > 0) {
            width = actual_w;
            height = actual_h;
            frame_rgb = cv::Mat::zeros(height, width, CV_8UC3);
        }
    }
    
    ~VideoEngine() {
        stop();
    }
    
    void start() {
        if (is_running) return;
        is_running = true;
        fps = 0;
        capture_thread = std::thread(&VideoEngine::capture_loop, this);
    }
    
    void stop() {
        if (!is_running) return;
        is_running = false;
        if (capture_thread.joinable()) {
            capture_thread.join();
        }
        if (cap.isOpened()) {
            cap.release();
        }
    }
    
    py::array_t<uint8_t> get_frame() {
        std::lock_guard<std::mutex> lock(mtx);
        
        if (frame_rgb.empty()) {
            // Return a fallback black frame if no data has been captured yet.
            cv::Mat black = cv::Mat::zeros(height, width, CV_8UC3);
            return py::array_t<uint8_t>(
                {height, width, 3},
                {static_cast<py::ssize_t>(width * 3), 3, 1},
                black.data
            );
        }
        
        // Safe Zero-Copy: Create a heap-allocated copy of the cv::Mat header.
        // This increments OpenCV's internal reference counter for the pixel buffer.
        // The capsule ensures the memory is released only when Python garbage-collects the numpy array.
        auto* kept_alive_frame = new cv::Mat(frame_rgb);
        
        auto capsule = py::capsule(kept_alive_frame, [](void* ptr) noexcept {
            delete reinterpret_cast<cv::Mat*>(ptr);
        });
        
        return py::array_t<uint8_t>(
            {kept_alive_frame->rows, kept_alive_frame->cols, 3},
            {static_cast<py::ssize_t>(kept_alive_frame->step[0]), 
             static_cast<py::ssize_t>(kept_alive_frame->step[1]), 
             static_cast<py::ssize_t>(kept_alive_frame->step[2])},
            kept_alive_frame->data,
            capsule
        );
    }
    
    int get_fps() const noexcept { return fps.load(); }
    int get_width() const noexcept { return width; }
    int get_height() const noexcept { return height; }
    bool is_opened() const noexcept { return cap.isOpened() && is_running.load(); }
    
private:
    void capture_loop() {
        int frame_count = 0;
        auto start_time = std::chrono::steady_clock::now();
        
        cv::Mat raw_frame;
        cv::Mat processed_bgr;
        cv::Mat processed_rgb;
        
        while (is_running) {
            if (!cap.read(raw_frame) || raw_frame.empty()) {
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
                continue;
            }
            
            // Handle resizing if the camera feed doesn't match requested dimensions.
            if (raw_frame.cols != width || raw_frame.rows != height) {
                cv::resize(raw_frame, processed_bgr, cv::Size(width, height), 0, 0, cv::INTER_NEAREST);
            } else {
                processed_bgr = raw_frame;
            }
            
            // Convert BGR to RGB (required for models like MediaPipe).
            cv::cvtColor(processed_bgr, processed_rgb, cv::COLOR_BGR2RGB);
            
            // Thread-safe swap of the active frame buffer.
            {
                std::lock_guard<std::mutex> lock(mtx);
                frame_rgb = std::move(processed_rgb);
            }
            
            // Calculate metrics (FPS calculated once per second).
            frame_count++;
            auto now = std::chrono::steady_clock::now();
            auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - start_time).count();
            
            if (elapsed >= 1000) {
                fps = frame_count;
                frame_count = 0;
                start_time = now;
            }
            
            // Relinquish timeslice to prevent CPU starvation.
            std::this_thread::sleep_for(std::chrono::microseconds(100));
        }
    }
};

// Pybind11 Module Bindings.
PYBIND11_MODULE(video_engine, m) {
    m.doc() = "FocusGuardian C++ High-Performance Video Capture Engine";

    py::class_<VideoEngine>(m, "VideoEngine")
        .def(py::init<int, int, int>(), 
             py::arg("cam_id") = 0, 
             py::arg("width") = 640, 
             py::arg("height") = 480,
             "Initialize the video capture engine with target camera ID and resolution.")
        .def("start", &VideoEngine::start, "Start the background frame capture thread.")
        .def("stop", &VideoEngine::stop, "Stop the background frame capture thread.")
        .def("get_frame", &VideoEngine::get_frame, 
             "Retrieve the latest captured frame as a NumPy array (zero-copy memory sharing).")
        .def("get_fps", &VideoEngine::get_fps, "Get the current operating frame rate (FPS).")
        .def("get_width", &VideoEngine::get_width, "Get frame width.")
        .def("get_height", &VideoEngine::get_height, "Get frame height.")
        .def("is_opened", &VideoEngine::is_opened, "Check if the camera acquisition is actively running.");
    
    m.attr("__version__") = "2.0.0";
}
