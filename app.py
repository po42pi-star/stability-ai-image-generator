# app.py
"""
Flask веб-приложение для генерации изображений.
"""
import os
import uuid
import json
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from concurrent.futures import ThreadPoolExecutor

from config import Config, ensure_output_dir
from gigachat import PromptImprover
from stability import ImageGenerator, StabilityAIError

app = Flask(__name__)

# Папка для изображений
IMAGES_FOLDER = Config.OUTPUT_DIR.resolve()

# Файл для хранения метаданных изображений
METADATA_FILE = IMAGES_FOLDER / 'metadata.json'

# Глобальное хранилище задач
tasks = {}

# Добавляем executor для фоновых задач
executor = ThreadPoolExecutor(max_workers=1)

# Художественные стили
STYLES = {
    'realistic': {
        'name': 'Реализм',
        'prompt': 'photorealistic, highly detailed, 8k resolution, professional photography, natural lighting, sharp focus',
        'negative': 'cartoon, anime, drawing, painting, artificial, blurry, low quality'
    },
    'anime': {
        'name': 'Аниме',
        'prompt': 'anime style, manga illustration, vibrant colors, cel shading, detailed linework',
        'negative': 'realistic, photo, 3d render,油画,写实'
    },
    'oil_painting': {
        'name': 'Масляная живопись',
        'prompt': 'oil painting style, impasto technique, rich textures, classical art, museum quality',
        'negative': 'photo, realistic, digital art, cartoon, anime'
    },
    'cyberpunk': {
        'name': 'Киберпанк',
        'prompt': 'cyberpunk city, neon lights, futuristic, sci-fi, android, holographic displays',
        'negative': 'natural, peaceful, daylight, vintage, medieval'
    },
    'watercolor': {
        'name': 'Акварель',
        'prompt': 'watercolor painting, soft edges, fluid colors, artistic, delicate, whimsical',
        'negative': 'sharp, digital, 3d, realistic, dark, heavy'
    },
    'fantasy': {
        'name': 'Фэнтези',
        'prompt': 'fantasy art, magical, enchanted, mystical creatures, epic scene',
        'negative': 'modern, realistic, urban, technology, sci-fi'
    },
    'portrait': {
        'name': 'Портрет',
        'prompt': 'professional portrait, studio lighting, sharp details, natural skin texture',
        'negative': 'blurry, cartoon, anime, distorted, low quality'
    },
    'landscape': {
        'name': 'Пейзаж',
        'prompt': 'breathtaking landscape, dramatic lighting, golden hour, atmospheric',
        'negative': 'urban, city, building, indoor, artificial'
    }
}


def load_metadata() -> dict:
    """Загрузка метаданных изображений"""
    if METADATA_FILE.exists():
        try:
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_metadata(image_name: str, data: dict):
    """Сохранение метаданных изображения"""
    metadata = load_metadata()
    metadata[image_name] = data
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def generate_image_task(task_id: str, original_prompt: str, style_key: str, 
                       improve_prompt: bool, width: int, height: int):
    """Фоновая задача генерации изображения"""
    try:
        tasks[task_id]['status'] = 'improving_prompt'
        tasks[task_id]['message'] = 'GigaChat улучшает промпт...'
        
        improver = PromptImprover()
        generator = ImageGenerator()
        
        improved_prompt = original_prompt
        
        if improve_prompt:
            result = improver.improve(original_prompt)
            if result['success']:
                improved_prompt = result['improved']
        
        # Добавляем стиль
        style = STYLES.get(style_key, STYLES['realistic'])
        full_prompt = f"{improved_prompt}, {style['prompt']}"
        
        tasks[task_id]['status'] = 'generating'
        tasks[task_id]['message'] = 'Stability AI генерирует изображение...'
        tasks[task_id]['original_prompt'] = original_prompt
        tasks[task_id]['improved_prompt'] = improved_prompt
        tasks[task_id]['style'] = style['name']
        tasks[task_id]['prompt'] = full_prompt
        
        # Генерируем
        artifacts = generator.client.generate_image(
            prompt=full_prompt,
            negative_prompt=style['negative'],
            width=width,
            height=height,
            samples=1
        )
        
        tasks[task_id]['status'] = 'saving'
        tasks[task_id]['message'] = 'Сохранение изображения...'
        
        # Сохраняем
        saved_paths = generator.client.save_images(artifacts, full_prompt)
        
        image_names = [p.name for p in saved_paths]
        
        # Сохраняем метаданные
        for img_name in image_names:
            save_metadata(img_name, {
                'original_prompt': original_prompt,
                'improved_prompt': improved_prompt,
                'style': style['name'],
                'full_prompt': full_prompt,
                'created_at': str(uuid.uuid4())
            })
        
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['message'] = 'Готово!'
        tasks[task_id]['images'] = image_names
        tasks[task_id]['image_names'] = image_names
        
    except Exception as e:
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['message'] = f'Ошибка: {str(e)}'
        tasks[task_id]['error'] = str(e)
        print(f"ERROR: {e}")


