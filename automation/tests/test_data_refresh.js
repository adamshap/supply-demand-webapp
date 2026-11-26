const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const ismi = fs.existsSync(path.join(root, 'ism_webapp.html'));
const html = fs.readFileSync(path.join(root, ismi ? 'ism_webapp.html' : 'supply_demand_webapp.html'), 'utf8');
const commonStart = html.indexOf('        // Every deployment publishes');
const commonEnd = html.indexOf(ismi ? '        // Mobile controls toggle' : '        // Render from the selected data', commonStart);
const loadStart = html.indexOf('        async function loadData(');
const loadEnd = html.indexOf(ismi ? '        async function updateDataStatus()' : '        loadData(true);', loadStart);
const common = html.slice(commonStart, commonEnd), loader = html.slice(loadStart, loadEnd);
const files = vm.runInNewContext(/const RELEASE_FILES = (.*);/.exec(common)[1]);
const dates = Array.from({length: 81}, (_, i) => new Date(Date.UTC(2020, i, 1)).toISOString().slice(0, 7));
const csv = (count, revision = 0) => 'date,value\n' + dates.slice(0, count).map((date, i) => `${ismi ? date : date + '-01T12:00:00Z'},${i + revision}`).join('\n');
let version = 'a'.repeat(64), count = 80, revision = 0, fail = false, badManifest = false, calls = [], activePreset = '5Y';
const elements = new Map();
function element(id) {
    if (!elements.has(id)) elements.set(id, {value: '', hidden: true, textContent: '', style: {}, max: 0, remove() {}, setAttribute() {}});
    return elements.get(id);
}
const docEvents = {}, winEvents = {}, timers = [];
const document = {
    visibilityState: 'visible', getElementById: element,
    querySelector(selector) {
        if (selector.includes('.preset-chips')) return activePreset ? {textContent: activePreset, getAttribute: () => `setDateRange(${activePreset === 'All' ? "'all'" : parseInt(activePreset)})`} : null;
        if (selector.includes('frequency')) return {value: 'yearly'};
        return {prepend() {}};
    },
    createElement: () => ({setAttribute() {}}),
    addEventListener: (name, fn) => {docEvents[name] = fn;}
};
element('breakdown').value = 'baseline'; element('showAmbiguous').checked = true; element('inflation-series-select').value = '_c';
const context = vm.createContext({
    document, Date, console: {warn() {}}, chartUpdates: 0,
    window: {addEventListener: (name, fn) => {winEvents[name] = fn;}},
    setInterval: fn => timers.push(fn),
    updateDateDisplays() {}, syncChartTypeAvailability() {}, updateDataStatus: async () => {},
    parseCSV: text => text.split('\n').slice(1).filter(Boolean).map(line => {const [date, value] = line.split(','); return {date, value: Number(value)};}),
    fetch: async url => {
        calls.push(url);
        if (url.startsWith('data-manifest.json')) return {ok: true, status: 200, json: async () => ({version, published_at: new Date(Date.UTC(2026,0,1,0,0,version.charCodeAt(0))).toISOString(), files: Object.fromEntries(files.map(name => [name, badManifest ? 'invalid-path' : `data/${version}/${name}`]))})};
        if (fail) return {ok: false, status: 503};
        assert.ok(url.startsWith(`data/${version}/`), 'CSV must use the immutable release path');
        return {ok: true, status: 200, text: async () => csv(count, revision)};
    }
});
vm.runInContext(common + `
let sharingChart = false;
let allData = ${ismi ? '[]' : '{}'};
let timeseriesStartIdx = 0, timeseriesEndIdx = 0;
function getSheetData() {return allData.Baseline || [];}
function updateCharts() {
    if (!${ismi}) {
        if (!document.getElementById('startDateInput').value) document.getElementById('startDateInput').value = allData.Baseline[0].date.slice(0, 7);
        if (!document.getElementById('endDateInput').value) document.getElementById('endDateInput').value = allData.Baseline.at(-1).date.slice(0, 7);
    }
    chartUpdates++;
}
function setDateRange(years) {
    const rows = ${ismi ? 'allData' : 'allData.Baseline'};
    const start = years === 'all' ? 0 : Math.max(0, rows.length - years * 12);
    timeseriesStartIdx = start; timeseriesEndIdx = rows.length - 1;
    if (!${ismi}) {document.getElementById('startDateInput').value = rows[start].date.slice(0, 7);document.getElementById('endDateInput').value = rows.at(-1).date.slice(0, 7);}
}
` + loader, context);
const state = () => vm.runInContext(`({version:activeDataRelease?.version, length:${ismi ? 'allData.length' : '(allData.Baseline || []).length'}, last:Number(${ismi ? 'allData.at(-1)?.value' : 'allData.Baseline?.at(-1)?.value'}), start:timeseriesStartIdx,end:timeseriesEndIdx})`, context);
(async () => {
    await vm.runInContext('loadData(true)', context);
    assert.equal(state().length, 80, 'Initial release loads');
    assert.equal(state().version, version);
    calls = []; await vm.runInContext('loadData(true)', context);
    assert.equal(calls.length, 1, 'An unchanged release downloads only the manifest');
    version = 'b'.repeat(64); count = 81;
    await vm.runInContext('loadData(true)', context);
    assert.equal(state().length, 81, 'A new month is picked up');
    assert.equal(state().start, 21, 'The chosen five-year preset rolls forward');
    assert.equal(element('inflation-series-select').value, '_c', 'Selected series remains untouched');
    assert.ok(vm.runInContext(`dataFileUrl('${ismi ? 'ismi_data.xlsx' : 'supply_demand_public.xlsx'}')`, context).includes(version), 'Excel uses the current release too');
    activePreset = null;
    if (ismi) vm.runInContext('timeseriesStartIdx=10;timeseriesEndIdx=20;', context);
    else {element('startDateInput').value=dates[10];element('endDateInput').value=dates[20];}
    version='c'.repeat(64); revision=1;
    await vm.runInContext('loadData(true)', context);
    assert.equal(state().last, 81, 'Same-month revisions are picked up');
    if (ismi) {assert.equal(state().start,10);assert.equal(state().end,20);}
    else {assert.equal(element('startDateInput').value,dates[10]);assert.equal(element('endDateInput').value,dates[20]);}
    const stable = JSON.stringify(state());
    version='a'.repeat(64);
    await vm.runInContext('loadData(true)',context);
    assert.equal(JSON.stringify(state()),stable,'A cached older revision cannot replace newer data for the same month');
    version='d'.repeat(64); fail=true;
    await vm.runInContext('loadData(true)', context);
    assert.equal(JSON.stringify(state()),stable,'A failed download preserves the loaded release');
    fail=false; badManifest=true;
    await vm.runInContext('loadData(true)', context);
    assert.equal(JSON.stringify(state()),stable,'Invalid manifest paths are rejected');
    badManifest=false; count=79;
    await vm.runInContext('loadData(true)', context);
    assert.equal(JSON.stringify(state()),stable,'Older data cannot roll back a loaded release');
    calls=[]; vm.runInContext('sharingChart=true;',context);
    await vm.runInContext('loadData(true)',context); assert.equal(calls.length,0,'Refreshing does not interrupt an export');
    let checks=0; context.testRefresh=()=>checks++; vm.runInContext('startDataRefresh(testRefresh)',context);
    document.visibilityState='hidden'; timers[0](); assert.equal(checks,0);
    document.visibilityState='visible'; timers[0](); docEvents.visibilitychange(); winEvents.focus(); winEvents.online(); winEvents.pageshow({persisted:true});
    assert.equal(checks,5,'Visible timers, tab returns, reconnection and cached-page restoration all recheck');
    console.log((ismi?'ISMI':'Supply/demand')+': new months, revisions, preserved selections, versioned Excel, failure/rollback protection and refresh triggers passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
