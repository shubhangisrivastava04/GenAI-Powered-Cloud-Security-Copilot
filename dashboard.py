"""
Streamlit Dashboard
Interactive visualization for the Cloud Risk & Cost Copilot
Run: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import json
import os
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter

import risk_engine
import cost_engine
import prioritization
import copilot

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title  = "Cloud Risk & Cost Copilot",
    page_icon   = "☁️",
    layout      = "wide",
    initial_sidebar_state = "expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0f1117; }
    .metric-card {
        background: linear-gradient(135deg, #1e2130, #252a3d);
        border: 1px solid #2e3450;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    .metric-value { font-size: 2.2rem; font-weight: 700; }
    .metric-label { color: #8892b0; font-size: 0.85rem; margin-top: 4px; }
    .critical { color: #ff4b6e; }
    .high     { color: #ff8c42; }
    .medium   { color: #ffd166; }
    .low      { color: #06d6a0; }
    .p1 { background: rgba(255,75,110,0.15); border-left: 3px solid #ff4b6e; padding: 8px 12px; border-radius: 4px; }
    .p2 { background: rgba(255,140,66,0.15); border-left: 3px solid #ff8c42; padding: 8px 12px; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ── State ─────────────────────────────────────────────────────────────────────
if "df"           not in st.session_state: st.session_state.df           = None
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "context"      not in st.session_state: st.session_state.context      = ""
if "pipeline_run" not in st.session_state: st.session_state.pipeline_run = False

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/cloud.png", width=60)
    st.title("Cloud Copilot")
    st.caption("GenAI-Powered Risk & Cost Intelligence")
    st.divider()

    uploaded = st.file_uploader("Upload cloud_resources.csv", type="csv")

    if uploaded:
        df_raw = pd.read_csv(uploaded)
        if st.button("▶ Run Pipeline", type="primary", use_container_width=True):
            with st.spinner("Running Risk Engine..."):
                df = risk_engine.run(df_raw)
            with st.spinner("Running Cost Engine..."):
                df = cost_engine.run(df)
            with st.spinner("Computing Unified Scores..."):
                df = prioritization.run(df)

            finops = cost_engine.summary(df)
            # Build context
            top_teams = (
                df.groupby("owner_team")["unified_score"]
                .mean().sort_values(ascending=False).head(5).index.tolist()
            )
            all_v = [v for vlist in df["violations"] for v in vlist]
            top_rules = [n for n, _ in Counter(v["name"] for v in all_v).most_common(5)]
            context = f"""
