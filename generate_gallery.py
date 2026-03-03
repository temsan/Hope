import os
import base64
from pathlib import Path
from PIL import Image
import io

# Путь к папке с изображениями
IMAGES_PATH = r'C:\Users\temsan\OneDrive\Desktop\Сканы\JPEG'
CROPPED_PATH = r'C:\Users\temsan\OneDrive\Pictures\Надежда'
OUTPUT_FILE = 'gallery.html'
CACHE_FILE = 'temperature_cache.json'
IMAGES_CACHE_FILE = 'images_cache.json'
THUMBNAIL_WIDTH = 400
FULL_WIDTH = 1920
QUALITY = 85

def load_temperature_cache():
    """Загружает кеш температур из файла."""
    import json
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_temperature_cache(cache):
    """Сохраняет кеш температур в файл."""
    import json
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def load_images_cache():
    """Загружает кеш обработанных изображений."""
    import json
    if os.path.exists(IMAGES_CACHE_FILE):
        try:
            with open(IMAGES_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_images_cache(cache):
    """Сохраняет кеш обработанных изображений."""
    import json
    with open(IMAGES_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)

def get_image_hash(image_path):
    """Возвращает хеш файла для проверки изменений."""
    import hashlib
    try:
        stat = os.stat(image_path)
        # Используем путь + размер + время модификации как уникальный идентификатор
        key = f"{image_path}:{stat.st_size}:{stat.st_mtime}"
        return hashlib.md5(key.encode()).hexdigest()
    except:
        return image_path

def auto_crop_gray_border(img, padding=0, bg_tolerance=3, aggressive=False):
    """
    Агрессивно обрезает серые/белые поля сканирования.
    """
    import numpy as np
    
    original_size = img.size
    
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Конвертируем в grayscale
    img_array = np.array(img.convert('L'))
    h, w = img_array.shape
    
    # Усредняем по полосам для стабильности
    strip_height = max(20, h // 80)
    strip_width = max(20, w // 80)
    
    tolerance = 1 if aggressive else bg_tolerance
    
    def find_edge_vertical(arr, from_top=True):
        """Ищет вертикальную границу контента"""
        rows = arr.shape[0]
        start = 0 if from_top else rows - 1
        end = rows // 2 if from_top else rows // 2 - 1
        step = 1 if from_top else -1
        
        # Базовая яркость края (усредняем больше пикселей)
        edge_size = min(100, rows // 8)
        if from_top:
            base_region = arr[:edge_size, :]
        else:
            base_region = arr[-edge_size:, :]
        
        base_brightness = np.mean(base_region)
        base_std = np.std(base_region)
        
        for y in range(start, end, step):
            # Усредняем полосу
            strip_end = min(y + strip_height, rows) if from_top else max(y - strip_height, 0)
            if from_top:
                strip = arr[y:strip_end, :]
            else:
                strip = arr[strip_end:y, :]
            
            if strip.size == 0:
                continue
                
            brightness = np.mean(strip)
            strip_std = np.std(strip)
            
            diff = abs(brightness - base_brightness)
            
            # Контент: резкое изменение ИЛИ высокий разброс
            if diff > tolerance or strip_std > base_std * 1.2 + tolerance:
                # Доп. проверка: смотрим следующие несколько полос
                next_y = y + step * strip_height * 2 if from_top else y - step * strip_height * 2
                if 0 <= next_y < rows - strip_height:
                    next_strip = arr[next_y:next_y+strip_height, :] if from_top else arr[next_y-strip_height:next_y, :]
                    next_brightness = np.mean(next_strip)
                    if abs(next_brightness - base_brightness) > tolerance * 0.5:
                        return y
        
        return start
    
    def find_edge_horizontal(arr, from_left=True):
        """Ищет горизонтальную границу контента"""
        cols = arr.shape[1]
        start = 0 if from_left else cols - 1
        end = cols // 2 if from_left else cols // 2 - 1
        step = 1 if from_left else -1
        
        edge_size = min(100, cols // 8)
        if from_left:
            base_region = arr[:, :edge_size]
        else:
            base_region = arr[:, -edge_size:]
        
        base_brightness = np.mean(base_region)
        base_std = np.std(base_region)
        
        for x in range(start, end, step):
            strip_end = min(x + strip_width, cols) if from_left else max(x - strip_width, 0)
            if from_left:
                strip = arr[:, x:strip_end]
            else:
                strip = arr[:, strip_end:x]
            
            if strip.size == 0:
                continue
                
            brightness = np.mean(strip)
            strip_std = np.std(strip)
            
            diff = abs(brightness - base_brightness)
            
            if diff > tolerance or strip_std > base_std * 1.2 + tolerance:
                next_x = x + step * strip_width * 2 if from_left else x - step * strip_width * 2
                if 0 <= next_x < cols - strip_width:
                    next_strip = arr[:, next_x:next_x+strip_width] if from_left else arr[:, next_x-strip_width:next_x]
                    next_brightness = np.mean(next_strip)
                    if abs(next_brightness - base_brightness) > tolerance * 0.5:
                        return x
        
        return start
    
    # Находим все границы
    top = find_edge_vertical(img_array, from_top=True)
    bottom = find_edge_vertical(img_array, from_top=False)
    left = find_edge_horizontal(img_array, from_left=True)
    right = find_edge_horizontal(img_array, from_left=False)
    
    if right <= left or bottom <= top:
        return img
    
    content_w = right - left
    content_h = bottom - top
    content_ratio = (content_w * content_h) / (w * h)
    
    # Доп. обрезка в агрессивном режиме - увеличенный отступ
    if aggressive and content_ratio > 0.3:
        safety = min(100, content_w // 20, content_h // 20)
        left = left + safety
        right = right - safety
        top = top + safety
        bottom = bottom - safety
        
        # Дополнительная проверка краёв - обрезаем ещё если края серые
        edge_check_size = 50
        if left + edge_check_size < right:
            left_edge = img_array[top:bottom, left:left+edge_check_size]
            if np.std(left_edge) < 10:  # Если мало вариации - значит серое поле
                left += edge_check_size
        
        if right - edge_check_size > left:
            right_edge = img_array[top:bottom, right-edge_check_size:right]
            if np.std(right_edge) < 10:
                right -= edge_check_size
        
        if top + edge_check_size < bottom:
            top_edge = img_array[top:top+edge_check_size, left:right]
            if np.std(top_edge) < 10:
                top += edge_check_size
        
        if bottom - edge_check_size > top:
            bottom_edge = img_array[bottom-edge_check_size:bottom, left:right]
            if np.std(bottom_edge) < 10:
                bottom -= edge_check_size
        
        # Проверяем валидность границ после всех обрезок
        left = max(0, min(left, w - 100))
        right = max(left + 100, min(right, w))
        top = max(0, min(top, h - 100))
        bottom = max(top + 100, min(bottom, h))
    
    if content_ratio < 0.25 or content_ratio > 0.99:
        return img
    
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(w, right + padding)
    bottom = min(h, bottom + padding)
    
    cropped = img.crop((left, top, right, bottom))
    
    if (cropped.size[0], cropped.size[1]) != original_size:
        print(f"    [cropped {w}x{h} -> {cropped.size[0]}x{cropped.size[1]}]")
    
    return cropped

def compress_image(image_path, max_width, quality, auto_crop=True):
    """Сжимает изображение, опционально обрезает серые поля и возвращает base64"""
    try:
        with Image.open(image_path) as img:
            # Конвертируем в RGB если нужно
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Обрезаем серые поля только для исходных файлов
            if auto_crop:
                img = auto_crop_gray_border(img, padding=0, bg_tolerance=2, aggressive=True)
            
            # Изменяем размер
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Сохраняем в буфер
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            buffer.seek(0)
            
            # Конвертируем в base64
            img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            return f'data:image/jpeg;base64,{img_base64}'
    except Exception as e:
        print(f'Ошибка обработки {image_path}: {e}')
        return None

def get_image_path(filename):
    """Возвращает путь к изображению: сначала ищет в кропнутых, затем в исходных"""
    # Проверяем, есть ли кропнутая версия
    cropped_path = os.path.join(CROPPED_PATH, filename)
    if os.path.exists(cropped_path):
        return cropped_path, True  # True = используется кропнутая версия
    
    # Иначе используем исходное
    original_path = os.path.join(IMAGES_PATH, filename)
    return original_path, False

def get_color_temperature(image_path, cache=None):
    """
    Определяет "теплоту" картины.
    Возвращает значение: отрицательное = холодная, положительное = тёплая.
    Использует соотношение красного к синему (R/B) в среднем цвете.
    Использует кеш для ускорения повторных запусков.
    """
    if cache is None:
        cache = {}
    
    # Проверяем кеш
    image_hash = get_image_hash(image_path)
    if image_hash in cache:
        return cache[image_hash]['temperature']
    
    try:
        with Image.open(image_path) as img:
            # Уменьшаем для быстрого анализа
            img_small = img.copy().convert('RGB')
            img_small.thumbnail((100, 100))
            
            # Получаем массив пикселей
            import numpy as np
            pixels = np.array(img_small)
            
            # Считаем среднее по каналам
            r_mean = np.mean(pixels[:, :, 0])
            g_mean = np.mean(pixels[:, :, 1])
            b_mean = np.mean(pixels[:, :, 2])
            
            # Яркость для нормализации
            brightness = r_mean + g_mean + b_mean + 1
            
            # Теплота = (красный - синий) / яркость
            # Отрицательное = больше синего (холодная)
            # Положительное = больше красного (тёплая)
            warmth = (r_mean - b_mean) / brightness
            
            # Сохраняем в кеш
            cache[image_hash] = {
                'temperature': warmth,
                'path': image_path
            }
            
            return warmth
    except Exception as e:
        print(f'Ошибка анализа {image_path}: {e}')
        return 0

def generate_gallery():
    print('Начинаем генерацию галереи...')
    print(f'Исходные изображения: {IMAGES_PATH}')
    print(f'Кропнутые изображения: {CROPPED_PATH}')
    
    # Загружаем кеш температур
    temp_cache = load_temperature_cache()
    cached_count = len(temp_cache)
    print(f'Загружено {cached_count} записей из кеша температур')
    
    # Получаем список изображений
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
    image_files = []
    
    for file in sorted(os.listdir(IMAGES_PATH)):
        if Path(file).suffix.lower() in image_extensions:
            image_files.append(file)
    
    print(f'Найдено изображений: {len(image_files)}')
    
    # Анализируем температуру цвета каждой картины
    print('Анализ цветовой температуры...')
    images_with_temp = []
    new_analyzed = 0
    for filename in image_files:
        image_path, is_cropped = get_image_path(filename)
        temp = get_color_temperature(image_path, temp_cache)
        images_with_temp.append((filename, temp))
        temp_label = "теплая" if temp > 0 else "холодная"
        cached_marker = "[cached]" if len(temp_cache) > cached_count else ""
        print(f'  {filename}: {temp:.3f} ({temp_label}) {cached_marker}')
        if len(temp_cache) > cached_count:
            cached_count = len(temp_cache)
            new_analyzed += 1
    
    # Сохраняем обновлённый кеш
    save_temperature_cache(temp_cache)
    print(f'Сохранено {new_analyzed} новых анализов в кеш')
    
    # Сортируем от холодного к теплому
    images_with_temp.sort(key=lambda x: x[1])
    image_files = [(item[0], item[1]) for item in images_with_temp]  # (filename, temperature)
    print('Сортировка: холодные к теплым')
    
    # Загружаем кеш изображений
    images_cache = load_images_cache()
    images_cache_updated = False
    print(f'Загружено {len(images_cache)} записей из кеша изображений')
    
    images_data = []
    cropped_count = 0
    cached_images_count = 0
    
    for i, (filename, temperature) in enumerate(image_files, 1):
        image_path, is_cropped = get_image_path(filename)
        source_label = "[CROPPED]" if is_cropped else "[original]"
        
        # Проверяем кеш изображений
        image_hash = get_image_hash(image_path)
        cache_key = f"{filename}_{THUMBNAIL_WIDTH}_{FULL_WIDTH}_{QUALITY}"
        
        if cache_key in images_cache and images_cache[cache_key].get('hash') == image_hash:
            # Используем кешированные данные
            thumbnail = images_cache[cache_key]['thumbnail']
            full = images_cache[cache_key]['full']
            cached_images_count += 1
            cache_status = "[cache]"
        else:
            # Обрабатываем изображение
            cache_status = "[process]"
            
            # Создаем thumbnail (обрезаем только исходные)
            thumbnail = compress_image(image_path, THUMBNAIL_WIDTH, QUALITY, auto_crop=not is_cropped)
            if not thumbnail:
                continue
            
            # Создаем полноразмерное изображение (обрезаем только исходные)
            full = compress_image(image_path, FULL_WIDTH, QUALITY, auto_crop=not is_cropped)
            if not full:
                continue
            
            # Сохраняем в кеш
            images_cache[cache_key] = {
                'hash': image_hash,
                'thumbnail': thumbnail,
                'full': full
            }
            images_cache_updated = True
        
        if is_cropped:
            cropped_count += 1
        
        temp_label = "теплая" if temperature > 0 else "холодная"
        print(f'Обработка {i}/{len(image_files)}: {filename} {source_label} {cache_status} ({temp_label})')
        
        images_data.append({
            'name': filename,
            'thumbnail': thumbnail,
            'full': full,
            'temperature': round(temperature, 4)
        })
    
    # Сохраняем кеш изображений
    if images_cache_updated:
        save_images_cache(images_cache)
        print(f'Сохранено {len(images_cache)} записей в кеш изображений')
    
    # Генерируем HTML
    html_content = generate_html(images_data)
    
    # Сохраняем файл
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    file_size = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f'\nГотово! Создан файл: {OUTPUT_FILE}')
    print(f'Обработано изображений: {len(images_data)}')
    print(f'Использовано кропнутых: {cropped_count}')
    print(f'Размер файла: {file_size:.2f} MB')

def generate_html(images_data):
    import json
    images_json = json.dumps(images_data, ensure_ascii=False)
    
    return f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Надежда Терёшкина — Галерея работ</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
    <style>
        /* 2026 Design System - Emotionally Aware Variables */
        :root {{
            /* Time-based color palettes */
            --morning-primary: #1a1a2e;
            --morning-secondary: #16213e;
            --morning-accent: #f4d03f;
            --day-primary: #0d0d12;
            --day-secondary: #151520;
            --day-accent: #667eea;
            --evening-primary: #0f0518;
            --evening-secondary: #1a0b2e;
            --evening-accent: #e74c3c;
            --night-primary: #050508;
            --night-secondary: #0a0a0f;
            --night-accent: #9b59b6;
            
            /* Current theme (default night) */
            --bg-primary: var(--night-primary);
            --bg-secondary: var(--night-secondary);
            --accent: var(--night-accent);
            --text-primary: #f5f3f0;
            --text-secondary: rgba(232, 228, 220, 0.7);
            
            /* Glassmorphism 2.0 */
            --glass-bg: rgba(255, 255, 255, 0.03);
            --glass-border: rgba(255, 255, 255, 0.08);
            --glass-blur: 20px;
            --glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            
            /* 3D Depth */
            --depth-1: translateZ(20px);
            --depth-2: translateZ(50px);
            --depth-3: translateZ(100px);
            --perspective: 1000px;
        }}
        
        /* Time-based theme classes */
        .theme-morning {{
            --bg-primary: var(--morning-primary);
            --bg-secondary: var(--morning-secondary);
            --accent: var(--morning-accent);
        }}
        .theme-day {{
            --bg-primary: var(--day-primary);
            --bg-secondary: var(--day-secondary);
            --accent: var(--day-accent);
        }}
        .theme-evening {{
            --bg-primary: var(--evening-primary);
            --bg-secondary: var(--evening-secondary);
            --accent: var(--evening-accent);
        }}
        .theme-night {{
            --bg-primary: var(--night-primary);
            --bg-secondary: var(--night-secondary);
            --accent: var(--night-accent);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        html {{
            scroll-behavior: smooth;
        }}

        body {{
            font-family: 'Inter', sans-serif;
            background: var(--bg-primary);
            min-height: 100vh;
            overflow-x: hidden;
            color: var(--text-primary);
            perspective: var(--perspective);
            transform-style: preserve-3d;
            transition: background 1.5s ease;
        }}

        /* 3D Atmospheric Layers */
        .atmosphere {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            background: 
                radial-gradient(ellipse 80% 50% at 50% -10%, rgba(30, 30, 50, 0.4) 0%, transparent 50%),
                radial-gradient(ellipse 60% 40% at 20% 100%, rgba(40, 30, 60, 0.3) 0%, transparent 40%),
                radial-gradient(ellipse 50% 30% at 80% 100%, rgba(30, 40, 60, 0.3) 0%, transparent 40%),
                linear-gradient(180deg, var(--bg-secondary) 0%, var(--bg-primary) 50%, var(--bg-secondary) 100%);
            transition: background 2s ease;
            transform: translateZ(-200px) scale(1.4);
        }}
        
        /* Floating Nebula Particles */
        .nebula {{
            position: fixed;
            width: 100%;
            height: 100%;
            top: 0;
            left: 0;
            z-index: 1;
            pointer-events: none;
            transform: translateZ(-100px);
        }}
        
        .nebula-particle {{
            position: absolute;
            border-radius: 50%;
            filter: blur(60px);
            opacity: 0.3;
            animation: float-3d 20s infinite ease-in-out;
        }}

        /* 3D Moon with Glassmorphism glow */
        .moon {{
            position: fixed;
            top: 8%;
            right: 12%;
            width: 140px;
            height: 140px;
            background: radial-gradient(circle at 35% 35%, 
                rgba(255, 254, 245, 0.95) 0%, 
                rgba(245, 243, 232, 0.9) 40%, 
                rgba(232, 228, 213, 0.8) 100%);
            border-radius: 50%;
            box-shadow: 
                0 0 80px rgba(255, 250, 230, 0.4),
                0 0 160px rgba(255, 250, 230, 0.2),
                inset -15px -15px 40px rgba(180, 175, 160, 0.4),
                0 20px 60px rgba(0, 0, 0, 0.3);
            z-index: 2;
            opacity: 0.95;
            transform: translateZ(50px);
            transition: all 1.5s ease;
            backdrop-filter: blur(2px);
        }}

        .moon::before {{
            content: '';
            position: absolute;
            top: 25%;
            left: 20%;
            width: 20px;
            height: 20px;
            background: rgba(200, 195, 180, 0.5);
            border-radius: 50%;
            box-shadow: 
                30px 12px 0 -3px rgba(200, 195, 180, 0.4),
                12px 35px 0 -5px rgba(200, 195, 180, 0.35);
        }}

        /* 3D Starfield */
        .stars {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 1;
            pointer-events: none;
            transform: translateZ(-50px);
        }}

        .star {{
            position: absolute;
            background: white;
            border-radius: 50%;
            animation: twinkle-3d 4s infinite ease-in-out;
        }}

        @keyframes twinkle-3d {{
            0%, 100% {{ opacity: 0.1; transform: scale(1) translateZ(0); }}
            50% {{ opacity: 1; transform: scale(1.5) translateZ(20px); }}
        }}
        
        @keyframes float-3d {{
            0%, 100% {{ transform: translateY(0) translateZ(0) rotate(0deg); }}
            33% {{ transform: translateY(-30px) translateZ(30px) rotate(120deg); }}
            66% {{ transform: translateY(20px) translateZ(-20px) rotate(240deg); }}
        }}

        /* Candles */
        .candles-container {{
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 200px;
            z-index: 1;
            pointer-events: none;
        }}

        .candle {{
            position: absolute;
            bottom: 0;
        }}

        .candle-body {{
            width: 24px;
            height: 80px;
            background: linear-gradient(90deg, 
                rgba(255, 250, 240, 0.9) 0%, 
                rgba(255, 248, 230, 0.95) 50%, 
                rgba(240, 235, 220, 0.9) 100%);
            border-radius: 3px 3px 8px 8px;
            position: relative;
        }}

        .candle-body::before {{
            content: '';
            position: absolute;
            top: -8px;
            left: 50%;
            transform: translateX(-50%);
            width: 4px;
            height: 10px;
            background: #3a3020;
            border-radius: 2px;
        }}

        .flame {{
            position: absolute;
            top: -35px;
            left: 50%;
            transform: translateX(-50%);
            width: 16px;
            height: 30px;
            background: radial-gradient(ellipse at 50% 80%, 
                rgba(255, 200, 100, 0.9) 0%, 
                rgba(255, 150, 50, 0.7) 40%, 
                rgba(255, 100, 50, 0.4) 70%, 
                transparent 100%);
            border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%;
            filter: blur(1px);
            animation: flicker 2s infinite ease-in-out;
            box-shadow: 
                0 0 20px rgba(255, 150, 50, 0.5),
                0 0 40px rgba(255, 100, 30, 0.3),
                0 0 60px rgba(255, 80, 20, 0.15);
        }}

        @keyframes flicker {{
            0%, 100% {{ transform: translateX(-50%) scale(1) rotate(-2deg); opacity: 0.95; }}
            25% {{ transform: translateX(-50%) scale(1.05) rotate(1deg); opacity: 1; }}
            50% {{ transform: translateX(-50%) scale(0.98) rotate(-1deg); opacity: 0.9; }}
            75% {{ transform: translateX(-50%) scale(1.02) rotate(2deg); opacity: 0.95; }}
        }}

        .candle:nth-child(1) {{ left: 5%; .candle-body {{ height: 60px; }} }}
        .candle:nth-child(2) {{ left: 8%; .candle-body {{ height: 90px; }} }}
        .candle:nth-child(3) {{ right: 6%; .candle-body {{ height: 75px; }} }}
        .candle:nth-child(4) {{ right: 10%; .candle-body {{ height: 55px; }} }}

        /* Floating Mist */
        .mist {{
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 300px;
            background: linear-gradient(to top, 
                rgba(13, 13, 18, 0.9) 0%, 
                rgba(13, 13, 18, 0.5) 30%, 
                transparent 100%);
            z-index: 2;
            pointer-events: none;
        }}

        /* Kinetic Typography Header */
        .header {{
            position: relative;
            z-index: 10;
            padding: 80px 40px 40px;
            text-align: center;
            transform-style: preserve-3d;
        }}

        .header-content {{
            transform: translateZ(80px);
        }}

        .header-content h1 {{
            font-family: 'Cormorant Garamond', serif;
            font-size: clamp(2.5rem, 6vw, 4rem);
            font-weight: 300;
            letter-spacing: 0.15em;
            color: var(--text-primary);
            margin-bottom: 20px;
            line-height: 1.1;
            transform-style: preserve-3d;
        }}
        
        /* Kinetic Letter Animation */
        .kinetic-text {{
            display: inline-block;
            opacity: 0;
            transform: translateY(100px) rotateX(-90deg);
            animation: kinetic-reveal 1.2s cubic-bezier(0.23, 1, 0.32, 1) forwards;
        }}
        
        @keyframes kinetic-reveal {{
            to {{
                opacity: 1;
                transform: translateY(0) rotateX(0);
            }}
        }}

        .subtitle {{
            font-family: 'Cormorant Garamond', serif;
            font-size: clamp(1.1rem, 2.2vw, 1.5rem);
            font-weight: 300;
            font-style: italic;
            color: var(--text-secondary);
        }}

        .sort-hint {{
            font-family: 'Inter', sans-serif;
            font-size: clamp(0.75rem, 1.5vw, 0.9rem);
            font-weight: 300;
            color: var(--text-muted);
            margin-top: 15px;
            letter-spacing: 0.1em;
            opacity: 0.8;
            letter-spacing: 0.3em;
            opacity: 0;
            animation: fade-in 1s ease 0.8s forwards;
        }}
        
        @keyframes fade-in {{
            to {{ opacity: 1; }}
        }}

        .divider {{
            width: 60px;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent), transparent);
            margin: 25px auto;
            opacity: 0;
            animation: expand-width 1s ease 0.5s forwards, glow 3s ease-in-out infinite;
        }}
        
        @keyframes expand-width {{
            from {{ width: 0; opacity: 0; }}
            to {{ width: 60px; opacity: 1; }}
        }}
        
        @keyframes glow {{
            0%, 100% {{ box-shadow: 0 0 10px var(--accent); }}
            50% {{ box-shadow: 0 0 30px var(--accent), 0 0 60px var(--accent); }}
        }}

        /* Container */
        .container {{
            position: relative;
            z-index: 10;
            max-width: 1600px;
            margin: 0 auto;
            padding: 20px 60px 80px;
            transform-style: preserve-3d;
        }}
        
        /* Intent-Based Mood Filter */
        .mood-filter {{
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-bottom: 50px;
            flex-wrap: wrap;
            transform: translateZ(60px);
        }}
        
        .mood-btn {{
            padding: 12px 28px;
            border: 1px solid var(--glass-border);
            background: var(--glass-bg);
            backdrop-filter: blur(var(--glass-blur));
            border-radius: 30px;
            color: var(--text-secondary);
            font-family: 'Inter', sans-serif;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.4s cubic-bezier(0.23, 1, 0.32, 1);
            box-shadow: var(--glass-shadow);
        }}
        
        .mood-btn:hover {{
            transform: translateY(-3px) scale(1.05);
            border-color: var(--accent);
            color: var(--text-primary);
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.4), 0 0 30px rgba(255, 255, 255, 0.1);
        }}
        
        .mood-btn.active {{
            background: rgba(255, 255, 255, 0.1);
            border-color: var(--accent);
            color: var(--text-primary);
            box-shadow: 0 0 30px var(--accent);
        }}



        /* Glassmorphism 2.0 Gallery Grid */
        .gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 50px 40px;
            padding: 40px 0;
            perspective: 1200px;
            transform-style: preserve-3d;
        }}

        .gallery-item {{
            position: relative;
            cursor: pointer;
            opacity: 0;
            transform: translateY(30px);
            transition: all 0.6s ease;
            border-radius: 8px;
            overflow: hidden;
            background: transparent;
        }}

        .gallery-item.loaded {{
            opacity: 1;
            transform: translateY(0);
        }}

        .gallery-item:hover {{
            transform: translateY(-8px) scale(1.02);
        }}

        /* Temperature Indicator */
        .temp-indicator {{
            position: absolute;
            top: 12px;
            right: 12px;
            width: 8px;
            height: 40px;
            border-radius: 4px;
            background: linear-gradient(to top, 
                #3b82f6 0%,   /* Cold - blue */
                #8b5cf6 50%,  /* Neutral - purple */
                #ef4444 100%  /* Warm - red */
            );
            opacity: 0.7;
            transition: opacity 0.3s ease;
            z-index: 10;
        }}

        .gallery-item:hover .temp-indicator {{
            opacity: 1;
        }}

        /* Image Container */
        .gallery-item .img-container {{
            position: relative;
            overflow: hidden;
            border-radius: 16px;
            height: 420px;
            background: rgba(0, 0, 0, 0.2);
        }}

        .gallery-item img {{
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: block;
            transition: transform 0.4s ease;
        }}

        .gallery-item:hover img {{
            transform: scale(1.05);
        }}
        /* Immersive Modal View */
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(2, 2, 4, 0.98);
            backdrop-filter: blur(40px) saturate(180%);
            transform-style: preserve-3d;
            perspective: 1500px;
        }}
        
        /* Ambient Background in Modal */
        .modal-ambient {{
            position: absolute;
            width: 100%;
            height: 100%;
            background: 
                radial-gradient(circle at 30% 50%, var(--accent) 0%, transparent 50%),
                radial-gradient(circle at 70% 50%, rgba(255,255,255,0.05) 0%, transparent 40%);
            opacity: 0.1;
            filter: blur(80px);
            animation: ambient-pulse 8s ease-in-out infinite;
        }}
        
        @keyframes ambient-pulse {{
            0%, 100% {{ opacity: 0.08; transform: scale(1); }}
            50% {{ opacity: 0.15; transform: scale(1.1); }}
        }}

        .modal-content {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%) translateZ(100px);
            max-width: 85vw;
            max-height: 80vh;
            object-fit: contain;
            border-radius: 16px;
            box-shadow: 
                0 50px 150px rgba(0, 0, 0, 0.6),
                0 0 100px rgba(255, 250, 240, 0.05);
            opacity: 0;
            transition: all 0.6s cubic-bezier(0.23, 1, 0.32, 1);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .modal-content.loaded {{
            opacity: 1;
            transform: translate(-50%, -50%) translateZ(100px) scale(1);
        }}

        .image-info {{
            position: absolute;
            bottom: 40px;
            left: 50%;
            transform: translateX(-50%) translateZ(50px);
            font-family: 'Cormorant Garamond', serif;
            font-size: 1.2rem;
            color: var(--text-secondary);
            letter-spacing: 0.25em;
            text-shadow: 0 2px 20px rgba(0,0,0,0.5);
        }}

        /* Moon-styled buttons */
        .close {{
            position: absolute;
            top: 40px;
            right: 50px;
            width: 56px;
            height: 56px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: rgba(245, 243, 232, 0.7);
            font-size: 28px;
            font-weight: 300;
            cursor: pointer;
            z-index: 1001;
            transition: all 0.4s cubic-bezier(0.23, 1, 0.32, 1);
            border-radius: 50%;
            background: radial-gradient(circle at 35% 35%, 
                rgba(255, 254, 245, 0.15) 0%, 
                rgba(245, 243, 232, 0.08) 50%, 
                rgba(232, 228, 213, 0.05) 100%);
            border: 1px solid rgba(255, 250, 240, 0.15);
            box-shadow: 
                0 0 20px rgba(255, 250, 230, 0.1),
                inset -5px -5px 15px rgba(200, 195, 180, 0.1);
            text-shadow: 0 0 10px rgba(255, 250, 240, 0.3);
        }}

        .close:hover {{
            color: rgba(255, 255, 250, 0.95);
            background: radial-gradient(circle at 35% 35%, 
                rgba(255, 254, 245, 0.25) 0%, 
                rgba(245, 243, 232, 0.15) 50%, 
                rgba(232, 228, 213, 0.08) 100%);
            box-shadow: 
                0 0 30px rgba(255, 250, 230, 0.2),
                0 0 60px rgba(255, 250, 230, 0.1),
                inset -5px -5px 15px rgba(200, 195, 180, 0.15);
            transform: rotate(90deg) scale(1.05);
            border-color: rgba(255, 250, 240, 0.25);
        }}

        .nav-buttons {{
            position: absolute;
            top: 50%;
            width: 100%;
            display: flex;
            justify-content: space-between;
            padding: 0 40px;
            transform: translateY(-50%);
            pointer-events: none;
        }}

        .nav-btn {{
            width: 64px;
            height: 64px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: radial-gradient(circle at 35% 35%, 
                rgba(255, 254, 245, 0.12) 0%, 
                rgba(245, 243, 232, 0.06) 50%, 
                rgba(232, 228, 213, 0.04) 100%);
            border: 1px solid rgba(255, 250, 240, 0.12);
            border-radius: 50%;
            color: rgba(245, 243, 232, 0.75);
            font-size: 22px;
            cursor: pointer;
            transition: all 0.4s cubic-bezier(0.23, 1, 0.32, 1);
            pointer-events: auto;
            box-shadow: 
                0 0 25px rgba(255, 250, 230, 0.08),
                inset -4px -4px 12px rgba(200, 195, 180, 0.08);
            text-shadow: 0 0 8px rgba(255, 250, 240, 0.25);
        }}

        .nav-btn:hover {{
            background: radial-gradient(circle at 35% 35%, 
                rgba(255, 254, 245, 0.22) 0%, 
                rgba(245, 243, 232, 0.12) 50%, 
                rgba(232, 228, 213, 0.06) 100%);
            border-color: rgba(255, 250, 240, 0.22);
            color: rgba(255, 255, 250, 0.95);
            box-shadow: 
                0 0 40px rgba(255, 250, 230, 0.15),
                0 0 80px rgba(255, 250, 230, 0.08),
                inset -4px -4px 12px rgba(200, 195, 180, 0.12);
            transform: scale(1.08);
        }}

        .nav-btn:active {{
            transform: scale(0.98);
            box-shadow: 
                0 0 20px rgba(255, 250, 230, 0.1),
                inset -2px -2px 8px rgba(200, 195, 180, 0.1);
        }}

        /* Footer */
        .footer {{
            position: relative;
            z-index: 10;
            padding: 60px 40px;
            text-align: center;
            border-top: 1px solid rgba(255, 255, 255, 0.04);
        }}

        .footer p {{
            font-family: 'Cormorant Garamond', serif;
            font-size: 1rem;
            color: rgba(232, 228, 220, 0.4);
            letter-spacing: 0.15em;
        }}

        /* Responsive - Adaptive */
        
        /* Large Desktop */
        @media (min-width: 1600px) {{
            .gallery {{ 
                grid-template-columns: repeat(auto-fill, minmax(450px, 1fr)); 
                gap: 40px; 
            }}
            .gallery-item img {{ height: 520px; }}
        }}
        
        /* Desktop */
        @media (max-width: 1400px) {{
            .gallery {{ 
                grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); 
                gap: 35px; 
            }}
            .gallery-item img {{ height: 450px; }}
        }}

        /* Tablet Landscape */
        @media (max-width: 1024px) {{
            .container {{ padding: 30px; }}
            .gallery {{ 
                grid-template-columns: repeat(2, 1fr); 
                gap: 25px; 
            }}
            .gallery-item img {{ height: 380px; }}
            .moon {{ width: 80px; height: 80px; right: 6%; top: 6%; }}
            .header {{ padding: 80px 30px 50px; }}
        }}

        /* Tablet Portrait */
        @media (max-width: 768px) {{
            .header {{ padding: 60px 20px 40px; }}
            .header-content h1 {{ letter-spacing: 0.1em; }}
            .container {{ padding: 20px; }}
            .gallery {{ 
                grid-template-columns: repeat(2, 1fr); 
                gap: 15px; 
            }}
            .gallery-item img {{ height: 280px; }}
            .gallery-item:hover {{ transform: scale(1.04); }}
            .gallery-item:hover img {{ transform: scale(1.06); }}
            .image-name {{ font-size: 0.65rem; bottom: -25px; }}
            .nav-buttons {{ padding: 0 15px; }}
            .nav-btn {{ width: 45px; height: 45px; font-size: 18px; }}
            .close {{ right: 15px; top: 15px; width: 45px; height: 45px; font-size: 26px; }}
            .moon {{ width: 50px; height: 50px; top: 4%; right: 5%; }}
            .candles-container {{ display: none; }}
            .modal-content {{ max-width: 95vw; max-height: 80vh; }}
        }}
        
        /* Mobile */
        @media (max-width: 480px) {{
            .header {{ padding: 50px 15px 30px; }}
            .subtitle {{ letter-spacing: 0.2em; }}
            .sort-hint {{ font-size: 0.7rem; margin-top: 10px; }}
            .divider {{ margin: 20px auto; }}
            .container {{ padding: 15px; }}
            .intro {{ margin-bottom: 40px; font-size: 1rem; }}
            .gallery {{ 
                grid-template-columns: 1fr; 
                gap: 20px; 
            }}
            .gallery-item img {{ height: 320px; }}

            .footer {{ padding: 40px 20px; }}
            .footer p {{ font-size: 0.9rem; }}
            .nav-buttons {{ padding: 0 10px; }}
            .nav-btn {{ 
                width: 40px; 
                height: 40px; 
                font-size: 16px;
                background: rgba(255, 255, 255, 0.08);
            }}
            .stars {{ display: none; }}
            .moon {{ width: 40px; height: 40px; }}
        }}
        
        /* Small Mobile */
        @media (max-width: 360px) {{
            .gallery-item img {{ height: 260px; }}
            .header-content h1 {{ font-size: 2rem; }}
        }}

        /* Scrollbar */
        ::-webkit-scrollbar {{
            width: 8px;
        }}

        ::-webkit-scrollbar-track {{
            background: var(--deep-night);
        }}

        ::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}
    </style>
