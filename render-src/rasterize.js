// rasterize SVG files to PNG: node raster.js out_dir file1.svg file2.svg ...
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
(async () => {
  const [out, ...files] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  for (const f of files) {
    const src = fs.readFileSync(f, 'utf8');
    const m = src.match(/width="(\d+)" height="(\d+)"/);
    const w = +m[1], h = +m[2];
    await page.setViewportSize({ width: w, height: h });
    await page.setContent(`<html><body style="margin:0;background:transparent">${src}</body></html>`);
    const name = path.basename(f).replace('.svg', '.png');
    await page.screenshot({ path: path.join(out, name), omitBackground: true, clip: { x: 0, y: 0, width: w, height: h } });
    console.log('wrote', name, w, h);
  }
  await browser.close();
})();
