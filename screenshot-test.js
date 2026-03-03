const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch();
    const page = await browser.newPage({
        viewport: { width: 1920, height: 1080 }
    });
    
    await page.goto('http://localhost:8888/gallery.html');
    await page.waitForTimeout(3000);
    
    // Скриншот 1: Главная страница
    await page.screenshot({ path: 'test-results/screenshot-1-main.png', fullPage: true });
    console.log('Screenshot 1: Main page saved');
    
    // Скриншот 2: Клик на первую картину (модальное окно)
    const firstItem = await page.locator('.gallery-item').first();
    await firstItem.click();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'test-results/screenshot-2-modal.png' });
    console.log('Screenshot 2: Modal opened');
    
    // Скриншот 3: Переключение на следующую картину
    const nextBtn = await page.locator('#nextBtn');
    await nextBtn.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'test-results/screenshot-3-next.png' });
    console.log('Screenshot 3: Next image');
    
    await browser.close();
    console.log('All screenshots saved!');
})();
