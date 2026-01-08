# main.py
#!/usr/bin/env python3
"""
CLI приложение для генерации изображений.
Использует GigaChat для улучшения промптов и Stability AI для генерации.
"""
import sys
import argparse
from pathlib import Path

from config import Config, ensure_output_dir
from gigachat import PromptImprover
from stability import ImageGenerator, StabilityAIError


def print_banner():
    """Выводит приветственный баннер"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║          🖼️  AI Image Generator CLI                           ║
║                                                               ║
║  GigaChat + Stability AI                                       ║
╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_help():
    """Выводит справку по командам"""
    help_text = """
📖 Использование:

  python main.py "ваш промпт"           - Быстрая генерация
  python main.py -i "файл.txt"          - Из файла с промптами
  python main.py --interactive          - Интерактивный режим
  python main.py --models               - Список моделей GigaChat
  python main.py --test-connection      - Тест подключения

⚙️ Параметры:

  --size W H        Размер изображения (по умолчанию 1024 1024)
  --samples N       Количество изображений (по умолчанию 1)
  --steps N         Шагов генерации (по умолчанию 30)
  --no-improve      Не улучшать промпт
  --output DIR      Папка для сохранения
  --help            Эта справка

📝 Примеры:

  python main.py "лес с горами на закате"
  python main.py "космический город" --size 1280 720 --samples 3
  python main.py -i prompts.txt --output my_images
    """
    print(help_text)


def test_connection(config: Config) -> bool:
    """Тестирует подключение к API"""
    print("\n🔍 Тестирование подключения...")
    
    all_ok = True
    
    # Тест Stability AI
    print("\n1️⃣ Stability AI:")
    if config.STABILITY_KEY:
        try:
            import requests
            response = requests.get(
                "https://api.stability.ai/v1/account",
                headers={"Authorization": f"Bearer {config.STABILITY_KEY}"},
                timeout=10
            )
            if response.status_code == 200:
                print("   ✅ Подключение успешно!")
            else:
                print(f"   ❌ Ошибка: {response.status_code}")
                all_ok = False
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            all_ok = False
    else:
        print("   ❌ Ключ не найден в переменных окружения")
        all_ok = False
    
    # Тест GigaChat
    print("\n2️⃣ GigaChat:")
    if config.CLIENT_ID and config.CLIENT_SECRET:
        try:
            from gigachat import GigaChatClient
            client = GigaChatClient()
            token = client._get_access_token()
            print("   ✅ Токен получен успешно!")
            
            # Проверяем доступность моделей
            models = client.get_models()
            print(f"   📋 Доступно моделей: {len(models)}")
            
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            all_ok = False
    else:
        print("   ❌ CLIENT_ID или CLIENT_SECRET не найдены")
        all_ok = False
    
    return all_ok


def process_prompt(
    prompt: str,
    improver: PromptImprover,
    generator: ImageGenerator,
    improve: bool = True
) -> None:
    """Обрабатывает один промпт: улучшает и генерирует изображение"""
    
    # Улучшаем промпт если нужно
    if improve:
        result = improver.improve(prompt)
        final_prompt = result['improved']
    else:
        final_prompt = prompt
    
    print(f"\n🚀 Отправляем на генерацию...")
    
    try:
        paths = generator.generate(final_prompt)
        print(f"\n✨ Готово! Изображения в: {paths}")
        
    except StabilityAIError as e:
        print(f"\n❌ Ошибка генерации: {e}")
        sys.exit(1)


def interactive_mode(improver: PromptImprover, generator: ImageGenerator):
    """Интерактивный режим работы"""
    print("\n🎮 Интерактивный режим")
    print("Введите 'exit' или 'q' для выхода")
    print("Введите 'help' для справки\n")
    
    while True:
        try:
            prompt = input("💭 Ваш промпт: ").strip()
            
            if prompt.lower() in ('exit', 'q', 'quit'):
                print("👋 До встречи!")
                break
            
            if prompt.lower() in ('help', '?', 'помощь'):
                print("""
