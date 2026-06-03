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
<title>Apex Capital — M&A Intelligence Platform</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0b1120; --surface: #111827; --border: #1e293b; --text: #e2e8f0;
  --muted: #64748b; --accent: #3b82f6; --green: #22c55e; --amber: #f59e0b;
  --red: #ef4444; --cyan: #06b6d4; --purple: #8b5cf6;
  --radius: 10px; --shadow: 0 1px 3px rgba(0,0,0,.3);
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Inter',system-ui,sans-serif; background:var(--bg); color:var(--text); padding:28px; min-height:100vh; }
.app { display:flex; gap:24px; max-width:1480px; margin:0 auto; }
.sidebar { width:280px; flex-shrink:0; }
.sidebar-inner { background:var(--surface); border-radius:var(--radius); border:1px solid var(--border); padding:20px; position:sticky; top:28px; box-shadow:var(--shadow); }
.sidebar-inner h3 { font-size:11px; text-transform:uppercase; letter-spacing:1.2px; color:var(--accent); margin-bottom:18px; }
.pipeline-btn { display:block; width:100%; padding:10px 14px; margin-bottom:7px; background:var(--border); color:var(--text); border:1px solid transparent; border-radius:6px; cursor:pointer; font-size:12.5px; font-family:inherit; font-weight:500; text-align:left; transition:all .15s; position:relative; }
.pipeline-btn:hover { background:#334155; border-color:#475569; }
.pipeline-btn .icon { margin-right:6px; font-size:10px; }
.pipeline-btn .status-dot { position:absolute; right:12px; top:50%; transform:translateY(-50%); width:8px; height:8px; border-radius:50%; }
.status-dot.idle { background:#475569; } .status-dot.running { background:var(--accent); animation:pulse .8s infinite; } .status-dot.done { background:var(--green); } .status-dot.error { background:var(--red); }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.4; } }
.btn-action { display:block; width:100%; padding:12px; margin-top:14px; background:var(--accent); color:#fff; border:none; border-radius:6px; cursor:pointer; font-size:13px; font-family:inherit; font-weight:600; transition:background .15s; }
.btn-action:hover { background:#2563eb; }
.live-log { margin-top:18px; background:#0f172a; border-radius:6px; padding:12px; max-height:160px; overflow-y:auto; font-family:'Cascadia Code',monospace; font-size:10.5px; border:1px solid var(--border); }
.live-log .entry { padding:2px 0; color:var(--muted); border-bottom:1px solid rgba(30,41,59,.5); }
.live-log .entry .ts { color:#475569; margin-right:6px; }
.live-log .entry .phase { color:var(--accent); font-weight:600; margin-right:6px; }
.content { flex:1; min-width:0; }
.topbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; }
.topbar h1 { font-size:22px; font-weight:700; background:linear-gradient(135deg,var(--accent),var(--cyan)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.topbar .badge { font-size:11px; color:var(--muted); background:var(--surface); padding:5px 14px; border-radius:20px; border:1px solid var(--border); }
.kpi-grid { display:grid; grid-template-columns:repeat(6,1fr); gap:12px; margin-bottom:24px; }
.kpi-card { background:var(--surface); border-radius:var(--radius); padding:18px; border:1px solid var(--border); box-shadow:var(--shadow); transition:border-color .15s; }
.kpi-card:hover { border-color:#334155; }
.kpi-card .kpi-icon { font-size:14px; margin-bottom:6px; }
.kpi-card .kpi-label { font-size:10px; text-transform:uppercase; letter-spacing:.8px; color:var(--muted); margin-bottom:4px; }
.kpi-card .kpi-value { font-size:26px; font-weight:700; line-height:1; margin-bottom:2px; }
.kpi-card .kpi-sub { font-size:11px; color:var(--muted); }
.section-header { display:flex; justify-content:space-between; align-items:center; margin:28px 0 14px; }
.section-header h2 { font-size:13px; text-transform:uppercase; letter-spacing:1px; color:var(--muted); }
.panel { background:var(--surface); border-radius:var(--radius); border:1px solid var(--border); box-shadow:var(--shadow); overflow:hidden; margin-bottom:20px; }
table { width:100%; border-collapse:collapse; }
th { text-align:left; padding:10px 16px; font-size:10px; text-transform:uppercase; letter-spacing:.8px; color:var(--muted); border-bottom:1px solid var(--border); background:#0f172a; }
td { padding:10px 16px; font-size:12.5px; border-bottom:1px solid #1e293b; }
tr:hover td { background:rgba(59,130,246,.04); }
tr.expanded td { background:rgba(59,130,246,.06); }
.score-pill { display:inline-block; padding:3px 8px; border-radius:4px; font-weight:600; font-size:11px; min-width:40px; text-align:center; }
.score-high { background:rgba(34,197,94,.15); color:var(--green); }
.score-good { background:rgba(59,130,246,.15); color:var(--accent); }
.score-mid { background:rgba(245,158,11,.15); color:var(--amber); }
.score-low { background:rgba(239,68,68,.15); color:var(--red); }
.rating-tag { display:inline-block; padding:2px 10px; border-radius:12px; font-size:10px; font-weight:700; letter-spacing:.3px; }
.rating-strong { background:rgba(34,197,94,.2); color:var(--green); }
.rating-buy { background:rgba(59,130,246,.2); color:var(--accent); }
.rating-hold { background:rgba(245,158,11,.2); color:var(--amber); }
.rating-weak { background:rgba(239,68,68,.2); color:var(--red); }
.mini-bar { height:4px; border-radius:2px; margin-top:3px; }
.expand-btn { cursor:pointer; background:none; border:none; color:var(--accent); font-size:14px; padding:2px 8px; }
.company-detail { padding:16px 20px; border-bottom:1px solid var(--border); font-size:12px; display:none; }
.company-detail.open { display:block; }
.detail-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }
.detail-col { }
.detail-col h4 { font-size:10px; text-transform:uppercase; color:var(--muted); margin-bottom:6px; letter-spacing:.5px; }
.detail-item { padding:3px 0; font-size:11.5px; }
.detail-item .key { color:var(--muted); } .detail-item .val { color:var(--text); margin-left:4px; }
.risk-chip { display:inline-block; padding:2px 8px; border-radius:4px; margin:2px; font-size:10px; }
.risk-red { background:rgba(239,68,68,.15); color:var(--red); }
.risk-amber { background:rgba(245,158,11,.15); color:var(--amber); }
.risk-blue { background:rgba(59,130,246,.15); color:var(--accent); }
.split2 { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.eval-bar { margin-bottom:10px; }
.eval-bar .elabel { display:flex; justify-content:space-between; font-size:11px; margin-bottom:3px; }
.eval-bar .elabel span:first-child { color:var(--muted); }
.eval-bar .etrack { height:6px; background:var(--border); border-radius:3px; overflow:hidden; }
.eval-bar .efill { height:100%; border-radius:3px; transition:width .4s; }
.score-history { margin-top:14px; }
.score-history h4 { font-size:10px; text-transform:uppercase; color:var(--muted); margin-bottom:6px; }
.history-row { display:flex; align-items:center; gap:10px; padding:5px 0; font-size:11px; }
.history-row .iter { color:var(--muted); width:60px; }
.history-row .hscore { font-weight:700; width:45px; }
.history-row .hbar { flex:1; height:4px; background:var(--border); border-radius:2px; overflow:hidden; }
.history-row .hbar-fill { height:100%; border-radius:2px; }
.improvement-box { padding:14px; }
.improvement-box .delta-positive { color:var(--green); font-size:24px; font-weight:700; }
.improvement-box .delta-negative { color:var(--red); font-size:24px; font-weight:700; }
.improvement-box .agent-list { margin-top:8px; font-size:11px; color:var(--muted); }
.empty-state { text-align:center; padding:40px; color:var(--muted); }
.empty-state .empty-icon { font-size:32px; margin-bottom:10px; }
.empty-state p { font-size:12px; }
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="sidebar-inner">
      <h3>Pipeline Controls</h3>
      <button class="pipeline-btn" onclick="run('orchestrator')"><span class="status-dot idle"></span> Orchestrator</button>
      <button class="pipeline-btn" onclick="run('evaluator')"><span class="status-dot idle"></span> Evaluator</button>
      <button class="pipeline-btn" onclick="run('improve')"><span class="status-dot idle"></span> Improvement Loop</button>
      <button class="pipeline-btn" onclick="run('benchmark')"><span class="status-dot idle"></span> Benchmark</button>
      <button class="btn-action" onclick="refresh()">Refresh Data</button>
      <div class="live-log" id="log"></div>
    </div>
  </aside>
  <main class="content">
    <div class="topbar">
      <h1>Apex Capital — M&A Intelligence Platform</h1>
      <span class="badge">Board of Directors</span>
    </div>
    <div class="kpi-grid" id="cards"></div>

    <div class="section-header"><h2>Target Pipeline</h2><span style="font-size:11px;color:var(--muted);" id="pipeline-count"></span></div>
    <div class="panel"><table><thead><tr><th></th><th>Rank</th><th>Company</th><th>Sector</th><th style="width:100px">Score</th><th>Fin</th><th>Risk</th><th>Strat</th><th>Rating</th><th>Rev</th><th>Growth</th></tr></thead><tbody id="pipeline"></tbody></table></div>

    <div class="section-header"><h2>Analysis</h2></div>
    <div class="split2">
      <div class="panel" style="padding:18px;" id="evaluator-panel"><div class="empty-state"><div class="empty-icon">📊</div><p>Run Evaluator to see scores</p></div></div>
      <div class="panel" style="padding:18px;" id="improvement-panel"><div class="empty-state"><div class="empty-icon">🔄</div><p>Run Improvement Loop to see delta</p></div></div>
    </div>

    <div class="section-header"><h2>Performance</h2></div>
    <div class="panel" style="padding:18px;" id="bench-panel"><div class="empty-state"><div class="empty-icon">⚡</div><p>Run Benchmark to see speedup</p></div></div>
  </main>
</div>

<script>
function $(id){return document.getElementById(id);}
function api(p,m,b){return fetch(p,{method:m||'GET',headers:{'Content-Type':'application/json'},body:b}).then(r=>r.json());}
function log(msg,phase){var l=$('log');var t=new Date().toLocaleTimeString();l.innerHTML=`<div class="entry"><span class="ts">${t}</span><span class="phase">${phase||'sys'}</span>${msg}</div>`+l.innerHTML;}

async function refresh(){
  var d=await api('/api/data');
  var r=d.multi_agent?.ranked_companies||[];
  var ma=d.multi_agent||{};
  var evals=d.evals?.iterations||[];
  var last=evals.length?evals[evals.length-1].evaluation:null;
  var bench=d.benchmark?.timings||{};
  var top=r[0]||{};
  var strong=r.filter(c=>c.rating==='STRONG BUY').length;
  var avg=r.length?(r.reduce((s,c)=>s+(c.composite_score||0),0)/r.length).toFixed(1):0;

  // KPI cards
  $('cards').innerHTML=[
    ['🎯','Targets Screened',ma.passed_screening||'—','Passed criteria','b'],
    ['⭐','Strong Buy',strong,'Top recommendations','g'],
    ['📈','Avg Score',avg,'Composite score','y'],
    ['⚡','Speedup',(bench.speedup_x||'—')+'x','Fan-out vs sequential','c'],
    ['🏆','Top Pick',top.name||'—',(top.rating||'')+' · '+(top.composite_score||''),'g'],
    ['🔍','Eval',last?last.overall_score+'/10':'—',last?last.production_readiness||'':'Run evaluator','p'],
  ].map(([ico,l,v,s,col])=>{
    var cl='kpi-value';if(col=='g')cl+=' g';else if(col=='y')cl+=' y';else if(col=='r')cl+=' r';else if(col=='b')cl+=' b';else if(col=='c')cl+=' cyan';else if(col=='p')cl+=' purple';
    return `<div class="kpi-card"><div class="kpi-icon">${ico}</div><div class="kpi-label">${l}</div><div class="${cl}" style="${col=='c'?'color:var(--cyan)':col=='p'?'color:var(--purple)':''}">${v}</div><div class="kpi-sub">${s}</div></div>`;
  }).join('');

  $('pipeline-count').textContent=r.length+' targets ranked';

  // Pipeline
  $('pipeline').innerHTML=r.map((c,i)=>{
    var sc=c.composite_score||0;
    var scl=sc>=85?'score-high':sc>=72?'score-good':sc>=55?'score-mid':'score-low';
    var rcl=c.rating==='STRONG BUY'?'rating-strong':c.rating==='BUY'?'rating-buy':c.rating==='HOLD / CONSIDER'?'rating-hold':'rating-weak';
    return `<tr onclick="toggleDetail('d${i}')" style="cursor:pointer">
      <td><button class="expand-btn" id="btn-d${i}">+</button></td>
      <td>${i+1}</td><td><b>${c.name}</b></td><td>${c.sector}</td>
      <td><span class="score-pill ${scl}">${sc}</span><div class="mini-bar" style="background:${sc>=85?'var(--green)':sc>=72?'var(--accent)':sc>=55?'var(--amber)':'var(--red)'};width:${sc}%"></div></td>
      <td>${c.financial_score||'—'}</td><td>${c.risk_score||'—'}</td><td>${c.strategy_score||'—'}</td>
      <td><span class="rating-tag ${rcl}">${c.rating||'—'}</span></td>
      <td>$${((c.revenue_2024||0)/1e6).toFixed(1)}M</td><td>${c.growth_rate||0}%</td>
    </tr>
    <tr id="d${i}" class="company-detail"><td colspan="11">
      <div class="detail-grid">
        <div class="detail-col"><h4>Risk Flags</h4>${(c.risk_flags||[]).map(f=>`<div class="risk-chip risk-red">${f}</div>`).join('')||'<div class="detail-item">No flags</div>'}</div>
        <div class="detail-col"><h4>Financials</h4><div class="detail-item"><span class="key">Score:</span><span class="val">${c.financial_score||'—'}</span></div><div class="detail-item"><span class="key">Revenue:</span><span class="val">$${((c.revenue_2024||0)/1e6).toFixed(1)}M</span></div><div class="detail-item"><span class="key">Growth:</span><span class="val">${c.growth_rate||0}%</span></div></div>
        <div class="detail-col"><h4>Valuation</h4><div class="detail-item"><span class="key">Valuation:</span><span class="val">$${((c.valuation||0)/1e6).toFixed(1)}M</span></div><div class="detail-item"><span class="key">Risk Score:</span><span class="val">${c.risk_score||'—'}</span></div><div class="detail-item"><span class="key">Strategy:</span><span class="val">${c.strategy_score||'—'}</span></div></div>
      </div>
    </td></tr>`;
  }).join('')||'<tr><td colspan="11" class="empty-state"><p>No data. Click Orchestrator to run.</p></td></tr>';

  // Evaluator panel
  if(last){
    var dims=[['Architecture',(last.architecture_design||{}).score||0],['Prompt Quality',(last.prompt_quality||{}).score||0],['Output Quality',(last.output_quality||{}).score||0],['Scalability',(last.scalability||{}).score||0]];
    $('evaluator-panel').innerHTML='<h3 style="font-size:14px;margin-bottom:14px;">Evaluator Breakdown</h3>'+dims.map(([n,s])=>{
      var col=s>=8?'var(--green)':s>=6?'var(--amber)':'var(--red)';
      return `<div class="eval-bar"><div class="elabel"><span>${n}</span><span style="font-weight:700;color:${col}">${s}/10</span></div><div class="etrack"><div class="efill" style="width:${s*10}%;background:${col}"></div></div></div>`;
    }).join('')+'<div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--border);font-size:13px;"><b>Overall: '+last.overall_score+'/10</b> · '+last.production_readiness+'</div><div style="font-size:11px;color:var(--muted);margin-top:4px;">'+(last.summary||'')+'</div>';
    if(evals.length>1){
      $('evaluator-panel').innerHTML+='<div class="score-history"><h4>Score History</h4>'+evals.map((e,i)=>{
        var sc=e.evaluation.overall_score||0;
        var col=sc>=8?'var(--green)':sc>=6?'var(--amber)':'var(--red)';
        return `<div class="history-row"><span class="iter">Iter ${i+1}</span><span class="hscore" style="color:${col}">${sc}/10</span><div class="hbar"><div class="hbar-fill" style="width:${sc*10}%;background:${col}"></div></div></div>`;
      }).join('')+'</div>';
    }
  }

  // Improvement panel
  var imp=d.improvement||{};
  if(imp.before_score){
    var old=parseFloat(imp.before_score)||0,now=parseFloat(imp.after_score)||0,dl=now-old;
    $('improvement-panel').innerHTML='<div class="improvement-box"><h3 style="font-size:14px;margin-bottom:14px;">Improvement Loop</h3><div style="display:flex;align-items:center;gap:20px;"><div><div style="font-size:10px;text-transform:uppercase;color:var(--muted);">Before</div><div style="font-size:20px;font-weight:700;">'+imp.before_score+'/10</div></div><div style="font-size:20px;color:var(--muted);">→</div><div><div style="font-size:10px;text-transform:uppercase;color:var(--muted);">After</div><div style="font-size:20px;font-weight:700;">'+imp.after_score+'/10</div></div><div><div class="'+(dl>=0?'delta-positive':'delta-negative')+'">'+(dl>=0?'+':'')+dl.toFixed(1)+'</div></div></div><div class="agent-list">Agents improved: '+(d.improved_agents||[]).join(', ')+'</div></div>';
  }

  // Benchmark panel
  if(bench.sequential_analysis_sec){
    $('bench-panel').innerHTML=`<div style="display:flex;gap:30px;align-items:center;"><div><div style="font-size:10px;text-transform:uppercase;color:var(--muted);">Sequential</div><div style="font-size:18px;font-weight:600;">${bench.sequential_analysis_sec}s</div></div><div><div style="font-size:10px;text-transform:uppercase;color:var(--muted);">Fan-Out</div><div style="font-size:18px;font-weight:600;color:var(--green);">${bench.fanout_analysis_sec}s</div></div><div><div style="font-size:10px;text-transform:uppercase;color:var(--muted);">Speedup</div><div style="font-size:28px;font-weight:700;color:var(--accent);">${bench.speedup_x}x</div></div><div><div style="font-size:10px;text-transform:uppercase;color:var(--muted);">Reduction</div><div style="font-size:18px;font-weight:600;color:var(--green);">${bench.time_reduction_pct}%</div></div></div>`;
  }
}

var expanded={};
function toggleDetail(id){
  var el=$(id);if(el){el.classList.toggle('open');}
  var btn=$('btn-'+id);if(btn){btn.textContent=el.classList.contains('open')?'−':'+';}
}

async function run(phase){
  var btn=event.target;btn.querySelector('.status-dot').className='status-dot running';
  var id={orchestrator:'orch',evaluator:'eval',improve:'imp',benchmark:'bench'}[phase]||phase;
  log('Starting...',id);
  try{
    var r=await api('/api/run/'+phase,'POST');
    btn.querySelector('.status-dot').className='status-dot '+(r.ok?'done':'error');
    log(r.message||r.error||'Done ('+r.time+'s)',id);
    refresh();
  }catch(e){
    btn.querySelector('.status-dot').className='status-dot error';
    log('Failed: '+e.message,id);
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
