# gigachat.py
"""
Модуль для работы с GigaChat API.
Улучшает и конкретизирует промпты для генерации изображений.
"""
import requests
import base64
import time
import json
from typing import Optional
from config import Config

class GigaChatClient:
    """Клиент для работы с GigaChat API"""
    
    def __init__(self, verify_ssl: bool = False):
        self.base_url = "https://gigachat.devices.sberbank.ru/api/v1"
        self.auth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        self.access_token: Optional[str] = None
        self.token_expires_at: float = 0
        self.verify_ssl = verify_ssl
    
    def _get_access_token(self) -> str:
        """Получает access token для GigaChat API"""
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': Config.CLIENT_SECRET,  # Исправлено: значение CLIENT_SECRET
            'Authorization': f'Basic {Config.AUTHORIZATION_KEY}'
        }
        
        payload = {
            'scope': 'GIGACHAT_API_PERS'
        }
        
        try:
            response = requests.post(
                self.auth_url, 
                headers=headers, 
                data=payload, 
                verify=self.verify_ssl,  # Добавлено
                timeout=30
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get('access_token')
            self.token_expires_at = time.time() + 25 * 60
            
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ошибка получения токена GigaChat: {e}")
    
    def _make_request(self, endpoint: str, method: str = 'GET', 
                     data: Optional[dict] = None) -> dict:
        """Базовый метод для выполнения запросов к GigaChat API"""
        token = self._get_access_token()
        
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {token}'
        }
        
        try:
            if method == 'GET':
                response = requests.get(
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    verify=self.verify_ssl,  # Добавлено
                    timeout=30
                )
            elif method == 'POST':
                headers['Content-Type'] = 'application/json'
                response = requests.post(
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    json=data,
                    verify=self.verify_ssl,  # Добавлено
                    timeout=60
                )
            else:
                raise ValueError(f"Неподдерживаемый метод: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ошибка запроса к GigaChat: {e}")
    
    def get_models(self) -> list:
        """Получает список доступных моделей"""
        data = self._make_request("/models", "GET")
        return data.get('data', [])
    
    def improve_prompt(self, prompt: str, language: str = 'ru') -> str:
        """
        Улучшает и конкретизирует промпт для генерации изображения.
        
        Args:
            prompt: Исходный промпт на русском языке
            language: Язык исходного промпта (по умолчанию 'ru')
        
        Returns:
            Улучшенный промпт на английском языке
        """
        system_prompt = """Ты — эксперт по созданию промптов для генерации изображений в AI.
Твоя задача — улучшить и конкретизировать промпт, добавив:
1. Детали окружения и атмосферы
2. Описание освещения
3. Художественный стиль (если не указан)
4. Технические параметры (соотношение сторон, качество)

ВАЖНО: Отвечай ТОЛЬКО улучшенным промптом на АНГЛИЙСКОМ языке, без объяснений и дополнительного текста.
Промпт должен быть подробным, но не слишком длинным (150-300 слов).
В конце добавь технические параметры качества: --ar 16:9 --v 6.0 --style raw --quality 1"""
        
        user_prompt = f"""Улучши этот промпт для генерации изображения:

{prompt}

Пожалуйста, сделай промпт более конкретным, добавь детали и переведи на английский язык."""
        
        try:
            data = {
                "model": Config.GIGACHAT_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 500
            }
            
            response = self._make_request("/chat/completions", "POST", data)
            
            improved_prompt = response['choices'][0]['message']['content']
            
            # Очищаем ответ от возможных кавычек и лишнего текста
            improved_prompt = improved_prompt.strip().strip('"').strip("'")
            
            return improved_prompt
            
        except Exception as e:
            print(f"⚠️ Ошибка улучшения промпта: {e}")
            print(f"ℹ️ Использую исходный промпт (переведённый на английский)")
            
            # Fallback: простой перевод на английский
            return self._simple_translate(prompt)
    
    def _simple_translate(self, text: str) -> str:
        """
        Простой перевод на английский (fallback при ошибке GigaChat).
        В реальном приложении лучше использовать переводчик API.
        """
        # Простой словарь для демонстрации
        translations = {
            'лес': 'forest',
            'город': 'city',
            'море': 'sea',
            'гора': 'mountain',
            'река': 'river',
            'дом': 'house',
            'кошка': 'cat',
            'собака': 'dog',
            'солнце': 'sun',
            'луна': 'moon',
            'звёзды': 'stars',
            'ночь': 'night',
            'день': 'day',
        }
        
        result = text.lower()
        for ru, en in translations.items():
            result = result.replace(ru, en)
        
        return result


class PromptImprover:
    """Улучшатель промптов с дополнительной логикой"""
    
    def __init__(self):
        self.client = GigaChatClient()
    
    def improve(self, original_prompt: str) -> dict:
        """
        Полностью обрабатывает промпт: улучшает и возвращает результат.
        
        Returns:
            dict с ключами:
                - original: исходный промпт
                - improved: улучшенный промпт
                - success: успех операции
        """
        print(f"\n📝 Исходный промпт: {original_prompt}")
        print("🔄 GigaChat улучшает промпт...")
        
        try:
            improved = self.client.improve_prompt(original_prompt)
            
            print(f"✨ Улучшенный промпт:")
            print(f"   {improved}")
            
            return {
                'original': original_prompt,
                'improved': improved,
                'success': True
            }
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return {
                'original': original_prompt,
                'improved': original_prompt,
                'success': False
            }