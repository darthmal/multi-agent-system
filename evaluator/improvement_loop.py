"""Improvement Loop — closes the feedback loop between Evaluator and agents.

Flow:
  1. Load latest evaluator score (iteration N)
  2. Extract top improvements targeting specific agents
  3. Use LLM to rewrite the weakest agent prompt(s)
  4. Save improved prompts as prompt_v2.md (original preserved)
  5. Re-run evaluator using improved prompts
  6. Compare before/after scores → show improvement delta
  7. Loop can run again to improve further
"""

import json
import os
import sys
from copy import deepcopy
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from multi_agent.llm_client import call_agent

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
AGENTS_DIR = os.path.join(BASE_DIR, "multi_agent", "agents")
EVAL_DIR = os.path.join(BASE_DIR, "evaluator")
LOGS_DIR = os.path.join(BASE_DIR, "logs")


def load_json_file(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def latest_evaluation():
    scores = load_json_file(os.path.join(EVAL_DIR, "scores.json"))
    if not scores or not scores.get("iterations"):
        return None, 0
    iterations = scores["iterations"]
    return iterations[-1]["evaluation"], len(iterations)


def rewrite_prompt(agent_name, original_prompt, improvements):
    """Use LLM to improve a prompt based on evaluator suggestions."""
    system = (
        "You are a prompt engineering expert. Your job is to improve an existing "
        "AI agent prompt based on specific feedback from an architecture evaluator. "
        "Rewrite the prompt to address every improvement suggestion while preserving "
        "the original role, output JSON format, and evaluation criteria. "
        "Make changes concrete and specific — not vague. "
        "Return ONLY the improved prompt text (no JSON wrapper, no markdown fences)."
    )

    imp_text = "\n".join(
        f"- [{i.get('area', '')}] {i.get('specific_change', '')}"
        for i in improvements
    )

    user = f"""IMPROVEMENTS TO APPLY:
{imp_text}

ORIGINAL PROMPT:
---
{original_prompt}
---

Rewrite this prompt incorporating all improvements. Return the complete rewritten prompt."""
    
    result = call_agent(system, user, temperature=0.3, expect_json=False)
    # Strip markdown fences if the LLM wrapped the output
    text = result if isinstance(result, str) else str(result)
    if text.startswith("```"):
        lines = text.split("\n")
        while lines and lines[0].startswith("```"):
            lines.pop(0)
        while lines and lines[-1].startswith("```"):
            lines.pop()
        text = "\n".join(lines)
    return text


def run_improvement_loop():
    print("=" * 60)
    print("PHASE 5: IMPROVEMENT LOOP")
    print("=" * 60)

    # Step 1: Load latest evaluation
    evaluation, iter_num = latest_evaluation()
    if not evaluation:
        print("ERROR: No evaluation found. Run 'python evaluator\\evaluator.py' first.")
        return

    before_score = evaluation.get("overall_score", "N/A")
    print(f"\n[1] Loaded evaluation iteration #{iter_num}")
    print(f"    Baseline score: {before_score}/10")
    print(f"    Production readiness: {evaluation.get('production_readiness', 'N/A')}")

    # Step 2: Extract improvements
    improvements = evaluation.get("top_improvements", [])
    if not improvements:
        print("\n[2] No improvements suggested. Nothing to optimize.")
        return

    high_impact = [i for i in improvements if i.get("expected_impact") in ("HIGH", "MEDIUM")]
    if not high_impact:
        high_impact = improvements[:3]

    print(f"\n[2] Found {len(improvements)} improvements, {len(high_impact)} HIGH/MEDIUM impact")
    for i in high_impact:
        print(f"    #{i['priority']}: [{i['area']}] → {i.get('affected_agent', 'N/A')}")
        print(f"       {i['specific_change'][:100]}")

    # Step 3: Map improvements to agent prompts
    valid_agents = ["scout", "financial_analyst", "risk_analyst", "strategy_analyst", "report_writer"]
    agent_imps = {}
    for imp in high_impact:
        raw_agents = imp.get("affected_agent", "")
        # Split comma-separated agents, filter out non-prompt targets like "orchestrator"
        candidates = [a.strip().lower().replace(" ", "_") for a in raw_agents.split(",")]
        candidates = [a for a in candidates if a in valid_agents]

        if not candidates:
            area = imp.get("area", "").lower()
            map_area = {
                "scout": "scout", "financial": "financial_analyst",
                "risk": "risk_analyst", "strategy": "strategy_analyst",
                "report": "report_writer", "scoring": "financial_analyst",
                "prompt quality": evaluation.get("prompt_quality", {}).get("worst_agent", ""),
                "prompt": evaluation.get("prompt_quality", {}).get("worst_agent", ""),
                "output consistency": "report_writer",
            }
            mapped = map_area.get(area, "")
            if mapped and mapped in valid_agents:
                candidates = [mapped]
            else:
                print(f"    SKIP #{imp['priority']}: no prompt agent target ({area})")
                continue

        for agent in candidates:
            agent_imps.setdefault(agent, []).append(imp)

    if not agent_imps:
        # Fall back to weakest agent
        worst = evaluation.get("prompt_quality", {}).get("worst_agent", "")
        if worst:
            agent_imps[worst] = high_impact

    # Step 4: Rewrite prompts AND promote them to active
    print(f"\n[3] Rewriting prompts for {len(agent_imps)} agent(s)...")
    updated = {}

    for agent_name, imps in agent_imps.items():
        prompt_path = os.path.join(AGENTS_DIR, agent_name, "prompt.md")
        if not os.path.exists(prompt_path):
            print(f"    SKIP {agent_name}: prompt.md not found")
            continue

        with open(prompt_path, "r", encoding="utf-8") as f:
            original = f.read()

        print(f"\n    Rewriting {agent_name} ({len(imps)} improvements)...")
        try:
            improved = rewrite_prompt(agent_name, original, imps)
        except Exception as e:
            print(f"    FAILED: {e}")
            continue

        # Save improved version as prompt_v2.md (historical record)
        v2_path = os.path.join(AGENTS_DIR, agent_name, "prompt_v2.md")
        with open(v2_path, "w", encoding="utf-8") as f:
            f.write(improved)

        # Backup original before promoting (only first time — prompt_v1.md is the original baseline)
        v1_path = os.path.join(AGENTS_DIR, agent_name, "prompt_v1.md")
        if not os.path.exists(v1_path):
            os.rename(prompt_path, v1_path)
        else:
            os.remove(prompt_path)

        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(improved)

        print(f"    Original backed up → {v1_path}")
        print(f"    Improved promoted → {prompt_path} (NOW ACTIVE)")
        updated[agent_name] = {
            "backup_path": v1_path,
            "active_path": prompt_path,
            "improvements_applied": [i["specific_change"][:80] for i in imps]
        }

    if not updated:
        print("\nERROR: No prompts were updated.")
        return

    # Step 5: Re-evaluate using improved prompts
    print(f"\n[4] Re-evaluating with improved prompts...")
    print("    Temporarily using prompt_v2.md files for evaluation...")

    # Build evidence with v2 prompts where available
    evidence = {
        "system_description": "Multi-agent M&A system — IMPROVED using evaluator feedback loop.",
        "agent_prompts": {},
        "note": "This evaluation uses IMPROVED prompts (prompt_v2.md) where available.",
        "improvements_applied": {
            agent: data["improvements_applied"] for agent, data in updated.items()
        }
    }

    for agent in ["scout", "financial_analyst", "risk_analyst", "strategy_analyst", "report_writer"]:
        v2_path = os.path.join(AGENTS_DIR, agent, "prompt_v2.md")
        orig_path = os.path.join(AGENTS_DIR, agent, "prompt.md")
        if os.path.exists(v2_path):
            with open(v2_path, "r", encoding="utf-8") as f:
                evidence["agent_prompts"][agent] = f"**IMPROVED**\n{f.read()}"
        elif os.path.exists(orig_path):
            with open(orig_path, "r", encoding="utf-8") as f:
                evidence["agent_prompts"][agent] = f.read()

    evaluator_prompt_path = os.path.join(EVAL_DIR, "prompt.md")
    with open(evaluator_prompt_path, "r", encoding="utf-8") as f:
        evaluator_prompt = f.read()

    user_msg = json.dumps({
        "task": "Re-evaluate this system AFTER improvements. Compare to previous score if possible.",
        "evidence": evidence,
        "previous_score": before_score,
        "previous_evaluation": str(evaluation)[:5000]
    })

    print("    Calling evaluator LLM...")
    try:
        after_eval = call_agent(evaluator_prompt, user_msg, temperature=0.2)
    except Exception as e:
        print(f"    Evaluator error: {e}")
        after_eval = {"error": str(e), "overall_score": "FAILED"}

    after_score = after_eval.get("overall_score", "N/A")

    # Step 6: Compare
    print(f"\n{'═' * 55}")
    print("IMPROVEMENT LOOP RESULTS")
    print(f"{'═' * 55}")
    print(f"  Agents improved: {', '.join(updated.keys())}")
    print(f"  Before score:    {before_score}/10")
    print(f"  After score:     {after_score}/10")

    try:
        delta = round(float(after_score) - float(before_score), 1)
        if delta > 0:
            print(f"  Improvement:     +{delta}  (SCORE INCREASED)")
        elif delta < 0:
            print(f"  Change:          {delta}  (score decreased — prompts may need rollback)")
        else:
            print(f"  Change:          0.0  (no change)")
    except (ValueError, TypeError):
        print(f"  Change:          N/A (non-numeric score)")

    print(f"  WARNING: Evaluator score is subjective (LLM opinion of LLM prompts).")
    print(f"  Real validation requires A/B testing actual agent outputs.")
    print(f"  ROLLBACK: rename prompt_v1.md → prompt.md to restore originals.")

    # Save iteration
    scores = load_json_file(os.path.join(EVAL_DIR, "scores.json")) or {"iterations": []}
    scores["iterations"].append({
        "iteration": len(scores["iterations"]) + 1,
        "timestamp": datetime.now().isoformat(),
        "type": "post_improvement",
        "agents_improved": list(updated.keys()),
        "evaluation": after_eval
    })
    save_json_file(os.path.join(EVAL_DIR, "scores.json"), scores)

    # Save improvement log
    loop_log = {
        "phase": "improvement_loop",
        "date": datetime.now().isoformat(),
        "baseline_iteration": iter_num,
        "before_score": before_score,
        "after_score": after_score,
        "agents_improved": {a: d["improvements_applied"] for a, d in updated.items()},
        "delta": str(delta) if 'delta' in dir() else "N/A"
    }
    save_json_file(os.path.join(LOGS_DIR, "improvement_loop.json"), loop_log)

    print(f"  Log saved: logs/improvement_loop.json")
    print(f"  Scores saved: evaluator/scores.json (iteration {len(scores['iterations'])})")
    print(f"{'═' * 55}")

    return loop_log


if __name__ == "__main__":
    run_improvement_loop()