Команды:
  exit, q, quit    - Выйти из программы
  help, ?          - Показать эту справку
  clear            - Очистить экран

Просто введите вашу идею для изображения!
                """)
                continue
            
            if not prompt:
                continue
            
            process_prompt(prompt, improver, generator)
            
        except KeyboardInterrupt:
            print("\n\n👋 До встречи!")
            break
        except EOFError:
            break


def main():
    """Основная функция CLI"""
    print_banner()
    
    # Проверяем конфигурацию
    if not Config.validate():
        print("\n📋 Заполните файл .env согласно примеру из .env.example")
        sys.exit(1)
    
    # Создаём выходную директорию
    ensure_output_dir()
    
    # Парсим аргументы командной строки
    parser = argparse.ArgumentParser(
        description="AI Image Generator CLI",
        add_help=False
    )
    
    parser.add_argument('prompt', nargs='?', help="Промпт для генерации")
    parser.add_argument('-i', '--input', type=str, help="Файл с промптами")
    parser.add_argument('--interactive', action='store_true', 
                       help="Интерактивный режим")
    parser.add_argument('--models', action='store_true',
                       help="Показать доступные модели GigaChat")
    parser.add_argument('--test-connection', action='store_true',
                       help="Тест подключения к API")
    parser.add_argument('--no-improve', action='store_true',
                       help="Не улучшать промпт через GigaChat")
    parser.add_argument('--size', nargs=2, type=int, default=[1024, 1024],
                       metavar=('W', 'H'), help="Размер изображения")
    parser.add_argument('--samples', type=int, default=1,
                       help="Количество изображений")
    parser.add_argument('--steps', type=int, default=30,
                       help="Шагов генерации")
    parser.add_argument('--output', type=str, help="Папка для сохранения")
    parser.add_argument('--help', action='store_true', help="Показать справку")
    
    args = parser.parse_args()
    
    # Показываем помощь
    if args.help:
        print_help()
        sys.exit(0)
    
    # Тест подключения
    if args.test_connection:
        test_connection(Config)
        sys.exit(0)
    
    # Показываем модели
    if args.models:
        try:
            from gigachat import GigaChatClient
            client = GigaChatClient()
            models = client.get_models()
            print("\n📋 Доступные модели GigaChat:")
            for model in models:
                print(f"   - {model['id']}")
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        sys.exit(0)
    
    # Инициализируем модули
        # Инициализируем модули (verify_ssl=False для обхода ошибки самоподписанного сертификата)
    improver = PromptImprover()
    improver.client.verify_ssl = False  # Обход SSL ошибки
    generator = ImageGenerator()
    
    # Обновляем настройки из аргументов
    if args.size:
        Config.IMAGE_SIZE = (args.size[0], args.size[1])
    if args.samples:
        Config.NUM_IMAGES = args.samples
    
    # Интерактивный режим
    if args.interactive or (not args.prompt and not args.input):
        interactive_mode(improver, generator)
        sys.exit(0)
    
    # Промпт из командной строки
    if args.prompt:
        save_dir = Path(args.output) if args.output else None
        process_prompt(
            args.prompt, 
            improver, 
            generator,
            improve=not args.no_improve
        )
    
    # Промпты из файла
    if args.input:
        input_file = Path(args.input)
        if not input_file.exists():
            print(f"❌ Файл не найден: {input_file}")
            sys.exit(1)
        
        save_dir = Path(args.output) if args.output else Config.OUTPUT_DIR
        save_dir.mkdir(parents=True, exist_ok=True)
        
        prompts = input_file.read_text(encoding='utf-8').split('\n')
        prompts = [p.strip() for p in prompts if p.strip()]
        
        print(f"\n📄 Найдено {len(prompts)} промптов в файле")
        
        for i, prompt in enumerate(prompts, 1):
            print(f"\n--- Промпт {i}/{len(prompts)} ---")
            process_prompt(
                prompt, 
                improver, 
                generator,
                improve=not args.no_improve
            )
    
    print("\n✨ Все операции завершены!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Программа прервана пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)