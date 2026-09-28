// Read-only browser acceptance. Never creates a guest run or sends credentials.
const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');

(async () => {
  const base = process.argv[2];
  const out = process.argv[3] || 'var/browser';
  if (!base || !base.startsWith('https://')) throw new Error('An HTTPS base URL is required');
  await fs.mkdir(out, { recursive: true });
  const browser = await chromium.launch();
  const results = [];
  try {
    for (const [name, viewport] of [['desktop', {width: 1440, height: 1000}], ['mobile', {width: 390, height: 844}]]) {
      const page = await browser.newPage({ viewport });
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      for (const [label, url] of [
        ['portfolio', 'https://ahines99.github.io/systematic-research-factory/'],
        ['demo', base.replace(/\/$/, '') + '/demo'],
      ]) {
        const response = await page.goto(url, { waitUntil: 'networkidle', timeout: 90000 });
        if (!response.ok()) throw new Error(`${label}: HTTP ${response.status()}`);
        const text = await page.locator('body').innerText();
        if (!/simulat/i.test(text)) throw new Error(`${label}: missing simulation disclosure`);
        const fits = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1);
        if (!fits) throw new Error(`${label}: horizontal page overflow at ${name}`);
        await page.screenshot({path: path.join(out, `${label}-${name}.png`), fullPage: true});
        results.push({page: label, viewport: name, http_status: response.status(), horizontal_overflow: false});
        if (label === 'demo') {
          const link = page.locator('a[href^="/demo/runs/"]').first();
          await link.click();
          await page.waitForLoadState('networkidle');
          if (!/simulat/i.test(await page.locator('body').innerText())) throw new Error('Report missing simulation disclosure');
          await page.screenshot({path: path.join(out, `report-${name}.png`), fullPage: true});
          results.push({page: 'report', viewport: name, navigated: true});
        }
      }
      if (errors.length) throw new Error(`Browser errors: ${errors.join('; ')}`);
      await page.close();
    }
    await fs.writeFile(path.join(out, 'browser-checks.json'), JSON.stringify({checked_at: new Date().toISOString(), results}, null, 2));
    console.log('Desktop/mobile page, navigation, overflow and JavaScript checks passed.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
