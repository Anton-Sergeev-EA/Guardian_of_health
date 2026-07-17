"""
Fatigue Detector - Monitors overall fatigue and productivity.
"""

import time
from dataclasses import dataclass
from typing import Optional, List
from collections import deque

# Import metrics for type hinting.
from .eye_tracker import EyeMetrics
from .posture_analyzer import PostureMetrics


@dataclass
class FatigueMetrics:
    """Overall fatigue and productivity metrics."""
    session_duration: int = 0  # in minutes.
    blinks_per_minute: float = 0.0
    slouch_ratio: float = 0.0  # Percentage of time spent slouching.
    eye_closure_ratio: float = 0.0  # Percentage of time eyes were closed.
    productivity_score: float = 1.0
    fatigue_level: str = 'low'  # 'low', 'medium', 'high', 'critical'.
    break_recommended: bool = False
    break_reason: str = ''


class FatigueDetector:
    """
    Detects fatigue using a sliding window approach to evaluate 
    blink frequency, slouching duration, and eye closure state over time.
    """
    
    def __init__(
        self,
        break_interval: int = 45,  # Time in minutes before recommending a break.
        window_size_sec: int = 60,  # Sliding window size to compute active rates.
        expected_fps: int = 30
    ):
        self.break_interval = break_interval
        self.window_size_sec = window_size_sec
        self.max_history_len = window_size_sec * expected_fps
        
        # Sliding history windows to evaluate real-time state shifts.
        self.slouch_history: deque = deque(maxlen=self.max_history_len)
        self.closure_history: deque = deque(maxlen=self.max_history_len)
        self.blink_timestamps: List[float] = []
        
        # Session timing.
        self.start_time = time.time()
        self.last_break_time = time.time()
        
        # Tracks last recorded cumulative blinks to extract intervals.
        self.last_total_blinks = 0
        
        # Persist metrics to avoid returning empty states on intermediate frames.
        self.current_metrics = FatigueMetrics()
        self.last_calculation_time = 0.0

    def update(self, eye_metrics: Optional[EyeMetrics], posture_metrics: Optional[PostureMetrics]) -> FatigueMetrics:
        """
        Update fatigue metrics with new data frame.
        
        :param eye_metrics: Eye metrics from EyeTracker.
        :param posture_metrics: Posture metrics from PostureAnalyzer.
        :return: Persisted and updated FatigueMetrics object.
        """
        current_time = time.time()
        session_duration = (current_time - self.start_time) / 60.0
        
        # Append temporal frame states.
        is_slouching_frame = 1 if (posture_metrics and posture_metrics.is_slouching) else 0
        is_closed_frame = 1 if (eye_metrics and eye_metrics.is_blinking) else 0
        
        self.slouch_history.append(is_slouching_frame)
        self.closure_history.append(is_closed_frame)
        
        # Detect discrete blink events from EyeTracker's internal count.
        if eye_metrics:
            if eye_metrics.blink_count > self.last_total_blinks:
                # Add current timestamp for each registered new blink.
                new_blinks_count = eye_metrics.blink_count - self.last_total_blinks
                for _ in range(new_blinks_count):
                    self.blink_timestamps.append(current_time)
                self.last_total_blinks = eye_metrics.blink_count
        
        # Clean up blink timestamps older than the sliding window size.
        cutoff_time = current_time - self.window_size_sec
        self.blink_timestamps = [t for t in self.blink_timestamps if t > cutoff_time]
        
        # Recalculate rates periodically (e.g., once every 1 second to optimize CPU usage).
        if current_time - self.last_calculation_time >= 1.0:
            self.last_calculation_time = current_time
            
            # Compute actual sliding statistics.
            total_recorded_frames = max(len(self.closure_history), 1)
            slouch_ratio = sum(self.slouch_history) / total_recorded_frames
            eye_closure_ratio = sum(self.closure_history) / total_recorded_frames
            
            # Calculate Blinks Per Minute (BPM) based on active sliding window.
            blinks_in_window = len(self.blink_timestamps)
            blinks_per_minute = blinks_in_window * (60.0 / self.window_size_sec)
            
            # Normalize fatigue components (0.0 to 1.0 scale).
            # 1. Slouching Penalty (linear scale).
            slouch_score = slouch_ratio
            
            # 2. Eye Closure Penalty (micro-sleep/heavy drowsiness indicator).
            closure_score = min(1.0, eye_closure_ratio * 4.0)
            
            # 3. Blink Anomaly Penalty.
            # Healthy working rate is typically between 10 and 25 BPM.
            # Fatigue is indicated by very low rates (dry eyes/staring) or extreme rates (drowsy fluttering).
            if blinks_per_minute < 8.0:
                blink_score = 0.6  # Severe staring / fatigue indicator.
            elif blinks_per_minute > 30.0:
                blink_score = 0.4  # Struggling to focus / fluttering eyelids.
            else:
                blink_score = 0.0
                
            # Aggregate Weighted Fatigue Score.
            fatigue_score = (slouch_score * 0.3) + (closure_score * 0.4) + (blink_score * 0.3)
            fatigue_score = min(1.0, max(0.0, fatigue_score))
            
            # Classify Fatigue Levels.
            if fatigue_score > 0.75:
                fatigue_level = 'critical'
            elif fatigue_score > 0.55:
                fatigue_level = 'high'
            elif fatigue_score > 0.25:
                fatigue_level = 'medium'
            else:
                fatigue_level = 'low'
            
            # Evaluate break recommendations.
            break_recommended = False
            break_reason = ''
            
            if session_duration > self.break_interval:
                break_recommended = True
                break_reason = 'Time for a break (session duration limit reached)'
            elif fatigue_level in ['high', 'critical']:
                break_recommended = True
                break_reason = f'High fatigue level detected ({fatigue_level})'
                
            # Productivity score represents cognitive readiness.
            productivity_score = max(0.0, 1.0 - fatigue_score)
            
            # Update the persistent state.
            self.current_metrics = FatigueMetrics(
                session_duration=int(session_duration),
                blinks_per_minute=float(blinks_per_minute),
                slouch_ratio=float(slouch_ratio),
                eye_closure_ratio=float(eye_closure_ratio),
                productivity_score=float(productivity_score),
                fatigue_level=fatigue_level,
                break_recommended=break_recommended,
                break_reason=break_reason
            )
            
        # Return the cached current state on intermediate frames.
        return self.current_metrics

    def reset(self):
        """Reset all session history and counters."""
        self.start_time = time.time()
        self.last_break_time = time.time()
        self.last_total_blinks = 0
        self.slouch_history.clear()
        self.closure_history.clear()
        self.blink_timestamps.clear()
        self.current_metrics = FatigueMetrics()
        self.last_calculation_time = 0.0
