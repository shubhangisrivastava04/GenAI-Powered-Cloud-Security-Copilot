"""
Main Pipeline
Orchestrates: Data → Risk Engine → Cost Engine → Prioritization → Copilot → Output
"""

import pandas as pd
import json
import os
from collections import Counter

import risk_engine
import cost_engine
import prioritization
import copilot


def build_context_string(df: pd.DataFrame, finops_summary: dict) -> str:
    """Build a compact context string for the copilot chat."""
    top_teams = (
        df.groupby("owner_team")["unified_score"]
        .mean()
        .sort_values(ascending=False)
        .head(5)
        .index.tolist()
    )
    sev_counts = df["risk_severity"].value_counts().to_dict()
    waste_types = df["waste_flag"].value_counts().to_dict()

    return f"""
Total resources: {len(df)}
Risk severity breakdown: {sev_counts}
Waste breakdown: {waste_types}
Total monthly cost: ${finops_summary['total_monthly_cost']:,.2f}
Potential monthly savings: ${finops_summary['potential_monthly_savings']:,.2f}
Potential annual savings: ${finops_summary['potential_annual_savings']:,.2f}
Top risk teams: {', '.join(top_teams)}
P1 resources: {len(df[df['priority'] == 'P1'])}
P2 resources: {len(df[df['priority'] == 'P2'])}
""".strip()


def run_pipeline(
    csv_path: str,
    output_dir: str = "output",
    top_n_remediation: int = 5,
    generate_exec_summary: bool = True,
) -> dict:
    """
    Full pipeline run.
    Returns dict with dataframes and summary stats.
    """
    os.makedirs(output_dir, exist_ok=True)

    # ── 1. Load data ──────────────────────────────────────────────────────────
    print("📥 Loading dataset...")
    df = pd.read_csv(csv_path)
    print(f"   Loaded {len(df)} resources across {df['resource_type'].nunique()} types")

    # ── 2. Risk engine ────────────────────────────────────────────────────────
    print("\n🔍 Running Risk Detection Engine...")
    df = risk_engine.run(df)
    risk_flagged = len(df[df["violation_count"] > 0])
    print(f"   {risk_flagged} resources with violations ({risk_flagged/len(df)*100:.1f}%)")
    sev = df["risk_severity"].value_counts()
    for s in ["critical", "high", "medium", "low"]:
        print(f"   {s.capitalize():10} {sev.get(s, 0)}")

    # ── 3. Cost engine ────────────────────────────────────────────────────────
    print("\n💰 Running Cost Optimization Engine...")
    df = cost_engine.run(df)
    finops = cost_engine.summary(df)
    print(f"   Total monthly spend:    ${finops['total_monthly_cost']:,.2f}")
    print(f"   Potential monthly save: ${finops['potential_monthly_savings']:,.2f}")
    print(f"   Potential annual save:  ${finops['potential_annual_savings']:,.2f}")
    print(f"   Idle resources:         {finops['idle_count']}")
    print(f"   Overprovisioned:        {finops['overprovisioned_count']}")

    # ── 4. Prioritization ─────────────────────────────────────────────────────
    print("\n📊 Computing Unified Impact Scores...")
    df = prioritization.run(df)
    p_counts = df["priority"].value_counts()
    for p in ["P1", "P2", "P3", "P4"]:
        print(f"   {p} ({prioritization.PRIORITY_LABELS[p]}): {p_counts.get(p, 0)}")

    # ── 5. Save scored dataset ────────────────────────────────────────────────
    scored_path = os.path.join(output_dir, "cloud_resources_scored.csv")
    # Save without the violations list column (it's a list of dicts, not CSV-friendly)
    df.drop(columns=["violations"], errors="ignore").to_csv(scored_path, index=False)
    print(f"\n💾 Scored dataset saved → {scored_path}")

    # Save top 20 remediation queue
    queue = prioritization.top_n(df, 20)
    queue_path = os.path.join(output_dir, "remediation_queue.csv")
    queue.to_csv(queue_path, index=False)
    print(f"💾 Remediation queue saved → {queue_path}")

    # ── 6. GenAI Copilot — per-resource remediation ───────────────────────────
    print(f"\n🤖 Generating AI remediation for top {top_n_remediation} resources...")
    top_resources = df.head(top_n_remediation).to_dict("records")
    remediations  = []

    for i, resource in enumerate(top_resources):
        print(f"   [{i+1}/{top_n_remediation}] {resource['resource_id']} ({resource['resource_type']})...")
        result = copilot.get_remediation(resource)
        remediations.append({
            "resource_id":    resource["resource_id"],
            "resource_type":  resource["resource_type"],
            "priority":       resource["priority"],
            "unified_score":  resource["unified_score"],
            **result,
        })

    remediation_path = os.path.join(output_dir, "ai_remediations.json")
    with open(remediation_path, "w") as f:
        json.dump(remediations, f, indent=2)
    print(f"💾 AI remediations saved → {remediation_path}")

    # ── 7. Executive summary ──────────────────────────────────────────────────
    exec_summary = ""
    if generate_exec_summary:
        print("\n📝 Generating executive summary...")
        top_teams = (
            df.groupby("owner_team")["unified_score"]
            .mean().sort_values(ascending=False).head(5).index.tolist()
        )
        # Top violated rules
        all_violations = [v for vlist in df["violations"] for v in vlist]
        top_rules = [name for name, _ in Counter(v["name"] for v in all_violations).most_common(5)]

        stats = {
            **finops,
            "risk_count":          risk_flagged,
            "risk_pct":            round(risk_flagged / len(df) * 100, 1),
            "critical_high_count": int(sev.get("critical", 0) + sev.get("high", 0)),
            "waste_count":         finops["wasteful_resources"],
            "waste_pct":           finops["waste_pct"],
        }
        exec_summary = copilot.get_executive_summary(stats, top_teams, top_rules)
        summary_path = os.path.join(output_dir, "executive_summary.txt")
        with open(summary_path, "w") as f:
            f.write(exec_summary)
        print(f"💾 Executive summary saved → {summary_path}")
        print(f"\n{'─'*60}\n{exec_summary}\n{'─'*60}")

    # ── 8. Return all artifacts ───────────────────────────────────────────────
    return {
        "df":              df,
        "finops_summary":  finops,
        "remediations":    remediations,
        "exec_summary":    exec_summary,
        "context_string":  build_context_string(df, finops),
    }


# ── Interactive chat loop (CLI) ───────────────────────────────────────────────

def chat_loop(context: str):
    print("\n🤖 Cloud Copilot ready. Type 'exit' to quit.\n")
    history = []
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("exit", "quit"):
            break
        if not user_input:
            continue
        reply, history = copilot.chat(user_input, context, history)
        print(f"\nCopilot: {reply}\n")


if __name__ == "__main__":
    results = run_pipeline(
        csv_path            = "cloud_resources.csv",
        output_dir          = "output",
        top_n_remediation   = 5,
        generate_exec_summary = True,
    )
    chat_loop(results["context_string"])
