"""
Cost Optimization Engine
Utilization-based FinOps analysis:
- Idle resource detection
- Overprovisioning detection
- Annual savings estimation
"""

import pandas as pd

# ── Thresholds (FinOps Foundation + AWS Cost Optimization best practices) ──────
IDLE_CPU_THRESHOLD     = 10.0   # % — below this = idle
IDLE_MEM_THRESHOLD     = 20.0   # %
OVERPROV_CPU_THRESHOLD = 25.0   # % — below this (but not idle) = overprovisioned
OVERPROV_MEM_THRESHOLD = 40.0   # %
MIN_UPTIME_FOR_IDLE    = 7      # days — ignore very new resources

# Right-sizing savings assumptions (% of monthly cost recoverable)
SAVINGS_RATE = {
    "idle":            0.90,   # idle → terminate or stop: recover ~90%
    "overprovisioned": 0.40,   # downsize one tier: recover ~40%
    "rightsized":      0.00,
}

# Storage waste: buckets with no lifecycle policy and large size
STORAGE_WASTE_THRESHOLD_GB = 100
STORAGE_SAVINGS_RATE       = 0.30


def _safe_float(val, default=None):
    try:
        f = float(val)
        return f if f >= 0 else default
    except (TypeError, ValueError):
        return default


def analyze_resource(row: dict) -> dict:
    rtype       = row.get("resource_type", "")
    cost        = _safe_float(row.get("cost_per_month"), 0)
    uptime      = _safe_float(row.get("uptime_days"), 0)
    cpu         = _safe_float(row.get("cpu_utilization"))
    mem         = _safe_float(row.get("memory_utilization"))

    waste_flag       = "none"
    waste_reason     = ""
    savings_monthly  = 0.0
    utilization_tier = "unknown"

    # ── Compute & Database ────────────────────────────────────────────────────
    if rtype in ("compute_instance", "database"):
        if cpu is not None and mem is not None and uptime >= MIN_UPTIME_FOR_IDLE:
            if cpu < IDLE_CPU_THRESHOLD and mem < IDLE_MEM_THRESHOLD:
                waste_flag       = "idle"
                waste_reason     = f"CPU {cpu}% and memory {mem}% both below idle thresholds"
                utilization_tier = "idle"
                savings_monthly  = round(cost * SAVINGS_RATE["idle"], 2)

            elif cpu < OVERPROV_CPU_THRESHOLD and mem < OVERPROV_MEM_THRESHOLD:
                waste_flag       = "overprovisioned"
                waste_reason     = f"CPU {cpu}% and memory {mem}% indicate right-sizing opportunity"
                utilization_tier = "overprovisioned"
                savings_monthly  = round(cost * SAVINGS_RATE["overprovisioned"], 2)

            else:
                utilization_tier = "rightsized"

        elif cpu is not None:
            utilization_tier = "insufficient_data"

    # ── Storage ──────────────────────────────────────────────────────────────
    elif rtype == "storage_bucket":
        size_gb          = _safe_float(row.get("size_gb"), 0)
        lifecycle_policy = str(row.get("lifecycle_policy", "")).lower() in ("true", "1", "yes")
        replication      = str(row.get("replication_enabled", "")).lower() in ("true", "1", "yes")

        if size_gb > STORAGE_WASTE_THRESHOLD_GB and not lifecycle_policy:
            waste_flag       = "overprovisioned"
            waste_reason     = f"Large bucket ({size_gb:.0f} GB) with no lifecycle policy"
            utilization_tier = "overprovisioned"
            savings_monthly  = round(cost * STORAGE_SAVINGS_RATE, 2)
        elif replication and size_gb < 10:
            waste_flag       = "overprovisioned"
            waste_reason     = f"Replication enabled on a tiny bucket ({size_gb:.1f} GB) — likely unnecessary"
            utilization_tier = "overprovisioned"
            savings_monthly  = round(cost * 0.20, 2)
        else:
            utilization_tier = "rightsized"

    # ── Load Balancer ─────────────────────────────────────────────────────────
    elif rtype == "load_balancer":
        rps = _safe_float(row.get("requests_per_sec"), 0)
        if rps < 1.0 and uptime >= MIN_UPTIME_FOR_IDLE:
            waste_flag       = "idle"
            waste_reason     = f"Load balancer receiving < 1 req/sec (actual: {rps})"
            utilization_tier = "idle"
            savings_monthly  = round(cost * SAVINGS_RATE["idle"], 2)
        else:
            utilization_tier = "rightsized"

    savings_annual = round(savings_monthly * 12, 2)

    return {
        **row,
        "waste_flag":        waste_flag,
        "waste_reason":      waste_reason,
        "utilization_tier":  utilization_tier,
        "savings_monthly":   savings_monthly,
        "savings_annual":    savings_annual,
    }


def run(df: pd.DataFrame) -> pd.DataFrame:
    """Run cost engine on entire dataframe. Returns df with cost columns added."""
    results = [analyze_resource(r) for r in df.to_dict("records")]
    return pd.DataFrame(results)


def summary(df: pd.DataFrame) -> dict:
    """Return high-level FinOps summary stats."""
    waste = df[df["waste_flag"] != "none"]
    return {
        "total_resources":         len(df),
        "wasteful_resources":      len(waste),
        "waste_pct":               round(len(waste) / len(df) * 100, 1),
        "total_monthly_cost":      round(df["cost_per_month"].apply(lambda x: _safe_float(x, 0)).sum(), 2),
        "potential_monthly_savings": round(df["savings_monthly"].sum(), 2),
        "potential_annual_savings":  round(df["savings_annual"].sum(), 2),
        "idle_count":              len(df[df["waste_flag"] == "idle"]),
        "overprovisioned_count":   len(df[df["waste_flag"] == "overprovisioned"]),
    }
