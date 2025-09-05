import os
import json
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import plotly.express as px
from datetime import datetime

# -----------------------------
# GOOGLE SHEETS AUTH (works both local & cloud)
# -----------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

try:
    # Streamlit Cloud
    creds_dict = dict(st.secrets["creds"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
except Exception:
    # Local development
    with open("creds.json") as f:
        creds_dict = json.load(f)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)

# Load the first sheet
sheet = client.open("Dummy_calls_data").sheet1
data = sheet.get_all_records()
df = pd.DataFrame(data)

# -----------------------------
# DATA CLEANING & METRICS
# -----------------------------
df["Call Duration(mins)"] = df["Call Duration(secs)"] / 60

total_calls = len(df)
answered_calls = df[df["Appointment Status"] == "Booked"].shape[0]
missed_calls = total_calls - answered_calls
queries_resolved = df[df["Query Resolved"] == "Yes"].shape[0]
avg_duration = df["Call Duration(mins)"].mean()

# ROI: 200$ per appointment booked - 100$ fee
revenue = answered_calls * 200
roi = revenue - 100

# -----------------------------
# STREAMLIT DASHBOARD LAYOUT
# -----------------------------
st.set_page_config(page_title="AI Call Dashboard", layout="wide")

st.markdown(
    """
    <style>
    .main {
        background-color: #fff9f4;
    }
    .big-title {
        font-size: 36px !important;
        color: #ff6f3c;
        text-align: center;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .sub-title {
        font-size: 18px !important;
        color: #444;
        text-align: center;
        margin-bottom: 30px;
    }
    .greeting-box {
        background-color: #ffe5d0;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        font-size: 20px;
        font-weight: bold;
        margin-bottom: 25px;
        color: #333;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Dynamic greeting
hour = datetime.now().hour
if hour < 12:
    greeting = "Good Morning"
elif hour < 18:
    greeting = "Good Afternoon"
else:
    greeting = "Good Evening"

# Header
st.markdown("<div class='big-title'>📞 Welcome to Your AI Call Dashboard</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Track your calls, queries, and ROI in real-time</div>", unsafe_allow_html=True)
st.markdown(f"<div class='greeting-box'>{greeting}, Dr. [Name]! 👋 Here’s how your AI assistant is doing today.</div>", unsafe_allow_html=True)

# Metrics row
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("📊 Total Calls", total_calls)
col2.metric("✅ Answered Calls", answered_calls)
col3.metric("❌ Missed Calls", missed_calls)
col4.metric("💡 Queries Resolved", queries_resolved)
col5.metric("⏱️ Avg Duration (mins)", f"{avg_duration:.2f}")

# ROI section
st.markdown("### 💵 ROI Overview")
col1, col2 = st.columns(2)
col1.metric("Revenue Generated", f"${revenue}")
col2.metric("Net ROI", f"${roi}")

# -----------------------------
# TODAY VS YESTERDAY COMPARISON
# -----------------------------
if "Call Date" in df.columns:
    df["Call Date"] = pd.to_datetime(df["Call Date"])
    today = pd.to_datetime("today").normalize()
    yesterday = today - pd.Timedelta(days=1)

    today_calls = df[df["Call Date"] == today].shape[0]
    yesterday_calls = df[df["Call Date"] == yesterday].shape[0]

    delta = today_calls - yesterday_calls

    st.markdown("### 📅 Call Volume Comparison")
    st.metric("Calls Today vs Yesterday", today_calls, delta=delta)

# -----------------------------
# VISUALS
# -----------------------------
st.markdown("### 📈 Trends & Insights")

status_fig = px.histogram(df, x="Appointment Status", color="Appointment Status",
                          title="Appointment Status Distribution",
                          text_auto=True)
st.plotly_chart(status_fig, use_container_width=True)

if "Call Date" in df.columns:
    calls_per_day = df.groupby("Call Date").size().reset_index(name="Total Calls")
    date_fig = px.line(calls_per_day, x="Call Date", y="Total Calls",
                       title="Daily Calls Trend", markers=True)
    st.plotly_chart(date_fig, use_container_width=True)

# -----------------------------
# RAW DATA
# -----------------------------
with st.expander("🔍 View Raw Data"):
    st.dataframe(df)



