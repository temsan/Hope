import base64
import os

assets_dir = 'assets'
output_file = 'assets_base64.py'

assets = {}

for filename in ['moon.jpg', 'candle.jpg', 'flame.jpg']:
    filepath = os.path.join(assets_dir, filename)
    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
            assets[filename.replace('.jpg', '')] = f'data:image/jpeg;base64,{encoded}'
        print(f'✅ {filename} конвертирован')

# Сохраняем в Python файл
with open(output_file, 'w', encoding='utf-8') as f:
    f.write('# Auto-generated base64 encoded assets\n\n')
    f.write('ASSETS = {\n')
    for key, value in assets.items():
        f.write(f'    "{key}": "{value}",\n')
    f.write('}\n')

print(f'\n✨ Сохранено в {output_file}')
