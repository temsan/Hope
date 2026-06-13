const express = require('express');
const path = require('path');
const fs = require('fs');
const https = require('https');

const app = express();
const PORT = 3000;

// Telegram Bot настройки (замените на свои)
const TELEGRAM_BOT_TOKEN = 'YOUR_BOT_TOKEN';
const TELEGRAM_CHAT_ID = 'YOUR_CHAT_ID';

// Путь к папке с изображениями
const IMAGES_PATH = 'C:\\Users\\temsan\\OneDrive\\Desktop\\Сканы\\JPEG';

// Статические файлы
app.use(express.static(__dirname));

// Парсинг JSON
app.use(express.json());

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

// API для отправки заказа
app.post('/api/order', async (req, res) => {
    try {
        const order = req.body;
        
        // Валидация
        if (!order.name || !order.phone) {
            return res.status(400).json({ error: 'Имя и телефон обязательны' });
        }

        // Формируем сообщение для Telegram
        const message = `
🛒 *Новый заказ*

🖼 *Работа:* ${order.image}
👤 *Имя:* ${order.name}
📞 *Телефон:* ${order.phone}
📧 *Email:* ${order.email || 'Не указан'}
📏 *Размер:* ${order.size}
💬 *Комментарий:* ${order.comment || 'Нет'}

⏰ *Время:* ${new Date().toLocaleString('ru-RU')}
        `.trim();

        // Отправляем в Telegram
        await sendToTelegram(message);

        // Сохраняем заказ в файл (для истории)
        saveOrderToFile(order);

        res.json({ success: true, message: 'Заказ успешно отправлен' });
    } catch (error) {
        console.error('Ошибка обработки заказа:', error);
        res.status(500).json({ error: 'Ошибка сервера' });
    }
});

// Функция отправки в Telegram
function sendToTelegram(message) {
    return new Promise((resolve, reject) => {
        const data = JSON.stringify({
            chat_id: TELEGRAM_CHAT_ID,
            text: message,
            parse_mode: 'Markdown'
        });

        const options = {
            hostname: 'api.telegram.org',
            port: 443,
            path: `/bot${TELEGRAM_BOT_TOKEN}/sendMessage`,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': data.length
            }
        };

        const req = https.request(options, (res) => {
            let responseData = '';
            res.on('data', (chunk) => {
                responseData += chunk;
            });
            res.on('end', () => {
                console.log('Telegram ответ:', responseData);
                resolve(responseData);
            });
        });

        req.on('error', (error) => {
            console.error('Ошибка отправки в Telegram:', error);
            reject(error);
        });

        req.write(data);
        req.end();
    });
}

// Сохранение заказа в файл
function saveOrderToFile(order) {
    const ordersDir = path.join(__dirname, 'orders');
    if (!fs.existsSync(ordersDir)) {
        fs.mkdirSync(ordersDir);
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `order-${timestamp}.json`;
    const filepath = path.join(ordersDir, filename);

    const orderData = {
        ...order,
        timestamp: new Date().toISOString()
    };

    fs.writeFileSync(filepath, JSON.stringify(orderData, null, 2), 'utf8');
    console.log(`Заказ сохранен: ${filename}`);
}

app.listen(PORT, () => {
    console.log(`Сервер запущен на http://localhost:${PORT}`);
    console.log(`Папка с изображениями: ${IMAGES_PATH}`);
});
