// Executed by GitHub Actions, against a staged snapshot, never a personal browser.
import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile, writeFile, rename} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {captureHtml, imageName, latestCsvMonth, updateSharingImages} from './preview.mjs';

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(directory, '../..');
const arg = process.argv.indexOf('--site');
const site = path.resolve(arg >= 0 ? process.argv[arg + 1] : path.join(root, '_site'));
const config = JSON.parse(await readFile(path.join(directory, 'config.json'), 'utf8'));
const manifest = JSON.parse(await readFile(path.join(site, 'data-manifest.json'), 'utf8'));
const through = latestCsvMonth(await readFile(path.join(site, manifest.files[config.csv]), 'utf8'));
const original = await readFile(path.join(site, config.html), 'utf8');
const capture = captureHtml(original, config, through);
const assets = new Map([
  ['/__preview-assets/chart.js', path.join(directory, 'node_modules/chart.js/dist/chart.umd.js')],
  ['/__preview-assets/adapter.js', path.join(directory, 'node_modules/chartjs-adapter-date-fns/dist/chartjs-adapter-date-fns.bundle.min.js')]
]);
const server = createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    if (pathname === '/__preview.html') {
      res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'}); res.end(capture); return;
    }
    const target = assets.get(pathname) || path.resolve(site, '.' + pathname);
    if (!assets.has(pathname) && !target.startsWith(site + path.sep)) { res.writeHead(403); res.end(); return; }
    const types = {'.js':'text/javascript', '.html':'text/html', '.json':'application/json', '.csv':'text/csv', '.png':'image/png'};
    res.writeHead(200, {'Content-Type': types[path.extname(target)] || 'application/octet-stream', 'Cache-Control':'no-store'});
    res.end(await readFile(target));
  } catch {
    if (!res.headersSent) res.writeHead(404);
    res.end();
  }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  browser = await chromium.launch({headless:true});
  const context = await browser.newContext({viewport:{width:1200,height:630},deviceScaleFactor:1,
    locale:'en-US',timezoneId:'UTC',colorScheme:'light',reducedMotion:'reduce'});
  // All chart libraries and data are local. Never send analytics or load a
  // different data release from the live dashboard during image generation.
  await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(origin + '/__preview.html');
  await page.waitForFunction(id => typeof Chart !== 'undefined' && Chart.getChart(id)?.data.datasets.some(d => d.data.length), config.chartId, {timeout:30000});
  const chartInfo = await page.evaluate(async ({id, expected}) => {
    setDateRange(5);
    const chart = Chart.getChart(id);
    chart.options.animation = false;
    chart.resize(1124, 442);
    chart.update('none');
    await document.fonts.ready;
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const points = chart.data.datasets.flatMap(dataset => dataset.data).filter(p => p && Number.isFinite(p.y));
    const through = points.map(p => new Date(p.x).toISOString().slice(0,7)).sort().at(-1);
    if (through !== expected) throw new Error(`Chart ends ${through}; staged CSV ends ${expected}`);
    if (points.length < 12) throw new Error('Chart has too few populated points');
    for (const selector of ['.preview-heading','.preview-caption']) {
      const el = document.querySelector(selector), box = el.getBoundingClientRect();
      if (box.right > 1200 || box.bottom > 630 || el.scrollWidth > 1124) throw new Error(`Clipped preview text: ${selector}`);
    }
    const pixels = chart.canvas.getContext('2d').getImageData(0,0,chart.canvas.width,chart.canvas.height).data;
    let filled=0;
    for(let i=0;i<pixels.length;i+=4) if(pixels[i+3] && Math.min(pixels[i],pixels[i+1],pixels[i+2])<200) filled++;
    if(filled<1000) throw new Error('Chart canvas is blank');
    return {through,points:points.length,series:chart.data.datasets.map(d=>d.label)};
  }, {id:config.chartId,expected:through});
  if(errors.length) throw new Error(errors.join('\n'));
  const png = await page.screenshot({type:'png',animations:'disabled'});
  if(png.readUInt32BE(16)!==1200 || png.readUInt32BE(20)!==630) throw new Error('Incorrect preview dimensions');
  const filename = imageName(png), url = new URL(filename,config.baseUrl).href;
  await writeFile(path.join(site,filename),png);
  await writeFile(path.join(site,'preview.png.tmp'),png);
  await rename(path.join(site,'preview.png.tmp'),path.join(site,'preview.png'));
  for(const file of [config.html,'index.html']) {
    const html = await readFile(path.join(site,file),'utf8');
    await writeFile(path.join(site,file),updateSharingImages(html,url));
  }
  const report={data_version:manifest.version,data_through:through,image:filename,image_url:url,width:1200,height:630,...chartInfo};
  await writeFile(path.join(site,'preview-release.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify(report));
} finally {
  if(browser) await browser.close();
  await new Promise(resolve=>server.close(resolve));
}
