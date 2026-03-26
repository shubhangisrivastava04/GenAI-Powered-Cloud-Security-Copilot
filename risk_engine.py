"""
Risk Detection Engine
CIS-aligned rule-based detection + Likelihood × Impact scoring (NIST-inspired)
Normalizes severity to a 0–100 scale
"""

import pandas as pd
import ast

# ── CIS-aligned rules ──────────────────────────────────────────────────────────
# Each rule: (rule_id, description, check_fn, likelihood_weight, impact_weight)
# Likelihood and impact are on 1–5 scales

RULES = [
    {
        "rule_id": "SEC-001",
        "name": "Encryption Disabled",
        "description": "Resource is not encrypted at rest.",
        "check": lambda r: r.get("encryption_enabled") in [False, "False", "false"],
        "likelihood": 4,
        "impact": 5,
        "category": "data_protection",
        "cis_ref": "CIS 2.1",
    },
    {
        "rule_id": "SEC-002",
        "name": "MFA Not Enabled",
        "description": "Multi-factor authentication is not enforced.",
        "check": lambda r: r.get("multi_factor_auth") in [False, "False", "false"],
        "likelihood": 4,
        "impact": 4,
        "category": "access_control",
        "cis_ref": "CIS 1.5",
    },
    {
        "rule_id": "SEC-003",
        "name": "Public Access Enabled",
        "description": "Resource is publicly accessible from the internet.",
        "check": lambda r: r.get("public_access") in [True, "True", "true"],
        "likelihood": 5,
        "impact": 4,
        "category": "network_exposure",
        "cis_ref": "CIS 5.1",
    },
    {
        "rule_id": "SEC-004",
        "name": "Patch Status Outdated",
        "description": "Resource is running outdated software / OS patches.",
        "check": lambda r: r.get("patch_status") == "outdated",
        "likelihood": 3,
        "impact": 4,
        "category": "vulnerability_management",
        "cis_ref": "CIS 6.2",
    },
    {
        "rule_id": "SEC-005",
        "name": "Risky Ports Open",
        "description": "High-risk ports (SSH/22, RDP/3389, DB ports) are exposed.",
        "check": lambda r: _has_risky_ports(r.get("open_ports", "[]")),
        "likelihood": 4,
        "impact": 4,
        "category": "network_exposure",
        "cis_ref": "CIS 9.2",
    },
    {
        "rule_id": "SEC-006",
        "name": "Logging Disabled",
        "description": "Audit logging is not enabled on this resource.",
        "check": lambda r: r.get("logging_enabled") in [False, "False", "false"],
        "likelihood": 2,
        "impact": 3,
        "category": "audit_logging",
        "cis_ref": "CIS 3.1",
    },
    {
        "rule_id": "SEC-007",
        "name": "Backup Not Enabled",
        "description": "No backup policy is configured.",
        "check": lambda r: r.get("backup_enabled") in [False, "False", "false"],
        "likelihood": 2,
        "impact": 4,
        "category": "resilience",
        "cis_ref": "CIS 10.1",
    },
    {
        "rule_id": "SEC-008",
        "name": "SSL/TLS Not Enforced",
        "description": "Traffic is not enforced over encrypted channels.",
        "check": lambda r: r.get("ssl_tls_enforced") in [False, "False", "false"] and r.get("resource_type") == "load_balancer",
        "likelihood": 3,
        "impact": 4,
        "category": "data_in_transit",
        "cis_ref": "CIS 14.4",
    },
    {
        "rule_id": "SEC-009",
        "name": "Storage Versioning Disabled",
        "description": "Object versioning is disabled, risking data loss.",
        "check": lambda r: r.get("versioning_enabled") in [False, "False", "false"] and r.get("resource_type") == "storage_bucket",
        "likelihood": 2,
        "impact": 3,
        "category": "data_protection",
        "cis_ref": "CIS 2.3",
    },
    {
        "rule_id": "SEC-010",
        "name": "High-Sensitivity Public Resource",
        "description": "Resource with high data sensitivity is publicly accessible.",
        "check": lambda r: r.get("data_sensitivity") == "high" and r.get("public_access") in [True, "True", "true"],
        "likelihood": 5,
        "impact": 5,
        "category": "data_protection",
        "cis_ref": "CIS 2.1 / 5.1",
    },
    {
        "rule_id": "SEC-011",
        "name": "Database Publicly Exposed",
        "description": "Database port is open to public access.",
        "check": lambda r: r.get("resource_type") == "database" and _has_db_ports(r.get("open_ports", "[]")),
        "likelihood": 5,
        "impact": 5,
        "category": "network_exposure",
        "cis_ref": "CIS 9.4",
    },
    {
        "rule_id": "SEC-012",
        "name": "DB Version Outdated",
        "description": "Database engine is not running the latest version.",
        "check": lambda r: r.get("resource_type") == "database" and r.get("db_version_current") in [False, "False", "false"],
        "likelihood": 3,
        "impact": 4,
        "category": "vulnerability_management",
        "cis_ref": "CIS 6.3",
    },
]

