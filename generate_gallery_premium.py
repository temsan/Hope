import os
import base64
import json
import hashlib
from pathlib import Path
from PIL import Image
import io

# Путь к папке с изображениями
IMAGES_PATH = r'C:\Users\temsan\OneDrive\Desktop\Сканы\JPEG'
OUTPUT_FILE = 'gallery.html'
CACHE_FILE = 'gallery_cache.json'
THUMBNAIL_WIDTH = 600
FULL_WIDTH = 2400
QUALITY = 90

def get_file_hash(file_path):
    """Получает хеш файла для проверки изменений"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def load_cache():
    """Загружает кеш из файла"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache):
    """Сохраняет кеш в файл"""
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)

def compress_image(image_path, max_width, quality):
    """Сжимает изображение и возвращает base64"""
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

def generate_gallery():
    print('🎨 Начинаем генерацию премиальной галереи...')
    
    # Загружаем кеш
    cache = load_cache()
    cache_updated = False
    
    # Получаем список изображений
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp'}
    image_files = []
    
    for file in sorted(os.listdir(IMAGES_PATH)):
        if Path(file).suffix.lower() in image_extensions:
            image_files.append(file)
    
    print(f'📁 Найдено изображений: {len(image_files)}')
    
    images_data = []
    cached_count = 0
    processed_count = 0
    
    for i, filename in enumerate(image_files, 1):
        image_path = os.path.join(IMAGES_PATH, filename)
        file_hash = get_file_hash(image_path)
        
        # Проверяем кеш
        if filename in cache and cache[filename].get('hash') == file_hash:
            # Используем кешированные данные
            print(f'✓ {i}/{len(image_files)}: {filename} (из кеша)')
            images_data.append({
                'name': filename,
                'thumbnail': cache[filename]['thumbnail'],
                'full': cache[filename]['full']
            })
            cached_count += 1
        else:
            # Обрабатываем изображение
            print(f'⚙ {i}/{len(image_files)}: {filename} (обработка...)')
            
            # Создаем thumbnail
            thumbnail = compress_image(image_path, THUMBNAIL_WIDTH, QUALITY)
            if not thumbnail:
                continue
            
            # Создаем полноразмерное изображение
            full = compress_image(image_path, FULL_WIDTH, QUALITY)
            if not full:
                continue
            
            # Сохраняем в кеш
            cache[filename] = {
                'hash': file_hash,
                'thumbnail': thumbnail,
                'full': full
            }
            cache_updated = True
            
            images_data.append({
                'name': filename,
                'thumbnail': thumbnail,
                'full': full
            })
            processed_count += 1
    
    # Сохраняем кеш если были изменения
    if cache_updated:
        print(f'\n💾 Сохранение кеша...')
        save_cache(cache)
    
    # Генерируем HTML
    print(f'📝 Генерация HTML...')
    html_content = generate_html(images_data)
    
    # Сохраняем файл
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    file_size = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
    print(f'\n✨ Готово! Создан файл: {OUTPUT_FILE}')
    print(f'📸 Обработано изображений: {len(images_data)}')
    print(f'   • Из кеша: {cached_count}')
    print(f'   • Обработано заново: {processed_count}')
    print(f'📦 Размер файла: {file_size:.2f} MB')