@app.route('/')
def index():
    """Главная страница"""
    ensure_output_dir()
    
    metadata = load_metadata()
    existing_images = []
    
    if IMAGES_FOLDER.exists():
        for img_path in sorted(IMAGES_FOLDER.glob('*.png'), reverse=True)[:20]:
            if img_path.exists() and img_path.stat().st_size > 0:
                img_meta = metadata.get(img_path.name, {})
                existing_images.append({
                    'name': img_path.name,
                    'path': f'/images/{img_path.name}',
                    'prompt': img_meta.get('improved_prompt', img_path.name.replace('_', ' ').replace('.png', '')[:50]),
                    'original_prompt': img_meta.get('original_prompt', ''),
                    'improved_prompt': img_meta.get('improved_prompt', ''),
                    'style': img_meta.get('style', ''),
                    'is_new': img_meta.get('created_at', '')
                })
    
    return render_template(
        'index.html', 
        styles=STYLES,
        existing_images=existing_images
    )


@app.route('/generate', methods=['POST'])
def generate():
    """Запуск генерации"""
    data = request.get_json()
    
    prompt = data.get('prompt', '').strip()
    style = data.get('style', 'realistic')
    improve = data.get('improve', True)
    width = int(data.get('width', 1024))
    height = int(data.get('height', 1024))
    
    if not prompt:
        return jsonify({'error': 'Введите промпт'}), 400
    
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': 'starting',
        'message': 'Подготовка...',
        'prompt': prompt,
        'original_prompt': prompt,
        'images': [],
        'image_names': []
    }
    
    executor.submit(
        generate_image_task,
        task_id, prompt, style, improve, width, height
    )
    
    return jsonify({'task_id': task_id})


@app.route('/status/<task_id>')
def status(task_id):
    """Проверка статуса"""
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Задача не найдена'}), 404
    
    return jsonify(task)


@app.route('/images/<path:filename>')
def serve_image(filename):
    """Сервинг изображений"""
    try:
        return send_from_directory(str(IMAGES_FOLDER), filename)
    except Exception as e:
        print(f"Image not found: {e}")
        return "Файл не найден", 404


@app.route('/api/styles')
def get_styles():
    """Список стилей"""
    return jsonify({
        key: {'name': v['name']} for key, v in STYLES.items()
    })


@app.route('/api/images')
def get_images():
    """API для получения изображений"""
    metadata = load_metadata()
    images = []
    
    if IMAGES_FOLDER.exists():
        for img_path in sorted(IMAGES_FOLDER.glob('*.png'), reverse=True):
            if img_path.exists() and img_path.stat().st_size > 0:
                img_meta = metadata.get(img_path.name, {})
                images.append({
                    'name': img_path.name,
                    'path': f'/images/{img_path.name}',
                    'prompt': img_meta.get('improved_prompt', ''),
                    'original_prompt': img_meta.get('original_prompt', ''),
                    'improved_prompt': img_meta.get('improved_prompt', ''),
                    'style': img_meta.get('style', '')
                })
    
    return jsonify(images)


if __name__ == '__main__':
    ensure_output_dir()
    app.run(debug=True, host='0.0.0.0', port=5000)