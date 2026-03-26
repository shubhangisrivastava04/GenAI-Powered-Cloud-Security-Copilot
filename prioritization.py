"""
Prioritization Engine
Computes Unified Impact Score combining risk + cost waste.
Outputs a ranked remediation queue.
"""

import pandas as pd

# Weights for unified score (sum to 1.0)
RISK_WEIGHT = 0.65
COST_WEIGHT = 0.35

# Cost normalization ceiling (monthly savings above this = max cost score)
MAX_SAVINGS_FOR_NORM = 500.0

PRIORITY_LABELS = {
    "P1": "Immediate Action",
    "P2": "High Priority",
    "P3": "Medium Priority",
    "P4": "Low Priority",
}


def compute_unified_score(row: dict) -> dict:
    risk_score    = float(row.get("risk_score", 0))
    savings_mo    = float(row.get("savings_monthly", 0))

    # Normalize cost savings to 0–100
    cost_score = min(savings_mo / MAX_SAVINGS_FOR_NORM * 100, 100)

    unified = round(RISK_WEIGHT * risk_score + COST_WEIGHT * cost_score, 2)

    # Priority tier
    if unified >= 70:
        priority = "P1"
    elif unified >= 45:
        priority = "P2"
    elif unified >= 20:
        priority = "P3"
    else:
        priority = "P4"

    return {
        **row,
        "cost_score":     round(cost_score, 2),
        "unified_score":  unified,
        "priority":       priority,
        "priority_label": PRIORITY_LABELS[priority],
    }


def run(df: pd.DataFrame) -> pd.DataFrame:
    """Compute unified scores and return ranked remediation queue."""
    results = [compute_unified_score(r) for r in df.to_dict("records")]
    out = pd.DataFrame(results)
    out = out.sort_values("unified_score", ascending=False).reset_index(drop=True)
    out["rank"] = out.index + 1
    return out


def top_n(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    cols = [
        "rank", "resource_id", "resource_name", "resource_type",
        "cloud_provider", "environment", "owner_team",
        "risk_score", "risk_severity", "waste_flag",
        "savings_monthly", "unified_score", "priority", "priority_label",
        "violations_summary",
    ]
    available = [c for c in cols if c in df.columns]
    return df[available].head(n)
