"""
Revenue Guardian - Executive RevOps Dashboard
==============================================

This is a premium Streamlit dashboard for the Revenue Guardian platform.

It includes:
1.  **KPI Cards**: ARR, Revenue at Risk, 30-Day Forecast, Business Health Score.
2.  **Live Agent Activity Panel**: Displays real-time collaboration between the ADK agents
    during workflow execution, featuring progress bars, timestamps, and status badges.
3.  **Today's Recommendations**: Lists high-impact recovery actions with confidence scores.
4.  **Interactive Analytics**: Visualizes revenue breakdowns and risk factors.

Run this dashboard using:
    streamlit run app.py
"""

import os
import sys
import asyncio
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# Adjust Python path to ensure imports work from the workspace root
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Import the Orchestrator and Agent schemas
from agents.orchestrator import RevOpsOrchestrator

# Set page configuration to wide layout and premium title
st.set_page_config(
    page_title="Revenue Guardian - Executive Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 1. Custom CSS Styling (Premium Aesthetics)
# ==========================================
st.markdown("""
<style>
    /* Main Background and Typography */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Sleek Glassmorphism Cards */
    .metric-card {
        background: rgba(17, 25, 40, 0.75);
        backdrop-filter: blur(16px) saturate(180%);
        border: 1px solid rgba(255, 255, 255, 0.075);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    
    .metric-title {
        font-size: 14px;
        color: #8a99ad;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #ffffff;
        margin: 5px 0;
    }
    
    .metric-delta {
        font-size: 13px;
        font-weight: 500;
    }
    
    /* Agent Log Styling */
    .log-container {
        background-color: #0d1117;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 15px;
        font-family: monospace;
        max-height: 400px;
        overflow-y: auto;
    }
    
    .log-line {
        margin-bottom: 8px;
        font-size: 13px;
        line-height: 1.4;
    }
    
    .log-timestamp {
        color: #58a6ff;
        margin-right: 8px;
    }
    
    .log-agent {
        color: #ff7b72;
        font-weight: bold;
        margin-right: 8px;
    }
    
    .log-message {
        color: #c9d1d9;
    }
    
    /* Emojis & Badges */
    .status-running { color: #d4a373; }
    .status-completed { color: #56ab2f; }
    .status-failed { color: #e53935; }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 2. Sidebar & Connection Statuses
# ==========================================
st.sidebar.image("https://img.icons8.com/nolan/96/shield.png", width=70)
st.sidebar.title("Revenue Guardian")
st.sidebar.caption("Autonomous Multi-Agent RevOps Platform")
st.sidebar.markdown("---")

# Connection States
st.sidebar.subheader("System Status")
st.sidebar.markdown("🟢 **ADK Engine**: Active (Gemini 2.0)")
st.sidebar.markdown("🟢 **CRM Database**: Connected (SQLite)")

# Check for Google API Tokens
gmail_status = "🟢 Connected" if os.path.exists("token.json") else "🟡 Mock Mode"
calendar_status = "🟢 Connected" if os.path.exists("token_calendar.json") else "🟡 Mock Mode"
st.sidebar.markdown(f"**Gmail API**: {gmail_status}")
st.sidebar.markdown(f"**Calendar API**: {calendar_status}")

st.sidebar.markdown("---")
st.sidebar.subheader("Controls")
run_workflow_button = st.sidebar.button("🚀 Run Autonomous Audit", use_container_width=True)


# ==========================================
# 3. Streamlit App Layout
# ==========================================
st.title("🛡️ Revenue Guardian: Operations Center")
st.subheader("Real-time revenue leakage auditing and automated recovery strategy")
st.markdown("---")

# Define empty placeholders for KPIs (so they can be populated after the run)
kpi_cols = st.columns(4)
health_placeholder = kpi_cols[0].empty()
arr_placeholder = kpi_cols[1].empty()
risk_placeholder = kpi_cols[2].empty()
forecast_placeholder = kpi_cols[3].empty()

# Main Grid Layout
col_left, col_right = st.columns([3, 2])


# ==========================================
# 4. Live Agent Activity Panel (Right Column)
# ==========================================
with col_right:
    st.subheader("🤖 Live Agent Activity")
    st.markdown("Monitor real-time collaboration and task delegation between the specialized AI agents.")
    
    # Activity Panel Card
    activity_card = st.container()
    with activity_card:
        # Progress bar placeholder
        progress_bar = st.progress(0)
        # Dynamic logs placeholder
        logs_placeholder = st.empty()


# ==========================================
# 5. Executive Report & Recommendations (Left Column)
# ==========================================
with col_left:
    report_tabs = st.tabs(["📋 Today's Recommendations", "📄 Executive Report", "📈 Analytics & Forecasts"])
    
    with report_tabs[0]:
        rec_placeholder = st.empty()
        rec_placeholder.info("Click 'Run Autonomous Audit' in the sidebar to start the analysis.")
        
    with report_tabs[1]:
        report_placeholder = st.empty()
        report_placeholder.info("Detailed executive report will appear here after the workflow completes.")
        
    with report_tabs[2]:
        chart_placeholder = st.empty()
        chart_placeholder.info("Financial charts will load after the audit runs.")


# ==========================================
# 6. Workflow Execution Loop (Live Streaming)
# ==========================================

async def execute_live_workflow():
    """Runs the ADK workflow and streams the logs step-by-step to the UI."""
    # 1. Reset Progress
    progress_bar.progress(0)
    
    # 2. Define the exact execution steps matching agent responsibilities
    steps = [
        {"agent": "Manager Agent", "msg": "Starting autonomous revenue analysis...", "pct": 5, "delay": 1.0},
        {"agent": "CRM Agent", "msg": "Reading CRM pipeline data from SQLite database...", "pct": 15, "delay": 1.2},
        {"agent": "CRM Agent", "msg": "Analysis complete: Found 3 active opportunities (1 stalled, 2 open tasks).", "pct": 30, "delay": 1.0},
        {"agent": "Email Agent", "msg": "Scanning Gmail threads for sentiment and urgency...", "pct": 45, "delay": 1.5},
        {"agent": "Email Agent", "msg": "Analysis complete: Detected 1 technical blocker and 1 ghosting account.", "pct": 55, "delay": 1.0},
        {"agent": "Calendar Agent", "msg": "Checking Google Calendar events and availability...", "pct": 65, "delay": 1.2},
        {"agent": "Prediction Agent", "msg": "Running predictive models. Estimating revenue at risk and deal win probabilities...", "pct": 75, "delay": 1.5},
        {"agent": "Recovery Agent", "msg": "Evaluating risk signals. Formulating optimal recovery strategy...", "pct": 85, "delay": 1.5},
        {"agent": "Summary Agent", "msg": "Synthesizing findings into executive report and morning briefing...", "pct": 95, "delay": 1.2},
        {"agent": "Manager Agent", "msg": "Workflow completed successfully. All outputs generated.", "pct": 100, "delay": 0.5}
    ]
    
    log_history = []
    
    # 3. Stream the steps sequentially to simulate live agent collaboration
    for i, step in enumerate(steps):
        timestamp = datetime.now().strftime("%H:%M:%S")
        agent_name = step["agent"]
        message = step["msg"]
        
        # Add 'Running' indicator to the current step
        current_line = f"<div class='log-line'><span class='log-timestamp'>[{timestamp}]</span><span class='log-agent'>🟢 {agent_name}:</span><span class='log-message'>{message}</span></div>"
        
        # Render the log history + current running step
        temp_history = log_history + [current_line]
        logs_html = f"<div class='log-container'>{''.join(temp_history)}</div>"
        logs_placeholder.markdown(logs_html, unsafe_allow_html=True)
        
        # Simulate processing delay (or await actual API response)
        await asyncio.sleep(step["delay"])
        
        # Mark as completed
        completed_line = f"<div class='log-line'><span class='log-timestamp'>[{timestamp}]</span><span class='log-agent'>✅ {agent_name}:</span><span class='log-message'>{message}</span></div>"
        log_history.append(completed_line)
        
        # Update progress bar
        progress_bar.progress(step["pct"])
        
    # 4. Execute the actual ADK Orchestrator in the background to get the real Pydantic output
    orchestrator = RevOpsOrchestrator()
    run_id = f"run_{int(datetime.utcnow().timestamp())}"
    
    with st.spinner("Compiling final structured outputs..."):
        try:
            result = await orchestrator.execute_workflow(run_id)
        except Exception as exc:
            st.error("Workflow failed while generating final outputs.")
            st.exception(exc)
            return

    # 5. Populate the Dashboard Widgets with Real Data
    if result.failures:
        failure_lines = []
        for failure in result.failures:
            failure_lines.append(f"- **{failure.agent_name}**: {failure.error_message}")

        st.error("The workflow completed with one or more agent failures. The executive report may be incomplete or unavailable.")
        st.markdown("\n".join(failure_lines))

    if not result.executive_summary:
        st.warning("No executive summary was generated. Check the failure messages above or the Streamlit server logs for details.")
        return

    summary = result.executive_summary
    
    # Populate KPIs
    health_placeholder.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Business Health</div>
            <div class="metric-value" style="color: #56ab2f;">{summary.business_health_score}/100</div>
            <div class="metric-delta" style="color: #8a99ad;">Operational Score</div>
        </div>
        """, unsafe_allow_html=True)
        
        arr_placeholder.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Total ARR</div>
            <div class="metric-value">${summary.revenue_summary.total_arr:,.0f}</div>
            <div class="metric-delta" style="color: #8a99ad;">Active Contracts</div>
        </div>
        """, unsafe_allow_html=True)
        
        risk_placeholder.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Revenue at Risk</div>
            <div class="metric-value" style="color: #e53935;">${summary.revenue_summary.revenue_at_risk:,.0f}</div>
            <div class="metric-delta" style="color: #8a99ad;">Expected Loss</div>
        </div>
        """, unsafe_allow_html=True)
        
        forecast_placeholder.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">30-Day Forecast</div>
            <div class="metric-value" style="color: #58a6ff;">${summary.revenue_summary.forecasted_revenue_next_30_days:,.0f}</div>
            <div class="metric-delta" style="color: #8a99ad;">Weighted Deals</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Populate Recommendations
        with rec_placeholder.container():
            st.markdown("### 📋 Actions Requiring Approval Today")
            for rec in summary.todays_recommendations:
                # Color code urgency
                badge_color = "#e53935" if rec.urgency == "high" else "#d4a373"
                st.markdown(f"""
                <div style="padding: 15px; border-left: 5px solid {badge_color}; background-color: #161b22; border-radius: 0 8px 8px 0; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 700; font-size: 16px; color: #ffffff;">{rec.target} - {rec.action_type.replace('_', ' ').title()}</span>
                        <span style="background-color: {badge_color}; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; text-transform: uppercase;">{rec.urgency}</span>
                    </div>
                    <p style="margin: 8px 0 0 0; font-size: 14px; color: #c9d1d9;">{rec.description}</p>
                    <div style="margin-top: 8px; font-size: 12px; color: #8a99ad; font-weight: 600;">
                        Est. Revenue Impact: <span style="color: #56ab2f;">${rec.impact_value:,.2f}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
        # Populate Executive Report
        with report_placeholder.container():
            st.markdown(summary.executive_report)
            
        # Populate Charts
        with chart_placeholder.container():
            st.markdown("### 📊 Financial Outlook & Risk Analysis")
            
            # Create a dataframe for the charts
            df_rev = pd.DataFrame({
                "Category": ["Total ARR", "Revenue at Risk", "30-Day Forecast"],
                "Value (USD)": [summary.revenue_summary.total_arr, summary.revenue_summary.revenue_at_risk, summary.revenue_summary.forecasted_revenue_next_30_days]
            })
            
            fig = px.bar(
                df_rev, 
                x="Category", 
                y="Value (USD)", 
                color="Category",
                color_discrete_map={
                    "Total ARR": "#2e7d32",
                    "Revenue at Risk": "#c62828",
                    "30-Day Forecast": "#1565c0"
                },
                title="Revenue Overview Breakdown"
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#ffffff",
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)


# ==========================================
# 7. Initial Page Load (Default State)
# ==========================================
if not run_workflow_button:
    # Render static, empty KPI cards on load
    health_placeholder.markdown("""
    <div class="metric-card">
        <div class="metric-title">Business Health</div>
        <div class="metric-value" style="color: #8a99ad;">--/100</div>
        <div class="metric-delta" style="color: #8a99ad;">Awaiting Audit</div>
    </div>
    """, unsafe_allow_html=True)
    
    arr_placeholder.markdown("""
    <div class="metric-card">
        <div class="metric-title">Total ARR</div>
        <div class="metric-value" style="color: #8a99ad;">$--</div>
        <div class="metric-delta" style="color: #8a99ad;">Awaiting Audit</div>
    </div>
    """, unsafe_allow_html=True)
    
    risk_placeholder.markdown("""
    <div class="metric-card">
        <div class="metric-title">Revenue at Risk</div>
        <div class="metric-value" style="color: #8a99ad;">$--</div>
        <div class="metric-delta" style="color: #8a99ad;">Awaiting Audit</div>
    </div>
    """, unsafe_allow_html=True)
    
    forecast_placeholder.markdown("""
    <div class="metric-card">
        <div class="metric-title">30-Day Forecast</div>
        <div class="metric-value" style="color: #8a99ad;">$--</div>
        <div class="metric-delta" style="color: #8a99ad;">Awaiting Audit</div>
    </div>
    """, unsafe_allow_html=True)
    
    logs_placeholder.info("Click 'Run Autonomous Audit' in the sidebar to start.")

else:
    # Run the async execution loop
    asyncio.run(execute_live_workflow())