Resources: {len(df)} | Monthly spend: ${finops['total_monthly_cost']:,.0f}
Potential savings: ${finops['potential_annual_savings']:,.0f}/yr
P1 items: {len(df[df['priority']=='P1'])} | Critical: {len(df[df['risk_severity']=='critical'])}
Top teams by risk: {', '.join(top_teams)}
Top violations: {', '.join(top_rules)}
            """.strip()

            st.session_state.df           = df
            st.session_state.context      = context
            st.session_state.pipeline_run = True
            st.session_state.finops       = finops
            st.success("Pipeline complete!")

    st.divider()
    nav = st.radio("Navigate", ["Overview", "Risk Analysis", "Cost Optimization", "Remediation Queue", "AI Copilot"])

# ── Guard ─────────────────────────────────────────────────────────────────────
if not st.session_state.pipeline_run:
    st.title("☁️ Cloud Risk & Cost Copilot")
    st.info("Upload your `cloud_resources.csv` in the sidebar and click **Run Pipeline** to begin.")
    st.stop()

df     = st.session_state.df
finops = st.session_state.finops


# ══════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
if nav == "Overview":
    st.title("☁️ Cloud Environment Overview")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total Resources",    len(df))
    with c2:
        critical = len(df[df["risk_severity"] == "critical"])
        st.metric("Critical Risk",      critical, delta=f"{critical/len(df)*100:.1f}%", delta_color="inverse")
    with c3:
        st.metric("Monthly Spend",      f"${finops['total_monthly_cost']:,.0f}")
    with c4:
        st.metric("Monthly Savings Opp.", f"${finops['potential_monthly_savings']:,.0f}", delta="identified")
    with c5:
        p1 = len(df[df["priority"] == "P1"])
        st.metric("P1 Actions",         p1, delta="immediate", delta_color="inverse")

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Risk Severity Distribution")
        sev_order = ["critical", "high", "medium", "low"]
        sev_colors = {"critical": "#ff4b6e", "high": "#ff8c42", "medium": "#ffd166", "low": "#06d6a0"}
        sev_counts = df["risk_severity"].value_counts().reindex(sev_order).fillna(0)
        fig = px.bar(
            x=sev_counts.index, y=sev_counts.values,
            color=sev_counts.index,
            color_discrete_map=sev_colors,
            labels={"x": "Severity", "y": "Count"},
        )
        fig.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Resources by Cloud Provider")
        prov = df["cloud_provider"].value_counts()
        fig2 = px.pie(values=prov.values, names=prov.index, hole=0.45,
                      color_discrete_sequence=px.colors.qualitative.Bold)
        fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig2, use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Priority Queue Breakdown")
        pri = df["priority"].value_counts().reindex(["P1","P2","P3","P4"]).fillna(0)
        fig3 = px.bar(x=pri.index, y=pri.values,
                      color=pri.index,
                      color_discrete_map={"P1":"#ff4b6e","P2":"#ff8c42","P3":"#ffd166","P4":"#06d6a0"})
        fig3.update_layout(showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        st.subheader("Cost Waste by Team")
        team_waste = df.groupby("owner_team")["savings_annual"].sum().sort_values(ascending=True).tail(8)
        fig4 = px.bar(x=team_waste.values, y=team_waste.index, orientation="h",
                      labels={"x": "Annual Savings Opportunity ($)", "y": "Team"},
                      color=team_waste.values, color_continuous_scale="Oranges")
        fig4.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white", coloraxis_showscale=False)
        st.plotly_chart(fig4, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# RISK ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
elif nav == "Risk Analysis":
    st.title("🔍 Risk Analysis")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top Violated Rules")
        all_v = [v for vlist in df["violations"] for v in vlist]
        if all_v:
            rule_counts = Counter(v["name"] for v in all_v)
            rc_df = pd.DataFrame(rule_counts.most_common(10), columns=["Rule", "Count"])
            fig = px.bar(rc_df, x="Count", y="Rule", orientation="h",
                         color="Count", color_continuous_scale="Reds")
            fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                              font_color="white", coloraxis_showscale=False, yaxis={"autorange": "reversed"})
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Risk Score by Environment")
        env_risk = df.groupby("environment")["risk_score"].mean().sort_values(ascending=False)
        fig2 = px.bar(x=env_risk.index, y=env_risk.values,
                      labels={"x": "Environment", "y": "Avg Risk Score"},
                      color=env_risk.values, color_continuous_scale="RdYlGn_r")
        fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           font_color="white", coloraxis_showscale=False)
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Risk Score Distribution (scatter by resource type)")
    fig3 = px.scatter(
        df, x="violation_count", y="risk_score",
        color="risk_severity", symbol="resource_type",
        color_discrete_map={"critical":"#ff4b6e","high":"#ff8c42","medium":"#ffd166","low":"#06d6a0"},
        hover_data=["resource_id", "owner_team", "environment"],
        labels={"violation_count": "# Violations", "risk_score": "Risk Score (0-100)"},
    )
    fig3.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("High Risk Resources")
    high_risk = df[df["risk_severity"].isin(["critical", "high"])][
        ["resource_id","resource_type","cloud_provider","environment","owner_team",
         "risk_score","risk_severity","violation_count","violations_summary"]
    ].head(30)
    st.dataframe(high_risk, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# COST OPTIMIZATION
# ══════════════════════════════════════════════════════════════════════════════
elif nav == "Cost Optimization":
    st.title("💰 Cost Optimization")

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total Monthly Spend",     f"${finops['total_monthly_cost']:,.0f}")
    with c2: st.metric("Monthly Savings Opp.",    f"${finops['potential_monthly_savings']:,.0f}")
    with c3: st.metric("Annual Savings Opp.",     f"${finops['potential_annual_savings']:,.0f}")
    with c4: st.metric("Waste %",                 f"{finops['waste_pct']}%")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Waste Type Breakdown")
        waste = df[df["waste_flag"] != "none"]["waste_flag"].value_counts()
        fig = px.pie(values=waste.values, names=waste.index, hole=0.4,
                     color_discrete_sequence=["#ff4b6e", "#ff8c42", "#ffd166"])
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Monthly Spend vs. Savings by Provider")
        prov_spend   = df.groupby("cloud_provider")["cost_per_month"].sum()
        prov_savings = df.groupby("cloud_provider")["savings_monthly"].sum()
        fig2 = go.Figure(data=[
            go.Bar(name="Monthly Spend",    x=prov_spend.index,   y=prov_spend.values,   marker_color="#4361ee"),
            go.Bar(name="Savings Opp.",     x=prov_savings.index, y=prov_savings.values, marker_color="#06d6a0"),
        ])
        fig2.update_layout(barmode="group", plot_bgcolor="rgba(0,0,0,0)",
                           paper_bgcolor="rgba(0,0,0,0)", font_color="white")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Wasteful Resources")
    waste_df = df[df["waste_flag"] != "none"][
        ["resource_id","resource_type","cloud_provider","environment","owner_team",
         "cost_per_month","waste_flag","utilization_tier","savings_monthly","savings_annual","waste_reason"]
    ].sort_values("savings_annual", ascending=False)
    st.dataframe(waste_df, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# REMEDIATION QUEUE
# ══════════════════════════════════════════════════════════════════════════════
elif nav == "Remediation Queue":
    st.title("📋 Remediation Queue")

    queue = prioritization.top_n(df, 50)
    st.caption(f"Showing top 50 of {len(df)} resources, ranked by Unified Impact Score")

    # Priority filter
    pf = st.multiselect("Filter by priority", ["P1","P2","P3","P4"], default=["P1","P2"])
    if pf:
        queue = queue[queue["priority"].isin(pf)]

    # Color-code priority column
    def color_priority(val):
        colors = {"P1": "background-color: rgba(255,75,110,0.25)",
                  "P2": "background-color: rgba(255,140,66,0.25)",
                  "P3": "background-color: rgba(255,209,102,0.15)",
                  "P4": ""}
        return colors.get(val, "")

    styled = queue.style.map(color_priority, subset=["priority"])
    st.dataframe(styled, use_container_width=True)

    # AI remediation for selected resource
    st.divider()
    st.subheader("🤖 Get AI Remediation")
    resource_ids = df.head(20)["resource_id"].tolist()
    selected_id  = st.selectbox("Select a resource for AI-generated remediation", resource_ids)

    if st.button("Generate Remediation Plan", type="primary"):
        resource = df[df["resource_id"] == selected_id].to_dict("records")[0]
        with st.spinner("Consulting AI Copilot..."):
            result = copilot.get_remediation(resource)

        st.write("Raw result:", result)
        st.markdown(f"**Explanation:** {result.get('explanation', '')}")
        st.markdown("**Remediation Steps:**")
        for i, step in enumerate(result.get("remediation_steps", []), 1):
            st.markdown(f"{i}. {step}")
        st.markdown(f"**ROI Estimate:** {result.get('roi_estimate', '')}")
        if result.get("urgency_note"):
            st.warning(result["urgency_note"])


# ══════════════════════════════════════════════════════════════════════════════
# AI COPILOT CHAT
# ══════════════════════════════════════════════════════════════════════════════
elif nav == "AI Copilot":
    st.title("🤖 AI Cloud Copilot")
    st.caption("Ask anything about your cloud environment — risk, cost, compliance, team ownership")

    # Suggested prompts
    st.markdown("**Suggested questions:**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Which team has the highest risk?"):
            st.session_state.prefill = "Which team has the highest average risk score?"
    with col2:
        if st.button("Biggest cost savings opportunities?"):
            st.session_state.prefill = "What are the biggest cost savings opportunities?"
    with col3:
        if st.button("Generate executive summary"):
            st.session_state.prefill = "Generate a concise executive summary of our cloud security and cost posture."

    # Chat history display
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # Input
    prefill = st.session_state.pop("prefill", "") if "prefill" in st.session_state else ""
    user_input = st.chat_input("Ask the copilot...", key="chat_input")
    if prefill and not user_input:
        user_input = prefill

    if user_input:
        with st.chat_message("user"):
            st.write(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                reply, updated = copilot.chat(
                    user_input,
                    st.session_state.context,
                    st.session_state.chat_history,
                )
            st.write(reply)
            st.session_state.chat_history = updated
