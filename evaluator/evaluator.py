"""Evaluator Agent — scores the multi-agent architecture 1-10.

Gathers all agent prompts, orchestrator code, benchmark results, and
sample outputs, then calls DeepSeek to produce an architectural grade.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from multi_agent.llm_client import call_agent

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
AGENTS_DIR = os.path.join(BASE_DIR, "multi_agent", "agents")
EVAL_DIR = os.path.join(BASE_DIR, "evaluator")
LOGS_DIR = os.path.join(BASE_DIR, "logs")


def load_file(path, default=""):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return default


def load_json_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_agent_outputs():
    outputs = {}
    for agent in ["scout", "financial_analyst", "risk_analyst", "strategy_analyst", "report_writer"]:
        mem_dir = os.path.join(AGENTS_DIR, agent, "memory")
        agent_outputs = {}
        if os.path.isdir(mem_dir):
            for fname in os.listdir(mem_dir):
                if fname.endswith(".json"):
                    with open(os.path.join(mem_dir, fname), "r") as f:
                        agent_outputs[fname.replace(".json", "")] = json.load(f)
        outputs[agent] = agent_outputs
    return outputs


def gather_evidence():
    return {
        "system_description": "Multi-agent M&A target evaluation system for Apex Capital Partners. Orchestrator coordinates 5 specialist agents (scout, financial_analyst, risk_analyst, strategy_analyst, report_writer) using real DeepSeek LLM calls. Fan-out strategy parallelizes the 3 analysis agents across all screened companies.",
        "agent_prompts": {
            agent: load_file(os.path.join(AGENTS_DIR, agent, "prompt.md"))
            for agent in ["scout", "financial_analyst", "risk_analyst", "strategy_analyst", "report_writer"]
        },
        "orchestrator_code": load_file(os.path.join(BASE_DIR, "multi_agent", "orchestrator.py"))[:8000],
        "fanout_code": load_file(os.path.join(BASE_DIR, "multi_agent", "fanout.py"))[:6000],
        "benchmark_data": load_json_file(os.path.join(LOGS_DIR, "run_3_fanout_benchmark.json")),
        "sample_outputs": load_agent_outputs(),
        "multi_agent_report": load_json_file(os.path.join(LOGS_DIR, "report_multi_agent.json")),
        "single_agent_report": load_json_file(os.path.join(LOGS_DIR, "report_single_agent.json")),
    }


def run_evaluator():
    print("=" * 60)
    print("PHASE 4: EVALUATOR AGENT")
    print("=" * 60)
    print("Gathering evidence from all agents...")

    evidence = gather_evidence()
    evidence_str = json.dumps(evidence, indent=2, default=str)

    # Truncate if needed (DeepSeek context is large, but be safe)
    if len(evidence_str) > 80000:
        evidence_str = evidence_str[:80000]
    print(f"Evidence size: {len(evidence_str)} chars")

    evaluator_prompt = load_file(os.path.join(EVAL_DIR, "prompt.md"))
    user_message = json.dumps({
        "task": "Evaluate this multi-agent M&A system. Score it 1-10.",
        "evidence": json.loads(evidence_str) if len(evidence_str) < 80000 else {"truncated": True, "raw": evidence_str}
    })

    print("Calling evaluator LLM...")
    try:
        evaluation = call_agent(evaluator_prompt, json.dumps({"task": "Evaluate this multi-agent M&A system. Score it 1-10.", "evidence": evidence}), temperature=0.2)
    except Exception as e:
        print(f"Evaluator error: {e}")
        evaluation = {"error": str(e), "overall_score": 0}

    scores_path = os.path.join(EVAL_DIR, "scores.json")
    existing = load_json_file(scores_path) or {"iterations": []}
    iteration = len(existing["iterations"]) + 1

    existing["iterations"].append({
        "iteration": iteration,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "evaluation": evaluation
    })

    os.makedirs(EVAL_DIR, exist_ok=True)
    with open(scores_path, "w") as f:
        json.dump(existing, f, indent=2, default=str)

    # Print summary
    print(f"\n  Overall Score: {evaluation.get('overall_score', 'N/A')} / 10")
    print(f"  Production Readiness: {evaluation.get('production_readiness', 'N/A')}")
    print(f"  Summary: {evaluation.get('summary', 'N/A')[:200]}")

    arch = evaluation.get("architecture_design", {})
    print(f"\n  Architecture: {arch.get('score', 'N/A')}/10")
    for s in arch.get("strengths", [])[:2]:
        print(f"    + {s}")
    for w in arch.get("weaknesses", [])[:2]:
        print(f"    - {w}")

    pq = evaluation.get("prompt_quality", {})
    print(f"\n  Prompt Quality: {pq.get('score', 'N/A')}/10")
    print(f"    Best: {pq.get('best_agent', 'N/A')} | Worst: {pq.get('worst_agent', 'N/A')}")

    oq = evaluation.get("output_quality", {})
    print(f"\n  Output Quality: {oq.get('score', 'N/A')}/10")
    print(f"    Hallucination Risk: {oq.get('hallucination_risk', 'N/A')}")

    sc = evaluation.get("scalability", {})
    print(f"\n  Scalability: {sc.get('score', 'N/A')}/10")
    print(f"    Bottleneck: {sc.get('bottleneck', 'N/A')}")

    improvements = evaluation.get("top_improvements", [])
    if improvements:
        print(f"\n  Top {len(improvements)} Improvements:")
        for imp in improvements:
            print(f"    #{imp['priority']}: [{imp['area']}] {imp['specific_change'][:90]}")

    print(f"\n[EVAL] Saved to {scores_path}")
    return evaluation


if __name__ == "__main__":
    run_evaluator()
