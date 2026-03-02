import os
import base64
from pathlib import Path
from PIL import Image
import io

# Путь к папке с изображениями
IMAGES_PATH = r'C:\Users\temsan\OneDrive\Desktop\Сканы\JPEG'
CROPPED_PATH = r'C:\Users\temsan\OneDrive\Pictures\Надежда'
OUTPUT_FILE = 'gallery.html'
THUMBNAIL_WIDTH = 400
FULL_WIDTH = 1920
QUALITY = 85

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
    
    tolerance = 2 if aggressive else bg_tolerance
    
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
    
    # Доп. обрезка в агрессивном режиме
    if aggressive and content_ratio > 0.3:
        safety = min(20, content_w // 50, content_h // 50)
        left = min(left + safety, right - 100)
        right = max(right - safety, left + 100)
        top = min(top + safety, bottom - 100)
        bottom = max(bottom - safety, top + 100)
    
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

def generate_gallery():
    print('Начинаем генерацию галереи...')
    print(f'Исходные изображения: {IMAGES_PATH}')
    print(f'Кропнутые изображения: {CROPPED_PATH}')
    
    # Получаем список изображений
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
    image_files = []
    
    for file in sorted(os.listdir(IMAGES_PATH)):
        if Path(file).suffix.lower() in image_extensions:
            image_files.append(file)
    
    print(f'Найдено изображений: {len(image_files)}')
    
    images_data = []
    cropped_count = 0
    
    for i, filename in enumerate(image_files, 1):
        image_path, is_cropped = get_image_path(filename)
        source_label = "[CROPPED]" if is_cropped else "[original]"
        print(f'Обработка {i}/{len(image_files)}: {filename} {source_label}')
        
        if is_cropped:
            cropped_count += 1
        
        # Создаем thumbnail (обрезаем только исходные)
        thumbnail = compress_image(image_path, THUMBNAIL_WIDTH, QUALITY, auto_crop=not is_cropped)
        if not thumbnail:
            continue
        
        # Создаем полноразмерное изображение (обрезаем только исходные)
        full = compress_image(image_path, FULL_WIDTH, QUALITY, auto_crop=not is_cropped)
        if not full:
            continue
        
        images_data.append({
            'name': filename,
            'thumbnail': thumbnail,
            'full': full
        })
    
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
        :root {{
            --moon-glow: rgba(255, 248, 220, 0.15);
            --candle-warm: rgba(255, 180, 80, 0.12);
            --deep-night: #0d0d12;
            --midnight: #151520;
            --mist: rgba(255, 255, 255, 0.03);
            --glass: rgba(255, 255, 255, 0.04);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Inter', sans-serif;
            background: var(--deep-night);
            min-height: 100vh;
            overflow-x: hidden;
            color: #e8e6e1;
        }}

        /* Atmospheric Background with Moon */
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
                linear-gradient(180deg, #0a0a0f 0%, #12121a 30%, #0d0d14 70%, #0a0a0f 100%);
        }}

        /* Moon */
        .moon {{
            position: fixed;
            top: 8%;
            right: 12%;
            width: 120px;
            height: 120px;
            background: radial-gradient(circle at 35% 35%, #fffef5 0%, #f5f3e8 40%, #e8e4d5 100%);
            border-radius: 50%;
            box-shadow: 
                0 0 60px rgba(255, 250, 230, 0.3),
                0 0 120px rgba(255, 250, 230, 0.15),
                inset -10px -10px 30px rgba(200, 195, 180, 0.3);
            z-index: 1;
            opacity: 0.9;
        }}

        .moon::before {{
            content: '';
            position: absolute;
            top: 25%;
            left: 20%;
            width: 15px;
            height: 15px;
            background: rgba(200, 195, 180, 0.4);
            border-radius: 50%;
            box-shadow: 
                25px 10px 0 -2px rgba(200, 195, 180, 0.3),
                10px 30px 0 -4px rgba(200, 195, 180, 0.25);
        }}

        /* Stars */
        .stars {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            pointer-events: none;
        }}

        .star {{
            position: absolute;
            background: white;
            border-radius: 50%;
            animation: twinkle 3s infinite ease-in-out;
        }}

        @keyframes twinkle {{
            0%, 100% {{ opacity: 0.2; transform: scale(1); }}
            50% {{ opacity: 0.8; transform: scale(1.2); }}
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

        /* Header */
        .header {{
            position: relative;
            z-index: 10;
            padding: 100px 40px 60px;
            text-align: center;
        }}

        .header-content h1 {{
            font-family: 'Cormorant Garamond', serif;
            font-size: clamp(2.5rem, 6vw, 4.5rem);
            font-weight: 300;
            letter-spacing: 0.15em;
            color: #f5f3f0;
            text-shadow: 
                0 0 40px rgba(255, 250, 240, 0.1),
                0 2px 4px rgba(0, 0, 0, 0.3);
            margin-bottom: 20px;
            line-height: 1.2;
        }}

        .subtitle {{
            font-family: 'Cormorant Garamond', serif;
            font-size: clamp(1.2rem, 2.5vw, 1.6rem);
            font-weight: 300;
            font-style: italic;
            color: rgba(232, 228, 220, 0.7);
            letter-spacing: 0.3em;
        }}

        .divider {{
            width: 60px;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(232, 228, 220, 0.4), transparent);
            margin: 30px auto;
        }}

        /* Container */
        .container {{
            position: relative;
            z-index: 10;
            max-width: 1600px;
            margin: 0 auto;
            padding: 40px 60px 100px;
        }}

        .intro {{
            text-align: center;
            margin-bottom: 60px;
            font-size: 1.1rem;
            font-weight: 300;
            color: rgba(232, 228, 220, 0.6);
            letter-spacing: 0.1em;
        }}

        .image-count {{
            text-align: center;
            margin-bottom: 40px;
            font-size: 0.9rem;
            color: rgba(232, 228, 220, 0.4);
            letter-spacing: 0.2em;
            text-transform: uppercase;
        }}

        /* Gallery Grid - Creative Shadow Reveal */
        .gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 60px 40px;
            padding: 40px 0;
            perspective: 1000px;
        }}

        .gallery-item {{
            position: relative;
            overflow: visible;
            cursor: pointer;
            opacity: 0;
            transform: translateY(80px) rotateX(10deg);
            transform-style: preserve-3d;
            transition: all 0.8s cubic-bezier(0.23, 1, 0.32, 1);
            background: transparent;
        }}

        .gallery-item.loaded {{
            opacity: 1;
            transform: translateY(0) rotateX(0deg);
        }}

        /* Shadow reveal effect */
        .gallery-item::before {{
            content: '';
            position: absolute;
            top: 5%;
            left: 5%;
            right: 5%;
            bottom: 0;
            background: radial-gradient(ellipse at center, 
                rgba(0,0,0,0.6) 0%, 
                rgba(0,0,0,0.3) 40%, 
                transparent 70%);
            filter: blur(20px);
            opacity: 0.8;
            transform: translateZ(-50px);
            transition: all 0.6s ease;
            z-index: -1;
        }}

        .gallery-item.revealed::before {{
            opacity: 0.3;
            filter: blur(10px);
            transform: translateZ(-20px);
        }}

        /* Vignette overlay that fades on reveal */
        .gallery-item::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: radial-gradient(ellipse at center, 
                transparent 20%, 
                rgba(13,13,18,0.6) 70%,
                rgba(13,13,18,0.9) 100%);
            opacity: 1;
            transition: opacity 1.2s ease;
            pointer-events: none;
        }}

        .gallery-item.revealed::after {{
            opacity: 0;
        }}

        .gallery-item:hover {{
            transform: scale(1.05) translateZ(30px);
            z-index: 100;
        }}

        .gallery-item img {{
            width: 100%;
            height: 480px;
            object-fit: contain;
            display: block;
            transition: all 0.8s cubic-bezier(0.23, 1, 0.32, 1);
            filter: brightness(0.6) contrast(0.95);
            transform: scale(0.95);
        }}

        .gallery-item.loaded img {{
            filter: brightness(0.92) contrast(1.02);
            transform: scale(1);
        }}

        .gallery-item.revealed img {{
            filter: brightness(1) contrast(1.05);
        }}

        .gallery-item:hover img {{
            transform: scale(1.08);
            filter: brightness(1.1) contrast(1.08);
        }}



        /* Modal */
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(5, 5, 8, 0.97);
            backdrop-filter: blur(30px);
        }}

        .modal-content {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            max-width: 90vw;
            max-height: 85vh;
            object-fit: contain;
            border-radius: 4px;
            box-shadow: 
                0 30px 100px rgba(0, 0, 0, 0.5),
                0 0 60px rgba(255, 250, 240, 0.03);
            opacity: 0;
            transition: opacity 0.5s ease;
        }}

        .modal-content.loaded {{
            opacity: 1;
        }}

        .image-info {{
            position: absolute;
            bottom: 40px;
            left: 50%;
            transform: translateX(-50%);
            font-family: 'Cormorant Garamond', serif;
            font-size: 1.1rem;
            color: rgba(232, 228, 220, 0.6);
            letter-spacing: 0.2em;
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
            .divider {{ margin: 20px auto; }}
            .container {{ padding: 15px; }}
            .intro {{ margin-bottom: 40px; font-size: 1rem; }}
            .gallery {{ 
                grid-template-columns: 1fr; 
                gap: 20px; 
            }}
            .gallery-item img {{ height: 320px; }}
            .image-count {{ font-size: 0.8rem; }}
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

    <header class="header">
        <div class="header-content">
            <h1>Надежда Александровна Терёшкина</h1>
            <div class="divider"></div>
            <p class="subtitle">Художница</p>
        </div>
    </header>

    <div class="container">
        <div class="intro">
            <p>Галерея работ</p>
        </div>
        
        <div id="imageCount" class="image-count"></div>
        <div id="gallery" class="gallery"></div>
    </div>

    <div id="modal" class="modal">
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
        const imageCount = document.getElementById('imageCount');
        const closeBtn = document.querySelector('.close');
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');

        // Generate stars
        function createStars() {{
            const starsContainer = document.getElementById('stars');
            const starCount = 80;
            
            for (let i = 0; i < starCount; i++) {{
                const star = document.createElement('div');
                star.className = 'star';
                const size = Math.random() * 2 + 1;
                star.style.width = size + 'px';
                star.style.height = size + 'px';
                star.style.left = Math.random() * 100 + '%';
                star.style.top = Math.random() * 60 + '%';
                star.style.animationDelay = Math.random() * 3 + 's';
                star.style.opacity = Math.random() * 0.5 + 0.2;
                starsContainer.appendChild(star);
            }}
        }}

        // Initialize gallery with Intersection Observer for reveal effect
        let revealObserver;
        let parallaxItems = [];

        function initGallery() {{
            createStars();
            imageCount.textContent = `Загружено работ: ${{imagesData.length}}`;
            
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
            
            const img = document.createElement('img');
            img.src = imageData.thumbnail;
            img.alt = '';
            img.loading = 'lazy';
            
            item.appendChild(img);
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

        // Simple parallax for moon only
        function setupParallax() {{
            window.addEventListener('scroll', () => {{
                const scrolled = window.pageYOffset;
                const moon = document.querySelector('.moon');
                if (moon) {{
                    moon.style.transform = `translateY(${{scrolled * 0.08}}px)`;
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

        function openModal(index) {{
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
            imageInfo.textContent = `${{currentIndex + 1}} / ${{imagesData.length}}`;
        }}

        function closeModal() {{
            modal.style.display = 'none';
            document.body.style.overflow = '';
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