RISKY_PORTS = {22, 23, 3389, 3306, 5432, 27017, 6379, 9200, 1521}
DB_PORTS    = {3306, 5432, 27017, 1521, 1433}

def _parse_ports(raw):
    try:
        if isinstance(raw, list):
            return set(raw)
        return set(ast.literal_eval(str(raw)))
    except Exception:
        return set()

def _has_risky_ports(raw):
    return bool(_parse_ports(raw) & RISKY_PORTS)

def _has_db_ports(raw):
    return bool(_parse_ports(raw) & DB_PORTS)


# ── Sensitivity / criticality multipliers ─────────────────────────────────────
SENSITIVITY_MULT = {"high": 1.4, "medium": 1.0, "low": 0.7}
CRITICALITY_MULT = {"high": 1.4, "medium": 1.0, "low": 0.7}


def score_resource(row: dict) -> dict:
    """
    Run all rules against a single resource row.
    Returns enriched dict with violations, scores, and severity.
    """
    violations = []
    raw_score  = 0

    for rule in RULES:
        try:
            triggered = rule["check"](row)
        except Exception:
            triggered = False

        if triggered:
            base = rule["likelihood"] * rule["impact"]   # max 25
            violations.append({
                "rule_id":     rule["rule_id"],
                "name":        rule["name"],
                "description": rule["description"],
                "category":    rule["category"],
                "cis_ref":     rule["cis_ref"],
                "likelihood":  rule["likelihood"],
                "impact":      rule["impact"],
                "base_score":  base,
            })
            raw_score += base

    # Apply context multipliers
    sens_mult = SENSITIVITY_MULT.get(str(row.get("data_sensitivity", "medium")).lower(), 1.0)
    crit_mult = CRITICALITY_MULT.get(str(row.get("business_criticality", "medium")).lower(), 1.0)

    adjusted = raw_score * sens_mult * crit_mult

    # Normalize to 0–100 (theoretical max: 12 rules × 25 × 1.4 × 1.4 ≈ 588)
    MAX_PRACTICAL = 200
    risk_score = round(min(adjusted / MAX_PRACTICAL * 100, 100), 2)

    severity = (
        "critical" if risk_score >= 70 else
        "high"     if risk_score >= 45 else
        "medium"   if risk_score >= 20 else
        "low"
    )

    return {
        **row,
        "violation_count":  len(violations),
        "violations":       violations,
        "raw_risk_score":   round(raw_score, 2),
        "risk_score":       risk_score,
        "risk_severity":    severity,
    }


def run(df: pd.DataFrame) -> pd.DataFrame:
    """Run risk engine on entire dataframe. Returns df with risk columns added."""
    results = [score_resource(r) for r in df.to_dict("records")]
    out = pd.DataFrame(results)
    out["violations_summary"] = out["violations"].apply(
        lambda v: "; ".join(x["rule_id"] + ":" + x["name"] for x in v) if v else "none"
    )
    return out
