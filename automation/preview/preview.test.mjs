import test from 'node:test';
import assert from 'node:assert/strict';
import {monthFromDate,latestCsvMonth,monthLabel,imageName,updateSharingImages,captureHtml} from './preview.mjs';

test('monthly dates support dashboard CSV formats and ignore empty trailing rows',()=>{
  for(const raw of ['2026-10','2026m10','2026-10-01T12:00:00Z','801']) assert.equal(monthFromDate(raw),'2026-10');
  assert.equal(latestCsvMonth('date,value\r\n2026m9,1\r\n2026m10,2\r\n2026m11,\r\n'),'2026-10');
  assert.equal(monthLabel('2026-10'),'October 2026');
  assert.throws(()=>monthFromDate('2026m13'));
  assert.throws(()=>latestCsvMonth('date,value\n2026m10,\n'));
});

test('new image bytes get a fresh immutable filename',()=>{
  const a=imageName(Buffer.from('October'));
  assert.equal(a,imageName(Buffer.from('October')));
  assert.notEqual(a,imageName(Buffer.from('November')));
  assert.match(a,/^preview-[a-f0-9]{20}\.png$/);
});

test('sharing metadata changes without altering public app code or body',()=>{
  const html='<head><meta property="og:image" content="old"><meta name="twitter:image" content="old"></head><body><canvas></canvas><script>const x=1;</script></body>';
  const output=updateSharingImages(html,'https://example.com/preview-new.png');
  assert.equal(output.split('<body')[1],html.split('<body')[1]);
  assert.equal((output.match(/https:\/\/example.com\/preview-new.png/g)||[]).length,2);
  assert.throws(()=>updateSharingImages('<body>no tags</body>','url'));
});

test('capture uses fresh CSV month and escaped title, not hard-coded metadata',()=>{
  const html='<head></head><body><script data-goatcounter="count" src="external"></script></body>';
  const output=captureHtml(html,{title:'Supply & Demand',caption:'Headline'},'2026-11');
  assert(output.includes('November 2026'));
  assert(output.includes('Supply &amp; Demand'));
  assert(!output.includes('data-goatcounter'));
});
