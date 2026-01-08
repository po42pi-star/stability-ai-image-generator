# app.py
"""
Flask веб-приложение для генерации изображений.
"""
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import time

# Храним задачи 1 час
TASK_TTL = 3600

def cleanup_old_tasks():
    """Удаляет старые задачи"""
    current_time = time.time()
    expired = [task_id for task_id, task in tasks.items() 
               if task.get('created_at', current_time) < current_time - TASK_TTL]
    for task_id in expired:
        del tasks[task_id]

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


def generate_image_task(task_id: str, original_prompt: str, style_key: str, 
                       improve_prompt: bool, width: int, height: int):
    """Фоновая задача генерации изображения"""
    try:
        logger.info(f"[{task_id}] === START ===")
        logger.info(f"[{task_id}] Prompt: {original_prompt}")
        
        tasks[task_id]['status'] = 'improving_prompt'
        tasks[task_id]['message'] = 'GigaChat улучшает промпт...'
        
        improver = PromptImprover()
        
        improved_prompt = original_prompt
        
        if improve_prompt:
            logger.info(f"[{task_id}] Calling GigaChat API...")
            try:
                result = improver.improve(original_prompt)
                logger.info(f"[{task_id}] GigaChat result: {result}")
                if result['success']:
                    improved_prompt = result['improved']
            except Exception as gigachat_error:
                logger.error(f"[{task_id}] GigaChat error: {gigachat_error}")
                improved_prompt = original_prompt  # Используем оригинальный
        
        # Добавляем стиль
        style = STYLES.get(style_key, STYLES['realistic'])
        full_prompt = f"{improved_prompt}, {style['prompt']}"
        
        logger.info(f"[{task_id}] Full prompt: {full_prompt[:200]}...")
        
        tasks[task_id]['status'] = 'generating'
        tasks[task_id]['message'] = 'Stability AI генерирует изображение...'
        tasks[task_id]['original_prompt'] = original_prompt
        tasks[task_id]['improved_prompt'] = improved_prompt
        tasks[task_id]['style'] = style['name']
        tasks[task_id]['prompt'] = full_prompt
        
        logger.info(f"[{task_id}] Calling Stability AI API...")
        
        generator = ImageGenerator()
        
        # Генерируем
        artifacts = generator.client.generate_image(
            prompt=full_prompt,
            negative_prompt=style['negative'],
            width=width,
            height=height,
            samples=1
        )
        
        logger.info(f"[{task_id}] Stability AI returned {len(artifacts)} artifacts")
        
        # Конвертируем в base64
        images_base64 = []
        for artifact in artifacts:
            image_data = base64.b64decode(artifact['base64'])
            b64_string = base64.b64encode(image_data).decode('utf-8')
            images_base64.append(f"data:image/png;base64,{b64_string}")
        
        tasks[task_id]['status'] = 'completed'
        tasks[task_id]['message'] = 'Готово!'
        tasks[task_id]['images'] = images_base64
        
        logger.info(f"[{task_id}] === DONE ===")
        
    except Exception as e:
        logger.error(f"[{task_id}] ERROR: {str(e)}")
        tasks[task_id]['status'] = 'error'
        tasks[task_id]['message'] = f'Ошибка: {str(e)}'
        tasks[task_id]['error'] = str(e)


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
        'images': [],
        'created_at': time.time()
    }
    
    executor.submit(
        generate_image_task,
        task_id, prompt, style, improve, width, height
    )
    
    return jsonify({'task_id': task_id})

@app.route('/status/<task_id>')
def status(task_id):
    """Проверка статуса"""
    logger.info(f"[status] Request for task_id: {task_id}")
    logger.info(f"[status] Available tasks: {list(tasks.keys())}")
    
    task = tasks.get(task_id)
    if not task:
        logger.warning(f"[status] Task {task_id} not found")
        return jsonify({'error': 'Задача не найдена', 'task_id': task_id}), 404
    
    return jsonify(task)


@app.route('/api/styles')
def get_styles():
    """Список стилей"""
    return jsonify({
        key: {'name': v['name']} for key, v in STYLES.items()
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)