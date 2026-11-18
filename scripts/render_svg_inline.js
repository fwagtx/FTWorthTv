// Render SVG files to PNG with Chromium, with the SVG inlined in the DOM so @font-face fonts from a local folder apply.
// usage: node scripts/render_svg_inline.js <font_dir> <max_px> <out_dir> <file.svg> [file.svg ...]
// Every .ttf/.otf in font_dir is registered as a @font-face whose family name is the file's stem (e.g. "BodoniModa").
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
(async () => {
  const [fontDir, size, outDir, ...files] = process.argv.slice(2);
  const px = parseInt(size, 10);
  const faces = [];
  const walk = (d) => { for (const f of fs.readdirSync(d)) { const p = path.join(d, f); if (fs.statSync(p).isDirectory()) walk(p); else if (/\.(ttf|otf)$/i.test(f)) faces.push(p); } };
  if (fs.existsSync(fontDir)) walk(fontDir);
  const css = faces.map(p => {
    const stem = path.basename(p).replace(/\.(ttf|otf)$/i, '');
    const family = stem.replace(/\[.*\]$/, '');            // "BodoniModa[opsz,wght]" -> "BodoniModa"
    const italic = /italic/i.test(stem) ? 'italic' : 'normal';
    const fam = family.replace(/-?Italic$/i, '').replace(/-(Regular|Bold|Black)$/i, '');
    const b64 = fs.readFileSync(p).toString('base64');
    const fmt = /\.otf$/i.test(p) ? 'opentype' : 'truetype';
    return `@font-face{font-family:"${fam}";font-style:${italic};font-weight:100 900;src:url(data:font/${fmt};base64,${b64}) format("${fmt}")}`;
  }).join('\n');
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: px + 40, height: px + 40 }, deviceScaleFactor: 1 });
  for (const f of files) {
    const svg = fs.readFileSync(f, 'utf8');
    const w = parseFloat((svg.match(/<svg[^>]*\swidth="([\d.]+)"/) || [0, 1000])[1]);
    const h = parseFloat((svg.match(/<svg[^>]*\sheight="([\d.]+)"/) || [0, 1000])[1]);
    const scale = px / Math.max(w, h);
    const iw = Math.round(w * scale), ih = Math.round(h * scale);
    await page.setViewportSize({ width: iw + 40, height: ih + 40 });
    const inner = svg.replace(/width="[\d.]+"\s+height="[\d.]+"/, `width="${iw}" height="${ih}"`);
    await page.setContent(`<html><head><style>${css} body{margin:0;background:transparent} #wrap{width:${iw}px;height:${ih}px}</style></head><body><div id="wrap">${inner}</div></body></html>`);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(120);
    const out = path.join(outDir, path.basename(f).replace(/\.svg$/, `-${px}.png`));
    await page.locator('#wrap').screenshot({ path: out, omitBackground: true });
  }
  await browser.close();
  console.log('rendered', files.length, 'files at', px, 'px with', faces.length, 'fonts');
})();
