"""
Voice command definitions and registry with multi-language support.
"""

from enum import Enum
from typing import Dict, List, Tuple, Optional
import re


class VoiceCommand(Enum):
    """All available voice commands."""
    STATUS = "status"
    PAUSE = "pause"
    RESUME = "resume"
    REPORT = "report"
    RESET = "reset"
    QUIT = "quit"
    HELP = "help"
    CALIBRATE = "calibrate"
    BREAK = "break"
    CONTINUE = "continue"
    POSTURE = "posture"
    BLINKS = "blinks"


class CommandRegistry:
    """Registry of voice commands with multi-language support."""
    
    def __init__(self):
        # Localized command phrase dictionaries for speech recognition.
        self._commands = {
            VoiceCommand.STATUS: {
                'ru': ['статус', 'состояние', 'что сейчас', 'как дела', 'информация'],
                'en': ['status', 'state', 'what\'s up', 'how are you', 'info']
            },
            VoiceCommand.PAUSE: {
                'ru': ['пауза', 'паузу', 'стоп', 'останови', 'перестань', 'тихо'],
                'en': ['pause', 'stop', 'hold', 'quiet', 'freeze']
            },
            VoiceCommand.RESUME: {
                'ru': ['продолжить', 'возобновить', 'дальше', 'включи', 'запусти'],
                'en': ['resume', 'start', 'proceed']
            },
            VoiceCommand.REPORT: {
                'ru': ['отчет', 'статистика', 'итоги', 'покажи отчет', 'результаты'],
                'en': ['report', 'statistics', 'summary', 'show report', 'results']
            },
            VoiceCommand.RESET: {
                'ru': ['сбросить', 'очистить', 'начать заново', 'обнулить'],
                'en': ['reset', 'clear', 'start over', 'restart']
            },
            VoiceCommand.QUIT: {
                'ru': ['выход', 'закрыть', 'выключи', 'выйти', 'завершить', 'пока'],
                'en': ['quit', 'exit', 'close', 'goodbye', 'shutdown']
            },
            VoiceCommand.HELP: {
                'ru': ['помощь', 'помоги', 'команды', 'что умеешь', 'возможности'],
                'en': ['help', 'commands', 'what can you do', 'capabilities']
            },
            VoiceCommand.CALIBRATE: {
                'ru': ['калибровка', 'настройка', 'откалибруй', 'подстрой'],
                'en': ['calibrate', 'setup', 'adjust']
            },
            VoiceCommand.BREAK: {
                'ru': ['перерыв', 'отдых', 'сделай перерыв', 'отдохнуть'],
                'en': ['break', 'rest', 'take a break']
            },
            VoiceCommand.CONTINUE: {
                'ru': ['продолжай', 'работать', 'продолжить работу', 'работаем'],
                'en': ['continue', 'go on', 'resume work', 'keep going']
            },
            VoiceCommand.POSTURE: {
                'ru': ['осанка', 'спина', 'как спина', 'сижу ровно'],
                'en': ['posture', 'sit up', 'straighten up']
            },
            VoiceCommand.BLINKS: {
                'ru': ['моргание', 'моргания', 'глаза', 'сколько моргнул'],
                'en': ['blinks', 'eyes', 'blinking']
            }
        }
        
        # Build flat list for faster lookup.
        # Any phrase must map to exactly one command: two commands quietly sharing
        # a trigger word is exactly the class of bug that let "pause" silently
        # resolve to BREAK instead of PAUSE, so we fail fast at construction time.
        self._flat_lookup: Dict[str, VoiceCommand] = {}
        for cmd, lang_dict in self._commands.items():
            for phrases in lang_dict.values():
                for phrase in phrases:
                    key = phrase.lower()
                    existing = self._flat_lookup.get(key)
                    if existing is not None and existing is not cmd:
                        raise ValueError(
                            f"Voice command phrase {key!r} is registered to both "
                            f"{existing.name} and {cmd.name} - trigger phrases must be unique."
                        )
                    self._flat_lookup[key] = cmd
    
    def parse_command(self, text: str) -> Tuple[Optional[VoiceCommand], float]:
        """
        Parse text and return matched VoiceCommand with a confidence score.
        Uses regex word boundaries to prevent false positives with short substrings.
        
        Returns:
            Tuple[Optional[VoiceCommand], float]: (command, confidence).
        """
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', '', text)  # Keep letters and spaces (Unicode-safe).
        
        best_match = None
        best_score = 0.0
        
        for phrase, cmd in self._flat_lookup.items():
            # Create a regex to match the phrase with word boundaries to avoid sub-word false matches.
            # e.g., prevents "stop" matching in "stopping" or "стоп" in "стопка".
            pattern = r'\b' + re.escape(phrase) + r'\b'
            match = re.search(pattern, text)
            
            if match:
                pos = match.start()
                length = len(phrase)
                
                # Calculate confidence score based on text coverage and position.
                coverage = length / max(len(text), 1)
                position_score = 1.0 - (pos / max(len(text), 1))
                
                # Perfect exact match yields score = 1.0.
                score = coverage * 0.7 + position_score * 0.3
                
                if score > best_score:
                    best_score = score
                    best_match = cmd
                    
        # Minimum confidence threshold.
        if best_score < 0.3:
            return None, 0.0
        
        return best_match, best_score
    
    def get_help_text(self, language: str = 'ru') -> str:
        """Get help text formatted in the specified language."""
        if language == 'ru':
            return """
            Доступные команды:
            • Статус - показать текущее состояние.
            • Пауза - приостановить мониторинг.
            • Продолжить - возобновить мониторинг.
            • Отчет - показать статистику сессии.
            • Сбросить - сбросить счетчики.
            • Перерыв - напомнить о перерыве.
            • Осанка - проверить осанку.
            • Моргание - статистика морганий.
            • Калибровка - настроить датчики.
            • Помощь - показать это сообщение.
            • Выход - завершить работу.
            """
        else:
            return """
            Available commands:
            • Status - show current state.
            • Pause - pause monitoring.
            • Resume - resume monitoring.
            • Report - show session statistics.
            • Reset - reset counters.
            • Break - remind about break.
            • Posture - check posture.
            • Blinks - blink statistics.
            • Calibrate - calibrate sensors.
            • Help - show this message.
            • Quit - exit application.
            """
        