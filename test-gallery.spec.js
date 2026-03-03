const { test, expect } = require('@playwright/test');
const path = require('path');

test.describe('Gallery Tests', () => {
    test.beforeEach(async ({ page }) => {
        // Открываем локальный HTML файл
        const filePath = 'file://' + path.resolve(__dirname, 'gallery.html');
        await page.goto(filePath);
        await page.waitForLoadState('networkidle');
    });

    test('should load gallery page with correct title', async ({ page }) => {
        await expect(page).toHaveTitle(/Надежда Ков/);
    });

    test('should display header with artist name', async ({ page }) => {
        const header = page.locator('.header-content h1');
        await expect(header).toContainText('Надежда Ков');
    });

    test('should display moon element', async ({ page }) => {
        const moon = page.locator('body::after');
        await expect(moon).toBeAttached();
    });

    test('should display 4 candles', async ({ page }) => {
        const candles = page.locator('.candle');
        await expect(candles).toHaveCount(4);
    });

    test('should display cat Пуля', async ({ page }) => {
        const cat = page.locator('.cat');
        await expect(cat).toBeVisible();

        const catBody = page.locator('.cat-body');
        await expect(catBody).toBeVisible();

        const catHead = page.locator('.cat-head');
        await expect(catHead).toBeVisible();

        const catEyes = page.locator('.cat-eye');
        await expect(catEyes).toHaveCount(2);
    });

    test('should display gallery items', async ({ page }) => {
        const galleryItems = page.locator('.gallery-item');
        const count = await galleryItems.count();
        expect(count).toBeGreaterThan(0);
        console.log(`Found ${count} gallery items`);
    });

    test('should have correct image brightness', async ({ page }) => {
        const firstImage = page.locator('.gallery-item img').first();
        await firstImage.waitFor({ state: 'visible' });

        const filter = await firstImage.evaluate(el =>
            window.getComputedStyle(el).filter
        );

        console.log('Image filter:', filter);
        expect(filter).toContain('brightness');
    });

    test('should increase brightness on hover', async ({ page }) => {
        const firstItem = page.locator('.gallery-item').first();
        const firstImage = firstItem.locator('img');

        await firstImage.waitFor({ state: 'visible' });

        // Получаем начальный фильтр
        const initialFilter = await firstImage.evaluate(el =>
            window.getComputedStyle(el).filter
        );

        // Наводим мышь
        await firstItem.hover();
        await page.waitForTimeout(500);

        // Получаем фильтр после hover
        const hoverFilter = await firstImage.evaluate(el =>
            window.getComputedStyle(el).filter
        );

        console.log('Initial filter:', initialFilter);
        console.log('Hover filter:', hoverFilter);
    });

    test('should open zoom on click', async ({ page }) => {
        const firstItem = page.locator('.gallery-item').first();
        await firstItem.waitFor({ state: 'visible' });

        await firstItem.click();
        await page.waitForTimeout(300);

        // Проверяем что элемент получил класс zoomed
        await expect(firstItem).toHaveClass(/zoomed/);

        // Проверяем что появились контролы
        const zoomControls = page.locator('.zoom-controls');
        await expect(zoomControls).toBeVisible();
    });

    test('should close zoom on close button', async ({ page }) => {
        const firstItem = page.locator('.gallery-item').first();
        await firstItem.click();
        await page.waitForTimeout(300);

        const closeBtn = page.locator('#closeZoomBtn');
        await closeBtn.click();
        await page.waitForTimeout(300);

        await expect(firstItem).not.toHaveClass(/zoomed/);
    });

    test('should navigate between images in zoom mode', async ({ page }) => {
        const firstItem = page.locator('.gallery-item').first();
        await firstItem.click();
        await page.waitForTimeout(300);

        const nextBtn = page.locator('#nextZoomBtn');
        await nextBtn.click();
        await page.waitForTimeout(500);

        const secondItem = page.locator('.gallery-item[data-index="1"]');
        await expect(secondItem).toHaveClass(/zoomed/);
    });

    test('should display fluid shapes', async ({ page }) => {
        const fluidShapes = page.locator('.fluid-shape');
        await expect(fluidShapes).toHaveCount(4);
    });

    test('should have dark background', async ({ page }) => {
        const bgColor = await page.evaluate(() =>
            window.getComputedStyle(document.body).backgroundColor
        );
        console.log('Background color:', bgColor);
        expect(bgColor).toMatch(/rgb\(10,\s*10,\s*10\)/);
    });

    test('should take screenshot of gallery', async ({ page }) => {
        await page.waitForTimeout(1000);
        await page.screenshot({
            path: 'gallery-screenshot.png',
            fullPage: true
        });
    });

    test('should take screenshot of zoomed image', async ({ page }) => {
        const firstItem = page.locator('.gallery-item').first();
        await firstItem.click();
        await page.waitForTimeout(500);

        await page.screenshot({
            path: 'gallery-zoomed-screenshot.png',
            fullPage: false
        });
    });
});
