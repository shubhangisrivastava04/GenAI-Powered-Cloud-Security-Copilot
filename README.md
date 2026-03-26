# ☁️ GenAI-Powered Cloud Security Copilot

An AI-driven pipeline that scans cloud resources for security violations and cost waste, prioritizes them by risk, and generates actionable remediation guidance using a local LLM (Ollama/Llama 3.2).

---

## Features

- **Risk Detection Engine** — CIS-aligned rule-based scanning (encryption, MFA, public access, patch status, open ports, and more) with NIST-inspired Likelihood × Impact scoring
- **Cost Optimization Engine** — Flags idle and overprovisioned resources and estimates monthly/annual savings
- **Unified Prioritization** — Combines risk and cost scores into a P1–P4 priority queue
- **GenAI Remediation** — Uses a local Ollama LLM to generate plain-English explanations, step-by-step fixes, and ROI estimates per resource
- **Executive Summary** — Auto-generates a boardroom-ready summary for CTO/CFO stakeholders
- **Interactive Chat** — CLI chat loop to query your cloud posture in natural language
- **Streamlit Dashboard** — Visual interface with Plotly charts and an embedded copilot chat

---

## Architecture

```
CSV Data → Risk Engine → Cost Engine → Prioritization → GenAI Copilot → Output
                                                               ↓
                                                    Streamlit Dashboard
```

---

## Prerequisites

- Python 3.9+
- [Ollama](https://ollama.com) running locally (`ollama serve`)
- Llama 3.2 model pulled (`ollama pull llama3.2`)

---

## Installation

```bash
git clone https://github.com/your-org/GenAI-Powered-Cloud-Security-Copilot.git
cd GenAI-Powered-Cloud-Security-Copilot
pip install -r requirements.txt
```

---

## Usage

### CLI Pipeline

```bash
python main.py
```

Expects a `cloud_resources.csv` in the project root. Outputs to the `output/` directory:

| File | Description |
|------|-------------|
| `cloud_resources_scored.csv` | Full dataset with risk, cost, and priority scores |
| `remediation_queue.csv` | Top 20 resources ranked by unified impact score |
| `ai_remediations.json` | AI-generated remediation steps for top N resources |
| `executive_summary.txt` | Boardroom-ready summary prose |

### Streamlit Dashboard

```bash
streamlit run dashboard.py
```

---

## Modules

| File | Role |
|------|------|
| `main.py` | Orchestrates the full pipeline and CLI chat loop |
| `risk_engine.py` | CIS-aligned rule evaluation and severity scoring |
| `cost_engine.py` | Waste detection and savings estimation |
| `prioritization.py` | Unified P1–P4 scoring and ranking |
| `copilot.py` | Ollama API calls for remediation, summaries, and chat |
| `dashboard.py` | Streamlit + Plotly interactive UI |

---

## Configuration

In `copilot.py`, update these constants to point to your Ollama instance or swap models:

```python
OLLAMA_BASE_URL = "http://localhost:11434"
MODEL           = "llama3.2"
```

---

## Input Format

The pipeline expects a CSV with cloud resource records. Required columns include fields like `resource_id`, `resource_type`, `owner_team`, `encryption_enabled`, `multi_factor_auth`, `public_access`, `patch_status`, `open_ports`, and cost-related fields.

---

## Requirements

```
pandas>=2.0.0
numpy>=1.24.0
requests>=2.31.0
streamlit>=1.35.0
plotly>=5.18.0
```
