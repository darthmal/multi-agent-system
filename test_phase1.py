"""Test script for the single-agent baseline. Run with: python test_phase1.py"""

import json
import os
import sys

_BASE = os.path.dirname(__file__) if '__file__' in dir() else os.getcwd()
LOGS_DIR = os.path.join(_BASE, "logs")
DATA_DIR = os.path.join(_BASE, "data")

def test_data_exists():
    assert os.path.exists(os.path.join(DATA_DIR, "companies.json")), "companies.json missing"
    assert os.path.exists(os.path.join(DATA_DIR, "apex_portfolio.json")), "apex_portfolio.json missing"
    companies = json.load(open(os.path.join(DATA_DIR, "companies.json")))
    assert len(companies["targets"]) == 10, f"Expected 10 targets, got {len(companies['targets'])}"

def test_single_agent_runs():
    sys.path.insert(0, os.path.join(_BASE, "single_agent"))
    from baseline import SingleAgentBaseline
    agent = SingleAgentBaseline()
    result = agent.run()

    assert result["total_evaluated"] == 10
    assert result["passed_screening"] >= 5, "Too few passed screening"
    assert result["top_pick"] is not None
    assert len(result["ranked_companies"]) == result["passed_screening"]

    for c in result["ranked_companies"]:
        assert 0 <= c["composite_score"] <= 100, f"Score out of range for {c['name']}"
        assert c["rating"] in ["STRONG BUY", "BUY", "HOLD / CONSIDER", "WEAK HOLD", "PASS"]

def test_logs_generated():
    assert os.path.exists(os.path.join(LOGS_DIR, "run_1_single_agent.json"))
    assert os.path.exists(os.path.join(LOGS_DIR, "report_single_agent.json"))

    log = json.load(open(os.path.join(LOGS_DIR, "run_1_single_agent.json")))
    assert log["run_id"] == "single_agent_baseline"
    assert log["agent_type"] == "monolithic"
    assert len(log["log_entries"]) > 0

    report = json.load(open(os.path.join(LOGS_DIR, "report_single_agent.json")))
    assert "top_pick" in report

def test_screening_logic():
    companies = json.load(open(os.path.join(DATA_DIR, "companies.json")))
    block_settle = [c for c in companies["targets"] if c["name"] == "BlockSettle"][0]
    assert block_settle["revenue_2024"] < 10_000_000, "BlockSettle revenue should be below min"

    wealthGrid = [c for c in companies["targets"] if c["name"] == "WealthGrid"][0]
    assert wealthGrid["growth_rate_pct"] < 15.0, "WealthGrid growth should be below min"

if __name__ == "__main__":
    failed = 0
    tests = [test_data_exists, test_single_agent_runs, test_logs_generated, test_screening_logic]
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except Exception as e:
            print(f"FAIL: {t.__name__} — {e}")
            failed += 1

    print(f"\n{failed}/{len(tests)} tests failed")
    sys.exit(0 if failed == 0 else 1)
