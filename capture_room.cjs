// Конечный кадр влёта: комната галереи после пролёта, кадр 1600×900 — как кадр клипов.
// Дождь, кнопку «пройти ещё раз» и полосу прогресса не снимаем: живые проявятся поверх после клипа.
//   node capture_room.cjs  →  assets/stills/room.jpg
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: false,
    args: ['--window-position=-2700,0', '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding'] });
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
  await page.goto('file:///' + path.join(__dirname, 'index.html').replace(/\\/g, '/'), { waitUntil: 'load' });
  await page.waitForTimeout(1500);
  await page.evaluate(() => scrollTo(0, document.documentElement.scrollHeight));
  await page.waitForTimeout(6000);
  await page.addStyleTag({ content: '#rainBgCanvas, .flight .arrival, .flight .progress { visibility: hidden !important }' });
  await page.waitForTimeout(500);
  const out = path.join(__dirname, 'assets', 'stills', 'room.jpg');
  await page.screenshot({ path: out, type: 'jpeg', quality: 95 });
  console.log(out);
  await browser.close();
})();
