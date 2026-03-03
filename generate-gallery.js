const fs = require('fs');
const path = require('path');
const sharp = require('sharp');

// Путь к папке с изображениями
const IMAGES_PATH = 'C:\\Users\\temsan\\OneDrive\\Desktop\\Сканы\\JPEG';
const OUTPUT_FILE = 'gallery.html';
const THUMBNAIL_WIDTH = 400;
const FULL_WIDTH = 1920;
const QUALITY = 85;

async function generateGallery() {
    console.log('Начинаем генерацию галереи...');

    try {
        // Читаем файлы из папки
        const files = fs.readdirSync(IMAGES_PATH);
        const imageFiles = files.filter(file => {
            const ext = path.extname(file).toLowerCase();
            return ['.jpg', '.jpeg', '.png'].includes(ext);
        }).sort();

        console.log(`Найдено изображений: ${imageFiles.length}`);

        const images = [];

        // Обрабатываем каждое изображение
        for (let i = 0; i < imageFiles.length; i++) {
            const filename = imageFiles[i];
            const imagePath = path.join(IMAGES_PATH, filename);

            console.log(`Обработка ${i + 1}/${imageFiles.length}: ${filename}`);

            try {
                // Создаем thumbnail
                const thumbnailBuffer = await sharp(imagePath)
                    .resize(THUMBNAIL_WIDTH, null, {
                        fit: 'inside',
                        withoutEnlargement: true
                    })
                    .jpeg({ quality: QUALITY })
                    .toBuffer();

                const thumbnailBase64 = thumbnailBuffer.toString('base64');

                // Создаем полноразмерное изображение
                const fullBuffer = await sharp(imagePath)
                    .resize(FULL_WIDTH, null, {
                        fit: 'inside',
                        withoutEnlargement: true
                    })
                    .jpeg({ quality: QUALITY })
                    .toBuffer();

                const fullBase64 = fullBuffer.toString('base64');

                images.push({
                    name: filename,
                    thumbnail: `data:image/jpeg;base64,${thumbnailBase64}`,
                    full: `data:image/jpeg;base64,${fullBase64}`
                });

            } catch (error) {
                console.error(`Ошибка обработки ${filename}:`, error.message);
            }
        }

        // Генерируем HTML
        const html = generateHTML(images);

        // Сохраняем файл
        fs.writeFileSync(OUTPUT_FILE, html, 'utf8');

        console.log(`\nГотово! Создан файл: ${OUTPUT_FILE}`);
        console.log(`Обработано изображений: ${images.length}`);
        console.log(`Размер файла: ${(fs.statSync(OUTPUT_FILE).size / 1024 / 1024).toFixed(2)} MB`);

    } catch (error) {
        console.error('Ошибка:', error);
    }
}