</head>
<body>
    <div class="atmosphere"></div>
    
    <div class="moon"></div>
    
    <div class="stars" id="stars"></div>
    
    <div class="candles-container">
        <div class="candle">
            <div class="candle-body" style="height: 60px;">
                <div class="flame"></div>
            </div>
        </div>
        <div class="candle">
            <div class="candle-body" style="height: 90px;">
                <div class="flame"></div>
            </div>
        </div>
        <div class="candle">
            <div class="candle-body" style="height: 75px;">
                <div class="flame"></div>
            </div>
        </div>
        <div class="candle">
            <div class="candle-body" style="height: 55px;">
                <div class="flame"></div>
            </div>
        </div>
    </div>
    
    <div class="mist"></div>

    <!-- Nebula 3D Background -->
    <div class="nebula" id="nebula"></div>
    
    <header class="header">
        <div class="header-content">
            <h1 id="kineticTitle"></h1>
            <div class="divider"></div>
            <p class="subtitle">Художница</p>
            <p class="sort-hint">❄️ Сортировка: от холодного к тёплому 🔥</p>
        </div>
    </header>

    <div class="container">
        <!-- Intent-Based Mood Filter -->
        <div class="mood-filter">
            <button class="mood-btn active" data-mood="all">Все работы</button>
            <button class="mood-btn" data-mood="calm">Спокойствие</button>
            <button class="mood-btn" data-mood="energy">Энергия</button>
            <button class="mood-btn" data-mood="dream">Мечты</button>
        </div>
        <div id="gallery" class="gallery"></div>
    </div>

    <div id="modal" class="modal">
        <div class="modal-ambient"></div>
        <span class="close">&times;</span>
        <img class="modal-content" id="modalImg">
        <div class="image-info" id="imageInfo"></div>
        <div class="nav-buttons">
            <button id="prevBtn" class="nav-btn" title="Предыдущая">&#10094;</button>
            <button id="nextBtn" class="nav-btn" title="Следующая">&#10095;</button>
        </div>
    </div>

    <footer class="footer">
        <p>Надежда Александровна Терёшкина</p>
    </footer>

    <script>
        const imagesData = {images_json};
        let currentIndex = 0;
        const fullImagesLoaded = new Set();

        const gallery = document.getElementById('gallery');
        const modal = document.getElementById('modal');
        const modalImg = document.getElementById('modalImg');
        const imageInfo = document.getElementById('imageInfo');
        const closeBtn = document.querySelector('.close');
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');

        // Time-Based Emotionally Aware Theme
        function setTimeBasedTheme() {{
            const hour = new Date().getHours();
            const body = document.body;
            
            // Remove all theme classes
            body.classList.remove('theme-morning', 'theme-day', 'theme-evening', 'theme-night');
            
            // Apply theme based on time
            if (hour >= 5 && hour < 12) {{
                body.classList.add('theme-morning');
            }} else if (hour >= 12 && hour < 17) {{
                body.classList.add('theme-day');
            }} else if (hour >= 17 && hour < 21) {{
                body.classList.add('theme-evening');
            }} else {{
                body.classList.add('theme-night');
            }}
        }}
        
        // Create 3D Nebula Particles
        function createNebula() {{
            const nebula = document.getElementById('nebula');
            const colors = ['#667eea', '#f4d03f', '#e74c3c', '#9b59b6', '#00f2fe'];
            
            for (let i = 0; i < 8; i++) {{
                const particle = document.createElement('div');
                particle.className = 'nebula-particle';
                const size = Math.random() * 200 + 100;
                particle.style.width = size + 'px';
                particle.style.height = size + 'px';
                particle.style.left = Math.random() * 100 + '%';
                particle.style.top = Math.random() * 100 + '%';
                particle.style.background = `radial-gradient(circle, ${{colors[i % colors.length]}}40 0%, transparent 70%)`;
                particle.style.animationDelay = `${{Math.random() * 10}}s`;
                particle.style.animationDuration = `${{15 + Math.random() * 10}}s`;
                nebula.appendChild(particle);
            }}
        }}

        // Generate stars
        function createStars() {{
            const starsContainer = document.getElementById('stars');
            const starCount = 100;
            
            for (let i = 0; i < starCount; i++) {{
                const star = document.createElement('div');
                star.className = 'star';
                const size = Math.random() * 2 + 1;
                star.style.width = size + 'px';
                star.style.height = size + 'px';
                star.style.left = Math.random() * 100 + '%';
                star.style.top = Math.random() * 70 + '%';
                star.style.animationDelay = Math.random() * 4 + 's';
                star.style.opacity = Math.random() * 0.6 + 0.1;
                starsContainer.appendChild(star);
            }}
        }}
        
        // Kinetic Typography Animation
        function createKineticText() {{
            const title = document.getElementById('kineticTitle');
            const text = 'Надежда';
            
            text.split('').forEach((char, i) => {{
                const span = document.createElement('span');
                span.className = 'kinetic-text';
                span.textContent = char === ' ' ? '\u00A0' : char;
                span.style.animationDelay = `${{i * 0.05}}s`;
                title.appendChild(span);
            }});
        }}
        
        // Intent-Based Mood Filter
        function setupMoodFilter() {{
            const moodBtns = document.querySelectorAll('.mood-btn');
            
            moodBtns.forEach(btn => {{
                btn.addEventListener('click', () => {{
                    moodBtns.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    
                    const mood = btn.dataset.mood;
                    filterGalleryByMood(mood);
                }});
            }});
        }}
        
        function filterGalleryByMood(mood) {{
            const items = document.querySelectorAll('.gallery-item');
            
            items.forEach((item, index) => {{
                if (mood === 'all') {{
                    item.style.display = 'block';
                    setTimeout(() => item.classList.add('loaded'), index * 50);
                }} else {{
                    // Simulate mood-based filtering based on image index
                    const itemMood = ['calm', 'energy', 'dream'][index % 3];
                    if (itemMood === mood) {{
                        item.style.display = 'block';
                        setTimeout(() => item.classList.add('loaded'), 100);
                    }} else {{
                        item.style.display = 'none';
                    }}
                }}
            }});
        }}

        // Initialize gallery with Intersection Observer for reveal effect
        let revealObserver;

        function initGallery() {{
            setTimeBasedTheme();
            createNebula();
            createStars();
            createKineticText();
            setupMoodFilter();
            
            imagesData.forEach((imageData, index) => {{
                createGalleryItem(imageData, index);
            }});

            setupRevealObserver();
            setupParallax();
            preloadFullImages();
        }}

        function createGalleryItem(imageData, index) {{
            const item = document.createElement('div');
            item.className = 'gallery-item';
            item.dataset.mood = ['calm', 'energy', 'dream'][index % 3];
            
            const imgContainer = document.createElement('div');
            imgContainer.className = 'img-container';
            
            const img = document.createElement('img');
            img.src = imageData.thumbnail;
            img.alt = '';
            img.loading = 'lazy';
            
            // Temperature indicator
            if (imageData.temperature !== undefined) {{
                const tempIndicator = document.createElement('div');
                tempIndicator.className = 'temp-indicator';
                // Map temperature (-0.15 to 0.15) to position (0% to 100%)
                const temp = Math.max(-0.15, Math.min(0.15, imageData.temperature));
                const position = ((temp + 0.15) / 0.30) * 100;
                tempIndicator.style.setProperty('--temp-position', position + '%');
                tempIndicator.style.cssText += `::after {{ top: calc(100% - ${{position}}%); }}`;
                // Use inline style for the marker position
                const marker = document.createElement('div');
                marker.style.cssText = `
                    position: absolute;
                    left: 50%;
                    top: ${{100 - position}}%;
                    transform: translate(-50%, -50%);
                    width: 12px;
                    height: 3px;
                    border-radius: 2px;
                    background: white;
                    box-shadow: 0 0 4px rgba(0,0,0,0.5);
                `;
                tempIndicator.appendChild(marker);
                imgContainer.appendChild(tempIndicator);
            }}
            
            imgContainer.appendChild(img);
            item.appendChild(imgContainer);
            item.addEventListener('click', () => openModal(index));
            gallery.appendChild(item);
            
            setTimeout(() => {{
                item.classList.add('loaded');
            }}, index * 100);
        }}

        // Shadow reveal effect using Intersection Observer
        function setupRevealObserver() {{
            const options = {{
                root: null,
                rootMargin: '-5% 0px -5% 0px',
                threshold: [0, 0.1, 0.25, 0.5, 0.75, 1]
            }};

            revealObserver = new IntersectionObserver((entries) => {{
                entries.forEach(entry => {{
                    const ratio = entry.intersectionRatio;
                    
                    if (ratio > 0.25) {{
                        entry.target.classList.add('revealed');
                    }} else {{
                        entry.target.classList.remove('revealed');
                    }}
                }});
            }}, options);

            document.querySelectorAll('.gallery-item').forEach(item => {{
                revealObserver.observe(item);
            }});
        }}

        // 3D Parallax on mouse move
        function setupParallax() {{
            document.addEventListener('mousemove', (e) => {{
                const mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
                const mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
                
                // Moon parallax
                const moon = document.querySelector('.moon');
                if (moon) {{
                    moon.style.transform = `translate(${{mouseX * 30}}px, ${{mouseY * 20}}px) translateZ(50px)`;
                }}
                
                // Nebula parallax
                const nebula = document.getElementById('nebula');
                if (nebula) {{
                    nebula.style.transform = `translate(${{mouseX * -50}}px, ${{mouseY * -30}}px) translateZ(-100px)`;
                }}
                
                // Header parallax
                const header = document.querySelector('.header-content');
                if (header) {{
                    header.style.transform = `translate(${{mouseX * 10}}px, ${{mouseY * 10}}px) translateZ(80px)`;
                }}
            }});
            
            // Scroll parallax
            window.addEventListener('scroll', () => {{
                const scrolled = window.pageYOffset;
                const moon = document.querySelector('.moon');
                if (moon) {{
                    moon.style.transform = `translateY(${{scrolled * 0.1}}px) translateZ(50px)`;
                }}
            }}, {{ passive: true }});
        }}

        function preloadFullImages() {{
            imagesData.forEach((imageData, index) => {{
                setTimeout(() => {{
                    const img = new Image();
                    img.onload = () => {{
                        fullImagesLoaded.add(index);
                    }};
                    img.src = imageData.full;
                }}, index * 150);
            }});
        }}

        let scrollPos = 0;
        
        function openModal(index) {{
            scrollPos = window.scrollY; // Сохраняем позицию скролла
            currentIndex = index;
            modal.style.display = 'block';
            modalImg.classList.remove('loaded');
            document.body.style.overflow = 'hidden';
            
            modalImg.src = imagesData[currentIndex].thumbnail;
            
            if (fullImagesLoaded.has(currentIndex)) {{
                modalImg.src = imagesData[currentIndex].full;
                modalImg.classList.add('loaded');
            }} else {{
                const fullImg = new Image();
                fullImg.onload = () => {{
                    modalImg.src = imagesData[currentIndex].full;
                    modalImg.classList.add('loaded');
                    fullImagesLoaded.add(currentIndex);
                }};
                fullImg.src = imagesData[currentIndex].full;
            }}
            
            updateImageInfo();
        }}

        function updateImageInfo() {{
            const currentImage = imagesData[currentIndex];
            let tempText = '';
            if (currentImage.temperature !== undefined) {{
                const temp = currentImage.temperature;
                const tempLabel = temp > 0.05 ? 'теплая' : temp < -0.05 ? 'холодная' : 'нейтральная';
                const tempIcon = temp > 0.05 ? '🔥' : temp < -0.05 ? '❄️' : '⚪';
                tempText = ` | ${{tempIcon}} ${{tempLabel}}`;
            }}
            imageInfo.textContent = `${{currentIndex + 1}} / ${{imagesData.length}}${{tempText}}`;
        }}

        function closeModal() {{
            modal.style.display = 'none';
            document.body.style.overflow = '';
            window.scrollTo(0, scrollPos); // Восстанавливаем позицию скролла
        }}

        closeBtn.addEventListener('click', closeModal);

        modal.addEventListener('click', (e) => {{
            if (e.target === modal) closeModal();
        }});

        prevBtn.addEventListener('click', (e) => {{
            e.stopPropagation();
            currentIndex = (currentIndex - 1 + imagesData.length) % imagesData.length;
            openModal(currentIndex);
        }});

        nextBtn.addEventListener('click', (e) => {{
            e.stopPropagation();
            currentIndex = (currentIndex + 1) % imagesData.length;
            openModal(currentIndex);
        }});

        document.addEventListener('keydown', (e) => {{
            if (modal.style.display === 'block') {{
                if (e.key === 'ArrowLeft') prevBtn.click();
                if (e.key === 'ArrowRight') nextBtn.click();
                if (e.key === 'Escape') closeModal();
            }}
        }});

        window.addEventListener('load', initGallery);
    </script>
</body>
</html>'''

if __name__ == '__main__':
    generate_gallery()
