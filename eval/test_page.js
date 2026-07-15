/*
 * test_page.js — free, deterministic eval for council-explorer.html.
 *
 * The page does only arithmetic over votes.json, so it's checked by re-running
 * its own JS in Node (with a tiny DOM stub) and asserting every figure it would
 * show matches an INDEPENDENT recount of votes.json. No browser, no LLM, no API
 * key, no spend — runs in well under a second.
 *
 *     node eval/test_page.js     # exits non-zero on any failure
 *
 * What it proves: given correct data (see validate_votes.py), the page computes
 * and renders correctly — the aggregations, the "Wrapped" facts, the click-to-
 * drill record counts, and that every measure x breakdown x chart renders.
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..");

const vj = JSON.parse(fs.readFileSync(path.join(ROOT, "amherst/votes.json"), "utf8"));
const html = fs.readFileSync(path.join(ROOT, "build/index.html"), "utf8");
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];

/* ---------- independent expectations, computed straight from votes.json ---------- */
const ball = vj.ballots;
const motById = {};
ball.forEach((x) => { (motById[x.motion_id] || (motById[x.motion_id] = [])).push(x); });

function expSeg(c) {
  const s = { yes: 0, no: 0, abstain: 0, absent: 0 };
  ball.forEach((x) => { if (x.councilor === c) s[x.vote]++; });
  return s;
}
const yrMot = {};
Object.values(motById).forEach((rows) => { const y = rows[0].date.slice(0, 4); yrMot[y] = (yrMot[y] || 0) + 1; });
const busiestYear = Object.entries(yrMot).sort((a, b) => b[1] - a[1])[0];

let exClosest = null;
Object.values(motById).forEach((rows) => {
  const t = rows[0].tally; if (!t) return;
  const p = t.split("-"); if (p.length < 2) return;
  const y = +p[0], n = +p[1]; if (isNaN(y) || isNaN(n) || y + n < 8) return;
  const mg = Math.abs(y - n);
  if (!exClosest || mg < exClosest.mg || (mg === exClosest.mg && y + n > exClosest.tot)) exClosest = { mg, tot: y + n, tl: t };
});

const moverCount = {};
Object.values(motById).forEach((rows) => { const m = rows[0].mover; if (m) moverCount[m] = (moverCount[m] || 0) + 1; });
const topMover = Object.entries(moverCount).sort((a, b) => b[1] - a[1])[0];

const dec2026 = Object.values(motById).filter((r) => r[0].date.startsWith("2026")).length;

var EXP = {
  schoen: expSeg("Schoen"),
  yrMot, busiestYear, exClosest, topMover, dec2026,
  schoenNo: expSeg("Schoen").no,
};
var RESULTS = [];

/* ---------- DOM stub so the page script runs headless ---------- */
const shim = `
const _els={};const _s=id=>_els[id]||(_els[id]={id,innerHTML:'',textContent:'',value:'',open:false,dataset:{},
  classList:{_c:new Set(),add(x){this._c.add(x)},remove(x){this._c.delete(x)},toggle(){},contains(x){return this._c.has(x)}},
  querySelectorAll:()=>[],querySelector:()=>_s(id+'q'),addEventListener(){},set onclick(f){},set onchange(f){},scrollIntoView(){}});
globalThis.window={};globalThis.performance={now:()=>0};globalThis.requestAnimationFrame=()=>{};
globalThis.document={getElementById:_s,querySelector:()=>_s('q'),querySelectorAll:()=>[],addEventListener(){}};
`;

