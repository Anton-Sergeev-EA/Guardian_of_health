"""
Structured logging with rotation and multiple outputs.
"""

import os
import sys
import json
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Avoid deprecated datetime.utcnow() in Python 3.12+.
        timestamp_iso = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        log_data = {
            'timestamp': timestamp_iso,
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'process': record.process,
            'thread': record.thread
        }
        
        # Add exception info if present.
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields.
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
        
        return json.dumps(log_data, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan.
        'INFO': '\033[32m',      # Green.
        'WARNING': '\033[33m',   # Yellow.
        'ERROR': '\033[31m',     # Red.
        'CRITICAL': '\033[35m',  # Magenta.
        'RESET': '\033[0m'
    }
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        return f"{timestamp} {color}{record.levelname:8}{reset} {record.name:15} {record.getMessage()}"


class Logger:
    """Application logger with rotation."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._loggers = {}
        self._configure_root()
        
        # Determine base directory: use Docker-compatible path if writable, otherwise fall back to home dir.
        docker_home = Path('/home/guardian/.focus_guardian')
        if docker_home.exists() or os.access('/home/guardian', os.W_OK):
            self.base_dir = docker_home
        else:
            self.base_dir = Path.home() / '.focus_guardian'
            
    def _configure_root(self):
        """Configure root logger"""
        self.root = logging.getLogger()
        self.root.setLevel(logging.INFO)
        
        # Remove default handlers.
        self.root.handlers.clear()
    
    def get_logger(self, name: str, level: str = 'INFO', log_dir: Optional[Path] = None) -> logging.Logger:
        """Get or create logger."""
        if name in self._loggers:
            return self._loggers[name]
        
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        
        # Console handler with color.
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(ColoredConsoleFormatter())
        logger.addHandler(console)
        
        # File handler with rotation.
        target_dir = log_dir if log_dir else self.base_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        log_file = target_dir / f'{name}.log'
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(JSONFormatter())
        logger.addHandler(file_handler)
        
        self._loggers[name] = logger
        return logger
    
    def get_root(self) -> logging.Logger:
        """Get root logger."""
        return self.root


# Global logger instance.
_logger = Logger()


def get_logger(name: str = 'focus_guardian') -> logging.Logger:
    """Get logger instance."""
    return _logger.get_logger(name)


def log_error(e: Exception, context: Optional[Dict[str, Any]] = None):
    """Log error with context."""
    logger = get_logger('errors')
    extra = {'extra_data': context or {}}
    logger.error(f"{type(e).__name__}: {str(e)}", exc_info=True, extra=extra)
