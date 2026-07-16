"""
Configuration loader with validation.
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Any


@dataclass
class CameraConfig:
    id: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    backend: str = "auto"


@dataclass
class PostureConfig:
    slouch_threshold: float = 15.0
    critical_threshold: float = 25.0
    smoothing_window: int = 5


@dataclass
class EyeConfig:
    ear_threshold: float = 0.2
    blink_threshold: float = 0.25
    smoothing_window: int = 3


@dataclass
class FatigueConfig:
    break_interval: int = 45
    max_blinks_per_minute: float = 20.0
    max_slouches_per_minute: float = 5.0


@dataclass
class AnalyticsConfig:
    posture: PostureConfig = field(default_factory=PostureConfig)
    eye: EyeConfig = field(default_factory=EyeConfig)
    fatigue: FatigueConfig = field(default_factory=FatigueConfig)


@dataclass
class VoiceConfig:
    enabled: bool = True
    language: str = "ru"
    cooldown: float = 1.5
    model_path: str = "src/voice/models/vosk-model-small-ru-0.22"


@dataclass
class StreamConfig:
    enabled: bool = True
    quality: int = 75
    frame_skip: int = 2


@dataclass
class WebConfig:
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 5000
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    secret_key: str = "change-this-in-production"
    stream: StreamConfig = field(default_factory=StreamConfig)


@dataclass
class DatabaseConfig:
    enabled: bool = True
    path: str = "~/.focus_guardian/logs.db"
    retention_days: int = 30


@dataclass
class NotificationsConfig:
    enabled: bool = True
    cooldown: int = 60
    sound: bool = True
    desktop: bool = True


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "json"
    file: str = "~/.focus_guardian/logs/guardian.log"
    max_size: int = 10
    backup_count: int = 5


@dataclass
class AppConfig:
    name: str = "FocusGuardian"
    version: str = "2.0.0"
    debug: bool = False
    log_level: str = "INFO"
    camera: CameraConfig = field(default_factory=CameraConfig)
    analytics: AnalyticsConfig = field(default_factory=AnalyticsConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    web: WebConfig = field(default_factory=WebConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


class ConfigLoader:
    """Load and validate configuration"""
    
    DEFAULT_CONFIG = {
        'app': {
            'name': 'FocusGuardian',
            'version': '2.0.0',
            'debug': False,
            'log_level': 'INFO'
        },
        'camera': {
            'id': 0,
            'width': 640,
            'height': 480,
            'fps': 30,
            'backend': 'auto'
        },
        'analytics': {
            'posture': {
                'slouch_threshold': 15.0,
                'critical_threshold': 25.0,
                'smoothing_window': 5
            },
            'eye': {
                'ear_threshold': 0.2,
                'blink_threshold': 0.25,
                'smoothing_window': 3
            },
            'fatigue': {
                'break_interval': 45,
                'max_blinks_per_minute': 20.0,
                'max_slouches_per_minute': 5.0
            }
        },
        'voice': {
            'enabled': True,
            'language': 'ru',
            'cooldown': 1.5,
            'model_path': 'src/voice/models/vosk-model-small-ru-0.22'
        },
        'web': {
            'enabled': True,
            'host': '0.0.0.0',
            'port': 5000,
            'cors_origins': ['*'],
            'secret_key': 'change-this-in-production',
            'stream': {
                'enabled': True,
                'quality': 75,
                'frame_skip': 2
            }
        },
        'database': {
            'enabled': True,
            'path': '~/.focus_guardian/logs.db',
            'retention_days': 30
        },
        'notifications': {
            'enabled': True,
            'cooldown': 60,
            'sound': True,
            'desktop': True
        },
        'logging': {
            'level': 'INFO',
            'format': 'json',
            'file': '~/.focus_guardian/logs/guardian.log',
            'max_size': 10,
            'backup_count': 5
        }
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path
        self._config = None
    
    def load(self) -> AppConfig:
        """Load configuration from file or defaults."""
        config_data = self.DEFAULT_CONFIG.copy()
        
        if self.config_path and self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    user_config = yaml.safe_load(f)
                    if user_config:
                        config_data = self._deep_merge(config_data, user_config)
            except Exception as e:
                print(f"[CONFIG] Error loading config: {e}")
        
        return self._parse_config(config_data)
    
    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    def _parse_config(self, data: dict) -> AppConfig:
        """Parse dictionary to dataclass structure."""
        try:
            app = AppConfig(
                name=data['app']['name'],
                version=data['app']['version'],
                debug=data['app']['debug'],
                log_level=data['app']['log_level'],
                camera=CameraConfig(**data['camera']),
                analytics=AnalyticsConfig(
                    posture=PostureConfig(**data['analytics']['posture']),
                    eye=EyeConfig(**data['analytics']['eye']),
                    fatigue=FatigueConfig(**data['analytics']['fatigue'])
                ),
                voice=VoiceConfig(**data['voice']),
                web=WebConfig(
                    **{k: v for k, v in data['web'].items() if k != 'stream'},
                    stream=StreamConfig(**data['web']['stream'])
                ),
                database=DatabaseConfig(**data['database']),
                notifications=NotificationsConfig(**data['notifications']),
                logging=LoggingConfig(**data['logging'])
            )
            return app
        except KeyError as e:
            raise ValueError(f"Missing configuration key: {e}")
    
    def save(self, config: AppConfig, path: Path):
        """Save configuration to file"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump(self._dataclass_to_dict(config), f, default_flow_style=False, allow_unicode=True)
    
    def _dataclass_to_dict(self, obj) -> dict:
        """Convert dataclass to dict"""
        if hasattr(obj, '__dataclass_fields__'):
            result = {}
            for field_name in obj.__dataclass_fields__:
                value = getattr(obj, field_name)
                if hasattr(value, '__dataclass_fields__'):
                    result[field_name] = self._dataclass_to_dict(value)
                elif isinstance(value, list):
                    result[field_name] = [
                        self._dataclass_to_dict(item) if hasattr(item, '__dataclass_fields__') else item
                        for item in value
                    ]
                else:
                    result[field_name] = value
            return result
        return obj


# Global config instance.
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get global configuration."""
    global _config
    if _config is None:
        loader = ConfigLoader(Path('config.yaml'))
        _config = loader.load()
    return _config


def reload_config():
    """Reload configuration."""
    global _config
    loader = ConfigLoader(Path('config.yaml'))
    _config = loader.load()
