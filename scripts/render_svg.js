// Render SVG files to transparent PNGs with the system Chromium (Playwright), keeping each file's aspect ratio.
// usage: node scripts/render_svg.js <max_px> <out_dir> <file.svg> [file.svg ...]
// The SVG is inlined as a data: URL so an about:blank page may load it (file:// subresources are blocked there).
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const [size, outDir, ...files] = process.argv.slice(2);
  const px = parseInt(size, 10);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: px + 20, height: px + 20 }, deviceScaleFactor: 1 });
  for (const f of files) {
    const svg = fs.readFileSync(f, 'utf8');
    const w = parseFloat((svg.match(/<svg[^>]*\swidth="([\d.]+)"/) || [0, 1000])[1]);
    const h = parseFloat((svg.match(/<svg[^>]*\sheight="([\d.]+)"/) || [0, 1000])[1]);
    const scale = px / Math.max(w, h);
    const iw = Math.round(w * scale), ih = Math.round(h * scale);
    await page.setViewportSize({ width: iw + 20, height: ih + 20 });
    const src = 'data:image/svg+xml;base64,' + Buffer.from(svg, 'utf8').toString('base64');
    await page.setContent(`<html><body style="margin:0;background:transparent"><img id="i" src="${src}" style="width:${iw}px;height:${ih}px;display:block"></body></html>`);
    await page.waitForFunction(() => { const i = document.getElementById('i'); return i && i.complete && i.naturalWidth > 0; });
    await page.waitForTimeout(80);
    const out = path.join(outDir, path.basename(f).replace(/\.svg$/, `-${px}.png`));
    await page.locator('#i').screenshot({ path: out, omitBackground: true });
  }
  await browser.close();
  console.log('rendered', files.length, 'files at', px, 'px');
})();
