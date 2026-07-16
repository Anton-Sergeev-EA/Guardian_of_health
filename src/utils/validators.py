"""
Input validation utilities
"""

import os
import re
from typing import Any, Optional, Tuple
from exceptions import ValidationError


def validate_camera_id(cam_id: int) -> bool:
    """Validate camera ID."""
    return isinstance(cam_id, int) and cam_id >= 0


def validate_resolution(width: int, height: int) -> bool:
    """Validate resolution limits."""
    return (isinstance(width, int) and isinstance(height, int) and
            0 < width <= 4096 and 0 < height <= 4096)


def validate_fps(fps: int) -> bool:
    """Validate operational FPS range."""
    return isinstance(fps, int) and 1 <= fps <= 120


def validate_port(port: int) -> bool:
    """Validate network port number."""
    return isinstance(port, int) and 1 <= port <= 65535


def validate_ip(ip: str) -> bool:
    """Validate IPv4 address format."""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False
    return all(0 <= int(part) <= 255 for part in ip.split('.'))


def validate_path(path: str, writable: bool = True) -> Tuple[bool, str]:
    """
    Validate if a path's parent directory exists and is writable.
    Avoids failing on non-existent files (like new DB or logs) that will be created at runtime.
    """
    expanded_path = os.path.abspath(os.path.expanduser(path))
    parent_dir = os.path.dirname(expanded_path)
    
    # If the parent directory doesn't exist, try to create it, or verify we can.
    if not os.path.exists(parent_dir):
        try:
            # Test-create parent directories (but do not leave dummy directories if we fail).
            os.makedirs(parent_dir, exist_ok=True)
        except OSError:
            return False, expanded_path
            
    if writable:
        return os.access(parent_dir, os.W_OK), expanded_path
    return os.path.exists(parent_dir), expanded_path


def validate_email(email: str) -> bool:
    """Validate email address syntax."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


class Validator:
    """Configuration validator protecting FocusGuardian runtime stability."""
    
    @staticmethod
    def validate_config(config: dict) -> dict:
        """Validate all key sections of the configuration dictionary."""
        errors = []
        
        # 1. Camera validation.
        if 'camera' in config:
            cam = config['camera']
            if not validate_camera_id(cam.get('id', 0)):
                errors.append("Invalid camera ID")
            if not validate_resolution(cam.get('width', 640), cam.get('height', 480)):
                errors.append("Invalid camera resolution parameters")
            if not validate_fps(cam.get('fps', 30)):
                errors.append("Invalid camera FPS limit")
        
        # 2. Web interface validation.
        if 'web' in config:
            web = config['web']
            if not validate_port(web.get('port', 5000)):
                errors.append("Invalid web interface port")
            if not validate_ip(web.get('host', '0.0.0.0')):
                errors.append("Invalid web host IP address")
            
            # Stream sub-config.
            if 'stream' in web:
                stream = web['stream']
                quality = stream.get('quality', 75)
                frame_skip = stream.get('frame_skip', 2)
                if not (isinstance(quality, int) and 1 <= quality <= 100):
                    errors.append("Web stream quality must be between 1 and 100")
                if not (isinstance(frame_skip, int) and frame_skip >= 1):
                    errors.append("Web frame_skip must be an integer >= 1")
        
        # 3. Database validation.
        if 'database' in config:
            db = config['database']
            if db.get('enabled', True):
                db_path = db.get('path', '')
                if not db_path:
                    errors.append("Database path is missing")
                else:
                    is_valid, _ = validate_path(db_path, writable=True)
                    if not is_valid:
                        errors.append(f"Database parent directory is not writable: {db_path}")
        
        # 4. Logging validation.
        if 'logging' in config:
            log_cfg = config['logging']
            log_file = log_cfg.get('file', '')
            if log_file:
                is_valid, _ = validate_path(log_file, writable=True)
                if not is_valid:
                    errors.append(f"Log output directory is not writable: {log_file}")
                    
        # 5. Analytics thresholds validation.
        if 'analytics' in config:
            analytics = config['analytics']
            
            # Posture thresholds.
            if 'posture' in analytics:
                posture = analytics['posture']
                slouch = posture.get('slouch_threshold', 15.0)
                critical = posture.get('critical_threshold', 25.0)
                window = posture.get('smoothing_window', 5)
                
                if not (0.0 < slouch < critical):
                    errors.append("slouch_threshold must be positive and less than critical_threshold")
                if not (isinstance(window, int) and window > 0):
                    errors.append("posture smoothing_window must be a positive integer")
            
            # Eye Tracking thresholds.
            if 'eye' in analytics:
                eye = analytics['eye']
                ear = eye.get('ear_threshold', 0.2)
                blink_t = eye.get('blink_threshold', 0.25)
                
                if not (0.0 < ear < 1.0):
                    errors.append("ear_threshold must be a float between 0.0 and 1.0")
                if not (0.0 < blink_t < 5.0):
                    errors.append("blink_threshold must be a positive float (seconds)")

        # Raise consolidated errors.
        if errors:
            raise ValidationError(f"Configuration validation failed: {'; '.join(errors)}")
        
        return config
    