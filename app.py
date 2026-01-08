# app.py
"""
Flask веб-приложение для генерации изображений.
"""
import os
import uuid
import json
import base64
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from concurrent.futures import ThreadPoolExecutor

from config import Config, ensure_output_dir
from gigachat import PromptImprover
from stability import ImageGenerator, StabilityAIError

app = Flask(__name__)

# Глобальное хранилище задач (в памяти)
tasks = {}

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
        
        # Конвертируем в base64 (НЕ сохраняем на диск!)
        images_base64 = []
        for artifact in artifacts:
            image_data = base64.b64decode(artifact['base64'])
            b64_string = base64.b64encode(image_data).decode('utf-8')
            images_base64.append(f"data:image/png;base64,{b64_string}")
        
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['message'] = 'Готово!'
        tasks[task_id]['images'] = images_base64  # base64 строки
        
    except Exception as e:
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['message'] = f'Ошибка: {str(e)}'
        tasks[task_id]['error'] = str(e)
        print(f"ERROR: {e}")


@app.route('/')
def index():
    """Главная страница"""
    return render_template(
        'index.html', 
        styles=STYLES,
        existing_images=[]
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
        'images': []
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


@app.route('/api/styles')
def get_styles():
    """Список стилей"""
    return jsonify({
        key: {'name': v['name']} for key, v in STYLES.items()
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)