function generateHTML(images) {
    const imagesJSON = JSON.stringify(images);

    return `<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Надежда Ков - Галерея работ</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0a0a;
            min-height: 100vh;
            overflow-x: hidden;
            position: relative;
        }

        .fluid-bg {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 0;
            overflow: hidden;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        }

        .fluid-shape {
            position: absolute;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.4;
            animation: float 20s infinite ease-in-out;
        }

        .shape-1 {
            width: 500px;
            height: 500px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            top: -10%;
            left: -10%;
            animation-delay: 0s;
        }

        .shape-2 {
            width: 400px;
            height: 400px;
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            top: 50%;
            right: -5%;
            animation-delay: -7s;
        }

        .shape-3 {
            width: 450px;
            height: 450px;
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            bottom: -10%;
            left: 30%;
            animation-delay: -14s;
        }

        @keyframes float {
            0%, 100% {
                transform: translate(0, 0) scale(1);
            }
            33% {
                transform: translate(50px, -50px) scale(1.1);
            }
            66% {
                transform: translate(-30px, 30px) scale(0.9);
            }
        }

        .header {
            position: relative;
            z-index: 1;
            padding: 120px 20px 80px;
            text-align: center;
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .header-content h1 {
            font-size: 3.5em;
            margin-bottom: 15px;
            font-weight: 300;
            letter-spacing: 3px;
            color: #ffffff;
            text-shadow: 0 0 30px rgba(102, 126, 234, 0.5);
        }

        .subtitle {
            font-size: 1.5em;
            font-style: italic;
            color: rgba(255, 255, 255, 0.8);
            letter-spacing: 2px;
        }

        .container {
            position: relative;
            z-index: 1;
            max-width: 1400px;
            margin: 0 auto;
            padding: 60px 20px;
        }

        .intro {
            text-align: center;
            margin-bottom: 50px;
            font-size: 1.3em;
            color: rgba(255, 255, 255, 0.7);
            letter-spacing: 1px;
        }

        .image-count {
            text-align: center;
            margin-bottom: 30px;
            font-size: 1.2em;
            color: rgba(255, 255, 255, 0.6);
            letter-spacing: 1px;
        }

        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 40px;
            padding: 20px 0;
        }

        .gallery-item {
            position: relative;
            overflow: hidden;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
            opacity: 0;
            transform: translateY(30px);
        }

        .gallery-item.loaded {
            opacity: 1;
            transform: translateY(0);
        }

        .gallery-item::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%);
            opacity: 0;
            transition: opacity 0.5s ease;
            border-radius: 20px;
            z-index: 1;
        }

        .gallery-item:hover::before {
            opacity: 1;
        }

        .gallery-item:hover {
            transform: translateY(-15px) scale(1.02);
            box-shadow: 0 20px 60px rgba(102, 126, 234, 0.4);
            border-color: rgba(255, 255, 255, 0.3);
        }

        .gallery-item img {
            width: 100%;
            height: 350px;
            object-fit: contain;
            display: block;
            background: rgba(0, 0, 0, 0.3);
            padding: 20px;
            border-radius: 20px;
            transition: transform 0.5s ease;
        }

        .gallery-item:hover img {
            transform: scale(1.05);
        }

        .loading-spinner {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            to { transform: translate(-50%, -50%) rotate(360deg); }
        }

        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.95);
            backdrop-filter: blur(20px);
        }

        .modal-content {
            margin: auto;
            display: block;
            max-width: 85%;
            max-height: 85%;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            box-shadow: 0 20px 80px rgba(102, 126, 234, 0.5);
            border-radius: 10px;
            opacity: 0;
            transition: opacity 0.5s ease;
        }

        .modal-content.loaded {
            opacity: 1;
        }

        .image-info {
            position: absolute;
            bottom: 40px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            color: white;
            padding: 12px 30px;
            border-radius: 50px;
            font-size: 18px;
            letter-spacing: 1px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .close {
            position: absolute;
            top: 30px;
            right: 50px;
            color: white;
            font-size: 50px;
            font-weight: 300;
            cursor: pointer;
            z-index: 1001;
            transition: all 0.3s ease;
        }

        .close:hover {
            color: #667eea;
            transform: rotate(90deg);
        }

        .nav-buttons {
            position: absolute;
            top: 50%;
            width: 100%;
            display: flex;
            justify-content: space-between;
            padding: 0 30px;
            transform: translateY(-50%);
        }

        .nav-btn {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.2);
            font-size: 35px;
            padding: 15px 25px;
            cursor: pointer;
            border-radius: 50%;
            transition: all 0.3s ease;
            width: 70px;
            height: 70px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .nav-btn:hover {
            background: rgba(102, 126, 234, 0.3);
            border-color: rgba(255, 255, 255, 0.5);
            transform: scale(1.1);
        }

        .footer {
            position: relative;
            z-index: 1;
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(10px);
            color: rgba(255, 255, 255, 0.7);
            text-align: center;
            padding: 40px 20px;
            margin-top: 80px;
            font-size: 1.1em;
            letter-spacing: 1px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        @media (max-width: 768px) {
            .header-content h1 {
                font-size: 2.2em;
            }
            
            .subtitle {
                font-size: 1.2em;
            }
            
            .gallery {
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 25px;
            }
            
            .gallery-item img {
                height: 280px;
            }
            
            .nav-btn {
                width: 50px;
                height: 50px;
                font-size: 25px;
            }
            
            .fluid-shape {
                filter: blur(60px);
            }
        }
    </style>
</head>
<body>
    <div class="fluid-bg">
        <div class="fluid-shape shape-1"></div>
        <div class="fluid-shape shape-2"></div>
        <div class="fluid-shape shape-3"></div>
    </div>

    <header class="header">
        <div class="header-content">
            <h1 class="parallax-title" data-speed="0.5">Надежда Ков</h1>
            <p class="subtitle parallax-subtitle" data-speed="0.3">Художница</p>
        </div>
    </header>

    <div class="container">
        <div class="intro">
            <p>Добро пожаловать в галерею работ</p>
        </div>
        
        <div id="imageCount" class="image-count"></div>
        <div id="gallery" class="gallery"></div>
    </div>

    <div id="modal" class="modal">
        <span class="close">&times;</span>
        <img class="modal-content" id="modalImg">
        <div class="image-info" id="imageInfo"></div>
        <div class="nav-buttons">
            <button id="prevBtn" class="nav-btn" title="Предыдущая работа">&#10094;</button>
            <button id="nextBtn" class="nav-btn" title="Следующая работа">&#10095;</button>
        </div>
    </div>

    <footer class="footer">
        <p>&copy; Надежда Ков</p>
    </footer>

    <script>
        const imagesData = ${imagesJSON};
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

        // Parallax effect
        window.addEventListener('scroll', () => {
            const scrolled = window.pageYOffset;
            const parallaxElements = document.querySelectorAll('[data-speed]');
            
            parallaxElements.forEach(element => {
                const speed = element.getAttribute('data-speed');
                element.style.transform = \`translateY(\${scrolled * speed}px)\`;
            });
        });

        // Mouse move effect for fluid shapes
        document.addEventListener('mousemove', (e) => {
            const shapes = document.querySelectorAll('.fluid-shape');
            const x = e.clientX / window.innerWidth;
            const y = e.clientY / window.innerHeight;
            
            shapes.forEach((shape, index) => {
                const speed = (index + 1) * 20;
                const xMove = (x - 0.5) * speed;
                const yMove = (y - 0.5) * speed;
                shape.style.transform = \`translate(\${xMove}px, \${yMove}px)\`;
            });
        });

        // Инициализация галереи
        function initGallery() {
            imageCount.textContent = \`Загружено работ: \${imagesData.length}\`;
            
            imagesData.forEach((imageData, index) => {
                createGalleryItem(imageData, index);
            });

            // Фоновая предзагрузка полноразмерных изображений
            preloadFullImages();
        }

        function createGalleryItem(imageData, index) {
            const item = document.createElement('div');
            item.className = 'gallery-item';
            
            const img = document.createElement('img');
            img.src = imageData.thumbnail;
            img.alt = imageData.name;
            img.loading = 'lazy';
            
            item.appendChild(img);
            item.addEventListener('click', () => openModal(index));
            gallery.appendChild(item);
            
            // Fade in animation
            setTimeout(() => {
                item.classList.add('loaded');
            }, index * 50);
        }

        // Фоновая предзагрузка полноразмерных изображений
        function preloadFullImages() {
            imagesData.forEach((imageData, index) => {
                setTimeout(() => {
                    const img = new Image();
                    img.onload = () => {
                        fullImagesLoaded.add(index);
                    };
                    img.src = imageData.full;
                }, index * 100);
            });
        }

        function openModal(index) {
            currentIndex = index;
            modal.style.display = 'block';
            modalImg.classList.remove('loaded');
            
            // Показываем thumbnail пока грузится полное изображение
            modalImg.src = imagesData[currentIndex].thumbnail;
            
            // Загружаем полное изображение
            if (fullImagesLoaded.has(currentIndex)) {
                modalImg.src = imagesData[currentIndex].full;
                modalImg.classList.add('loaded');
            } else {
                const fullImg = new Image();
                fullImg.onload = () => {
                    modalImg.src = imagesData[currentIndex].full;
                    modalImg.classList.add('loaded');
                    fullImagesLoaded.add(currentIndex);
                };
                fullImg.src = imagesData[currentIndex].full;
            }
            
            updateImageInfo();
        }

        function updateImageInfo() {
            imageInfo.textContent = \`\${currentIndex + 1} из \${imagesData.length}\`;
        }

        closeBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });

        prevBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            currentIndex = (currentIndex - 1 + imagesData.length) % imagesData.length;
            openModal(currentIndex);
        });

        nextBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            currentIndex = (currentIndex + 1) % imagesData.length;
            openModal(currentIndex);
        });

        document.addEventListener('keydown', (e) => {
            if (modal.style.display === 'block') {
                if (e.key === 'ArrowLeft') prevBtn.click();
                if (e.key === 'ArrowRight') nextBtn.click();
                if (e.key === 'Escape') modal.style.display = 'none';
            }
        });

        // Запуск
        window.addEventListener('load', initGallery);
    </script>
</body>
</html>`;
}

generateGallery();