def generate_html(images_data):
    import json
    images_json = json.dumps(images_data, ensure_ascii=False)
    
    return f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Надежда Терёшкина - Галерея работ</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            background: #0a0a0a;
            color: #fff;
            line-height: 1.6;
            overflow-x: hidden;
            position: relative;
        }}

        body::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: radial-gradient(circle at 50% 50%, #1a1a1a 0%, #0a0a0a 100%);
            z-index: -2;
        }}

        /* Луна */
        body::after {{
            content: '';
            position: fixed;
            top: 10%;
            right: 10%;
            width: 150px;
            height: 150px;
            background: radial-gradient(circle at 35% 35%, #fff 0%, #f0f0f0 40%, #d0d0d0 100%);
            border-radius: 50%;
            box-shadow: 0 0 60px rgba(255, 255, 255, 0.3),
                        0 0 100px rgba(255, 255, 255, 0.2),
                        inset -20px -20px 40px rgba(0, 0, 0, 0.2);
            z-index: -1;
            animation: moonGlow 8s ease-in-out infinite;
        }}

        @keyframes moonGlow {{
            0%, 100% {{
                box-shadow: 0 0 60px rgba(255, 255, 255, 0.3),
                            0 0 100px rgba(255, 255, 255, 0.2),
                            inset -20px -20px 40px rgba(0, 0, 0, 0.2);
            }}
            50% {{
                box-shadow: 0 0 80px rgba(255, 255, 255, 0.4),
                            0 0 120px rgba(255, 255, 255, 0.3),
                            inset -20px -20px 40px rgba(0, 0, 0, 0.2);
            }}
        }}

        /* Свечи */
        .candles {{
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            pointer-events: none;
        }}

        .candle {{
            position: absolute;
            width: 20px;
            height: 80px;
            background: linear-gradient(to bottom, #f4e4c1 0%, #d4c4a1 100%);
            border-radius: 3px 3px 0 0;
        }}

        .candle::before {{
            content: '';
            position: absolute;
            top: -15px;
            left: 50%;
            transform: translateX(-50%);
            width: 8px;
            height: 15px;
            background: radial-gradient(ellipse at center, #ff6b35 0%, #ff8c42 30%, transparent 70%);
            border-radius: 50% 50% 50% 50% / 60% 60% 40% 40%;
            animation: flicker 2s ease-in-out infinite;
        }}

        .candle::after {{
            content: '';
            position: absolute;
            top: -25px;
            left: 50%;
            transform: translateX(-50%);
            width: 3px;
            height: 12px;
            background: linear-gradient(to top, #ff6b35 0%, transparent 100%);
            border-radius: 50%;
            animation: flicker 2s ease-in-out infinite;
        }}

        @keyframes flicker {{
            0%, 100% {{
                opacity: 1;
                transform: translateX(-50%) scale(1);
            }}
            50% {{
                opacity: 0.8;
                transform: translateX(-50%) scale(1.1);
            }}
        }}

        .candle-1 {{
            bottom: 15%;
            left: 8%;
            animation-delay: 0s;
        }}

        .candle-2 {{
            bottom: 20%;
            left: 15%;
            height: 100px;
            animation-delay: -0.5s;
        }}

        .candle-3 {{
            bottom: 18%;
            right: 12%;
            height: 90px;
            animation-delay: -1s;
        }}

        .candle-4 {{
            bottom: 25%;
            right: 20%;
            animation-delay: -1.5s;
        }}

        /* Кошка Пуля */
        .cat {{
            position: fixed;
            bottom: 5%;
            left: 5%;
            width: 120px;
            height: 100px;
            z-index: -1;
            pointer-events: none;
            animation: catBreath 3s ease-in-out infinite;
        }}

        @keyframes catBreath {{
            0%, 100% {{
                transform: scale(1);
            }}
            50% {{
                transform: scale(1.02);
            }}
        }}

        /* Тело кошки */
        .cat-body {{
            position: absolute;
            bottom: 0;
            left: 20px;
            width: 80px;
            height: 50px;
            background: #2a2a2a;
            border-radius: 40% 40% 30% 30%;
        }}

        /* Голова кошки */
        .cat-head {{
            position: absolute;
            bottom: 35px;
            left: 60px;
            width: 50px;
            height: 45px;
            background: #2a2a2a;
            border-radius: 50% 50% 40% 40%;
        }}

        /* Уши */
        .cat-ear {{
            position: absolute;
            width: 0;
            height: 0;
            border-left: 12px solid transparent;
            border-right: 12px solid transparent;
            border-bottom: 20px solid #2a2a2a;
        }}

        .cat-ear-left {{
            top: -15px;
            left: 5px;
            transform: rotate(-15deg);
        }}

        .cat-ear-right {{
            top: -15px;
            right: 5px;
            transform: rotate(15deg);
        }}

        /* Глаза */
        .cat-eye {{
            position: absolute;
            top: 15px;
            width: 8px;
            height: 12px;
            background: #ffeb3b;
            border-radius: 50%;
            animation: catBlink 4s ease-in-out infinite;
        }}

        .cat-eye-left {{
            left: 12px;
        }}

        .cat-eye-right {{
            right: 12px;
        }}

        .cat-eye::after {{
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 3px;
            height: 10px;
            background: #000;
            border-radius: 50%;
        }}

        @keyframes catBlink {{
            0%, 96%, 100% {{
                height: 12px;
            }}
            98% {{
                height: 2px;
            }}
        }}

        /* Хвост */
        .cat-tail {{
            position: absolute;
            bottom: 15px;
            left: 0;
            width: 60px;
            height: 8px;
            background: #2a2a2a;
            border-radius: 50%;
            transform-origin: right center;
            animation: tailWag 3s ease-in-out infinite;
        }}

        @keyframes tailWag {{
            0%, 100% {{
                transform: rotate(-10deg);
            }}
            50% {{
                transform: rotate(5deg);
            }}
        }}

        .paintings-bg {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            overflow: hidden;
            opacity: 0.03;
            pointer-events: none;
        }}

        .paintings-bg img {{
            position: absolute;
            width: 300px;
            height: 300px;
            object-fit: cover;
            filter: blur(5px) grayscale(0.8);
            animation: floatPainting 30s infinite ease-in-out;
            opacity: 0.4;
        }}

        .paintings-bg img:nth-child(1) {{
            top: 5%;
            left: 5%;
            animation-delay: 0s;
            transform: rotate(-5deg);
        }}

        .paintings-bg img:nth-child(2) {{
            top: 15%;
            right: 10%;
            animation-delay: -5s;
            transform: rotate(8deg);
        }}

        .paintings-bg img:nth-child(3) {{
            bottom: 20%;
            left: 15%;
            animation-delay: -10s;
            transform: rotate(3deg);
        }}

        .paintings-bg img:nth-child(4) {{
            bottom: 10%;
            right: 20%;
            animation-delay: -15s;
            transform: rotate(-7deg);
        }}

        .paintings-bg img:nth-child(5) {{
            top: 40%;
            left: 50%;
            animation-delay: -20s;
            transform: rotate(5deg) translateX(-50%);
        }}

        @keyframes floatPainting {{
            0%, 100% {{
                transform: translateY(0) rotate(var(--rotate, 0deg));
            }}
            50% {{
                transform: translateY(-30px) rotate(calc(var(--rotate, 0deg) + 5deg));
            }}
        }}

        .fluid-bg {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            overflow: hidden;
            pointer-events: none;
        }}

        .fluid-shape {{
            position: absolute;
            filter: blur(180px);
            opacity: 0.15;
            animation: morphBlob 20s infinite ease-in-out;
            will-change: transform, border-radius;
            mix-blend-mode: screen;
        }}

        .shape-1 {{
            width: 900px;
            height: 900px;
            background: radial-gradient(circle at 30% 40%, 
                rgba(255, 179, 71, 0.8) 0%, 
                rgba(255, 107, 157, 0.6) 40%,
                rgba(196, 113, 237, 0.4) 100%);
            top: -25%;
            left: -20%;
            animation-delay: 0s;
            border-radius: 63% 37% 54% 46% / 55% 48% 52% 45%;
        }}

        .shape-2 {{
            width: 800px;
            height: 800px;
            background: radial-gradient(circle at 70% 60%, 
                rgba(255, 107, 157, 0.8) 0%, 
                rgba(196, 113, 237, 0.6) 40%,
                rgba(79, 172, 254, 0.4) 100%);
            top: 25%;
            right: -15%;
            animation-delay: -7s;
            border-radius: 38% 62% 63% 37% / 70% 33% 67% 30%;
        }}

        .shape-3 {{
            width: 850px;
            height: 850px;
            background: radial-gradient(circle at 50% 50%, 
                rgba(79, 172, 254, 0.8) 0%, 
                rgba(0, 242, 254, 0.6) 40%,
                rgba(255, 179, 71, 0.4) 100%);
            bottom: -25%;
            left: 15%;
            animation-delay: -14s;
            border-radius: 41% 59% 58% 42% / 45% 60% 40% 55%;
        }}

        .shape-4 {{
            width: 700px;
            height: 700px;
            background: radial-gradient(circle at 40% 70%, 
                rgba(196, 113, 237, 0.7) 0%, 
                rgba(255, 179, 71, 0.5) 50%,
                rgba(255, 107, 157, 0.3) 100%);
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            animation-delay: -10s;
            border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%;
        }}

        @keyframes morphBlob {{
            0%, 100% {{
                transform: translate(0, 0) scale(1) rotate(0deg);
                border-radius: 63% 37% 54% 46% / 55% 48% 52% 45%;
            }}
            14% {{
                transform: translate(120px, -120px) scale(1.4) rotate(45deg);
                border-radius: 40% 60% 70% 30% / 40% 40% 60% 50%;
            }}
            28% {{
                transform: translate(-100px, 100px) scale(0.7) rotate(-30deg);
                border-radius: 58% 42% 75% 25% / 76% 46% 54% 24%;
            }}
            42% {{
                transform: translate(140px, 80px) scale(1.3) rotate(90deg);
                border-radius: 50% 50% 33% 67% / 55% 27% 73% 45%;
            }}
            56% {{
                transform: translate(-120px, -80px) scale(0.8) rotate(-60deg);
                border-radius: 80% 20% 55% 45% / 20% 80% 20% 80%;
            }}
            70% {{
                transform: translate(100px, 120px) scale(1.2) rotate(120deg);
                border-radius: 45% 55% 62% 38% / 53% 51% 49% 47%;
            }}
            84% {{
                transform: translate(-90px, -100px) scale(0.9) rotate(-90deg);
                border-radius: 70% 30% 50% 50% / 30% 30% 70% 70%;
            }}
        }}

        /* Волновой эффект */
        .wave-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 1;
            pointer-events: none;
            opacity: 0.15;
        }}

        .wave {{
            position: absolute;
            width: 200%;
            height: 200%;
            background: linear-gradient(
                45deg,
                transparent 0%,
                rgba(255, 179, 71, 0.3) 25%,
                transparent 50%,
                rgba(255, 107, 157, 0.3) 75%,
                transparent 100%
            );
            animation: wave 15s linear infinite;
        }}

        .wave:nth-child(2) {{
            animation-delay: -5s;
            opacity: 0.5;
        }}

        .wave:nth-child(3) {{
            animation-delay: -10s;
            opacity: 0.3;
        }}

        @keyframes wave {{
            0% {{
                transform: translate(-50%, -50%) rotate(0deg);
            }}
            100% {{
                transform: translate(-50%, -50%) rotate(360deg);
            }}
        }}

        .header {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 100;
            background: rgba(255, 255, 255, 0.92);
            backdrop-filter: blur(20px) saturate(180%);
            border-bottom: 1px solid rgba(232, 232, 232, 0.8);
            transition: all 0.3s ease;
            will-change: transform;
        }}

        .header.scrolled {{
            box-shadow: 0 2px 20px rgba(0, 0, 0, 0.04);
        }}

        .header-content {{
            max-width: 1800px;
            margin: 0 auto;
            padding: 25px 60px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .header-content h1 {{
            font-size: 1.4em;
            font-weight: 400;
            letter-spacing: 0.3px;
            color: #000;
        }}

        .subtitle {{
            font-size: 0.85em;
            font-weight: 400;
            color: #666;
            letter-spacing: 1.5px;
            text-transform: uppercase;
        }}

        .hero {{
            position: relative;
            margin-top: 80px;
            padding: 140px 60px 100px;
            text-align: center;
            background: linear-gradient(180deg, rgba(250, 250, 250, 0.9) 0%, rgba(255, 255, 255, 0.95) 100%);
            overflow: hidden;
            backdrop-filter: blur(10px);
        }}

        .hero::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: radial-gradient(circle at 30% 50%, rgba(255, 179, 71, 0.15) 0%, transparent 50%),
                        radial-gradient(circle at 70% 50%, rgba(255, 107, 157, 0.15) 0%, transparent 50%);
            pointer-events: none;
            animation: heroGlow 8s ease-in-out infinite;
        }}

        @keyframes heroGlow {{
            0%, 100% {{
                opacity: 0.5;
            }}
            50% {{
                opacity: 1;
            }}
        }}

        .hero-content {{
            position: relative;
            z-index: 1;
        }}

        .hero h2 {{
            font-size: 4em;
            font-weight: 200;
            margin-bottom: 30px;
            letter-spacing: -1px;
            color: #000;
            animation: titlePulse 3s ease-in-out infinite;
        }}

        @keyframes titlePulse {{
            0%, 100% {{
                transform: scale(1);
                text-shadow: 0 0 20px rgba(232, 244, 248, 0.3);
            }}
            50% {{
                transform: scale(1.02);
                text-shadow: 0 0 40px rgba(232, 244, 248, 0.6),
                             0 0 60px rgba(240, 232, 244, 0.4);
            }}
        }}

        .hero p {{
            font-size: 1.1em;
            color: #666;
            max-width: 600px;
            margin: 0 auto;
            font-weight: 300;
        }}

        .container {{
            max-width: 1800px;
            margin: 80px auto 0;
            padding: 0;
        }}

        .gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
            gap: 40px;
            background: transparent;
            padding: 40px;
        }}

        .gallery-item {{
            position: relative;
            overflow: hidden;
            background: #000;
            cursor: zoom-in;
            opacity: 0;
            transform: translateY(60px) scale(0.9);
            transition: all 1.2s cubic-bezier(0.16, 1, 0.3, 1);
            will-change: transform, opacity, filter;
            border-radius: 8px;
            box-shadow: 0 0 0 rgba(255, 179, 71, 0);
            filter: brightness(0) contrast(0);
        }}

        .gallery-item.loaded {{
            opacity: 1;
            transform: translateY(0) scale(1);
        }}

        .gallery-item.visible {{
            filter: brightness(1) contrast(1.05);
            transition: filter 1.5s ease-out, 
                        transform 1.2s cubic-bezier(0.16, 1, 0.3, 1),
                        box-shadow 1.5s ease-out;
            box-shadow: 0 0 40px rgba(255, 179, 71, 0.3),
                        0 0 80px rgba(255, 107, 157, 0.2);
        }}

        .gallery-item::before {{
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, 
                rgba(255, 179, 71, 0.4) 0%, 
                rgba(255, 107, 157, 0.3) 30%,
                transparent 70%);
            opacity: 0;
            transition: opacity 0.6s ease;
            pointer-events: none;
            z-index: 3;
        }}

        .gallery-item:hover::before {{
            opacity: 1;
            animation: spotlight 2s ease-in-out infinite;
        }}

        @keyframes spotlight {{
            0%, 100% {{
                transform: translate(0, 0) scale(1);
            }}
            50% {{
                transform: translate(10px, 10px) scale(1.1);
            }}
        }}

        .gallery-item::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, 
                rgba(255, 179, 71, 0) 0%, 
                rgba(255, 107, 157, 0.1) 50%,
                rgba(196, 113, 237, 0) 100%);
            opacity: 0;
            transition: opacity 0.5s ease;
            pointer-events: none;
            z-index: 2;
        }}

        .gallery-item:hover::after {{
            opacity: 1;
        }}

        .gallery-item:hover {{
            box-shadow: 0 0 60px rgba(255, 179, 71, 0.6),
                        0 0 100px rgba(255, 107, 157, 0.4),
                        0 20px 60px rgba(0, 0, 0, 0.8);
            transform: translateY(-10px);
        }}

        .gallery-item.zoomed {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            width: 100vw !important;
            height: 100vh !important;
            z-index: 999;
            background: rgba(10, 10, 10, 0.98);
            backdrop-filter: blur(30px);
            cursor: zoom-out;
            animation: explosiveZoomIn 0.5s cubic-bezier(0.16, 1, 0.3, 1);
            border-radius: 0;
        }}

        @keyframes explosiveZoomIn {{
            0% {{
                opacity: 0;
                transform: scale(0.8);
            }}
            60% {{
                transform: scale(1.05);
            }}
            100% {{
                opacity: 1;
                transform: scale(1);
            }}
        }}

        .gallery-item.zoomed img {{
            width: 100% !important;
            height: 100% !important;
            object-fit: contain !important;
            padding: 60px;
            cursor: zoom-in;
            transition: transform 0.3s ease-out;
        }}

        .gallery-item.zoomed img.max-zoom {{
            cursor: zoom-out;
        }}

        .gallery-item::before {{
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, 
                rgba(255, 179, 71, 0.4) 0%, 
                rgba(255, 107, 157, 0.3) 30%,
                transparent 70%);
            opacity: 0;
            transition: opacity 0.6s ease;
            pointer-events: none;
            z-index: 3;
        }}

        .gallery-item:not(.zoomed):hover::before {{
            opacity: 1;
            animation: spotlight 2s ease-in-out infinite;
        }}

        .gallery-item::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, 
                rgba(255, 179, 71, 0) 0%, 
                rgba(255, 107, 157, 0.1) 50%,
                rgba(196, 113, 237, 0) 100%);
            opacity: 0;
            transition: opacity 0.5s ease;
            pointer-events: none;
            z-index: 2;
        }}

        .gallery-item:not(.zoomed):hover::after {{
            opacity: 1;
        }}

        .gallery-item img {{
            width: 100%;
            height: 600px;
            object-fit: cover;
            display: block;
            transition: transform 0.8s cubic-bezier(0.16, 1, 0.3, 1), 
                        filter 0.6s ease,
                        clip-path 0.6s ease;
            will-change: transform;
            filter: brightness(1.1) contrast(1.05) saturate(0.9);
            clip-path: polygon(0 0, 100% 0, 100% 100%, 0 100%);
        }}

        .gallery-item:not(.zoomed):hover img {{
            transform: scale(1.05) rotate(0.5deg);
            filter: brightness(1.3) contrast(1.1) saturate(1) drop-shadow(0 10px 30px rgba(255, 179, 71, 0.3));
            clip-path: polygon(
                2% 0%, 98% 1%, 99% 3%, 100% 97%, 98% 100%, 2% 99%, 1% 97%, 0% 3%
            );
        }}

        .zoom-controls {{
            position: fixed;
            top: 40px;
            right: 60px;
            z-index: 1000;
            display: none;
            gap: 15px;
        }}

        .gallery-item.zoomed ~ .zoom-controls {{
            display: flex;
        }}

        .zoom-btn {{
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            color: #fff;
            border: 1px solid rgba(255, 255, 255, 0.2);
            font-size: 24px;
            width: 50px;
            height: 50px;
            cursor: pointer;
            border-radius: 50%;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .zoom-btn:hover {{
            background: rgba(255, 255, 255, 0.2);
            border-color: rgba(255, 255, 255, 0.4);
            transform: scale(1.1);
        }}

        .image-counter {{
            position: fixed;
            bottom: 60px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 12px 30px;
            border-radius: 30px;
            font-size: 14px;
            letter-spacing: 1px;
            font-weight: 300;
            display: none;
            z-index: 1000;
        }}

        .gallery-item.zoomed ~ .image-counter {{
            display: block;
        }}

        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(255, 255, 255, 0.98);
            backdrop-filter: blur(30px);
            animation: modalFadeIn 0.4s ease;
        }}

        @keyframes modalFadeIn {{
            from {{
                opacity: 0;
            }}
            to {{
                opacity: 1;
            }}
        }}

        .modal-content {{
            margin: auto;
            display: block;
            max-width: 90%;
            max-height: 90%;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            opacity: 0;
            transition: opacity 0.5s ease;
            box-shadow: 0 20px 80px rgba(0, 0, 0, 0.1);
        }}

        .modal-content.loaded {{
            opacity: 1;
        }}

        .image-info {{
            position: absolute;
            bottom: 60px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 12px 30px;
            border-radius: 30px;
            font-size: 14px;
            letter-spacing: 1px;
            font-weight: 300;
        }}

        .close {{
            position: absolute;
            top: 40px;
            right: 60px;
            color: #000;
            font-size: 40px;
            font-weight: 200;
            cursor: pointer;
            z-index: 1001;
            transition: all 0.3s ease;
            width: 50px;
            height: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .close:hover {{
            transform: rotate(90deg);
            opacity: 0.6;
        }}

        .nav-buttons {{
            position: absolute;
            top: 50%;
            width: 100%;
            display: flex;
            justify-content: space-between;
            padding: 0 40px;
            transform: translateY(-50%);
        }}

        .nav-btn {{
            background: rgba(0, 0, 0, 0.05);
            backdrop-filter: blur(10px);
            color: #000;
            border: none;
            font-size: 30px;
            padding: 20px;
            cursor: pointer;
            border-radius: 50%;
            transition: all 0.3s ease;
            width: 60px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 200;
        }}

        .nav-btn:hover {{
            background: rgba(0, 0, 0, 0.1);
            transform: scale(1.1);
        }}

        .footer {{
            background: rgba(10, 10, 10, 0.95);
            color: #666;
            text-align: center;
            padding: 60px 40px;
            margin-top: 100px;
            font-size: 0.9em;
            letter-spacing: 1px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }}

        @media (max-width: 1200px) {{
            .gallery {{
                grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            }}
            
            .gallery-item img {{
                height: 500px;
            }}
        }}

        @media (max-width: 768px) {{
            .header-content {{
                padding: 20px 30px;
                flex-direction: column;
                gap: 5px;
            }}

            .header-content h1 {{
                font-size: 1.1em;
            }}

            .subtitle {{
                font-size: 0.7em;
            }}

            .hero {{
                padding: 100px 30px 60px;
            }}

            .hero h2 {{
                font-size: 2.2em;
            }}

            .hero p {{
                font-size: 1em;
            }}

            .gallery {{
                grid-template-columns: 1fr;
                gap: 0;
            }}

            .gallery-item img {{
                height: 350px;
            }}

            .gallery-item.zoomed img {{
                padding: 20px;
            }}

            .zoom-controls {{
                top: 15px;
                right: 15px;
                gap: 8px;
            }}

            .zoom-btn {{
                width: 45px;
                height: 45px;
                font-size: 20px;
            }}

            .image-counter {{
                bottom: 30px;
                font-size: 12px;
                padding: 10px 25px;
            }}

            .fluid-shape {{
                filter: blur(80px);
            }}
        }}

        @media (max-width: 480px) {{
            .header-content h1 {{
                font-size: 1em;
            }}

            .hero h2 {{
                font-size: 1.8em;
            }}

            .gallery-item img {{
                height: 300px;
            }}
        }}
    </style>
</head>
<body>
    <div class="paintings-bg" id="paintingsBg"></div>

    <div class="candles">
        <div class="candle candle-1"></div>
        <div class="candle candle-2"></div>
        <div class="candle candle-3"></div>
        <div class="candle candle-4"></div>
    </div>

    <div class="cat">
        <div class="cat-tail"></div>
        <div class="cat-body"></div>
        <div class="cat-head">
            <div class="cat-ear cat-ear-left"></div>
            <div class="cat-ear cat-ear-right"></div>
            <div class="cat-eye cat-eye-left"></div>
            <div class="cat-eye cat-eye-right"></div>
        </div>
    </div>

    <div class="wave-overlay">
        <div class="wave"></div>
        <div class="wave"></div>
        <div class="wave"></div>
    </div>

    <header class="header" id="header">
        <div class="header-content">
            <h1>Надежда Александровна Терёшкина</h1>
            <span class="subtitle">Художница</span>
        </div>
    </header>

    <div class="fluid-bg">
        <div class="fluid-shape shape-1"></div>
        <div class="fluid-shape shape-2"></div>
        <div class="fluid-shape shape-3"></div>
        <div class="fluid-shape shape-4"></div>
    </div>

    <div class="container">
        <div id="gallery" class="gallery"></div>
    </div>

    <div class="zoom-controls" id="zoomControls">
        <button class="zoom-btn" id="prevZoomBtn" title="Предыдущая">‹</button>
        <button class="zoom-btn" id="closeZoomBtn" title="Закрыть">×</button>
        <button class="zoom-btn" id="nextZoomBtn" title="Следующая">›</button>
    </div>

    <div class="image-counter" id="imageCounter"></div>

    <div id="modal" class="modal">
        <span class="close">&times;</span>
        <img class="modal-content" id="modalImg">
        <div class="image-info" id="imageInfo"></div>
        <div class="nav-buttons">
            <button id="prevBtn" class="nav-btn" title="Предыдущая работа">‹</button>
            <button id="nextBtn" class="nav-btn" title="Следующая работа">›</button>
        </div>
    </div>

    <footer class="footer">
        <p>&copy; 2024 Надежда Александровна Терёшкина. Все права защищены.</p>
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
        const header = document.getElementById('header');
        const zoomControls = document.getElementById('zoomControls');
        const imageCounter = document.getElementById('imageCounter');
        const prevZoomBtn = document.getElementById('prevZoomBtn');
        const nextZoomBtn = document.getElementById('nextZoomBtn');
        const closeZoomBtn = document.getElementById('closeZoomBtn');
        let ticking = false;
        let currentZoomedItem = null;

        // Parallax effect
        function updateParallax() {{
            const scrolled = window.pageYOffset;
            
            // Header scroll effect
            if (scrolled > 50) {{
                header.classList.add('scrolled');
            }} else {{
                header.classList.remove('scrolled');
            }}

            // Parallax elements
            const parallaxElements = document.querySelectorAll('[data-parallax]');
            parallaxElements.forEach(element => {{
                const speed = parseFloat(element.getAttribute('data-parallax'));
                const yPos = -(scrolled * speed);
                element.style.transform = `translateY(${{yPos}}px)`;
            }});

            // Gallery items parallax
            const galleryItems = document.querySelectorAll('.gallery-item.loaded');
            galleryItems.forEach((item, index) => {{
                const rect = item.getBoundingClientRect();
                const scrollPercent = (window.innerHeight - rect.top) / window.innerHeight;
                
                if (scrollPercent > 0 && scrollPercent < 1.2) {{
                    const translateY = (scrollPercent - 0.5) * 15;
                    const currentTransform = item.style.transform || '';
                    if (!currentTransform.includes('scale')) {{
                        item.style.transform = `translateY(${{translateY}}px)`;
                    }}
                }}
            }});

            ticking = false;
        }}

        function requestTick() {{
            if (!ticking) {{
                window.requestAnimationFrame(updateParallax);
                ticking = true;
            }}
        }}

        window.addEventListener('scroll', requestTick);

        // Mouse move effect for fluid shapes
        let mouseX = 0;
        let mouseY = 0;
        let currentX = 0;
        let currentY = 0;

        document.addEventListener('mousemove', (e) => {{
            mouseX = e.clientX / window.innerWidth - 0.5;
            mouseY = e.clientY / window.innerHeight - 0.5;
        }});

        function animateFluidShapes() {{
            currentX += (mouseX - currentX) * 0.05;
            currentY += (mouseY - currentY) * 0.05;

            const shapes = document.querySelectorAll('.fluid-shape');
            shapes.forEach((shape, index) => {{
                const speed = (index + 1) * 30;
                const xMove = currentX * speed;
                const yMove = currentY * speed;
                shape.style.transform = `translate(${{xMove}}px, ${{yMove}}px)`;
            }});

            requestAnimationFrame(animateFluidShapes);
        }}

        animateFluidShapes();

        // Инициализация галереи
        function initGallery() {{
            // Создаем фон из картин
            createPaintingsBackground();
            
            imagesData.forEach((imageData, index) => {{
                createGalleryItem(imageData, index);
            }});

            // Фоновая предзагрузка полноразмерных изображений
            preloadFullImages();
        }}

        function createPaintingsBackground() {{
            const paintingsBg = document.getElementById('paintingsBg');
            const numPaintings = Math.min(5, imagesData.length);
            
            for (let i = 0; i < numPaintings; i++) {{
                const img = document.createElement('img');
                const randomIndex = Math.floor(Math.random() * imagesData.length);
                img.src = imagesData[randomIndex].thumbnail;
                img.style.setProperty('--rotate', `${{(Math.random() - 0.5) * 15}}deg`);
                paintingsBg.appendChild(img);
            }}
        }}

        function createGalleryItem(imageData, index) {{
            const item = document.createElement('div');
            item.className = 'gallery-item';
            item.setAttribute('data-index', index);
            
            const img = document.createElement('img');
            img.src = imageData.thumbnail;
            img.alt = imageData.name;
            img.loading = 'lazy';
            
            // Hover effect with mouse position (только если не в zoom режиме)
            item.addEventListener('mousemove', (e) => {{
                if (item.classList.contains('zoomed')) {{
                    // Максимальное увеличение при наведении на увеличенное изображение
                    const rect = img.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;
                    
                    const percentX = (x / rect.width) * 100;
                    const percentY = (y / rect.height) * 100;
                    
                    img.style.transformOrigin = `${{percentX}}% ${{percentY}}%`;
                    img.style.transform = 'scale(2)';
                    img.classList.add('max-zoom');
                }} else {{
                    const rect = item.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;
                    const centerX = rect.width / 2;
                    const centerY = rect.height / 2;
                    const percentX = (x - centerX) / centerX;
                    const percentY = (y - centerY) / centerY;
                    
                    img.style.transform = `scale(1.08) translate(${{percentX * 15}}px, ${{percentY * 15}}px) rotate(${{percentX * 2}}deg)`;
                }}
            }});

            item.addEventListener('mouseleave', () => {{
                if (item.classList.contains('zoomed')) {{
                    img.style.transform = 'scale(1)';
                    img.style.transformOrigin = 'center';
                    img.classList.remove('max-zoom');
                }} else {{
                    img.style.transform = 'scale(1) translate(0, 0)';
                }}
            }});
            
            // Click to zoom
            item.addEventListener('click', (e) => {{
                // Если изображение в max-zoom, не закрываем при клике
                if (img.classList.contains('max-zoom')) {{
                    return;
                }}
                
                if (item.classList.contains('zoomed')) {{
                    closeZoom();
                }} else {{
                    openZoom(item, index);
                }}
            }});
            
            item.appendChild(img);
            gallery.appendChild(item);
            
            // Fade in animation with stagger and explosive effect
            setTimeout(() => {{
                item.classList.add('loaded');
                
                // Добавляем взрывной эффект при появлении
                const rect = item.getBoundingClientRect();
                if (rect.top < window.innerHeight) {{
                    item.style.animation = 'none';
                    setTimeout(() => {{
                        item.style.animation = '';
                    }}, 10);
                }}
            }}, index * 80);
        }}

        function openZoom(item, index) {{
            if (currentZoomedItem) closeZoom();
            
            currentZoomedItem = item;
            currentIndex = index;
            
            item.classList.add('zoomed');
            document.body.style.overflow = 'hidden';
            
            // Загружаем полное изображение если еще не загружено
            const img = item.querySelector('img');
            if (fullImagesLoaded.has(index)) {{
                img.src = imagesData[index].full;
            }} else {{
                const fullImg = new Image();
                fullImg.onload = () => {{
                    img.src = imagesData[index].full;
                    fullImagesLoaded.add(index);
                }};
                fullImg.src = imagesData[index].full;
            }}
            
            updateImageCounter();
        }}

        function closeZoom() {{
            if (!currentZoomedItem) return;
            
            const img = currentZoomedItem.querySelector('img');
            const index = parseInt(currentZoomedItem.getAttribute('data-index'));
            
            currentZoomedItem.classList.remove('zoomed');
            document.body.style.overflow = '';
            
            // Возвращаем thumbnail
            img.src = imagesData[index].thumbnail;
            img.style.transform = '';
            
            currentZoomedItem = null;
        }}

        function navigateZoom(direction) {{
            if (!currentZoomedItem) return;
            
            const currentIdx = parseInt(currentZoomedItem.getAttribute('data-index'));
            let newIndex;
            
            if (direction === 'next') {{
                newIndex = (currentIdx + 1) % imagesData.length;
            }} else {{
                newIndex = (currentIdx - 1 + imagesData.length) % imagesData.length;
            }}
            
            closeZoom();
            
            setTimeout(() => {{
                const newItem = document.querySelector(`[data-index="${{newIndex}}"]`);
                if (newItem) {{
                    openZoom(newItem, newIndex);
                }}
            }}, 100);
        }}

        function updateImageCounter() {{
            imageCounter.textContent = `${{currentIndex + 1}} / ${{imagesData.length}}`;
        }}

        // Zoom controls
        prevZoomBtn.addEventListener('click', (e) => {{
            e.stopPropagation();
            navigateZoom('prev');
        }});

        nextZoomBtn.addEventListener('click', (e) => {{
            e.stopPropagation();
            navigateZoom('next');
        }});

        closeZoomBtn.addEventListener('click', (e) => {{
            e.stopPropagation();
            closeZoom();
        }});

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {{
            if (currentZoomedItem) {{
                if (e.key === 'ArrowLeft') navigateZoom('prev');
                if (e.key === 'ArrowRight') navigateZoom('next');
                if (e.key === 'Escape') closeZoom();
            }} else if (modal.style.display === 'block') {{
                if (e.key === 'ArrowLeft') prevBtn.click();
                if (e.key === 'ArrowRight') nextBtn.click();
                if (e.key === 'Escape') closeModal();
            }}
        }});

        // Фоновая предзагрузка полноразмерных изображений
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
            document.body.style.overflow = 'hidden';
            modalImg.classList.remove('loaded');
            
            // Показываем thumbnail пока грузится полное изображение
            modalImg.src = imagesData[currentIndex].thumbnail;
            
            // Загружаем полное изображение
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

        function closeModal() {{
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }}

        function updateImageInfo() {{
            imageInfo.textContent = `${{currentIndex + 1}} / ${{imagesData.length}}`;
        }}

        closeBtn.addEventListener('click', closeModal);

        modal.addEventListener('click', (e) => {{
            if (e.target === modal) {{
                closeModal();
            }}
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
            if (currentZoomedItem) {{
                if (e.key === 'ArrowLeft') navigateZoom('prev');
                if (e.key === 'ArrowRight') navigateZoom('next');
                if (e.key === 'Escape') closeZoom();
            }} else if (modal.style.display === 'block') {{
                if (e.key === 'ArrowLeft') prevBtn.click();
                if (e.key === 'ArrowRight') nextBtn.click();
                if (e.key === 'Escape') closeModal();
            }}
        }});

        // Запуск
        window.addEventListener('load', initGallery);
    </script>
</body>
</html>'''

if __name__ == '__main__':
    generate_gallery()
