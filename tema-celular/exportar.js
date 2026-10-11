// Gera os PNGs (papéis de parede 1080×2340 e ícones 512×512) a partir do index.html.
// Uso: node tema-celular/exportar.js
const { chromium } = require("playwright");
const fs = require("fs"), path = require("path");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1200, height: 1000 } });
  await page.goto("file://" + path.join(__dirname, "index.html"));
  const out = await page.evaluate(() => window.exportAll());
  const dir = path.join(__dirname, "png");
  fs.mkdirSync(path.join(dir, "icones"), { recursive: true });
  const write = (file, url) => fs.writeFileSync(file, Buffer.from(url.split(",")[1], "base64"));
  for (const [k, v] of Object.entries(out.wallpapers)) write(path.join(dir, `papel-de-parede-${k}.png`), v);
  for (const [k, v] of Object.entries(out.icons)) write(path.join(dir, "icones", `${k}.png`), v);
  await page.screenshot({ path: path.join(dir, "previa.png"), fullPage: true });
  await browser.close();
})();
