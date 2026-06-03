"""Fan-Out Optimizer — Benchmarks sequential vs parallel execution strategies.

Phase 3 demonstrates fan-out speedup by comparing:
  SEQUENTIAL: Scout → then one analyst at a time per company (no parallelism)
  FAN-OUT:   Scout → then all analysts run in parallel across all companies

Measures wall-clock time, computes speedup, saves benchmark logs.
"""

import json
import os
import time
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from multi_agent.llm_client import call_agent

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
AGENTS_DIR = os.path.join(BASE_DIR, "multi_agent", "agents")

def load_json(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def load_prompt(agent_name):
    path = os.path.join(AGENTS_DIR, agent_name, "prompt.md")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def build_user_message(company, ape):
    return json.dumps({
        "company": {k: v for k, v in company.items() if not k.startswith("_")},
        "apex_criteria": ape["deal_parameters"],
        "apex_portfolio": ape["current_portfolio"],
        "apex_sector_preferences": ape["sector_preferences"],
        "apex_risk_tolerance": ape["risk_tolerance"]
    }, indent=2)

class FanOutBenchmark:
    def __init__(self):
        self.targets = load_json(os.path.join(DATA_DIR, "companies.json"))["targets"]
        self.apex = load_json(os.path.join(DATA_DIR, "apex_portfolio.json"))
        self.results = {}

    def scout(self):
        """Shared scout step — one LLM call for all companies (both modes use same scout)."""
        system = load_prompt("scout")
        user = json.dumps({
            "firm": self.apex["firm_name"],
            "criteria": self.apex["deal_parameters"],
            "sector_preferences": self.apex["sector_preferences"],
            "targets": self.targets
        }, indent=2)
        result = call_agent(system, user)
        screening = result.get("screening_results", [])

        screened = []
        for s in screening:
            company = next((t for t in self.targets if t["id"] == s["id"]), None)
            if company and s.get("passed"):
                company["_scout"] = s
                screened.append(company)
        return screened

    def run_analyst(self, agent_name, company):
        """Run a single analyst — used by both modes."""
        system = load_prompt(agent_name)
        user = build_user_message(company, self.apex)
        return agent_name, company["id"], call_agent(system, user)

    def run_sequential(self, screened):
        """SEQUENTIAL mode: one analyst at a time, one company at a time. No parallelism."""
        t0 = time.time()
        print(f"\n{'─' * 55}")
        print("SEQUENTIAL MODE — no parallelism")
        print(f"{'─' * 55}")
        step_start = time.time()

        results = {}
        task_count = len(screened) * 3
        done = 0

        for company in screened:
            for agent in ["financial_analyst", "risk_analyst", "strategy_analyst"]:
                agent_name, cid, result = self.run_analyst(agent, company)
                if cid not in results:
                    results[cid] = {}
                results[cid][agent_name] = result
                done += 1
                name = result.get("company_name", cid)
                elapsed = round(time.time() - step_start, 2)
                print(f"  [{done}/{task_count}] {agent_name}: {name} ({elapsed}s)")

        elapsed = round(time.time() - t0, 2)
        print(f"  Sequential total: {elapsed}s")
        return results, elapsed

    def run_fanout(self, screened):
        """FAN-OUT mode: all analysts for all companies run in parallel via ThreadPoolExecutor."""
        t0 = time.time()
        print(f"\n{'─' * 55}")
        print("FAN-OUT MODE — parallel analysts across companies")
        print(f"{'─' * 55}")

        tasks = []
        for company in screened:
            for agent in ["financial_analyst", "risk_analyst", "strategy_analyst"]:
                tasks.append((agent, company))

        results = {}
        done = [0]
        total = len(tasks)

        def run_task(agent, company):
            return self.run_analyst(agent, company)

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(run_task, agent, c): (agent, c["id"]) for agent, c in tasks}
            for future in as_completed(futures):
                agent_name, cid = futures[future]
                try:
                    a, cid, result = future.result()
                    if cid not in results:
                        results[cid] = {}
                    results[cid][agent_name] = result
                    done[0] += 1
                    name = result.get("company_name", cid)
                    print(f"  [{done[0]}/{total}] {agent_name}: {name} done")
                except Exception as e:
                    done[0] += 1
                    print(f"  [{done[0]}/{total}] {agent_name} ERROR: {e}")

        elapsed = round(time.time() - t0, 2)
        print(f"  Fan-out total: {elapsed}s")
        return results, elapsed

    def run_benchmark(self):
        print("=" * 60)
        print("PHASE 3: FAN-OUT OPTIMIZER BENCHMARK")
        print("=" * 60)
        print(f"Companies: {len(self.targets)}")
        print(f"Analysts per company: 3 (financial, risk, strategy)")
        print()

        # Step 1: Scout (shared — runs once, not benchmarked)
        t_scout = time.time()
        screened = self.scout()
        scout_time = round(time.time() - t_scout, 2)
        print(f"Scout: {len(screened)}/{len(self.targets)} passed ({scout_time}s)")
        for s in screened:
            print(f"  + {s['name']}")

        # Step 2: Sequential run
        seq_results, seq_time = self.run_sequential(screened)

        # Step 3: Fan-out run (different results because LLM is non-deterministic, but timing comparison is valid)
        fan_results, fan_time = self.run_fanout(screened)

        # Step 4: Compare
        speedup = round(seq_time / fan_time, 2) if fan_time > 0 else 0
        reduction_pct = round((1 - fan_time / seq_time) * 100, 1) if seq_time > 0 else 0

        print(f"\n{'═' * 55}")
        print("BENCHMARK RESULTS")
        print(f"{'═' * 55}")
        print(f"  Scout phase (shared):         {scout_time}s")
        print(f"  Sequential analysis:          {seq_time}s")
        print(f"  Fan-out analysis:             {fan_time}s")
        print(f"  Speedup:                      {speedup}x faster")
        print(f"  Time reduction:               {reduction_pct}%")
        print(f"  Tasks parallelized:           {len(screened) * 3}")
        print(f"  Max workers:                  6")
        print(f"{'═' * 55}")

        # Save benchmark
        benchmark = {
            "phase": "fanout_optimizer",
            "date": datetime.now().isoformat(),
            "config": {
                "companies_total": len(self.targets),
                "companies_screened": len(screened),
                "analysts_per_company": 3,
                "max_workers": 6
            },
            "timings": {
                "scout_shared_sec": scout_time,
                "sequential_analysis_sec": seq_time,
                "fanout_analysis_sec": fan_time,
                "speedup_x": speedup,
                "time_reduction_pct": reduction_pct
            },
            "sequential_results": self._summarize(seq_results),
            "fanout_results": self._summarize(fan_results),
            "verdict": (
                f"Fan-out achieves {speedup}x speedup "
                f"({reduction_pct}% time reduction) by parallelizing "
                f"{len(screened) * 3} analyst calls across {len(screened)} companies."
            )
        }

        os.makedirs(LOGS_DIR, exist_ok=True)
        bm_path = os.path.join(LOGS_DIR, "run_3_fanout_benchmark.json")
        with open(bm_path, "w") as f:
            json.dump(benchmark, f, indent=2, default=str)
        print(f"\n[LOG] Saved to {bm_path}")

        return benchmark

    def _summarize(self, results):
        return {
            cid: {
                "financial_score": agents.get("financial_analyst", {}).get("financial_score", "N/A"),
                "risk_score": agents.get("risk_analyst", {}).get("overall_risk_score", "N/A"),
                "strategy_score": agents.get("strategy_analyst", {}).get("strategic_fit_score", "N/A"),
            }
            for cid, agents in results.items()
        }


if __name__ == "__main__":
    benchmark = FanOutBenchmark()
    benchmark.run_benchmark()
