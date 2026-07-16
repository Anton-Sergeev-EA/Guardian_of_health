"""
Performance monitoring and profiling with thread-safe data structures.
"""

import time
import functools
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import threading


class PerformanceMonitor:
    """Thread-safe performance monitor for profiling in multi-threaded environments."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        # Instance lock for synchronizing dictionary updates.
        self._monitor_lock = threading.Lock()
        
        self._timings: Dict[str, List[float]] = defaultdict(list)
        self._counters: Dict[str, int] = defaultdict(int)
        
        # Maps (thread_id, timer_name) -> start_time to prevent overlaps between threads.
        self._active_timers: Dict[Tuple[int, str], float] = {}
    
    def start(self, name: str):
        """Start a timer for the current thread."""
        thread_id = threading.get_ident()
        with self._monitor_lock:
            self._active_timers[(thread_id, name)] = time.perf_counter()
    
    def stop(self, name: str) -> Optional[float]:
        """Stop a timer for the current thread and record timing safely."""
        thread_id = threading.get_ident()
        key = (thread_id, name)
        
        with self._monitor_lock:
            if key not in self._active_timers:
                return None
            
            elapsed = time.perf_counter() - self._active_timers[key]
            self._timings[name].append(elapsed)
            del self._active_timers[key]
            return elapsed
    
    def inc(self, name: str, count: int = 1):
        """Increment a counter safely."""
        with self._monitor_lock:
            self._counters[name] += count
    
    def get_stats(self, name: str) -> Dict[str, float]:
        """Get copy of statistics for a timer under lock."""
        with self._monitor_lock:
            timings = list(self._timings.get(name, []))
            
        if not timings:
            return {'count': 0}
        
        return {
            'count': len(timings),
            'min': min(timings) * 1000,  # Convert to ms.
            'max': max(timings) * 1000,
            'avg': sum(timings) / len(timings) * 1000,
            'total': sum(timings) * 1000
        }
    
    def get_counter(self, name: str) -> int:
        """Get counter value safely."""
        with self._monitor_lock:
            return self._counters.get(name, 0)
    
    def reset(self):
        """Reset all data safely."""
        with self._monitor_lock:
            self._timings.clear()
            self._counters.clear()
            self._active_timers.clear()
    
    def report(self) -> Dict[str, Dict]:
        """Generate performance report safely making sure data is not mutated during read."""
        report = {}
        with self._monitor_lock:
            # Capture snapshot of current keys to avoid dictionary size modification errors.
            timer_names = list(self._timings.keys())
            counter_names = list(self._counters.keys())
            
        for name in timer_names:
            report[name] = self.get_stats(name)
            
        for name in counter_names:
            count = self.get_counter(name)
            if name not in report:
                report[name] = {'count': count}
            else:
                report[name]['count'] = count
                
        return report


def profile(name: Optional[str] = None):
    """Decorator for profiling functions safely."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            timer_name = name or func.__name__
            monitor = PerformanceMonitor()
            monitor.start(timer_name)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                monitor.stop(timer_name)
        return wrapper
    return decorator


# Global monitor instance.
_monitor = PerformanceMonitor()


def get_monitor() -> PerformanceMonitor:
    """Get global performance monitor."""
    return _monitor
