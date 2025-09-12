import os
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta

# ----------------- PAGE CONFIG -----------------
st.set_page_config(
    page_title="Doctor Ops Intelligence",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- THEME & CSS -----------------
st.markdown(
    """
    <style>
    /* (CSS styling you already had, kept the same) */
    .stApp {background: linear-gradient(to bottom right, #fff8dc, #ffcc80);}
    .banner {background: linear-gradient(90deg, #ffecb3, #ffb74d); padding: 1.5rem; border-radius: 1rem; text-align: center; font-size: 1.6rem; font-weight: 600; color: #5d4037; margin-bottom: 1.2rem;}
    .metric-card {background-color: #ffffff; border-radius: 1rem; padding: 1.0rem 1.2rem; text-align: center; box-shadow: 1px 3px 8px rgba(0,0,0,0.1); margin: 0.5rem; font-size: 1.05rem; color: #5d4037; font-weight: 500;}
    .metric-value {display: block; margin-top: 0.25rem; font-size: 1.8rem; font-weight: 700; color: #e65100;}
    h3, h4 {color: #e65100 !important; font-weight: 600 !important;}
    header[data-testid="stHeader"] {background: linear-gradient(to right, #fff8dc, #ffcc80); color: #5d4037;}
    header[data-testid="stHeader"] button[kind="header"] svg {fill: #333333 !important; width: 1.5rem; height: 1.5rem;}
    section[data-testid="stSidebar"] {background: linear-gradient(to bottom, #fff8e1, #ffe0b2); color: #5d4037; padding: 1rem;}
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {color: #e65100 !important; font-weight: 600; margin-bottom: 1rem;}
    section[data-testid="stSidebar"] label {color: #5d4037 !important; font-weight: 500;}
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True
)

# ----------------- CONFIG -----------------
AVG_VISIT_VALUE = 200.0
MONTHLY_FEE    = 100.0

# ----------------- DATA LOADING -----------------
@st.cache_data
def load_data():
    try:
        conn = st.connection("postgres", type="sql")
        df = conn.query("SELECT * FROM call_test;", ttl=0)  # no auto-caching from Neon
        st.success("Fetched fresh data from Neon ✅")
        return df
    except Exception as e:
        st.warning(f"Neon not available, using local CSV. Error: {e}")
        if os.path.exists("call_test_dummy.csv"):
            return pd.read_csv("call_test_dummy.csv")
        else:
            st.error("No Neon connection and no local CSV file found.")
            st.stop()

# ----------------- REFRESH BUTTON -----------------
if st.button("🔄 Refresh Data from Neon"):
    st.cache_data.clear()   # clear cache so next load is fresh
    df = load_data()
else:
    # Load cached data (does NOT hit Neon unless you pressed button)
    if "df" not in st.session_state:
        df = load_data()
        st.session_state.df = df
    else:
        df = st.session_state.df


# Load once
df = load_data()

# ---- Transformations ----
if "ts_utc" in df.columns:
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], errors="coerce", utc=True)
    df["date"] = df["ts_utc"].dt.date
    df["hour"] = df["ts_utc"].dt.hour
    df["weekday"] = df["ts_utc"].dt.day_name().str.slice(0, 3)

if "success" in df.columns:
    df["success"] = df["success"].astype(str).str.lower().isin(["true", "1", "yes"])

    def outcome(row):
        if row["success"] and pd.notna(row.get("booking_id", None)):
            return "BOOKED"
        ec = str(row.get("error_code", "")).upper()
        if ec in ("SLOT_UNAVAILABLE", "SLOT_BUSY"):
            return "SLOT_UNAVAILABLE"
        if ec == "SLOT_CLOSED":
            return "CLOSED"
        return "OTHER"

    df["outcome"] = df.apply(outcome, axis=1)

# ----------------- SIDEBAR (VIEW OPTIONS) -----------------
st.sidebar.header("📂 Data Filters")

def get_date_range(choice: str):
    today = pd.Timestamp.utcnow().date()
    if choice == "Today":
        return today, today
    if choice == "Last 7 days":
        return today - timedelta(days=6), today
    if choice == "Last 30 days":
        return today - timedelta(days=29), today
    if choice == "Last 90 days":
        return today - timedelta(days=89), today
    return today - timedelta(days=6), today

range_choice = st.sidebar.selectbox(
    "Time range",
    ["Today", "Last 7 days", "Last 30 days", "Last 90 days"],
    index=1
)

start_date, end_date = get_date_range(range_choice)

clinics = st.sidebar.multiselect(
    "Clinic",
    sorted(df["clinic_name"].dropna().unique()) if "clinic_name" in df.columns else []
)
doctors = st.sidebar.multiselect(
    "Doctor",
    sorted(df["doctor"].dropna().unique()) if "doctor" in df.columns else []
)

# Apply filters
q = df.copy()
if "date" in q.columns:
    q = q[(q["date"] >= start_date) & (q["date"] <= end_date)]
if clinics:
    q = q[q["clinic_name"].isin(clinics)]
if doctors:
    q = q[q["doctor"].isin(doctors)]

# ----------------- GREETING BANNER -----------------
period_label = "today" if range_choice == "Today" else f"in the {range_choice.lower()}"
served_count = int(q.shape[0])

booked = int((q["outcome"] == "BOOKED").sum()) if "outcome" in q.columns else 0
recovered_revenue = booked * AVG_VISIT_VALUE
net_roi = recovered_revenue - MONTHLY_FEE

st.markdown(
    f"""
    <div class="banner">
        🌞 Good {('morning' if datetime.now().hour < 12 else ('afternoon' if datetime.now().hour < 18 else 'evening'))}, Dr [Name]!<br>
        We served <b>{served_count}</b> patients {period_label}.<br>
        🎉 Your net ROI generated is <b>£{net_roi:,.0f}</b>. Keep shining! ✨
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------- KPI CARDS -----------------
calls_received = int(q.shape[0])
call_handling_pct = float((q["success"].mean() * 100) if "success" in q.columns and len(q) else 0.0)

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"<div class='metric-card'>💰 Net ROI<span class='metric-value'>£{net_roi:,.0f}</span></div>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<div class='metric-card'>📞 Calls Received<span class='metric-value'>{calls_received:,}</span></div>", unsafe_allow_html=True)
with c3:
    st.markdown(f"<div class='metric-card'>🤝 Call Handling %<span class='metric-value'>{call_handling_pct:,.1f}%</span></div>", unsafe_allow_html=True)

# ----------------- CHARTS -----------------
st.markdown("#### 📈 Trend (Attempts vs Booked)")
if {"outcome", "date"}.issubset(q.columns):
    trend = q.groupby("date").agg(
        attempts=("outcome", "size"),
        booked=("outcome", lambda s: (s == "BOOKED").sum())
    ).reset_index()
    if not trend.empty:
        fig1 = px.line(trend, x="date", y=["attempts", "booked"], markers=True)
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("No data for selected filters.")

st.markdown("#### 🔥 Demand Heatmap (Attempts by Weekday × Hour)")
if {"weekday", "hour"}.issubset(q.columns):
    heat = q.groupby(["weekday", "hour"]).size().reset_index(name="attempts")
    wk_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    heat["weekday"] = pd.Categorical(heat["weekday"], categories=wk_order, ordered=True)
    heat = heat.sort_values(["weekday", "hour"])
    if not heat.empty:
        fig2 = px.density_heatmap(heat, x="hour", y="weekday", z="attempts", nbinsx=24)
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No attempts to show in heatmap.")

# ----------------- OPERATIONS TABLE -----------------
st.markdown("#### 📋 Operations (latest 500)")
ops_cols = [c for c in ["ts_utc","clinic_name","doctor","outcome","latency_ms","booking_id","error_code"] if c in q.columns]
ops = q.sort_values("ts_utc", ascending=False).head(500)[ops_cols] if "ts_utc" in q.columns else q.head(500)
st.dataframe(ops, use_container_width=True)

# ----------------- CSV DOWNLOAD -----------------
st.download_button("⬇️ Download filtered CSV", data=q.to_csv(index=False), file_name="filtered_calls.csv", mime="text/csv")







