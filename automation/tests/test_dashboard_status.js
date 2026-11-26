const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../../supply_demand_webapp.html'),'utf8');
const match=html.match(/async function updateDataStatus\(baseline\) \{[\s\S]*?(?=\n        \/\/ Fetch fresh data)/);
assert.ok(match);
async function check(metadata) {
 const element={hidden:true,textContent:''};
 await vm.runInNewContext(`(async()=>{${match[0]};await updateDataStatus([{date:'2026-10-01T12:00:00Z'}]);})()`,{
  document:{getElementById:()=>element},fetch:async()=>({ok:true,json:async()=>metadata}),Date,console,dataFileUrl:name=>name
 });return element;
}
(async()=>{
 let e=await check({data_through:'2026-10',bea_release_date:'2026-11-25'});
 assert.equal(e.textContent,'Last updated November 25, 2026');assert.equal(e.dateTime,'2026-11-25');assert.equal(e.hidden,false);
 e=await check({data_through:'2026-11',bea_release_date:'2026-12-23'});assert.equal(e.hidden,true);
 console.log('Dashboard release date and CSV-version matching passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
