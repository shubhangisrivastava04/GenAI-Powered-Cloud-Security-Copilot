"""
GenAI Copilot
Uses Ollama (local) to generate:
- Context-aware remediation steps per resource
- ROI estimates
- Executive summaries for cross-team alignment

Make sure Ollama is running: `ollama serve`
And the model is pulled: `ollama pull llama3.2`
"""

import json
import requests

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL           = "llama3.2"   # change to any model you have pulled


def _call_ollama(prompt: str, system: str = "") -> str:
    """Make a single call to the local Ollama API."""
    payload = {
        "model":  MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    return response.json().get("response", "")


# ── Remediation explanation ────────────────────────────────────────────────────

REMEDIATION_PROMPT = """You are a cloud security and FinOps expert assistant.

Given this cloud resource record and its detected issues, provide:
1. A plain-English explanation of why this resource is flagged (2-3 sentences)
2. Step-by-step remediation actions (numbered, specific to the cloud provider)
3. Estimated ROI / business justification for fixing it

Resource details:
{resource_json}

Detected violations:
{violations}

Cost waste flag: {waste_flag}
Waste reason: {waste_reason}
Estimated monthly savings if fixed: ${savings_monthly}
Unified priority score: {unified_score}/100 ({priority_label})

Respond in this exact JSON format with no extra text or markdown:
{{
  "explanation": "...",
  "remediation_steps": ["step 1", "step 2", "step 3"],
  "roi_estimate": "...",
  "urgency_note": "..."
}}"""


def get_remediation(resource: dict) -> dict:
    """Generate remediation guidance for a single resource."""
    violations_text = "; ".join(
        f"{v['rule_id']} - {v['name']}"
        for v in resource.get("violations", [])
    ) or "none"

    prompt = REMEDIATION_PROMPT.format(
        resource_json   = json.dumps({
            k: v for k, v in resource.items()
            if k not in ("violations",)
        }, indent=2, default=str),
        violations      = violations_text,
        waste_flag      = resource.get("waste_flag", "none"),
        waste_reason    = resource.get("waste_reason", ""),
        savings_monthly = resource.get("savings_monthly", 0),
        unified_score   = resource.get("unified_score", 0),
        priority_label  = resource.get("priority_label", ""),
    )

    raw = _call_ollama(prompt)

    try:
        clean = raw.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except Exception:
        return {
            "explanation":       raw,
            "remediation_steps": [],
            "roi_estimate":      "",
            "urgency_note":      "",
        }


# ── Executive summary ─────────────────────────────────────────────────────────

EXEC_SUMMARY_SYSTEM = (
    "You are a cloud risk and cost advisor preparing a brief for the CTO and CFO. "
    "Be concise and boardroom-ready: no jargon, no bullet points, just clear prose."
)

EXEC_SUMMARY_PROMPT = """Cloud environment summary:
- Total resources scanned: {total_resources}
- Resources with security violations: {risk_count} ({risk_pct}%)
- Critical/High severity: {critical_high_count}
- Wasteful resources (idle/overprovisioned): {waste_count} ({waste_pct}%)
- Total monthly cloud spend: ${total_monthly_cost}
- Potential monthly savings identified: ${potential_monthly_savings}
- Potential annual savings identified: ${potential_annual_savings}
- Top affected teams: {top_teams}
- Top violated rules: {top_rules}

Write a concise executive summary (4-6 sentences) that:
1. States the current risk and cost posture plainly
2. Highlights the most urgent findings
3. Quantifies the financial opportunity
4. Recommends immediate next steps"""


def get_executive_summary(stats: dict, top_teams: list, top_rules: list) -> str:
    """Generate executive summary from aggregated stats."""
    prompt = EXEC_SUMMARY_PROMPT.format(
        total_resources           = stats.get("total_resources", 0),
        risk_count                = stats.get("risk_count", 0),
        risk_pct                  = stats.get("risk_pct", 0),
        critical_high_count       = stats.get("critical_high_count", 0),
        waste_count               = stats.get("waste_count", 0),
        waste_pct                 = stats.get("waste_pct", 0),
        total_monthly_cost        = stats.get("total_monthly_cost", 0),
        potential_monthly_savings = stats.get("potential_monthly_savings", 0),
        potential_annual_savings  = stats.get("potential_annual_savings", 0),
        top_teams                 = ", ".join(top_teams[:5]),
        top_rules                 = ", ".join(top_rules[:5]),
    )
    return _call_ollama(prompt, system=EXEC_SUMMARY_SYSTEM)


# ── Chat interface ─────────────────────────────────────────────────────────────

CHAT_SYSTEM = """You are a GenAI Cloud Risk and Cost Copilot. You have access to a summary of the cloud environment.
Answer questions about cloud security posture, cost optimization, remediation priorities, and compliance.
Be concise, specific, and actionable. When relevant, cite specific resource IDs or teams.

Environment context:
{context}"""


def chat(user_message: str, context: str, history: list) -> tuple[str, list]:
    """
    Multi-turn chat with the copilot.
    Returns (reply, updated_history).
    history = list of {"role": "user"/"assistant", "content": "..."}
    """
    system_prompt = CHAT_SYSTEM.format(context=context)

    # Build a single prompt string from history for Ollama
    conversation = ""
    for msg in history:
        role    = "User" if msg["role"] == "user" else "Assistant"
        content = msg.get("content", "")
        conversation += f"{role}: {content}\n"
    conversation += f"User: {user_message}\nAssistant:"

    reply = _call_ollama(conversation, system=system_prompt)

    updated_history = history + [
        {"role": "user",      "content": user_message},
        {"role": "assistant", "content": reply},
    ]
    return reply, updated_history