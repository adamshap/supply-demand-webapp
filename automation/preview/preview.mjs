import {createHash} from 'node:crypto';

export function monthFromDate(value) {
  const raw = String(value).trim().replace(/^"|"$/g, '');
  let match = /^(\d{4})(?:-|m)(\d{1,2})(?:$|[-T])/.exec(raw);
  let year, month;
  if (match) {
    year = Number(match[1]); month = Number(match[2]);
  } else if (/^-?\d+$/.test(raw)) {
    const date = new Date(Date.UTC(1960, Number(raw), 1));
    year = date.getUTCFullYear(); month = date.getUTCMonth() + 1;
  } else {
    throw new Error(`Unrecognized monthly date: ${raw}`);
  }
  if (year < 1900 || year > 2200 || month < 1 || month > 12) throw new Error(`Invalid month: ${raw}`);
  return `${year}-${String(month).padStart(2, '0')}`;
}

export function latestCsvMonth(csv) {
  const rows = csv.trim().split(/\r?\n/);
  const header = rows.shift().replace(/^\uFEFF/, '').split(',');
  const column = header.findIndex(value => value.trim().replaceAll('"', '') === 'date');
  if (column < 0) throw new Error('Preview CSV has no date column');
  const months = rows.filter(Boolean).flatMap(row => {
    const values = row.split(',');
    if (!values.some((value, index) => index !== column && value.trim() && Number.isFinite(Number(value)))) return [];
    return [monthFromDate(values[column])];
  });
  if (!months.length) throw new Error('Preview CSV contains no populated monthly data');
  return months.sort().at(-1);
}

export function monthLabel(month) {
  return new Intl.DateTimeFormat('en-US', {month: 'long', year: 'numeric', timeZone: 'UTC'})
    .format(new Date(`${month}-01T00:00:00Z`));
}

export function imageName(png) {
  return `preview-${createHash('sha256').update(png).digest('hex').slice(0, 20)}.png`;
}

export function updateSharingImages(html, url, alt) {
  let openGraph = 0, twitter = 0;
  const updated = html.replace(/<meta\b[^>]*>/gi, tag => {
    const property = /\b(?:property|name)=["']([^"']+)["']/i.exec(tag)?.[1];
    if (alt && ['og:image:alt', 'twitter:image:alt'].includes(property)) {
      return tag.replace(/\bcontent=["'][^"']*["']/i, `content="${escape(alt)}"`);
    }
    if (!['og:image', 'og:image:secure_url', 'twitter:image'].includes(property)) return tag;
    if (property === 'og:image') openGraph++;
    if (property === 'twitter:image') twitter++;
    return tag.replace(/\bcontent=["'][^"']*["']/i, `content="${url}"`);
  });
  if (openGraph !== 1 || twitter !== 1) throw new Error('Expected one Open Graph and one Twitter image tag');
  if (updated.split('<body')[1] !== html.split('<body')[1]) throw new Error('Preview update changed the dashboard body');
  return updated;
}

const escape = text => String(text).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');

export function captureHtml(html, config, through) {
  // Render only a temporary chart-only page. Public application code is never
  // rewritten: these layout and animation changes exist in the render server.
  let result = html.replace(/<script\b[^>]*data-goatcounter[^>]*>\s*<\/script>/gi, '');
  result = result.replace(/https:\/\/cdn\.jsdelivr\.net\/npm\/chart\.js@[^/]+\/dist\/chart\.umd\.min\.js/g, '/__preview-assets/chart.js');
  result = result.replace(/https:\/\/cdn\.jsdelivr\.net\/npm\/chartjs-adapter-date-fns@[^/]+\/dist\/chartjs-adapter-date-fns\.bundle\.min\.js/g, '/__preview-assets/adapter.js');
  result = result.replace(/responsive: true,/g, 'responsive: true, animation: false,')
    .replace(/animation:\s*\{\s*duration:\s*\d+\s*\}/g, 'animation: false');
  const css = `<style>
html,body{margin:0!important;width:1200px!important;height:630px!important;overflow:hidden!important;background:white!important}
body>*{visibility:hidden}.chart-wrapper,.chart-wrapper *{visibility:visible!important}
.chart-wrapper{position:fixed!important;left:38px!important;top:105px!important;width:1124px!important;height:442px!important}
.preview-heading{visibility:visible!important;position:fixed;left:44px;top:24px;margin:0!important;font-size:36px!important;font-weight:500!important;line-height:1.2!important;letter-spacing:-.6px;color:#233342!important}
.preview-caption{visibility:visible!important;position:fixed;left:44px;bottom:26px;margin:0;font-size:17px;color:#647180}
</style>`;
  result = result.replace('</head>', css + '</head>');
  return result.replace('</body>', `<h1 class="preview-heading">${escape(config.title)}</h1><p class="preview-caption">${escape(config.caption)} &nbsp;·&nbsp; Data through ${escape(monthLabel(through))}</p></body>`);
}
