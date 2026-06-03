"""Board Dashboard Generator

Reads all JSON outputs (reports, evaluations, benchmarks, logs) and
generates a self-contained HTML dashboard for the Board of Directors.

Run: python dashboard\generate_dashboard.py
Open: dashboard\index.html
"""

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
EVAL_DIR = os.path.join(BASE_DIR, "evaluator")
DASH_DIR = os.path.join(BASE_DIR, "dashboard")
AGENTS_DIR = os.path.join(BASE_DIR, "multi_agent", "agents")


def safe_load(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def gather_data():
    data = {
        "generated_at": datetime.now().isoformat(),
        "single_agent": safe_load(os.path.join(LOGS_DIR, "report_single_agent.json")) or {},
        "multi_agent": safe_load(os.path.join(LOGS_DIR, "report_multi_agent.json")) or {},
        "benchmark": safe_load(os.path.join(LOGS_DIR, "run_3_fanout_benchmark.json")) or {},
        "evals": safe_load(os.path.join(EVAL_DIR, "scores.json")) or {"iterations": []},
        "improvement_loop": safe_load(os.path.join(LOGS_DIR, "improvement_loop.json")) or {},
        "multi_agent_log": safe_load(os.path.join(LOGS_DIR, "run_2_multi_agent.json")) or {},
    }

    # Count agent memory files
    data["memory_counts"] = {}
    for agent in os.listdir(AGENTS_DIR):
        mem_dir = os.path.join(AGENTS_DIR, agent, "memory")
        if os.path.isdir(mem_dir):
            data["memory_counts"][agent] = len([f for f in os.listdir(mem_dir) if f.endswith(".json")])

    # Check for v2 prompts
    data["improved_agents"] = []
    for agent in ["scout", "financial_analyst", "risk_analyst", "strategy_analyst", "report_writer"]:
        if os.path.exists(os.path.join(AGENTS_DIR, agent, "prompt_v1.md")):
            data["improved_agents"].append(agent)

    return data


def generate():
    data = gather_data()
    data_json = json.dumps(data, indent=2, default=str)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Apex Capital — M&A Target Evaluation Dashboard</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Segoe UI',system-ui,sans-serif; background:#0f172a; color:#e2e8f0; padding:24px; }}
.header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; }}
.header h1 {{ font-size:22px; color:#38bdf8; }}
.header .badge {{ background:#1e293b; padding:5px 14px; border-radius:6px; font-size:12px; color:#94a3b8; }}
.grid4 {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; margin-bottom:28px; }}
.card {{ background:#1e293b; border-radius:10px; padding:20px; border:1px solid #334155; }}
.card .lbl {{ font-size:11px; text-transform:uppercase; color:#64748b; letter-spacing:.5px; margin-bottom:6px; }}
.card .val {{ font-size:28px; font-weight:700; }}
.card .sub {{ font-size:12px; color:#94a3b8; margin-top:4px; }}
.g {{ color:#22c55e; }} .y {{ color:#eab308; }} .r {{ color:#ef4444; }} .b {{ color:#38bdf8; }}
.section-title {{ font-size:14px; font-weight:600; margin:28px 0 14px; color:#94a3b8; text-transform:uppercase; letter-spacing:1px; }}
table {{ width:100%; border-collapse:collapse; background:#1e293b; border-radius:10px; overflow:hidden; }}
th {{ text-align:left; padding:10px 14px; font-size:11px; text-transform:uppercase; color:#64748b; border-bottom:1px solid #334155; }}
td {{ padding:10px 14px; font-size:13px; border-bottom:1px solid #1e293b; }}
tr:hover td {{ background:#263348; }}
.tag {{ display:inline-block; padding:2px 9px; border-radius:10px; font-size:10px; font-weight:600; }}
.tag-g {{ background:#14532d; color:#22c55e; }} .tag-b {{ background:#1e3a5f; color:#38bdf8; }}
.tag-y {{ background:#422006; color:#eab308; }} .tag-r {{ background:#450a0a; color:#f87171; }}
.bar {{ width:100%; height:5px; background:#334155; border-radius:3px; margin-top:4px; overflow:hidden; }}
.bar-f {{ height:100%; border-radius:3px; }}
.grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:28px; }}
.heat {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:10px; }}
.heat-cell {{ background:#1e293b; border-radius:8px; padding:14px; text-align:center; border:1px solid #334155; }}
.heat-cell .cname {{ font-size:13px; font-weight:600; }}
.heat-cell .crisk {{ font-size:11px; color:#94a3b8; margin-top:3px; }}
.hl {{ border-left:3px solid #22c55e; }} .hm {{ border-left:3px solid #eab308; }} .hh {{ border-left:3px solid #ef4444; }}
.eval-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }}
.eval-cell {{ background:#1e293b; border-radius:8px; padding:14px; border:1px solid #334155; }}
.eval-cell .dim {{ font-size:10px; color:#64748b; text-transform:uppercase; }}
.eval-cell .ds {{ font-size:22px; font-weight:700; }}
.timeline {{ font-size:12px; }}
.timeline .row {{ padding:5px 0; border-bottom:1px solid #1e293b; display:flex; justify-content:space-between; }}
.timeline .step {{ color:#38bdf8; width:180px; }}
.timeline .detail {{ flex:1; color:#94a3b8; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.timeline .ts {{ color:#64748b; width:60px; text-align:right; }}
.footer {{ text-align:center; color:#475569; font-size:11px; margin-top:36px; padding-top:18px; border-top:1px solid #1e293b; }}
.delta-up {{ color:#22c55e; }} .delta-down {{ color:#ef4444; }}
.score-loop {{ margin-top:14px; }}
.score-row {{ display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid #1e293b; font-size:13px; }}
</style>
</head>
<body>

<div class="header">
  <h1>Apex Capital Partners — M&A Target Evaluation System</h1>
  <span class="badge">Board of Directors Dashboard</span>
</div>

<div class="grid4" id="cards"></div>

<div class="section-title">Ranked Target Pipeline</div>
<table>
  <thead><tr><th>Rank</th><th>Company</th><th>Sector</th><th>Composite</th><th>Financial</th><th>Risk</th><th>Strategy</th><th>Rating</th><th>Revenue</th><th>Growth</th></tr></thead>
  <tbody id="pipeline"></tbody>
</table>

<div class="grid2" style="margin-top:28px;">
  <div>
    <div class="section-title">Risk Heatmap</div>
    <div class="heat" id="heatmap"></div>
  </div>
  <div>
    <div class="section-title">Evaluator Scores</div>
    <div class="eval-grid" id="eval-scores"></div>
    <div class="card score-loop" id="eval-detail"></div>
  </div>
</div>

<div class="grid2" style="margin-top:28px;">
  <div>
    <div class="section-title">Improvement Loop</div>
    <div id="loop-info" class="card"></div>
  </div>
  <div>
    <div class="section-title">Benchmark</div>
    <div id="bench-info" class="card"></div>
  </div>
</div>

<div class="section-title">Execution Timeline (multi-agent run)</div>
<div class="timeline card" id="timeline"></div>

<div class="footer">
  Apex Capital Multi-Agent M&A System &middot; Evaluator Score: <span id="final-score" class="b">—</span> &middot; powered by DeepSeek
</div>

<script>
const D = {data_json};

function el(id) {{ return document.getElementById(id); }}

function build() {{
  // --- KPI Cards ---
  const ma = D.multi_agent || {{}};
  const ranked = ma.ranked_companies || [];
  const top = ranked[0] || {{}};
  const strong = ranked.filter(c => c.rating === 'STRONG BUY').length;
  const avg = ranked.length ? (ranked.reduce((s,c) => s + (c.composite_score||0), 0) / ranked.length).toFixed(1) : 0;
  const bench = D.benchmark || {{}};
  const timings = bench.timings || {{}};

  const cards = [
    {{ l:'Targets Screened', v:ma.passed_screening||0, s:'Passed investment criteria', c:'b' }},
    {{ l:'Strong Buy', v:strong, s:'Top-tier recommendations', c:'g' }},
    {{ l:'Avg Composite', v:avg, s:'Across all ranked targets', c:'y' }},
    {{ l:'Speedup', v:(timings.speedup_x||'—')+'x', s:'Fan-out vs sequential', c:'b' }},
    {{ l:'Top Pick', v:top.name||'—', s:(top.rating||'')+' · '+(top.composite_score||''), c:'g' }},
    {{ l:'Eval Score', v:(D.evals.iterations||[]).length ? D.evals.iterations[D.evals.iterations.length-1].evaluation.overall_score + '/10' : '—', s:'Architecture grade', c:'b' }},
  ];

  el('cards').innerHTML = cards.map(c => `<div class="card"><div class="lbl">${{c.l}}</div><div class="val ${{c.c}}">${{c.v}}</div><div class="sub">${{c.s}}</div></div>`).join('');

  // --- Pipeline Table ---
  el('pipeline').innerHTML = ranked.map((c,i) => {{
    const cls = c.rating === 'STRONG BUY' ? 'tag-g' : c.rating === 'BUY' ? 'tag-b' : c.rating === 'HOLD / CONSIDER' ? 'tag-y' : 'tag-r';
    const bc = (c.composite_score||0) >= 80 ? '#22c55e' : (c.composite_score||0) >= 65 ? '#38bdf8' : (c.composite_score||0) >= 50 ? '#eab308' : '#ef4444';
    return `<tr>
      <td>${{i+1}}</td><td>${{c.name}}</td><td>${{c.sector}}</td>
      <td><b>${{c.composite_score||'—'}}</b><div class="bar"><div class="bar-f" style="width:${{c.composite_score||0}}%;background:${{bc}}"></div></div></td>
      <td>${{c.financial_score||'—'}}</td><td>${{c.risk_score||'—'}}</td><td>${{c.strategy_score||'—'}}</td>
      <td><span class="tag ${{cls}}">${{c.rating||'—'}}</span></td>
      <td>${{((c.revenue_2024||c.revenue||0)/1e6).toFixed(0)}}M</td><td>${{c.growth_rate||c.growth||0}}%</td>
    </tr>`;
  }}).join('') || '<tr><td colspan="10">No data — run multi_agent orchestrator first.</td></tr>';

  // --- Heatmap ---
  el('heatmap').innerHTML = ranked.map(c => {{
    const rs = c.risk_score || 100;
    const lvl = rs >= 85 ? 'LOW' : rs >= 70 ? 'MED' : 'HIGH';
    const hc = lvl === 'LOW' ? 'hl' : lvl === 'MED' ? 'hm' : 'hh';
    return `<div class="heat-cell ${{hc}}"><div class="cname">${{c.name}}</div><div class="crisk">Risk: ${{rs}} (${{lvl}})</div></div>`;
  }}).join('') || '<div class="heat-cell"><div class="cname">No data</div></div>';

  // --- Evaluator Scores ---
  const evals = D.evals.iterations || [];
  const last = evals.length ? evals[evals.length-1].evaluation : null;
  if (last) {{
    const dims = [
      {{ n:'Architecture', s:(last.architecture_design||{{}}).score||0 }},
      {{ n:'Prompts', s:(last.prompt_quality||{{}}).score||0 }},
      {{ n:'Output', s:(last.output_quality||{{}}).score||0 }},
      {{ n:'Scalability', s:(last.scalability||{{}}).score||0 }}
    ];
    el('eval-scores').innerHTML = dims.map(d => {{
      const clr = d.s >= 8 ? 'g' : d.s >= 6 ? 'y' : 'r';
      return `<div class="eval-cell"><div class="dim">${{d.n}}</div><div class="ds ${{clr}}">${{d.s}}/10</div></div>`;
    }}).join('');
    el('eval-detail').innerHTML = `<div class="lbl">Overall: ${{last.overall_score}}/10 &middot; ${{last.production_readiness||'—'}}</div><div class="sub">${{last.summary||''}}</div>`;

    // Show score progression across iterations
    if (evals.length > 1) {{
      el('eval-detail').innerHTML += '<div style="margin-top:10px;"><div class="lbl">Score History</div>';
      evals.forEach((e,i) => {{
        const sc = e.evaluation.overall_score || '—';
        el('eval-detail').innerHTML += `<div class="score-row"><span>Iteration ${{i+1}} (${{e.type||'initial'}})</span><span class="b">${{sc}}/10</span></div>`;
      }});
      el('eval-detail').innerHTML += '</div>';
    }}
    el('final-score').textContent = last.overall_score + '/10';
  }} else {{
    el('eval-scores').innerHTML = '<div class="eval-cell"><div class="dim">No evaluation</div><div class="ds">—</div></div>';
    el('eval-detail').innerHTML = '<div class="lbl">Run evaluator first</div><div class="sub">python evaluator\\evaluator.py</div>';
  }}

  // --- Improvement Loop ---
  const loop = D.improvement_loop || {{}};
  if (loop.before_score) {{
    const dlt = parseFloat(loop.delta||0);
    el('loop-info').innerHTML = `
      <div class="lbl">Before: ${{loop.before_score}}/10 → After: ${{loop.after_score}}/10</div>
      <div class="sub">Agents improved: ${{(D.improved_agents||[]).join(', ')||'none'}}</div>
      <div class="sub ${{dlt > 0 ? 'g' : dlt < 0 ? 'r' : 'y'}}">Delta: ${{dlt > 0 ? '+' : ''}}${{dlt}}</div>
    `;
  }} else {{
    el('loop-info').innerHTML = '<div class="lbl">No improvement loop run yet</div><div class="sub">Run: python evaluator\\improvement_loop.py</div>';
  }}

  // --- Benchmark ---
  if (timings.sequential_analysis_sec) {{
    el('bench-info').innerHTML = `
      <div class="lbl">Sequential: ${{timings.sequential_analysis_sec}}s</div>
      <div class="lbl">Fan-out: ${{timings.fanout_analysis_sec}}s</div>
      <div class="val b">${{timings.speedup_x}}x faster</div>
      <div class="sub">${{timings.time_reduction_pct}}% time reduction &middot; ${{(bench.config||{{}}).max_workers||6}} workers</div>
    `;
  }} else {{
    el('bench-info').innerHTML = '<div class="lbl">No benchmark data</div><div class="sub">Run: python multi_agent\\fanout.py</div>';
  }}

  // --- Timeline ---
  const tl = (D.multi_agent_log.log_entries || []).slice(-30);
  el('timeline').innerHTML = tl.map(t => `
    <div class="row"><span class="step">${{t.step}}</span><span class="detail">${{t.detail}}</span><span class="ts">${{t.elapsed_sec}}s</span></div>
  `).join('') || '<div class="row"><span>No timeline data</span></div>';
}}

build();
</script>
</body>
</html>"""

    os.makedirs(DASH_DIR, exist_ok=True)
    out = os.path.join(DASH_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[DASHBOARD] Generated: {out}")
    return out


if __name__ == "__main__":
    generate()
