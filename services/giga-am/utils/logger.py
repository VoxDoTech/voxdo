import logging
import sys
import os
from config import settings

def setup_logging():
    """Настройка логирования приложения"""
    
    # Создаем форматтер
    formatter = logging.Formatter(settings.log_format)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Очищаем существующие обработчики
    root_logger.handlers.clear()
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Файловый обработчик (если директория существует)
    if os.path.exists('/app/logs'):
        try:
            file_handler = logging.FileHandler('/app/logs/app.log')
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            # Если не можем создать файловый лог, продолжаем без него
            logging.warning(f"Could not create file logger: {e}")
    
    # Устанавливаем уровень для конкретных логгеров
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("gigaam").setLevel(logging.INFO)
    
    return root_logger

# Инициализация логирования при импорте
logger = setup_logging()
