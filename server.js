const express = require('express');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = 3000;

// Путь к папке с изображениями
const IMAGES_PATH = 'C:\\Users\\temsan\\OneDrive\\Desktop\\Сканы\\JPEG';

// Статические файлы
app.use(express.static(__dirname));

// API для получения списка изображений
app.get('/api/images', (req, res) => {
    try {
        const files = fs.readdirSync(IMAGES_PATH);
        const imageFiles = files.filter(file => {
            const ext = path.extname(file).toLowerCase();
            return ['.jpg', '.jpeg', '.png', '.gif', '.webp'].includes(ext);
        }).sort();

        res.json({ images: imageFiles });
    } catch (error) {
        console.error('Ошибка чтения папки:', error);
        res.status(500).json({ error: 'Не удалось прочитать папку с изображениями' });
    }
});

// Отдача изображений
app.get('/api/image/:filename', (req, res) => {
    try {
        const filename = req.params.filename;
        const imagePath = path.join(IMAGES_PATH, filename);

        if (fs.existsSync(imagePath)) {
            res.sendFile(imagePath);
        } else {
            res.status(404).send('Изображение не найдено');
        }
    } catch (error) {
        console.error('Ошибка отдачи изображения:', error);
        res.status(500).send('Ошибка сервера');
    }
});

app.listen(PORT, () => {
    console.log(`Сервер запущен на http://localhost:${PORT}`);
    console.log(`Папка с изображениями: ${IMAGES_PATH}`);
});
