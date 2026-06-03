"""Single-Agent Baseline: Monolithic M&A Target Evaluation System

This is the BENCHMARK. One agent does everything:
scout -> screen -> financial analysis -> risk assessment -> strategic fit -> report.

The multi-agent version will split these into specialist agents for comparison.
"""

import json
import time
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")

def load_json(filename):
    with open(os.path.join(DATA_DIR, filename), "r") as f:
        return json.load(f)

def log_event(log_entries, step, detail, elapsed=0):
    log_entries.append({
        "timestamp": datetime.now().isoformat(),
        "step": step,
        "detail": detail,
        "elapsed_sec": round(elapsed, 4)
    })

class SingleAgentBaseline:
    """One agent handling the entire M&A evaluation pipeline."""

    def __init__(self):
        self.companies_data = load_json("companies.json")
        self.apex = load_json("apex_portfolio.json")
        self.targets = self.companies_data["targets"]
        self.deal_params = self.apex["deal_parameters"]
        self.sector_prefs = self.apex["sector_preferences"]
        self.risk_tolerance = self.apex["risk_tolerance"]
        self.log_entries = []
        self.results = []

    def run(self):
        t0 = time.time()
        print("=" * 60)
        print("SINGLE-AGENT BASELINE: M&A Target Evaluation")
        print("=" * 60)
        print(f"Firm: {self.apex['firm_name']}")
        print(f"AUM: ${self.apex['aum_billion']}B")
        print(f"Targets to evaluate: {len(self.targets)}")
        print()

        # Step 1: Scout & Screen
        screened = self.scout_and_screen()
        log_event(self.log_entries, "scout_screen", f"Screened {len(self.targets)} targets, {len(screened)} passed")

        # Step 2: Financial Analysis
        for company in screened:
            financials = self.financial_analysis(company)
            company["_financials"] = financials

        log_event(self.log_entries, "financial_analysis", f"Analyzed {len(screened)} companies")

        # Step 3: Risk Assessment
        for company in screened:
            risk = self.risk_assessment(company)
            company["_risk"] = risk

        log_event(self.log_entries, "risk_assessment", f"Assessed risk for {len(screened)} companies")

        # Step 4: Strategic Fit
        for company in screened:
            fit = self.strategic_fit(company)
            company["_strategy"] = fit

        log_event(self.log_entries, "strategic_fit", f"Evaluated fit for {len(screened)} companies")

        # Step 5: Composite Scoring & Ranking
        ranked = self.score_and_rank(screened)
        log_event(self.log_entries, "scoring", f"Ranked {len(ranked)} companies")

        # Step 6: Generate Report
        report = self.generate_report(ranked)
        log_event(self.log_entries, "report", "Generated executive report")

        total_time = round(time.time() - t0, 3)
        log_event(self.log_entries, "complete", f"Pipeline complete in {total_time}s", total_time)

        self.results = ranked
        self.save_logs()
        return report

    def scout_and_screen(self):
        screened = []
        for t in self.targets:
            passed = True
            reasons = []

            if t["revenue_2024"] < self.deal_params["min_revenue"]:
                passed = False
                reasons.append(f"Revenue below min (${t['revenue_2024']:,} < ${self.deal_params['min_revenue']:,})")

            if t["revenue_2024"] > self.deal_params["max_revenue"]:
                passed = False
                reasons.append(f"Revenue above max (${t['revenue_2024']:,} > ${self.deal_params['max_revenue']:,})")

            if t["growth_rate_pct"] < self.deal_params["min_growth_rate_pct"]:
                passed = False
                reasons.append(f"Growth below min ({t['growth_rate_pct']}% < {self.deal_params['min_growth_rate_pct']}%)")

            if t["estimated_valuation"] / t["revenue_2024"] > self.deal_params["max_valuation_multiple"]:
                passed = False
                reasons.append(f"Valuation multiple too high ({t['estimated_valuation']/t['revenue_2024']:.1f}x > {self.deal_params['max_valuation_multiple']}x)")

            sector = t["sector"]
            if sector in self.sector_prefs.get("avoid", []):
                passed = False
                reasons.append(f"Sector on avoid list: {sector}")

            t["_screened"] = passed
            t["_screen_reasons"] = reasons
            if passed:
                screened.append(t)

            log_event(self.log_entries, "screen", f"{t['name']}: {'PASS' if passed else 'FAIL'} - {'; '.join(reasons) if reasons else 'Met all criteria'}")

        return screened

    def financial_analysis(self, company):
        rev_2024 = company["revenue_2024"]
        rev_2023 = company["revenue_2023"]
        rev_2022 = company["revenue_2022"]
        ebitda_margin = company["ebitda_margin_pct"]
        burn = company["burn_rate_monthly"]
        cash = company["cash_reserves"]
        valuation = company["estimated_valuation"]

        rev_multiple = valuation / rev_2024 if rev_2024 > 0 else 0
        cash_runway_months = cash / burn if burn > 0 else 99
        rev_growth_1yr = ((rev_2024 - rev_2023) / rev_2023) * 100 if rev_2023 > 0 else 0
        rev_cagr_2yr = ((rev_2024 / rev_2022) ** (1/2) - 1) * 100 if rev_2022 > 0 else 0

        score = 0.0
        if rev_growth_1yr >= 40: score += 30
        elif rev_growth_1yr >= 25: score += 22
        elif rev_growth_1yr >= 15: score += 14
        else: score += 5

        if ebitda_margin >= 20: score += 25
        elif ebitda_margin >= 10: score += 18
        elif ebitda_margin >= 0: score += 10
        else: score += 0

        if rev_multiple <= 4: score += 20
        elif rev_multiple <= 5: score += 14
        elif rev_multiple <= 6: score += 8
        else: score += 2

        if cash_runway_months >= 24: score += 15
        elif cash_runway_months >= 12: score += 10
        elif cash_runway_months >= 6: score += 5
        else: score += 1

        if company["customer_churn_pct"] <= 5: score += 10
        elif company["customer_churn_pct"] <= 10: score += 6
        else: score += 2

        company["_financial_score"] = score

        return {
            "rev_multiple": round(rev_multiple, 2),
            "cash_runway_months": round(cash_runway_months, 1),
            "rev_growth_1yr_pct": round(rev_growth_1yr, 1),
            "rev_cagr_2yr_pct": round(rev_cagr_2yr, 1),
            "ebitda_margin": ebitda_margin,
            "financial_score": round(score, 1),
            "max_score": 100
        }

    def risk_assessment(self, company):
        score = 100.0
        risk_flags = []

        regulatory_count = len(company["regulatory_issues"])
        if regulatory_count >= 3:
            score -= 20
            risk_flags.append(f"High regulatory burden ({regulatory_count} issues)")
        elif regulatory_count >= 1:
            score -= 10
            risk_flags.append(f"Moderate regulatory issues ({regulatory_count})")

        if company["tech_debt_score"] >= 7:
            score -= 20
            risk_flags.append(f"Severe tech debt (score: {company['tech_debt_score']})")
        elif company["tech_debt_score"] >= 5:
            score -= 10
            risk_flags.append(f"High tech debt (score: {company['tech_debt_score']})")

        if company["estimated_valuation"] > 300_000_000:
            score -= 10
            risk_flags.append("Large deal size increases execution risk")

        if company["customer_churn_pct"] > 10:
            score -= 15
            risk_flags.append(f"High churn ({company['customer_churn_pct']}%)")
        elif company["customer_churn_pct"] > 7:
            score -= 7
            risk_flags.append(f"Elevated churn ({company['customer_churn_pct']}%)")

        if company["cash_reserves"] < 5_000_000:
            score -= 15
            risk_flags.append("Low cash reserves")
        elif company["cash_reserves"] < 10_000_000:
            score -= 7
            risk_flags.append("Moderate cash reserves")

        if company["primary_risk"]:
            risk_flags.append(company["primary_risk"])

        score = max(score, 0)
        company["_risk_score"] = score

        return {
            "risk_score": round(score, 1),
            "risk_flags": risk_flags,
            "regulatory_issues_count": regulatory_count,
            "tech_debt_score": company["tech_debt_score"],
            "max_score": 100
        }

    def strategic_fit(self, company):
        score = 0.0
        sector = company["sector"]
        positives = []

        if sector in self.sector_prefs["high_priority"]:
            score += 35
            positives.append(f"Sector is HIGH priority")
        elif sector in self.sector_prefs["medium_priority"]:
            score += 25
            positives.append(f"Sector is MEDIUM priority")
        elif sector in self.sector_prefs["low_priority"]:
            score += 10
            positives.append(f"Sector is LOW priority")

        portfolio_sectors = [p["sector"] for p in self.apex["current_portfolio"]]
        if sector in portfolio_sectors:
            score += 20
            positives.append("Complementary to existing portfolio holding")
        else:
            score += 10
            positives.append("New sector diversification")

        if company["employees"] <= 100:
            score += 15
            positives.append("Small team = easier integration")
        elif company["employees"] <= 200:
            score += 12
            positives.append("Manageable team size")
        elif company["employees"] <= 300:
            score += 8
            positives.append("Medium integration complexity")

        if company["headquarters"] in ["New York, NY", "Boston, MA", "Chicago, IL", "San Francisco, CA", "Austin, TX"]:
            score += 10
            positives.append("US-based HQ simplifies oversight")
        elif "Canada" in company["headquarters"]:
            score += 7
            positives.append("North American HQ")
        else:
            score += 3
            positives.append("International – adds complexity")

        if company["revenue_2024"] >= 50_000_000:
            score += 10
            positives.append("Platform-scale revenue")

        if company["ebitda_margin_pct"] > 0:
            score += 10
            positives.append("Already EBITDA-positive")

        company["_strategy_score"] = score

        return {
            "strategy_score": round(score, 1),
            "positives": positives,
            "max_score": 100
        }

    def score_and_rank(self, screened):
        for company in screened:
            fin = company["_financial_score"]
            risk = company["_risk_score"]
            strat = company["_strategy_score"]

            composite = (fin * 0.40) + (risk * 0.35) + (strat * 0.25)
            company["_composite_score"] = round(composite, 1)

            # 1-10 overall rating
            if composite >= 85: rating = "STRONG BUY"
            elif composite >= 72: rating = "BUY"
            elif composite >= 60: rating = "HOLD / CONSIDER"
            elif composite >= 45: rating = "WEAK HOLD"
            else: rating = "PASS"
            company["_rating"] = rating

        ranked = sorted(screened, key=lambda c: c["_composite_score"], reverse=True)
        return ranked

    def generate_report(self, ranked):
        print("\n" + "=" * 60)
        print("EXECUTIVE SUMMARY: M&A TARGET RANKINGS")
        print("=" * 60)

        report_lines = []
        header = f"{'Rank':<5} {'Company':<25} {'Sector':<22} {'Score':<7} {'Rating':<18} {'Revenue':<12} {'Valuation':<12}"
        print(header)
        print("-" * 105)
        report_lines.append(header)
        report_lines.append("-" * 105)

        for i, c in enumerate(ranked, 1):
            line = f"{i:<5} {c['name']:<25} {c['sector']:<22} {c['_composite_score']:<7} {c['_rating']:<18} ${c['revenue_2024']:>10,.0f}  ${c['estimated_valuation']:>10,.0f}"
            print(line)
            report_lines.append(line)

            fin = c["_financials"]
            risk = c["_risk"]
            strat = c["_strategy"]
            print(f"      Financial: {fin['financial_score']}/100 | Risk: {risk['risk_score']}/100 | Strategy: {strat['strategy_score']}/100")
            print(f"      Risk flags: {'; '.join(risk['risk_flags'][:2])}")
            print()

        print("=" * 60)
        print(f"Top Pick: {ranked[0]['name']} ({ranked[0]['_rating']})")
        print(f"Runner Up: {ranked[1]['name']} ({ranked[1]['_rating']})")
        print(f"Total evaluated: {len(self.targets)} | Passed screening: {len(ranked)}")

        return {
            "text_report": "\n".join(report_lines),
            "top_pick": ranked[0]["name"],
            "runner_up": ranked[1]["name"],
            "total_evaluated": len(self.targets),
            "passed_screening": len(ranked),
            "ranked_companies": [
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
                    "revenue_2024": c["revenue_2024"],
                    "valuation": c["estimated_valuation"],
                    "growth_rate": c["growth_rate_pct"],
                    "risk_flags": c["_risk"]["risk_flags"]
                } for i, c in enumerate(ranked)
            ]
        }

    def save_logs(self):
        os.makedirs(LOGS_DIR, exist_ok=True)
        log_path = os.path.join(LOGS_DIR, "run_1_single_agent.json")
        log_data = {
            "run_id": "single_agent_baseline",
            "agent_type": "monolithic",
            "log_entries": self.log_entries,
            "results": self.results_summary()
        }
        with open(log_path, "w") as f:
            json.dump(log_data, f, indent=2, default=str)
        print(f"\n[LOG] Saved to {log_path}")

    def results_summary(self):
        return [
            {
                "name": c["name"],
                "composite_score": c.get("_composite_score", 0),
                "financial_score": c.get("_financial_score", 0),
                "risk_score": c.get("_risk_score", 0),
                "strategy_score": c.get("_strategy_score", 0),
                "rating": c.get("_rating", "N/A"),
                "revenue": c["revenue_2024"],
                "growth": c["growth_rate_pct"]
            } for c in self.results
        ]


if __name__ == "__main__":
    agent = SingleAgentBaseline()
    result = agent.run()

    # Write report to file
    report_path = os.path.join(LOGS_DIR, "report_single_agent.json")
    with open(report_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[REPORT] Saved to {report_path}")
