"""Multi-Agent Orchestrator with Fan-Out Strategy

Coordinates 5 specialist agents (scout, financial_analyst, risk_analyst,
strategy_analyst, report_writer) using real DeepSeek LLM calls.

Fan-out: Financial, Risk, and Strategy analysts run in parallel per company.
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

def save_agent_memory(agent_name, company_id, data):
    mem_dir = os.path.join(AGENTS_DIR, agent_name, "memory")
    os.makedirs(mem_dir, exist_ok=True)
    path = os.path.join(mem_dir, f"{company_id}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

class Orchestrator:
    def __init__(self):
        self.companies_data = load_json(os.path.join(DATA_DIR, "companies.json"))
        self.apex = load_json(os.path.join(DATA_DIR, "apex_portfolio.json"))
        self.targets = self.companies_data["targets"]
        self.log_entries = []
        self.run_id = f"multi_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def log(self, step, detail, elapsed=0):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "run_id": self.run_id,
            "step": step,
            "detail": detail,
            "elapsed_sec": round(elapsed, 4)
        }
        self.log_entries.append(entry)
        print(f"[{step}] {detail}")

    def run(self):
        t0 = time.time()
        print("=" * 60)
        print("MULTI-AGENT ORCHESTRATOR: M&A Target Evaluation")
        print(f"Run ID: {self.run_id}")
        print(f"Agents: Scout → Financial Analyst → Risk Analyst → Strategy Analyst → Report Writer")
        print(f"Strategy: Fan-out (parallel specialist analysis per company)")
        print("=" * 60)
        print()

        # Phase 1: Scout — screen all companies
        screened = self.phase_scout()

        if not screened:
            self.log("pipeline", "No companies passed screening. Pipeline halted.")
            self.save_logs()
            return None

        # Phase 2: Fan-out — parallel specialist analysis per company
        analyzed = self.phase_analyze_fanout(screened)

        # Phase 3: Score & Rank
        ranked = self.phase_score_and_rank(analyzed)

        # Phase 4: Report Writer
        report = self.phase_report(ranked)

        total_time = round(time.time() - t0, 3)
        self.log("pipeline_complete", f"Total time: {total_time}s", total_time)

        self.save_logs()
        self.save_report(report)
        return report

    def phase_scout(self):
        t0 = time.time()
        self.log("scout_start", f"Scout evaluating {len(self.targets)} companies")

        system_prompt = load_prompt("scout")
        user_message = json.dumps({
            "firm": self.apex["firm_name"],
            "criteria": self.apex["deal_parameters"],
            "sector_preferences": self.apex["sector_preferences"],
            "targets": self.targets
        }, indent=2)

        try:
            result = call_agent(system_prompt, user_message)
        except Exception as e:
            self.log("scout_error", str(e))
            return []

        screening = result.get("screening_results", [])

        # Save scout memory
        save_agent_memory("scout", "all_companies", {
            "input": {"targets": [t["name"] for t in self.targets]},
            "output": screening
        })

        # Build screened list
        screened = []
        for s in screening:
            company = next((t for t in self.targets if t["id"] == s["id"]), None)
            if company:
                company["_scout"] = s
                if s.get("passed"):
                    screened.append(company)

        elapsed = round(time.time() - t0, 3)
        self.log("scout_complete", f"{len(screened)}/{len(self.targets)} passed screening ({elapsed}s)", elapsed)
        for s in screening:
            self.log("scout_result", f"{s['name']}: {'PASS' if s.get('passed') else 'FAIL'}")

        return screened

    def phase_analyze_fanout(self, screened):
        """Fan out: for each company, run Financial, Risk, and Strategy analysts in parallel."""
        t0 = time.time()
        self.log("fanout_start", f"Fanning out {len(screened)} companies × 3 analysts = {len(screened) * 3} tasks")

        tasks = []
        for company in screened:
            for agent in ["financial_analyst", "risk_analyst", "strategy_analyst"]:
                tasks.append((agent, company))

        results = {}
        completed_count = [0]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._run_analyst, agent, company): (agent, company["id"])
                for agent, company in tasks
            }
            for future in as_completed(futures):
                agent, cid = futures[future]
                try:
                    result = future.result()
                    if cid not in results:
                        results[cid] = {}
                    results[cid][agent] = result
                    completed_count[0] += 1
                    name = result.get("company_name", cid)
                    self.log("analyst_done", f"[{completed_count[0]}/{len(tasks)}] {agent}: {name}")
                except Exception as e:
                    self.log("analyst_error", f"{agent} for {cid}: {str(e)}")

        elapsed = round(time.time() - t0, 3)
        self.log("fanout_complete", f"All {completed_count[0]}/{len(tasks)} analyses done ({elapsed}s)", elapsed)

        # Attach results to companies
        for company in screened:
            cid = company["id"]
            if cid in results:
                company["_financial"] = results[cid].get("financial_analyst", {})
                company["_risk"] = results[cid].get("risk_analyst", {})
                company["_strategy"] = results[cid].get("strategy_analyst", {})

        return screened

    def _run_analyst(self, agent_name, company):
        system_prompt = load_prompt(agent_name)

        user_data = {
            "company": {k: v for k, v in company.items() if not k.startswith("_")},
            "apex_criteria": self.apex["deal_parameters"],
            "apex_portfolio": self.apex["current_portfolio"],
            "apex_sector_preferences": self.apex["sector_preferences"],
            "apex_risk_tolerance": self.apex["risk_tolerance"]
        }
        user_message = json.dumps(user_data, indent=2)

        result = call_agent(system_prompt, user_message)

        save_agent_memory(agent_name, company["id"], {
            "input": {"company": company["name"]},
            "output": result
        })

        return result

    def phase_score_and_rank(self, analyzed):
        self.log("scoring_start", f"Scoring {len(analyzed)} companies")

        for company in analyzed:
            fin = company.get("_financial", {})
            risk = company.get("_risk", {})
            strat = company.get("_strategy", {})

            fin_score = fin.get("financial_score", 50) if fin else 50
            risk_score = risk.get("overall_risk_score", 50) if risk else 50
            strat_score = strat.get("strategic_fit_score", 50) if strat else 50

            composite = (fin_score * 0.40) + (risk_score * 0.35) + (strat_score * 0.25)
            company["_composite_score"] = round(composite, 1)
            company["_financial_score"] = fin_score
            company["_risk_score"] = risk_score
            company["_strategy_score"] = strat_score

            if composite >= 85: rating = "STRONG BUY"
            elif composite >= 72: rating = "BUY"
            elif composite >= 60: rating = "HOLD / CONSIDER"
            elif composite >= 45: rating = "WEAK HOLD"
            else: rating = "PASS"
            company["_rating"] = rating

            self.log("scoring", f"{company['name']}: composite={composite} (F:{fin_score} R:{risk_score} S:{strat_score}) → {rating}")

        ranked = sorted(analyzed, key=lambda c: c["_composite_score"], reverse=True)
        return ranked

    def phase_report(self, ranked):
        t0 = time.time()
        self.log("report_start", "Generating Board memo")

        system_prompt = load_prompt("report_writer")

        rank_data = [
            {
                "rank": i+1,
                "name": c["name"],
                "id": c["id"],
                "sector": c["sector"],
                "composite_score": c["_composite_score"],
                "financial_score": c["_financial_score"],
                "risk_score": c["_risk_score"],
                "strategy_score": c["_strategy_score"],
                "rating": c["_rating"],
                "revenue": c["revenue_2024"],
                "growth": c["growth_rate_pct"],
                "valuation": c["estimated_valuation"],
                "financial_summary": c.get("_financial", {}).get("investment_thesis", ""),
                "risk_summary": c.get("_risk", {}).get("summary", ""),
                "strategy_summary": c.get("_strategy", {}).get("recommendation", "")
            }
            for i, c in enumerate(ranked)
        ]

        user_message = json.dumps({
            "firm": self.apex["firm_name"],
            "deal_criteria": self.apex["deal_parameters"],
            "ranked_targets": rank_data
        }, indent=2)

        try:
            report = call_agent(system_prompt, user_message)
        except Exception as e:
            self.log("report_error", str(e))
            report = {"error": str(e), "ranked_targets": rank_data}

        save_agent_memory("report_writer", "final_memo", {
            "input": {"num_targets": len(ranked)},
            "output": report
        })

        elapsed = round(time.time() - t0, 3)
        self.log("report_complete", f"Memo generated ({elapsed}s)", elapsed)

        print("\n" + "=" * 60)
        print("BOARD MEMO — TOP RECOMMENDATION")
        print("=" * 60)
        print(f"Title: {report.get('memo_title', 'N/A')}")
        print(f"Summary: {report.get('executive_summary', 'N/A')}")
        top = report.get("top_recommendation", {})
        print(f"Top Pick: {top.get('name', 'N/A')} — {top.get('rating', 'N/A')}")
        print(f"Rationale: {top.get('rationale', 'N/A')}")
        print()
        print("Ranked Targets:")
        print("-" * 60)
        for t in report.get("ranked_targets", []):
            print(f"  {t.get('rank')}. {t.get('name')} — {t.get('rating')} ({t.get('composite_score')})")
            print(f"     {t.get('one_line_rationale', '')}")

        if report.get("risk_watchlist"):
            print("\nRisk Watchlist:")
            for r in report["risk_watchlist"]:
                print(f"  ! {r['company']}: {r['risk']}")

        print(f"\nNext Steps: {'; '.join(report.get('next_steps', []))}")
        print(f"Closing: {report.get('closing_note', '')}")
        print("=" * 60)

        return report

    def save_logs(self):
        os.makedirs(LOGS_DIR, exist_ok=True)
        log_path = os.path.join(LOGS_DIR, "run_2_multi_agent.json")
        log_data = {
            "run_id": self.run_id,
            "agent_type": "multi_agent_orchestrated",
            "strategy": "fanout_parallel_analysis",
            "log_entries": self.log_entries
        }
        with open(log_path, "w") as f:
            json.dump(log_data, f, indent=2, default=str)
        print(f"\n[LOG] Saved to {log_path}")

    def save_report(self, report):
        os.makedirs(LOGS_DIR, exist_ok=True)
        report_path = os.path.join(LOGS_DIR, "report_multi_agent.json")
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"[REPORT] Saved to {report_path}")


if __name__ == "__main__":
    orchestrator = Orchestrator()
    orchestrator.run()
