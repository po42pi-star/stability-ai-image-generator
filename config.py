# config.py
"""
Конфигурация приложения для генерации изображений.
Загружает переменные окружения и предоставляет доступ к ним.
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# Загружаем переменные окружения из .env файла
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)


class Config:
    """Конфигурация приложения"""
    
    # Stability AI
    STABILITY_KEY = os.getenv('Stability_key')
    
    # GigaChat
    CLIENT_ID = os.getenv('CLIENT_ID')
    CLIENT_SECRET = os.getenv('CLIENT_SECRET')
    AUTHORIZATION_KEY = os.getenv('AUTHORIZATION_KEY')
    
    # Настройки генерации
    IMAGE_SIZE = (1024, 1024)  # Размер изображения по умолчанию
    OUTPUT_DIR = Path(__file__).parent / 'generated_images'
    NUM_IMAGES = 1  # Количество изображений для генерации
    
    # GigaChat настройки
    GIGACHAT_MODEL = 'GigaChat'  # или 'GigaChat Lite'
    
    @classmethod
    def validate(cls) -> bool:
        """Проверяет наличие необходимых ключей"""
        errors = []
        
        if not cls.STABILITY_KEY:
            errors.append("Stability_key (Stability AI API key)")
        if not cls.CLIENT_ID:
            errors.append("CLIENT_ID (GigaChat)")
        if not cls.CLIENT_SECRET:
            errors.append("CLIENT_SECRET (GigaChat)")
        if not cls.AUTHORIZATION_KEY:
            errors.append("AUTHORIZATION_KEY (GigaChat)")
        
        if errors:
            print(f"❌ Отсутствуют необходимые переменные окружения:")
            for error in errors:
                print(f"   - {error}")
            return False
        
        return True


def ensure_output_dir():
    """Создаёт директорию для изображений, если она не существует"""
    Config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)