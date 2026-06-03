"""Interactive Dashboard Server

Flask server that:
  - Serves the Board dashboard at /
  - Provides API endpoints to trigger each pipeline phase
  - Returns live data after each run

Run: python dashboard\server.py
Open: http://localhost:5000
"""

import json
import os
import sys
import threading
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from flask import Flask, render_template_string, jsonify, request

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
EVAL_DIR = os.path.join(BASE_DIR, "evaluator")
DASH_DIR = os.path.join(BASE_DIR, "dashboard")
AGENTS_DIR = os.path.join(BASE_DIR, "multi_agent", "agents")

app = Flask(__name__)

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Apex Capital — Interactive Dashboard</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Segoe UI',system-ui,sans-serif; background:#0f172a; color:#e2e8f0; padding:24px; display:flex; }
.sidebar { width:260px; background:#1e293b; border-radius:10px; padding:18px; margin-right:20px; flex-shrink:0; border:1px solid #334155; }
.sidebar h3 { font-size:13px; color:#38bdf8; margin-bottom:16px; text-transform:uppercase; letter-spacing:1px; }
.btn { display:block; width:100%; padding:10px 14px; margin-bottom:8px; background:#334155; color:#e2e8f0; border:none; border-radius:6px; cursor:pointer; font-size:13px; text-align:left; transition:background .2s; }
.btn:hover { background:#475569; }
.btn.running { background:#1e3a5f; color:#38bdf8; }
.btn .status { float:right; font-size:11px; }
.main { flex:1; min-width:0; }
.header { display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; }
.header h1 { font-size:20px; color:#38bdf8; }
.header .badge { background:#1e293b; padding:4px 12px; border-radius:6px; font-size:11px; color:#94a3b8; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-bottom:20px; }
.card { background:#1e293b; border-radius:8px; padding:16px; border:1px solid #334155; }
.card .lbl { font-size:10px; text-transform:uppercase; color:#64748b; letter-spacing:.5px; margin-bottom:4px; }
.card .val { font-size:24px; font-weight:700; }
.card .sub { font-size:11px; color:#94a3b8; margin-top:2px; }
.g { color:#22c55e; } .y { color:#eab308; } .r { color:#ef4444; } .b { color:#38bdf8; }
table { width:100%; border-collapse:collapse; background:#1e293b; border-radius:8px; overflow:hidden; margin-bottom:20px; }
th { text-align:left; padding:8px 12px; font-size:10px; text-transform:uppercase; color:#64748b; border-bottom:1px solid #334155; }
td { padding:8px 12px; font-size:12px; border-bottom:1px solid #1e293b; }
tr:hover td { background:#263348; }
.tag { display:inline-block; padding:2px 8px; border-radius:8px; font-size:9px; font-weight:600; }
.tag-g { background:#14532d; color:#22c55e; } .tag-b { background:#1e3a5f; color:#38bdf8; }
.tag-y { background:#422006; color:#eab308; } .tag-r { background:#450a0a; color:#f87171; }
.section { font-size:12px; font-weight:600; margin:20px 0 10px; color:#94a3b8; text-transform:uppercase; letter-spacing:1px; }
.log { background:#1e293b; border-radius:8px; padding:14px; max-height:200px; overflow-y:auto; font-family:monospace; font-size:11px; border:1px solid #334155; }
.log .entry { padding:2px 0; color:#94a3b8; }
.log .entry .ts { color:#64748b; margin-right:8px; }
.log .entry .st { color:#38bdf8; margin-right:8px; }
.footer { text-align:center; color:#475569; font-size:10px; margin-top:20px; padding-top:14px; border-top:1px solid #1e293b; }
</style>
</head>
<body>
<div class="sidebar">
  <h3>Pipeline Controls</h3>
  <button class="btn" onclick="runPhase('orchestrator')">&#9654; Run Orchestrator<span class="status" id="s-orch"></span></button>
  <button class="btn" onclick="runPhase('evaluator')">&#9654; Run Evaluator<span class="status" id="s-eval"></span></button>
  <button class="btn" onclick="runPhase('improve')">&#9654; Improve Loop<span class="status" id="s-imp"></span></button>
  <button class="btn" onclick="runPhase('benchmark')">&#9654; Run Benchmark<span class="status" id="s-bench"></span></button>
  <button class="btn" onclick="refresh()" style="margin-top:16px; background:#1e3a5f;">&#8635; Refresh Data</button>
  <div class="log" id="live-log" style="margin-top:16px;">
    <div class="entry"><span class="ts">--</span><span class="st">ready</span> Waiting for input</div>
  </div>
</div>

<div class="main">
  <div class="header">
    <h1>Apex Capital — M&A Evaluation System</h1>
    <span class="badge">Interactive Board Dashboard</span>
  </div>
  <div class="grid" id="cards"></div>
  <div class="section">Ranked Target Pipeline</div>
  <table>
    <thead><tr><th>Rank</th><th>Company</th><th>Sector</th><th>Score</th><th>Financial</th><th>Risk</th><th>Strategy</th><th>Rating</th><th>Revenue</th><th>Growth</th></tr></thead>
    <tbody id="pipeline"></tbody>
  </table>
  <div class="section">Evaluator Scores</div>
  <div id="eval-info" class="card"></div>
  <div class="footer">Apex Capital Multi-Agent System &middot; powered by DeepSeek</div>
</div>

<script>
function api(path, method, body) {
  return fetch(path, { method:method||'GET', headers:{'Content-Type':'application/json'}, body:body||undefined }).then(r => r.json());
}

async function refresh() {
  const d = await api('/api/data');
  render(d);
}

function doLog(msg) {
  const log = document.getElementById('live-log');
  const now = new Date().toLocaleTimeString();
  log.innerHTML = `<div class="entry"><span class="ts">${now}</span><span class="st">info</span>${msg}</div>` + log.innerHTML;
}

async function runPhase(phase) {
  const btn = event.target;
  const sid = 's-' + phase.substring(0,4).replace('orch','orch').replace('eval','eval').replace('impr','imp').replace('benc','bench');
  const st = document.getElementById('s-'+{orchestrator:'orch',evaluator:'eval',improve:'imp',benchmark:'bench'}[phase]);
  btn.classList.add('running');
  if(st) st.textContent = '...';
  doLog(`Starting ${phase}...`);
  try {
    const r = await api(`/api/run/${phase}`, 'POST');
    if(st) st.textContent = r.ok ? '✓' : '✗';
    doLog(`${phase}: ${r.message||r.error||'done'} (${r.time||'?'}s)`);
    refresh();
  } catch(e) {
    if(st) st.textContent = '✗';
    doLog(`${phase} failed: ${e.message}`);
  }
  btn.classList.remove('running');
}

function render(d) {
  const ranked = d.multi_agent?.ranked_companies || [];
  const ma = d.multi_agent || {};
  const evals = d.evals?.iterations || [];
  const last = evals.length ? evals[evals.length-1].evaluation : null;
  const bench = d.benchmark?.timings || {};
  const top = ranked[0]||{};

  document.getElementById('cards').innerHTML = [
    ['Targets Screened', ma.passed_screening||0, 'Passed criteria', 'b'],
    ['Strong Buy', ranked.filter(c=>c.rating==='STRONG BUY').length, 'Top-tier', 'g'],
    ['Avg Score', ranked.length ? (ranked.reduce((s,c)=>s+(c.composite_score||0),0)/ranked.length).toFixed(1):0, 'Composite', 'y'],
    ['Speedup', (bench.speedup_x||'—')+'x', 'Fan-out vs seq', 'b'],
    ['Top Pick', top.name||'—', (top.rating||'')+' · '+(top.composite_score||''), 'g'],
    ['Eval', (last?.overall_score||'—')+'/10', last?.production_readiness||'', 'b'],
  ].map(([l,v,s,c])=>`<div class="card"><div class="lbl">${l}</div><div class="val ${c}">${v}</div><div class="sub">${s}</div></div>`).join('');

  document.getElementById('pipeline').innerHTML = ranked.map((c,i)=>{
    const cl = c.rating==='STRONG BUY'?'tag-g':c.rating==='BUY'?'tag-b':c.rating==='HOLD / CONSIDER'?'tag-y':'tag-r';
    return `<tr><td>${i+1}</td><td>${c.name}</td><td>${c.sector}</td><td><b>${c.composite_score||0}</b></td><td>${c.financial_score||0}</td><td>${c.risk_score||0}</td><td>${c.strategy_score||0}</td><td><span class="tag ${cl}">${c.rating||'—'}</span></td><td>${((c.revenue_2024||0)/1e6).toFixed(0)}M</td><td>${c.growth_rate||0}%</td></tr>`;
  }).join('') || '<tr><td colspan="10">No data. Run orchestrator.</td></tr>';

  if(last) {
    document.getElementById('eval-info').innerHTML = `<div class="lbl">Overall: ${last.overall_score}/10 · ${last.production_readiness||'—'}</div><div class="sub">${last.summary||''}</div>`;
    if(evals.length>1) {
      document.getElementById('eval-info').innerHTML += '<div style="margin-top:8px;">' + evals.map((e,i) => `<div style="font-size:11px; color:#94a3b8;">Iter ${i+1}: ${e.evaluation.overall_score}/10 (${e.type||'initial'})</div>`).join('') + '</div>';
    }
  } else {
    document.getElementById('eval-info').innerHTML = '<div class="lbl">No evaluation yet</div><div class="sub">Run evaluator first</div>';
  }
}

refresh();
</script>
</body>
</html>"""


def safe_load(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def gather_data():
    return {
        "multi_agent": safe_load(os.path.join(LOGS_DIR, "report_multi_agent.json")) or {},
        "single_agent": safe_load(os.path.join(LOGS_DIR, "report_single_agent.json")) or {},
        "benchmark": safe_load(os.path.join(LOGS_DIR, "run_3_fanout_benchmark.json")) or {},
        "evals": safe_load(os.path.join(EVAL_DIR, "scores.json")) or {"iterations": []},
        "improvement": safe_load(os.path.join(LOGS_DIR, "improvement_loop.json")) or {},
        "improved_agents": [a for a in ["scout","financial_analyst","risk_analyst","strategy_analyst","report_writer"]
                           if os.path.exists(os.path.join(AGENTS_DIR, a, "prompt_v1.md"))]
    }


# --- Routes ---

@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/data")
def api_data():
    return jsonify(gather_data())


@app.route("/api/run/<phase>", methods=["POST"])
def api_run(phase):
    phases = {
        "orchestrator": ("multi_agent.orchestrator", "Orchestrator", "run"),
        "evaluator": ("evaluator.evaluator", "Evaluator", "run_evaluator"),
        "improve": ("evaluator.improvement_loop", "ImprovementLoop", "run_improvement_loop"),
        "benchmark": ("multi_agent.fanout", "FanOutBenchmark", "run_benchmark"),
    }

    if phase not in phases:
        return jsonify({"ok": False, "error": f"Unknown phase: {phase}"}), 400

    module_path, class_name, method_name = phases[phase]
    t0 = time.time()

    try:
        mod = __import__(module_path, fromlist=[class_name])
        cls = getattr(mod, class_name)
        instance = cls()
        method = getattr(instance, method_name)
        result = method()
        elapsed = round(time.time() - t0, 2)
        return jsonify({"ok": True, "message": f"{phase} completed", "time": elapsed})
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        return jsonify({"ok": False, "error": str(e), "time": elapsed}), 500


if __name__ == "__main__":
    print("=" * 60)
    print("Interactive Dashboard Server")
    print("Open http://localhost:5000 in your browser")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=True)
