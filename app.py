import streamlit as st
import pandas as pd
import plotly.express as px
import time
from agents import run_esg_pipeline, PROJECT_SCHEDULES, schedule_quant_agent

# Configure the webpage
st.set_page_config(page_title="nPlan ESG Copilot", page_icon="🌱", layout="wide")

# Custom Title & Header
st.title("🌱 nPlan ESG & Sustainability Copilot")
st.caption("Autonomous Multi-Agent System for Predicting Scope 3 Embodied Carbon in Construction Schedules")

st.divider()

# Sidebar: Controls
with st.sidebar:
    st.header("Project Configuration")
    project_name = st.selectbox("Select Project Schedule", list(PROJECT_SCHEDULES.keys()))
    monthly_cap = st.slider("Monthly Carbon Ceiling (t CO2e)", min_value=300, max_value=1200, value=600, step=50)
    
    run_button = st.button("🚀 Run Multi-Agent Forecast", type="primary", use_container_width=True)

# Initialize session state for persistent results
if "results" not in st.session_state:
    st.session_state.results = None

# Trigger pipeline when button is clicked
if run_button:
    with st.status(f"⚡ Running Multi-Agent Simulation: {project_name}...", expanded=True) as status:
        results = run_esg_pipeline(project_name=project_name, monthly_cap=monthly_cap)
        for log in results["logs"]:
            st.write(log)
            time.sleep(0.2)  # Visual pacing
        status.update(label=f"✅ Multi-Agent Simulation Complete: {project_name}", state="complete", expanded=False)
    
    st.session_state.results = results

# Render results or show initial preview
if st.session_state.results is None:
    st.info("👈 Select a project and click **'Run Multi-Agent Forecast'** in the sidebar to start the simulation.")
    
    # Preview data dynamically based on selected project
    st.subheader(f"📋 Sample Activities Ready for Ingestion ({project_name})")
    preview_schedule = PROJECT_SCHEDULES.get(project_name, [])
    st.table(pd.DataFrame(schedule_quant_agent(preview_schedule)))
else:
    results = st.session_state.results

    # Notice if sidebar settings differ from currently displayed forecast
    if results.get("project_name") != project_name or results.get("monthly_cap") != monthly_cap:
        st.info("💡 Sidebar settings have changed. Click **'Run Multi-Agent Forecast'** to recalculate for the new configuration.")

    # Determine critical month dynamically
    if results["monthly_totals"]:
        critical_month = max(results["monthly_totals"], key=results["monthly_totals"].get)
        peak_carbon = results["monthly_totals"][critical_month]
        critical_label = f"{critical_month} ({peak_carbon:,.1f} t)"
    else:
        critical_label = "N/A"

    # 2. Key Metrics Row
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Embodied Carbon", f"{results['total_co2e']:,.1f} t CO2e")
    col2.metric("Carbon Critical Month", critical_label)
    col3.metric("Critic Alerts", f"{len(results['flags'])} Items", delta_color="inverse")

    st.divider()

    display_project = results.get("project_name", project_name)
    display_cap = results.get("monthly_cap", monthly_cap)

    # 3. Dynamic Carbon Burn Curve
    st.subheader(f"📈 Time-Phased Carbon Burn Curve (Scope 3) — {display_project}")
    
    chart_df = pd.DataFrame(list(results["monthly_totals"].items()), columns=["Timeline", "Embodied Carbon (t CO2e)"])
    
    fig = px.bar(
        chart_df, 
        x="Timeline", 
        y="Embodied Carbon (t CO2e)", 
        text="Embodied Carbon (t CO2e)",
        color="Embodied Carbon (t CO2e)",
        color_continuous_scale="Reds"
    )
    # Add target line
    fig.add_hline(y=display_cap, line_dash="dash", line_color="red", annotation_text=f"Carbon Cap ({display_cap} t)")
    st.plotly_chart(fig, use_container_width=True)

    # 4. Human-in-the-loop Critic Guardrail Alerts
    st.subheader("🛡️ Compliance & Critic Guardrail Alerts")
    if not results["flags"]:
        st.info("✅ All monthly emissions are within the carbon budget and EPD match confidence meets thresholds.")
    else:
        for flag in results["flags"]:
            if flag["severity"] == "HIGH":
                st.error(flag["message"])
            else:
                st.warning(flag["message"])

    # 5. Full Carbon Ledger Table
    with st.expander("🔍 View Detailed Carbon Bill of Materials (C-BoM)"):
        st.dataframe(pd.DataFrame(results["carbon_data"]), use_container_width=True)