/* ---------- assertions run INSIDE the page's own scope ---------- */
const tests = `
function eq(a,b){return JSON.stringify(a)===JSON.stringify(b);}
function T(name,cond){RESULTS.push([name,!!cond]);}

(function(){const a=aggregate('vote_breakdown','none','Schoen','');const s={yes:0,no:0,abstain:0,absent:0};a.rows.forEach(b=>s[b.v]++);
  T('Schoen vote breakdown matches votes.json recount',eq(s,EXP.schoen));})();

(function(){const a=aggregate('motions_count','Year','__all','');const got={};a.groups.forEach(g=>got[g.key]=g.value);
  T('motions-per-year matches recount',eq(got,EXP.yrMot));})();

(function(){const a=aggregate('motions_proposed','Councilor','__all','');const top=a.groups[0];
  T('top motion proposer matches recount',top&&top.key===EXP.topMover[0]&&top.value===EXP.topMover[1]);})();

T('all-time busiest year (Surprise) correct', busiest && busiest[0]===EXP.busiestYear[0] && busiest[1]===EXP.busiestYear[1]);
T('all-time closest vote (Surprise) correct', closest && closest.m.tl===EXP.exClosest.tl);
T('Wrapped 2026 decision count correct', YI.dec===EXP.dec2026);

(function(){const recs=recordsTable('Schoen','',{dim:'Vote',key:'no'});const rows=(recs.match(/pill no/g)||[]).length;
  T('drill-down: Schoen No records == her No count',rows===EXP.schoenNo);})();

(function(){const recs=recordsTable('__all','',{dim:'Year',key:'2021'});const trs=(recs.match(/<tr>/g)||[]).length;
  T('drill-down: 2021 returns records (capped 300)',trs>0&&trs<=301);})();

(function(){let fails=0;
  for(const [mk] of EX_MEAS){ex.measure=mk;for(const[g] of exGroups()){ex.group=g;for(const[c] of EX_VIZ){ex.chart=c;
    try{const a=aggregate(ex.measure,ex.group,'Schoen','');
      const ct=ex.chart!=='auto'?ex.chart:(a.meas.kind==='breakdown'?(ex.group==='none'?'donut':'stacked'):(ex.group==='Year'?'line':'bar'));
      let h;if(ct==='table')h=a.meas.kind==='breakdown'?rBreakdownTable(a):rScalarTable(a,'x');
      else if(a.meas.kind==='breakdown'){if(ct==='donut'){const s={yes:0,no:0,abstain:0,absent:0};a.rows.forEach(b=>s[b.v]++);h=rDonut(s);}else{let aa=a.group==='none'?aggregate('vote_breakdown','Year','Schoen',''):a;h=rStacked(aa.groups);}}
      else h=ct==='line'?rLine(a.groups,''):rBar(a.groups,'');
      if(!/<svg|class="cards"|tablewrap/.test(h))fails++;
    }catch(e){fails++;}}}}
  T('every Explore measure x breakdown x chart renders ('+fails+' fails)',fails===0);})();

(function(){let fails=0;
  for(const set of[['who_councilor','Schoen','councilor'],['who_council','__all','council']])
   for(const q of QUESTIONS[set[0]]){wz={step:4,scope:set[2],councilor:'Schoen',q:q.id,viz:q.rec,topic:''};
    const a=aggregate(q.measure,q.group,set[1],'');
    if(sentence(q,a).length<10)fails++;
    for(const v of q.viz){wz.viz=v;if(!/<svg|class="cards"|tablewrap/.test(drawViz(q,a)))fails++;}}
  T('every Guided question x visual renders with a sentence ('+fails+' fails)',fails===0);})();

T('Wrapped story has slides', Array.isArray(SLIDES) && SLIDES.length>=5);
T('Surprise has mined facts', Array.isArray(FACTS) && FACTS.length>=5);
`;

try {
  eval(shim + script + tests);
} catch (e) {
  console.error("Harness error (page script failed to run):", e.message);
  process.exit(2);
}

console.log("=".repeat(64));
console.log("council-explorer.html — page logic checks");
console.log("=".repeat(64));
let failed = 0;
RESULTS.forEach(([name, ok]) => {
  if (!ok) failed++;
  console.log(`  [${ok ? "PASS" : "FAIL"}]  ${name}`);
});
console.log("-".repeat(64));
if (failed) { console.log(`RESULT: ${failed} of ${RESULTS.length} checks FAILED`); process.exit(1); }
console.log(`RESULT: all ${RESULTS.length} checks passed ✓`);
