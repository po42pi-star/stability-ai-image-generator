# stability.py
"""
Модуль для работы со Stability AI API.
Генерирует изображения по улучшенным промптам.
"""
import base64
import requests
from pathlib import Path
from typing import Optional, List
from config import Config


class StabilityAIError(Exception):
    """Исключение для ошибок Stability AI"""
    pass

class StabilityAIClient:
    """Клиент для работы со Stability AI API"""
    
    def __init__(self):
        self.api_key = Config.STABILITY_KEY
        self.api_host = "https://api.stability.ai"
        self.engine_id = "stable-diffusion-xl-1024-v1-0"
    
    def _get_headers(self) -> dict:
        """Возвращает заголовки для API запросов"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 30,
        cfg_scale: float = 7.0,
        samples: int = 1,
        seed: Optional[int] = None
    ) -> List[dict]:
        """
        Генерирует изображение по текстовому промпту.
        """
        url = f"{self.api_host}/v1/generation/{self.engine_id}/text-to-image"
        
        # Формируем payload как список промптов для корректного JSON
        text_prompts = [{"text": prompt, "weight": 1}]
        
        if negative_prompt:
            text_prompts.append({"text": negative_prompt, "weight": -1})
        
        payload = {
            "text_prompts": text_prompts,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "samples": samples,
            "seed": seed if seed is not None else 0,
        }
        
        headers = self._get_headers()
        
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,  # Используем json= вместо data=
                timeout=120
            )
            
            if response.status_code != 200:
                error_msg = response.json().get('message', 'Unknown error')
                raise StabilityAIError(
                    f"Ошибка генерации (код {response.status_code}): {error_msg}"
                )
            
            data = response.json()
            return data.get('artifacts', [])
            
        except requests.exceptions.RequestException as e:
            raise StabilityAIError(f"Сетевая ошибка: {e}")
    
    def save_images(
        self,
        artifacts: List[dict],
        prompt: str,
        output_dir: Optional[Path] = None
    ) -> List[Path]:
        """
        Сохраняет сгенерированные изображения.
        
        Args:
            artifacts: Список артефактов от API
            prompt: Промпт (для имени файла)
            output_dir: Директория для сохранения
        
        Returns:
            Список путей к сохранённым файлам
        """
        if output_dir is None:
            output_dir = Config.OUTPUT_DIR
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        saved_paths = []
        
        for i, artifact in enumerate(artifacts):
            # Декодируем base64 изображение
            image_data = base64.b64decode(artifact['base64'])
            
            # Создаём имя файла из промпта
            safe_name = "".join(
                c for c in prompt[:30] 
                if c.isalnum() or c in (' ', '-', '_')
            ).strip().replace(' ', '_')
            
            filename = f"{safe_name}_{i+1}.png"
            filepath = output_dir / filename
            
            # Сохраняем изображение
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            saved_paths.append(filepath)
            print(f"💾 Изображение сохранено: {filepath}")
        
        return saved_paths


class ImageGenerator:
    """Основной класс для генерации изображений"""
    
    def __init__(self):
        self.client = StabilityAIClient()
    
    def generate(
        self,
        prompt: str,
        show_improved: bool = True,
        save_dir: Optional[Path] = None
    ) -> List[Path]:
        """
        Генерирует изображение по промпту.
        
        Args:
            prompt: Исходный промпт
            show_improved: Показывать ли улучшенный промпт
            save_dir: Директория для сохранения
        
        Returns:
            Список путей к сохранённым файлам
        """
        print(f"\n🎨 Начинаю генерацию изображения...")
        print(f"📝 Промпт: {prompt}")
        
        try:
            # Генерируем изображение
            artifacts = self.client.generate_image(
                prompt=prompt,
                width=Config.IMAGE_SIZE[0],
                height=Config.IMAGE_SIZE[1],
                samples=Config.NUM_IMAGES
            )
            
            if not artifacts:
                raise StabilityAIError("Не получены изображения от API")
            
            # Сохраняем изображения
            saved_paths = self.client.save_images(artifacts, prompt, save_dir)
            
            print(f"\n✅ Готово! Сгенерировано {len(saved_paths)} изображений")
            return saved_paths
            
        except StabilityAIError as e:
            print(f"❌ Ошибка генерации: {e}")
            raise