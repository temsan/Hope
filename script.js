let images = [];
let imageNames = [];
let currentIndex = 0;

const loadBtn = document.getElementById('loadBtn');
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
        element.style.transform = `translateY(${scrolled * speed}px)`;
    });

    // Parallax for gallery items
    const galleryItems = document.querySelectorAll('.gallery-item');
    galleryItems.forEach((item, index) => {
        const rect = item.getBoundingClientRect();
        const scrollPercent = (window.innerHeight - rect.top) / window.innerHeight;

        if (scrollPercent > 0 && scrollPercent < 1) {
            const translateY = (scrollPercent - 0.5) * 20;
            item.style.transform = `translateY(${translateY}px)`;
        }
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
        shape.style.transform = `translate(${xMove}px, ${yMove}px)`;
    });
});

// Автоматическая загрузка изображений при открытии страницы
window.addEventListener('load', () => {
    loadImagesFromServer();
});

loadBtn.addEventListener('click', () => {
    loadImagesFromServer();
});

async function loadImagesFromServer() {
    try {
        loadBtn.textContent = 'Загрузка...';
        loadBtn.disabled = true;

        const response = await fetch('/api/images');
        const data = await response.json();

        if (data.images && data.images.length > 0) {
            images = [];
            imageNames = [];
            gallery.innerHTML = '';

            data.images.forEach((filename, index) => {
                const imageUrl = `/api/image/${encodeURIComponent(filename)}`;
                images.push(imageUrl);
                imageNames.push(filename);
                createGalleryItem(imageUrl, index, filename);
            });

            updateImageCount(data.images.length);
            loadBtn.textContent = 'Обновить галерею';
        } else {
            imageCount.textContent = 'Изображения не найдены';
            loadBtn.textContent = 'Попробовать снова';
        }

        loadBtn.disabled = false;
    } catch (error) {
        console.error('Ошибка загрузки изображений:', error);
        imageCount.textContent = 'Ошибка загрузки. Проверьте, что сервер запущен.';
        loadBtn.textContent = 'Попробовать снова';
        loadBtn.disabled = false;
    }
}

function updateImageCount(count) {
    imageCount.textContent = `Загружено работ: ${count}`;
    imageCount.style.opacity = '0';
    setTimeout(() => {
        imageCount.style.transition = 'opacity 0.5s ease';
        imageCount.style.opacity = '1';
    }, 10);
}

function createGalleryItem(src, index, name) {
    const item = document.createElement('div');
    item.className = 'gallery-item';
    item.style.opacity = '0';
    item.style.transform = 'translateY(30px)';

    const img = document.createElement('img');
    img.src = src;
    img.alt = name || `Работа ${index + 1}`;
    img.loading = 'lazy';

    img.onerror = () => {
        console.error(`Ошибка загрузки изображения: ${name}`);
        item.style.display = 'none';
    };

    item.appendChild(img);
    item.addEventListener('click', () => openModal(index));
    gallery.appendChild(item);

    // Fade in animation
    setTimeout(() => {
        item.style.transition = 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
        item.style.opacity = '1';
        item.style.transform = 'translateY(0)';
    }, index * 50);
}

function openModal(index) {
    currentIndex = index;
    modal.style.display = 'block';
    modalImg.style.opacity = '0';
    modalImg.src = images[currentIndex];

    setTimeout(() => {
        modalImg.style.transition = 'opacity 0.5s ease';
        modalImg.style.opacity = '1';
    }, 10);

    updateImageInfo();
}

function updateImageInfo() {
    imageInfo.textContent = `${currentIndex + 1} из ${images.length}`;
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
    currentIndex = (currentIndex - 1 + images.length) % images.length;
    modalImg.style.opacity = '0';
    setTimeout(() => {
        modalImg.src = images[currentIndex];
        modalImg.style.opacity = '1';
        updateImageInfo();
    }, 200);
});

nextBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    currentIndex = (currentIndex + 1) % images.length;
    modalImg.style.opacity = '0';
    setTimeout(() => {
        modalImg.src = images[currentIndex];
        modalImg.style.opacity = '1';
        updateImageInfo();
    }, 200);
});

document.addEventListener('keydown', (e) => {
    if (modal.style.display === 'block') {
        if (e.key === 'ArrowLeft') prevBtn.click();
        if (e.key === 'ArrowRight') nextBtn.click();
        if (e.key === 'Escape') modal.style.display = 'none';
    }
});
