import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px
from datetime import datetime

# ------------------------------
# PAGE SETUP
# ------------------------------
st.set_page_config(
    page_title="📊 Call Dashboard",
    page_icon="📞",
    layout="wide"
)

# ------------------------------
# LOAD DATA FROM GOOGLE SHEETS
# ------------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)

# Replace with your sheet name
SHEET_NAME = "Dummy_calls_data"
sheet = client.open(SHEET_NAME).sheet1  
data = sheet.get_all_records()
df = pd.DataFrame(data)

# Ensure Call Date is datetime
df["Call Date"] = pd.to_datetime(df["Call Date"], errors="coerce")

# ------------------------------
# SIDEBAR FILTERS
# ------------------------------
st.sidebar.header("🔍 Filters")

# Date filter
date_range = st.sidebar.date_input(
    "Select Date Range",
    [df["Call Date"].min(), df["Call Date"].max()]
)

# Status filter
status_filter = st.sidebar.multiselect(
    "Appointment Status",
    df["Appointment Status"].unique()
)

# Query Resolved filter
resolved_filter = st.sidebar.multiselect(
    "Query Resolved",
    df["Query Resolved"].unique()
)

# Apply filters
filtered_df = df.copy()
if len(date_range) == 2:
    start, end = date_range
    filtered_df = filtered_df[(filtered_df["Call Date"] >= pd.to_datetime(start)) &
                              (filtered_df["Call Date"] <= pd.to_datetime(end))]
if status_filter:
    filtered_df = filtered_df[filtered_df["Appointment Status"].isin(status_filter)]
if resolved_filter:
    filtered_df = filtered_df[filtered_df["Query Resolved"].isin(resolved_filter)]

# ------------------------------
# METRIC CARDS
# ------------------------------
st.markdown("## 📞 Call Dashboard Overview")

total_calls = len(filtered_df)
answered_calls = filtered_df[filtered_df["Appointment Status"] != "Slot Unavailable"].shape[0]
unanswered_calls = filtered_df[filtered_df["Appointment Status"] == "Slot Unavailable"].shape[0]
resolved_queries = filtered_df[filtered_df["Query Resolved"] == "Yes"].shape[0]
avg_duration = round(filtered_df["Call Duration(secs)"].mean(), 2) if total_calls > 0 else 0

col1, col2, col3, col4, col5 = st.columns(5)

def metric_card(value, label, icon):
    st.markdown(f"""
        <div style="padding:20px;border-radius:15px;background:#f9f9f9;
        box-shadow:2px 2px 10px rgba(0,0,0,0.1);text-align:center;">
            <div style="font-size:28px;font-weight:bold;color:#333;">{value}</div>
            <div style="font-size:16px;color:#555;">{icon} {label}</div>
        </div>
    """, unsafe_allow_html=True)

with col1: metric_card(total_calls, "Total Calls", "📞")
with col2: metric_card(answered_calls, "Answered Calls", "✅")
with col3: metric_card(unanswered_calls, "Missed Calls", "❌")
with col4: metric_card(resolved_queries, "Resolved Queries", "💬")
with col5: metric_card(avg_duration, "Avg Duration (secs)", "⏱️")

# ------------------------------
# CHARTS
# ------------------------------
st.markdown("## 📈 Insights & Trends")

# Pie Chart - Appointment Status
status_counts = filtered_df["Appointment Status"].value_counts().reset_index()
status_counts.columns = ["Status", "Count"]
fig_pie = px.pie(status_counts, values="Count", names="Status", title="Appointment Status Breakdown")
st.plotly_chart(fig_pie, use_container_width=True)

# Line Chart - Calls over Time
daily_calls = filtered_df.groupby("Call Date").size().reset_index(name="Total Calls")
fig_line = px.line(daily_calls, x="Call Date", y="Total Calls", markers=True, title="Daily Call Trends")
st.plotly_chart(fig_line, use_container_width=True)

# Bar Chart - Query Resolved
resolved_counts = filtered_df["Query Resolved"].value_counts().reset_index()
resolved_counts.columns = ["Resolved", "Count"]
fig_bar = px.bar(resolved_counts, x="Resolved", y="Count", title="Query Resolution Status")
st.plotly_chart(fig_bar, use_container_width=True)

# ------------------------------
# DATA TABLE
# ------------------------------
st.markdown("## 📋 Detailed Call Records")
st.dataframe(filtered_df, use_container_width=True)

