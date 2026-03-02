import urllib.request
import os

# Создаем папку для ассетов
os.makedirs('assets', exist_ok=True)

# URLs для бесплатных изображений с Unsplash
urls = {
    'moon.jpg': 'https://images.unsplash.com/photo-1509773896068-7fd415d91e2e?w=800&q=80',
    'candle.jpg': 'https://images.unsplash.com/photo-1515377905703-c4788e51af15?w=800&q=80',
    'flame.jpg': 'https://images.unsplash.com/photo-1516528387618-afa90b13e000?w=800&q=80',
}

print('📥 Загрузка изображений...')

headers = {'User-Agent': 'Mozilla/5.0'}

for filename, url in urls.items():
    filepath = os.path.join('assets', filename)
    try:
        print(f'⬇️  Загрузка {filename}...')
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            with open(filepath, 'wb') as out_file:
                out_file.write(response.read())
        print(f'✅ {filename} загружен')
    except Exception as e:
        print(f'❌ Ошибка загрузки {filename}: {e}')

print('\n✨ Готово!')
