"""Log Analyzer — Phase 7

Parses all JSON logs across every phase and produces:
  - Execution timing statistics
  - Score distributions & progression
  - Before/after comparison (single vs multi agent)
  - Improvement loop deltas
  - Error and warning counts
  - Comprehensive analysis report

Run: python log_analyzer.py
Output: logs/analysis_report.json + printed summary
"""

import json
import os
from datetime import datetime
from collections import Counter, defaultdict

BASE_DIR = os.path.dirname(__file__)
LOGS_DIR = os.path.join(BASE_DIR, "logs")
EVAL_DIR = os.path.join(BASE_DIR, "evaluator")


def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def analyze():
    print("=" * 65)
    print("PHASE 7: LOG ANALYZER")
    print("=" * 65)

    report = {
        "generated_at": datetime.now().isoformat(),
        "sections": {}
    }

    # ── 1. Single-Agent Log ──────────────────────────────────────
    sa_log = load_json(os.path.join(LOGS_DIR, "run_1_single_agent.json"))
    sa_report = load_json(os.path.join(LOGS_DIR, "report_single_agent.json"))

    sa_section = {"status": "not_found"}
    if sa_log and sa_report:
        entries = sa_log.get("log_entries", [])
        steps = Counter(e["step"] for e in entries)
        completed = next((e for e in entries if e["step"] == "complete"), {})
        sa_section = {
            "type": "monolithic",
            "total_targets": sa_report.get("total_evaluated", 0),
            "passed_screening": sa_report.get("passed_screening", 0),
            "top_pick": sa_report.get("top_pick", "N/A"),
            "runner_up": sa_report.get("runner_up", "N/A"),
            "total_time_sec": completed.get("elapsed_sec", 0),
            "step_counts": dict(steps),
            "ranking": [
                {"name": c["name"], "score": c["composite_score"], "rating": c["rating"]}
                for c in sa_report.get("ranked_companies", [])[:3]
            ]
        }

    report["sections"]["single_agent"] = sa_section

    # ── 2. Multi-Agent Log ───────────────────────────────────────
    ma_log = load_json(os.path.join(LOGS_DIR, "run_2_multi_agent.json"))
    ma_report = load_json(os.path.join(LOGS_DIR, "report_multi_agent.json"))

    ma_section = {"status": "not_found"}
    if ma_log and ma_report:
        entries = ma_log.get("log_entries", [])
        steps = Counter(e["step"] for e in entries)
        errors = [e for e in entries if "error" in e["step"].lower()]
        completed = next((e for e in entries if e["step"] == "pipeline_complete"), {})

        scout_entry = next((e for e in entries if e["step"] == "scout_complete"), {})
        fanout_start = next((e for e in entries if e["step"] == "fanout_start"), {})
        fanout_end = next((e for e in entries if e["step"] == "fanout_complete"), {})

        ranked = ma_report.get("ranked_companies", [])
        scores = [c.get("composite_score", 0) for c in ranked]
        ratings = Counter(c.get("rating", "UNKNOWN") for c in ranked)

        ma_section = {
            "type": "multi_agent_orchestrated",
            "strategy": ma_log.get("strategy", ""),
            "total_time_sec": completed.get("elapsed_sec", 0),
            "scout_time_sec": scout_entry.get("elapsed_sec", 0),
            "fanout_time_sec": round(fanout_end.get("elapsed_sec", 0) - fanout_start.get("elapsed_sec", 0), 2) if fanout_start and fanout_end else 0,
            "passed_screening": ma_report.get("passed_screening", 0),
            "errors": len(errors),
            "step_counts": dict(steps),
            "score_distribution": {
                "min": min(scores) if scores else 0,
                "max": max(scores) if scores else 0,
                "avg": round(sum(scores) / len(scores), 1) if scores else 0,
            },
            "rating_distribution": dict(ratings),
            "ranking": [
                {"name": c["name"], "score": c["composite_score"], "rating": c.get("rating")}
                for c in ranked[:3]
            ],
            "board_memo": ma_report.get("executive_summary", "")[:200] if ma_report.get("executive_summary") else "",
        }

    report["sections"]["multi_agent"] = ma_section

    # ── 3. Fan-Out Benchmark ─────────────────────────────────────
    benchmark = load_json(os.path.join(LOGS_DIR, "run_3_fanout_benchmark.json"))

    bm_section = {"status": "not_found"}
    if benchmark:
        t = benchmark.get("timings", {})
        bm_section = {
            "scout_time_sec": t.get("scout_shared_sec", 0),
            "sequential_sec": t.get("sequential_analysis_sec", 0),
            "fanout_sec": t.get("fanout_analysis_sec", 0),
            "speedup_x": t.get("speedup_x", 0),
            "time_reduction_pct": t.get("time_reduction_pct", 0),
            "verdict": benchmark.get("verdict", ""),
            "tasks_parallelized": (benchmark.get("config") or {}).get("companies_screened", 0) * 3,
        }

    report["sections"]["fanout_benchmark"] = bm_section

    # ── 4. Evaluator Scores ──────────────────────────────────────
    eval_data = load_json(os.path.join(EVAL_DIR, "scores.json"))

    eval_section = {"status": "not_found"}
    if eval_data:
        iterations = eval_data.get("iterations", [])
        scores_over_time = []
        for i, it in enumerate(iterations, 1):
            e = it.get("evaluation", {})
            timestamp = it.get("timestamp", "")
            score = e.get("overall_score", 0)
            scores_over_time.append({
                "iteration": i,
                "score": score,
                "type": it.get("type", "initial"),
                "readiness": e.get("production_readiness", "N/A"),
            })

        latest = iterations[-1].get("evaluation", {}) if iterations else {}
        eval_section = {
            "total_iterations": len(iterations),
            "first_score": scores_over_time[0]["score"] if scores_over_time else 0,
            "latest_score": scores_over_time[-1]["score"] if scores_over_time else 0,
            "score_progression": scores_over_time,
            "latest_breakdown": {
                "architecture": (latest.get("architecture_design") or {}).get("score", 0),
                "prompts": (latest.get("prompt_quality") or {}).get("score", 0),
                "output": (latest.get("output_quality") or {}).get("score", 0),
                "scalability": (latest.get("scalability") or {}).get("score", 0),
            },
            "best_agent": (latest.get("prompt_quality") or {}).get("best_agent", ""),
            "worst_agent": (latest.get("prompt_quality") or {}).get("worst_agent", ""),
            "hallucination_risk": (latest.get("output_quality") or {}).get("hallucination_risk", ""),
            "top_improvements": latest.get("top_improvements", [])[:3],
        }

    report["sections"]["evaluator"] = eval_section

    # ── 5. Improvement Loop ─────────────────────────────────────
    imp_log = load_json(os.path.join(LOGS_DIR, "improvement_loop.json"))

    imp_section = {"status": "not_found"}
    if imp_log:
        imp_section = {
            "before_score": imp_log.get("before_score", 0),
            "after_score": imp_log.get("after_score", 0),
            "delta": imp_log.get("delta", "N/A"),
            "agents_improved": list((imp_log.get("agents_improved") or {}).keys()),
        }

    report["sections"]["improvement_loop"] = imp_section

    # ── 6. Cross-Phase Comparison ────────────────────────────────
    cmp = {"single_vs_multi": {}}
    if sa_section.get("type") and ma_section.get("type"):
        sa_ranked = sa_report.get("ranked_companies", [])
        ma_ranked = ma_report.get("ranked_companies", [])
        cmp["single_vs_multi"] = {
            "pass_rate_single": f"{sa_section['passed_screening']}/{sa_section['total_targets']}",
            "pass_rate_multi": f"{ma_section['passed_screening']}/10",
            "time_single_sec": sa_section["total_time_sec"],
            "time_multi_sec": ma_section["total_time_sec"],
            "note": "Single-agent is deterministic (<1s). Multi-agent uses LLM APIs (seconds). Different speed classes.",
        }

    if eval_data and len(eval_data.get("iterations", [])) >= 2:
        iters = eval_data["iterations"]
        cmp["evaluator_progression"] = {
            "start": iters[0]["evaluation"].get("overall_score", 0),
            "end": iters[-1]["evaluation"].get("overall_score", 0),
            "total_iterations": len(iters),
            "net_change": round(iters[-1]["evaluation"].get("overall_score", 0) - iters[0]["evaluation"].get("overall_score", 0), 1),
        }

    report["sections"]["cross_phase"] = cmp

    # ── 7. Summary ───────────────────────────────────────────────
    report["summary"] = {
        "pipeline_health": "HEALTHY" if ma_section.get("errors", 99) == 0 else "ISSUES",
        "evaluation_trend": (
            "IMPROVING" if eval_section.get("latest_score", 0) > eval_section.get("first_score", 0)
            else "STABLE" if eval_section.get("latest_score", 0) == eval_section.get("first_score", 0)
            else "N/A"
        ),
        "speedup_achieved": f"{bm_section.get('speedup_x', 'N/A')}x",
        "key_findings": []
    }

    # Auto-generate findings
    if bm_section.get("speedup_x", 0) > 1:
        report["summary"]["key_findings"].append(
            f"Fan-out achieves {bm_section['speedup_x']}x speedup ({bm_section['time_reduction_pct']}% faster)"
        )
    if eval_section.get("latest_score"):
        report["summary"]["key_findings"].append(
            f"Architecture rated {eval_section['latest_score']}/10 by evaluator"
        )
    if imp_section.get("delta"):
        report["summary"]["key_findings"].append(
            f"Improvement loop moved score by {imp_section['delta']}"
        )
    if ma_section.get("passed_screening"):
        top_co = ma_section.get("ranking", [])[0] if ma_section.get("ranking") else {}
        report["summary"]["key_findings"].append(
            f"Top target: {top_co.get('name', 'N/A')} ({top_co.get('rating', 'N/A')})"
        )

    # ── 8. Print & Save ──────────────────────────────────────────
    print("\n--- Single-Agent ---")
    if sa_section.get("type"):
        print(f"  Targets: {sa_section['total_targets']} | Passed: {sa_section['passed_screening']} | Time: {sa_section['total_time_sec']}s")
        print(f"  Top: {sa_section['top_pick']} | Runner-up: {sa_section['runner_up']}")

    print("\n--- Multi-Agent ---")
    if ma_section.get("type"):
        print(f"  Passed: {ma_section['passed_screening']} | Time: {ma_section['total_time_sec']}s | Errors: {ma_section['errors']}")
        print(f"  Scores: min={ma_section['score_distribution']['min']} max={ma_section['score_distribution']['max']} avg={ma_section['score_distribution']['avg']}")
        print(f"  Ratings: {ma_section['rating_distribution']}")

    print("\n--- Fan-Out Benchmark ---")
    if bm_section.get("sequential_sec"):
        print(f"  Sequential: {bm_section['sequential_sec']}s | Fan-out: {bm_section['fanout_sec']}s")
        print(f"  Speedup: {bm_section['speedup_x']}x ({bm_section['time_reduction_pct']}% reduction)")

    print("\n--- Evaluator ---")
    if eval_section.get("latest_score"):
        print(f"  Iterations: {eval_section['total_iterations']} | First: {eval_section['first_score']}/10 -> Latest: {eval_section['latest_score']}/10")
        print(f"  Hallucination risk: {eval_section['hallucination_risk']}")
        bd = eval_section["latest_breakdown"]
        print(f"  Breakdown: Arch={bd['architecture']} Prompts={bd['prompts']} Output={bd['output']} Scale={bd['scalability']}")

    print("\n--- Improvement Loop ---")
    if imp_section.get("delta"):
        print(f"  {imp_section['before_score']} -> {imp_section['after_score']} (delta: {imp_section['delta']})")
        print(f"  Agents: {', '.join(imp_section['agents_improved'])}")

    print("\n--- Cross-Phase ---")
    for k, v in cmp.items():
        for kk, vv in v.items():
            print(f"  {kk}: {vv}")
    print()

    for finding in report["summary"]["key_findings"]:
        print(f"  > {finding}")

    # Save
    out = os.path.join(LOGS_DIR, "analysis_report.json")
    with open(out, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n[ANALYZER] Full report saved to {out}")
    return report


if __name__ == "__main__":
    analyze()
