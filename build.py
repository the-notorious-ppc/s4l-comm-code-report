"""
S4L Comm Code Report — build the static site from data/daily.csv.gz.

    python build.py

Writes docs/index.html and docs/data.json. Point GitHub Pages at /docs.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ARCHIVE = Path("data/daily.csv.gz")
OUT_DIR = Path("docs")
UNMAPPED = "Unmapped"

# Confidence floor. S4L runs roughly a quarter of RF's Shopping spend across a
# similar number of comm codes, so most codes carry too few clicks for a
# zero-conversion result to mean anything. Derive the threshold from the
# account's own blended CVR rather than hard-coding it:
#
#   n = ln(1 - CONFIDENCE) / ln(1 - CVR)
#
# the click count at which a code performing at the account average would have
# converted at least once. At the S4L blended CVR of 1.37% this lands near 170.
CONFIDENCE = 0.90
FLOOR_WINDOW_DAYS = 365
FLOOR_MIN, FLOOR_MAX = 30, 500


def confidence_floor(df: pd.DataFrame) -> tuple[int, float]:
    recent = df[df["date"] >= sorted(df["date"].unique())[-FLOOR_WINDOW_DAYS:][0]]
    clicks, convs = recent["clicks"].sum(), recent["conversions"].sum()
    if clicks <= 0 or convs <= 0:
        return FLOOR_MAX, 0.0
    cvr = convs / clicks
    if cvr >= 1:
        return FLOOR_MIN, cvr
    n = math.log(1 - CONFIDENCE) / math.log(1 - cvr)
    return int(min(FLOOR_MAX, max(FLOOR_MIN, math.ceil(n)))), cvr


def build_payload() -> dict:
    df = pd.read_csv(ARCHIVE)
    df["date"] = df["date"].astype(str)

    dates = sorted(df["date"].unique())
    groups = sorted(df["item_group_id"].unique())
    d_ix = {d: i for i, d in enumerate(dates)}
    g_ix = {g: i for i, g in enumerate(groups)}

    floor, cvr = confidence_floor(df)
    print(f"confidence floor: {floor} clicks (blended CVR {cvr * 100:.2f}%, {CONFIDENCE:.0%} conf.)")

    df = df.sort_values(["date", "item_group_id"])
    return {
        "generated": datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC"),
        "floor": floor,
        "cvrBase": round(cvr * 100, 3),
        "dates": dates,
        "groups": groups,
        "d": [d_ix[x] for x in df["date"]],
        "g": [g_ix[x] for x in df["item_group_id"]],
        "impr": [int(x) for x in df["impressions"]],
        "clk": [int(x) for x in df["clicks"]],
        "cost": [round(float(x), 2) for x in df["cost"]],
        "conv": [round(float(x), 2) for x in df["conversions"]],
        "val": [round(float(x), 2) for x in df["conv_value"]],
    }


def main():
    if not ARCHIVE.exists():
        raise SystemExit(f"Missing {ARCHIVE}. Run pull.py first.")

    OUT_DIR.mkdir(exist_ok=True)
    payload = build_payload()

    (OUT_DIR / "data.json").write_text(
        json.dumps(payload, separators=(",", ":")), encoding="utf-8"
    )
    (OUT_DIR / "index.html").write_text(TEMPLATE, encoding="utf-8")
    (OUT_DIR / ".nojekyll").write_text("", encoding="utf-8")

    size = (OUT_DIR / "data.json").stat().st_size / 1e6
    print(f"docs/data.json  {size:.1f} MB  ({len(payload['d']):,} rows)")
    print(f"docs/index.html written")
    print(f"{len(payload['groups']):,} comm codes, {len(payload['dates']):,} days")
    print(f"latest date: {payload['dates'][-1]}")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>S4L Comm Code Performance Report</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.0/chart.umd.min.js"></script>
<style>
:root{
  --ink:#1D1D1B; --ink-soft:#33322F; --paper:#F5F6F4; --card:#FFFFFF;
  --brand:#B82026; --brand-deep:#8E1A1E; --line:#E3E6E1;
  --text:#1D1D1B; --text-dim:#6B6F68; --good:#2E8B57; --bad:#B3413A;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--paper);color:var(--text);font-family:'Inter',system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.stripe{height:3px;background:var(--brand)}
header{background:var(--ink);color:#fff;padding:24px 40px}
.header-inner{max-width:1320px;margin:0 auto;display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:20px}
.brand{display:flex;align-items:center;gap:16px}
.brand img{height:44px;display:block}
.eyebrow{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--brand);margin:0 0 5px}
h1{font-family:'Space Grotesk',sans-serif;font-size:24px;margin:0;font-weight:600}
.gen{font-size:12px;color:#9A9E97;margin-top:5px}
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
.controls label{font-size:11px;color:#9A9E97;display:block;margin-bottom:4px;font-family:'IBM Plex Mono',monospace;letter-spacing:.08em;text-transform:uppercase}
select,input[type=date],input[type=search]{font-family:inherit;font-size:13px;padding:7px 10px;border:1px solid #3A3A37;border-radius:6px;background:var(--ink-soft);color:#fff}
input[type=search]{background:var(--card);color:var(--text);border-color:var(--line)}
main{max-width:1320px;margin:0 auto;padding:26px 40px 60px}
.tiles{display:grid;grid-template-columns:repeat(9,minmax(0,1fr));gap:8px;margin-bottom:24px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:10px 11px;min-width:0}
.tile .k{font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tile .v{font-family:'Space Grotesk',sans-serif;font-size:18px;font-weight:600;margin:4px 0 1px;white-space:nowrap}
.tile .d{font-size:11px;font-weight:500}
.tile .vs{font-size:9px;color:var(--text-dim);margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@media(max-width:1180px){.tiles{grid-template-columns:repeat(5,minmax(0,1fr))}}
@media(max-width:720px){.tiles{grid-template-columns:repeat(3,minmax(0,1fr))}}
.up{color:var(--good)}.down{color:var(--bad)}.flat{color:var(--text-dim)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-bottom:22px}
.card-head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px}
.card-head h2{font-family:'Space Grotesk',sans-serif;font-size:15px;margin:0;font-weight:600}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:6px;overflow:hidden}
.seg button{font-family:inherit;font-size:12px;padding:6px 12px;border:0;background:#fff;color:var(--text-dim);cursor:pointer}
.seg button.on{background:var(--brand);color:#fff}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:right;font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--text-dim);padding:8px 10px;border-bottom:1px solid var(--line);cursor:pointer;white-space:nowrap;user-select:none}
th:first-child,td:first-child{text-align:left}
th.sorted{color:var(--brand)}
td{padding:9px 10px;border-bottom:1px solid #F0F2EF;text-align:right;font-variant-numeric:tabular-nums}
tbody tr{cursor:pointer}
tbody tr:hover{background:#F7F9F6}
.name{font-weight:500;max-width:330px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.unmapped .name{color:var(--bad)}
.thin{color:var(--text-dim);font-style:italic}
.zeroflag{color:var(--bad)}
.toggle{display:inline-flex;align-items:center;gap:7px;font-size:12px;color:var(--text-dim);cursor:pointer;user-select:none}
.toggle input{accent-color:var(--brand);width:14px;height:14px;cursor:pointer}
.bar{height:3px;background:var(--brand);border-radius:2px;margin-top:4px}
.pager{display:flex;justify-content:space-between;align-items:center;margin-top:14px;font-size:12px;color:var(--text-dim)}
.pager button,.cardhead button{font-family:inherit;font-size:12px;padding:6px 12px;border:1px solid var(--line);background:#fff;border-radius:6px;cursor:pointer}
.cardhead button:hover{border-color:var(--brand);color:var(--brand)}
.pager button:disabled{opacity:.4;cursor:default}
.modal{position:fixed;inset:0;background:rgba(29,29,27,.55);display:none;align-items:center;justify-content:center;padding:24px;z-index:50}
.modal.on{display:flex}
.modal-box{background:var(--card);border-radius:12px;padding:22px 24px;max-width:880px;width:100%;max-height:88vh;overflow:auto}
.modal-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:16px}
.modal-head h3{font-family:'Space Grotesk',sans-serif;margin:0;font-size:18px}
.x{border:0;background:none;font-size:24px;line-height:1;cursor:pointer;color:var(--text-dim)}
.note{font-size:12px;color:var(--text-dim);line-height:1.6;margin-top:22px}
.note strong{color:var(--text)}
#loading{padding:60px;text-align:center;color:var(--text-dim)}
.hide{display:none}
canvas{max-height:300px}
@media(max-width:720px){header,main{padding-left:18px;padding-right:18px}}
</style>
</head>
<body>
<div class="stripe"></div>
<header>
  <div class="header-inner">
    <div class="brand">
      <img src="logo.svg" alt="Shelters4Less">
      <div>
        <p class="eyebrow">Google Ads &middot; Shopping + PMax</p>
        <h1>Comm Code Performance Report</h1>
        <div class="gen" id="gen"></div>
      </div>
    </div>
    <div class="controls">
      <div>
        <label for="range">Date range</label>
        <select id="range">
          <option value="1">Yesterday</option>
          <option value="7">Last 7 days</option>
          <option value="14">Last 14 days</option>
          <option value="30" selected>Last 30 days</option>
          <option value="90">Last 90 days</option>
          <option value="custom">Custom</option>
        </select>
      </div>
      <div id="customWrap" class="hide">
        <label for="from">From / to</label>
        <input type="date" id="from"> <input type="date" id="to">
      </div>
      <div>
        <label for="compare">Compare to</label>
        <select id="compare">
          <option value="py" selected>Previous year</option>
          <option value="pp">Previous period</option>
          <option value="none">No comparison</option>
        </select>
      </div>
    </div>
  </div>
</header>

<main>
  <div id="loading">Loading data…</div>
  <div id="app" class="hide">
    <div class="tiles" id="tiles"></div>

    <div class="card">
      <div class="card-head">
        <h2>Trend</h2>
        <div style="display:flex;gap:10px;flex-wrap:wrap">
          <select id="metric">
            <option value="cost">Cost</option>
            <option value="val">Conv. value</option>
            <option value="roas">ROAS</option>
            <option value="clk">Clicks</option>
            <option value="conv">Conversions</option>
            <option value="impr">Product impressions</option>
          </select>
          <div class="seg" id="gran">
            <button data-g="d" class="on">Daily</button>
            <button data-g="w">Weekly</button>
            <button data-g="m">Monthly</button>
          </div>
        </div>
      </div>
      <canvas id="trend"></canvas>
    </div>

    <div class="card">
      <div class="card-head">
        <h2>Comm codes <span id="count" style="color:var(--text-dim);font-weight:400"></span></h2>
        <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
          <label class="toggle"><input type="checkbox" id="hidethin"> Hide low-data codes</label>
          <button id="export">Export CSV</button>
          <input type="search" id="search" placeholder="Filter comm codes…" style="min-width:230px">
        </div>
      </div>
      <div style="overflow-x:auto">
        <table>
          <thead><tr>
            <th data-s="name">Comm code</th>
            <th data-s="cost" class="sorted">Cost</th>
            <th data-s="share">% spend</th>
            <th data-s="val">Conv. value</th>
            <th data-s="vshare">% value</th>
            <th data-s="roas">ROAS</th>
            <th data-s="impr">Product impr.</th>
            <th data-s="clk">Clicks</th>
            <th data-s="ctr">CTR</th>
            <th data-s="cpc">CPC</th>
            <th data-s="conv">Conv.</th>
            <th data-s="cvr">CVR</th>
            <th data-s="dcost">Cost &Delta;</th>
            <th data-s="dval">Value &Delta;</th>
          </tr></thead>
          <tbody id="tbody"></tbody>
        </table>
      </div>
      <div class="pager">
        <span id="pageinfo"></span>
        <span><button id="prev">Prev</button> <button id="next">Next</button></span>
      </div>
    </div>

    <p class="note">
      <strong>Product impressions</strong> are counted once per product shown in an ad, so an ad
      displaying several products records several impressions. This total will exceed campaign-level
      impressions, and CTR here is correspondingly lower than campaign CTR. Clicks, cost, conversions
      and conversion value are unaffected.<br>
      <strong>% spend</strong> and <strong>% value</strong> are shares of the product-level totals, not of
      total account spend or revenue. Performance Max activity on placements without a product attached is
      not included.<br>
      <strong>Unmapped</strong> covers item IDs absent from the comm code lookup plus those marked Uncoded.<br>
      <strong>Insufficient</strong> in the ROAS column means a code has no conversions <em>and</em> too few clicks
      for that to mean anything; the floor is derived from the account's own blended CVR. A red <strong>0.00x</strong>
      has cleared the floor and still not converted — that one is real. Sorting by ROAS files insufficient codes last.<br>
      Conversions are <strong>Purchase</strong> only, so every ROAS here is a floor on true performance.<br>
      <strong>Export CSV</strong> writes the current range, filter and sort — all rows, not just the page.<br>
      Conversion values are subject to attribution lag and the most recent days will rise slightly.
    </p>
  </div>
</main>

<div class="modal" id="modal">
  <div class="modal-box">
    <div class="modal-head">
      <div><h3 id="mtitle"></h3><div id="msub" style="font-size:12px;color:var(--text-dim);margin-top:4px"></div></div>
      <button class="x" id="mclose">&times;</button>
    </div>
    <canvas id="mchart"></canvas>
  </div>
</div>

<script>
const F = {
  gbp: n => '£' + n.toLocaleString('en-GB', {minimumFractionDigits:0, maximumFractionDigits:0}),
  gbp2: n => '£' + n.toLocaleString('en-GB', {minimumFractionDigits:2, maximumFractionDigits:2}),
  num: n => Math.round(n).toLocaleString('en-GB'),
  pct: n => n.toFixed(2) + '%',
  x: n => n.toFixed(2) + 'x'
};
let D, byDate = [], state = {page:1, sort:'cost', dir:-1, gran:'d', q:'', hidethin:false};
let trendChart, modalChart;

fetch('data.json').then(r => r.json()).then(d => {
  D = d;
  document.getElementById('gen').textContent =
    'Generated ' + d.generated + ' · data to ' + fmtD(d.dates[d.dates.length-1]);
  // index rows by date for fast range slicing
  byDate = D.dates.map(() => []);
  for (let i = 0; i < D.d.length; i++) byDate[D.d[i]].push(i);
  const last = D.dates[D.dates.length-1];
  document.getElementById('to').value = last;
  document.getElementById('from').value = D.dates[Math.max(0, D.dates.length-30)];
  document.getElementById('loading').classList.add('hide');
  document.getElementById('app').classList.remove('hide');
  render();
});

function fmtD(s){ const [y,m,dd]=s.split('-'); return dd+'/'+m+'/'+y; }
function dIdx(s){ return D.dates.indexOf(s); }

function rangeIdx(){
  const r = document.getElementById('range').value;
  const n = D.dates.length;
  if (r === 'custom'){
    let a = dIdx(document.getElementById('from').value);
    let b = dIdx(document.getElementById('to').value);
    if (a < 0) a = 0; if (b < 0) b = n-1;
    return [Math.min(a,b), Math.max(a,b)];
  }
  const days = parseInt(r,10);
  return [Math.max(0, n-days), n-1];
}

function compareIdx(a, b){
  const mode = document.getElementById('compare').value;
  if (mode === 'none') return null;
  if (mode === 'pp'){ const len = b-a+1; return a-len < 0 ? null : [a-len, a-1]; }
  // previous year: shift by 364 days to keep weekday alignment
  const s = a-364, e = b-364;
  return s < 0 ? null : [s, e];
}

function agg(a, b){
  const g = {}, t = {impr:0,clk:0,cost:0,conv:0,val:0};
  for (let di = a; di <= b; di++){
    for (const i of byDate[di]){
      const k = D.g[i];
      const o = g[k] || (g[k] = {impr:0,clk:0,cost:0,conv:0,val:0});
      o.impr += D.impr[i]; o.clk += D.clk[i]; o.cost += D.cost[i];
      o.conv += D.conv[i]; o.val += D.val[i];
      t.impr += D.impr[i]; t.clk += D.clk[i]; t.cost += D.cost[i];
      t.conv += D.conv[i]; t.val += D.val[i];
    }
  }
  return {g, t};
}

function derive(o){
  // conv — converted, ROAS is real | zero — past the floor, a genuine zero
  // thin — under the floor, not enough data to judge
  const q = o.conv > 0 ? 'conv' : (o.clk >= D.floor ? 'zero' : 'thin');
  return {
    ...o,
    q,
    roas: o.cost ? o.val/o.cost : 0,
    ctr: o.impr ? o.clk/o.impr*100 : 0,
    cpc: o.clk ? o.cost/o.clk : 0,
    cvr: o.clk ? o.conv/o.clk*100 : 0
  };
}

function roasKey(r){ return r.q === 'thin' ? null : r.roas; }

function roasCell(r){
  if (r.q === 'conv') return F.x(r.roas);
  if (r.q === 'zero') return `<span class="zeroflag" title="${F.num(r.clk)} clicks, no conversions — past the ${D.floor}-click floor">0.00x</span>`;
  return `<span class="thin" title="${F.num(r.clk)} clicks, below the ${D.floor}-click floor — not enough data to judge">insufficient</span>`;
}

function delta(cur, prev){
  if (prev === null || prev === undefined) return null;
  if (!prev) return cur ? 1 : 0;
  return (cur-prev)/prev;
}

function dEl(v, invert){
  if (v === null) return '<span class="d flat">—</span>';
  const good = invert ? v < 0 : v > 0;
  const cls = Math.abs(v) < 0.0005 ? 'flat' : (good ? 'up' : 'down');
  const sign = v > 0 ? '+' : '';
  return `<span class="d ${cls}">${sign}${(v*100).toFixed(1)}%</span>`;
}

function render(){
  const [a,b] = rangeIdx();
  const cmp = compareIdx(a,b);
  const cur = agg(a,b);
  const prev = cmp ? agg(cmp[0], cmp[1]) : null;
  window._cur = cur; window._prev = prev; window._range = [a,b];

  renderTiles(derive(cur.t), prev ? derive(prev.t) : null, [a,b], cmp);
  renderTrend(a,b);
  state.page = 1;
  renderTable();
}

function renderTiles(c, p, r, cmp){
  const sub = cmp ? `${fmtD(D.dates[cmp[0]])} – ${fmtD(D.dates[cmp[1]])}` : '';
  const defs = [
    ['Cost', F.gbp(c.cost), delta(c.cost, p&&p.cost), true],
    ['Conv. value', F.gbp(c.val), delta(c.val, p&&p.val), false],
    ['ROAS', F.x(c.roas), delta(c.roas, p&&p.roas), false],
    ['Conversions', F.num(c.conv), delta(c.conv, p&&p.conv), false],
    ['Clicks', F.num(c.clk), delta(c.clk, p&&p.clk), false],
    ['CPC', F.gbp2(c.cpc), delta(c.cpc, p&&p.cpc), true],
    ['Prod. impr.', F.num(c.impr), delta(c.impr, p&&p.impr), false],
    ['CTR', F.pct(c.ctr), delta(c.ctr, p&&p.ctr), false],
    ['CVR', F.pct(c.cvr), delta(c.cvr, p&&p.cvr), false]
  ];
  document.getElementById('tiles').innerHTML = defs.map(([k,v,d,inv]) =>
    `<div class="tile"><div class="k">${k}</div><div class="v">${v}</div>${dEl(d,inv)}
     ${sub && d!==null ? `<div class="vs">vs ${sub}</div>` : ''}</div>`
  ).join('');
}

function bucket(di){
  const s = D.dates[di];
  if (state.gran === 'd') return s;
  if (state.gran === 'm') return s.slice(0,7);
  const dt = new Date(s+'T00:00:00Z');
  dt.setUTCDate(dt.getUTCDate() - ((dt.getUTCDay()+6)%7));
  return dt.toISOString().slice(0,10);
}

function series(a, b, keys, keyOf){
  const map = {};
  for (const k of keys) map[k] = {cost:0,val:0,clk:0,conv:0,impr:0};
  for (let di=a; di<=b; di++){
    const k = keyOf(di);
    if (!(k in map)) continue;
    for (const i of byDate[di]){
      map[k].cost += D.cost[i]; map[k].val += D.val[i]; map[k].clk += D.clk[i];
      map[k].conv += D.conv[i]; map[k].impr += D.impr[i];
    }
  }
  return map;
}

function renderTrend(a,b){
  const m = document.getElementById('metric').value;
  const label = document.getElementById('metric').selectedOptions[0].text;
  const pick = o => m === 'roas' ? (o.cost ? o.val/o.cost : 0) : o[m];

  const keys = [];
  for (let di=a; di<=b; di++){ const k = bucket(di); if (!keys.includes(k)) keys.push(k); }
  const cur = series(a, b, keys, bucket);

  const datasets = [{
    label, data: keys.map(k => pick(cur[k])), borderColor:'#B82026',
    backgroundColor:'rgba(184,32,38,.10)', fill:true, tension:.25,
    pointRadius:0, borderWidth:2, order:1
  }];

  // comparison line, aligned position-for-position with the current period
  const cmp = compareIdx(a,b);
  if (cmp){
    const offset = a - cmp[0];
    const prev = series(cmp[0], cmp[1], keys, di => bucket(di + offset));
    const mode = document.getElementById('compare').value;
    datasets.push({
      label: mode === 'py' ? 'Previous year' : 'Previous period',
      data: keys.map(k => pick(prev[k])), borderColor:'#9A9E97',
      borderDash:[5,4], fill:false, tension:.25,
      pointRadius:0, borderWidth:1.5, order:2
    });
  }

  if (trendChart) trendChart.destroy();
  trendChart = new Chart(document.getElementById('trend'), {
    type: 'line',
    data: {labels: keys.map(k => k.length===7 ? k : fmtD(k)), datasets},
    options:{responsive:true, maintainAspectRatio:false,
      interaction:{mode:'index', intersect:false},
      plugins:{legend:{display: datasets.length > 1, position:'bottom',
        labels:{boxWidth:22, boxHeight:2, font:{size:11}, usePointStyle:false}}},
      scales:{x:{grid:{display:false},ticks:{maxTicksLimit:12,font:{size:10}}},
              y:{beginAtZero:true,ticks:{font:{size:10}}}}}
  });
}

function rows(){
  const cur = window._cur, prev = window._prev;
  const out = [];
  for (const k in cur.g){
    const name = D.groups[k];
    if (state.q && !name.toLowerCase().includes(state.q)) continue;
    const c = derive(cur.g[k]);
    if (state.hidethin && c.q === 'thin') continue;
    const p = prev && prev.g[k] ? prev.g[k] : null;
    out.push({k:+k, name, ...c,
      share: cur.t.cost ? c.cost/cur.t.cost*100 : 0,
      vshare: cur.t.val ? c.val/cur.t.val*100 : 0,
      dcost: delta(c.cost, p&&p.cost), dval: delta(c.val, p&&p.val)});
  }
  const s = state.sort, dir = state.dir;
  out.sort((x,y) => {
    if (s === 'name') return dir * x.name.localeCompare(y.name);
    if (s === 'roas'){
      const a = roasKey(x), b = roasKey(y);      // thin rows have no ROAS to sort
      if (a === null && b === null) return y.cost - x.cost;
      if (a === null) return 1;
      if (b === null) return -1;
      return dir * (a - b);
    }
    return dir * (((x[s]??-Infinity) - (y[s]??-Infinity)) || 0);
  });
  return out;
}

// Exports the current date range, filter and sort — every row, not just the
// visible page. The quality state travels as its own column and ROAS is left
// empty for thin rows: a zero in a spreadsheet is indistinguishable from a
// measured zero, and the tooltip that explains the difference does not survive.
function csvCell(v){
  const t = String(v ?? '');
  return /[",\n]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
}

function exportCSV(){
  const [a, b] = window._range;
  const from = D.dates[a], to = D.dates[b];
  const cmp = compareIdx(a, b);
  const all = rows();
  const qLabel = {
    conv: 'Converted',
    zero: `No conversions (past ${D.floor}-click floor)`,
    thin: `Insufficient data (under ${D.floor} clicks)`
  };

  const head = ['Comm code','Cost','% of cost','Conv. value','% of value','ROAS','Data quality',
                'Prod. impressions','Clicks','CTR %','CPC','Conversions','CVR %'];
  if (cmp) head.push('Cost change %','Value change %');

  const lines = [head.map(csvCell).join(',')];
  for (const r of all){
    const row = [r.name, r.cost.toFixed(2), r.share.toFixed(2), r.val.toFixed(2), r.vshare.toFixed(2),
      r.q === 'thin' ? '' : r.roas.toFixed(4), qLabel[r.q],
      Math.round(r.impr), Math.round(r.clk), r.ctr.toFixed(4), r.cpc.toFixed(2),
      r.conv.toFixed(2), r.cvr.toFixed(4)];
    if (cmp) row.push(r.dcost === null ? '' : (r.dcost*100).toFixed(2),
                      r.dval  === null ? '' : (r.dval *100).toFixed(2));
    lines.push(row.map(csvCell).join(','));
  }

  // BOM so Excel reads UTF-8 and renders £ correctly; CRLF for Excel line endings
  const blob = new Blob(['\ufeff' + lines.join('\r\n')], {type:'text/csv;charset=utf-8;'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `s4l-comm-codes_${from}_to_${to}.csv`;
  document.body.appendChild(link); link.click(); document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function renderTable(){
  const all = rows(), per = 25;
  const pages = Math.max(1, Math.ceil(all.length/per));
  state.page = Math.min(state.page, pages);
  const page = all.slice((state.page-1)*per, state.page*per);
  const max = all.length ? Math.max(...all.map(r => r.cost)) : 1;

  document.getElementById('count').textContent = `(${all.length})`;
  document.getElementById('tbody').innerHTML = page.map(r => `
    <tr data-k="${r.k}" class="${r.name === 'Unmapped' ? 'unmapped ' : ''}${r.q === 'thin' ? 'lowdata' : ''}">
      <td><div class="name">${r.name}</div><div class="bar" style="width:${Math.max(2, r.cost/max*100)}%"></div></td>
      <td>${F.gbp(r.cost)}</td><td>${r.share.toFixed(1)}%</td>
      <td>${F.gbp(r.val)}</td><td>${r.vshare.toFixed(1)}%</td><td>${roasCell(r)}</td>
      <td>${F.num(r.impr)}</td><td>${F.num(r.clk)}</td>
      <td>${F.pct(r.ctr)}</td><td>${F.gbp2(r.cpc)}</td>
      <td>${r.conv.toFixed(1)}</td><td>${F.pct(r.cvr)}</td>
      <td>${dEl(r.dcost, true)}</td><td>${dEl(r.dval, false)}</td>
    </tr>`).join('');

  const thin = all.filter(r => r.q === 'thin').length;
  document.getElementById('pageinfo').textContent =
    `Page ${state.page} of ${pages} · ${all.length} comm codes` +
    (state.hidethin ? ' · low-data hidden' : (thin ? ` · ${thin} below the floor` : ''));
  document.getElementById('prev').disabled = state.page <= 1;
  document.getElementById('next').disabled = state.page >= pages;
  document.querySelectorAll('th').forEach(th =>
    th.classList.toggle('sorted', th.dataset.s === state.sort));
  document.querySelectorAll('#tbody tr').forEach(tr =>
    tr.onclick = () => openModal(+tr.dataset.k));
}

function openModal(k){
  const [a,b] = window._range;
  const keys = [], map = {};
  for (let di=a; di<=b; di++){
    const kk = bucket(di);
    if (!(kk in map)){ map[kk] = {cost:0,val:0}; keys.push(kk); }
    for (const i of byDate[di]) if (D.g[i] === k){ map[kk].cost += D.cost[i]; map[kk].val += D.val[i]; }
  }
  const c = derive(window._cur.g[k]);
  document.getElementById('mtitle').textContent = D.groups[k];
  const roasTxt = c.q === 'thin' ? `ROAS not measurable (under ${D.floor} clicks)` : `${F.x(c.roas)} ROAS`;
  document.getElementById('msub').textContent =
    `${F.gbp(c.cost)} cost · ${F.gbp(c.val)} value · ${roasTxt} · ${F.num(c.clk)} clicks`;
  if (modalChart) modalChart.destroy();
  modalChart = new Chart(document.getElementById('mchart'), {
    type:'line',
    data:{labels: keys.map(x => x.length===7 ? x : fmtD(x)), datasets:[
      {label:'Cost', data: keys.map(x=>map[x].cost), borderColor:'#1D1D1B',
       fill:false, tension:.25, pointRadius:0, borderWidth:2},
      {label:'Conv. value', data: keys.map(x=>map[x].val), borderColor:'#B82026',
       backgroundColor:'rgba(184,32,38,.10)', fill:true, tension:.25,
       pointRadius:0, borderWidth:2}]},
    options:{responsive:true, maintainAspectRatio:false,
      interaction:{mode:'index', intersect:false},
      plugins:{legend:{position:'bottom', labels:{boxWidth:22, boxHeight:2, font:{size:11}}}},
      scales:{x:{grid:{display:false},ticks:{maxTicksLimit:12,font:{size:10}}},
              y:{beginAtZero:true,ticks:{font:{size:10}}}}}
  });
  document.getElementById('modal').classList.add('on');
}

document.getElementById('mclose').onclick = () => document.getElementById('modal').classList.remove('on');
document.getElementById('modal').onclick = e => { if (e.target.id === 'modal') e.currentTarget.classList.remove('on'); };
document.getElementById('range').onchange = e => {
  document.getElementById('customWrap').classList.toggle('hide', e.target.value !== 'custom');
  render();
};
['from','to','compare'].forEach(id => document.getElementById(id).onchange = render);
document.getElementById('metric').onchange = () => renderTrend(...window._range);
document.getElementById('gran').onclick = e => {
  if (e.target.tagName !== 'BUTTON') return;
  state.gran = e.target.dataset.g;
  document.querySelectorAll('#gran button').forEach(b => b.classList.toggle('on', b === e.target));
  renderTrend(...window._range);
};
document.getElementById('search').oninput = e => { state.q = e.target.value.toLowerCase().trim(); state.page = 1; renderTable(); };
document.getElementById('hidethin').onchange = e => { state.hidethin = e.target.checked; state.page = 1; renderTable(); };
document.getElementById('export').onclick = exportCSV;
document.getElementById('prev').onclick = () => { state.page--; renderTable(); };
document.getElementById('next').onclick = () => { state.page++; renderTable(); };
document.querySelectorAll('th').forEach(th => th.onclick = () => {
  const s = th.dataset.s;
  state.dir = state.sort === s ? -state.dir : (s === 'name' ? 1 : -1);
  state.sort = s; state.page = 1; renderTable();
});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
