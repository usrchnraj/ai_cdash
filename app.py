import os
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ----------------- PAGE CONFIG -----------------
st.set_page_config(page_title="Doctor Ops Intelligence", layout="wide")

# ---------- Custom CSS for styling ----------
st.markdown(
    """
    <style>
    /* Global gradient background */
    .stApp {
        background: linear-gradient(to bottom right, #fff8dc, #ffcc80);
        font-family: 'Poppins', sans-serif;
    }

    /* Load custom Google font */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap');

    /* Greeting banner */
    .banner {
        background: linear-gradient(90deg, #ffecb3, #ffb74d);
        padding: 1.5rem;
        border-radius: 1rem;
        text-align: center;
        font-size: 1.6rem;
        font-weight: 600;
        color: #5d4037;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 1.5rem;
    }

    /* KPI Cards */
    .metric-card {
        background-color: white;
        border-radius: 1rem;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 1px 3px 8px rgba(0,0,0,0.1);
        margin: 0.5rem;
        font-size: 1.1rem;
        color: #5d4037;  /* <-- Warm brown for labels */
        font-weight: 500;
    }

    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
        color: #e65100;  /* <-- Orange for numbers */
    }

    /* Section headings */
    h4, h3 {
        color: #e65100 !important;  /* Deep orange to pop */
        font-weight: 600;
    }

    /* Hide Streamlit default menu & footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Google Sheets Connection ----------
@st.cache_data(ttl=60)
def load_data() -> pd.DataFrame:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    if os.path.exists("creds.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
        client = gspread.authorize(creds)
    elif "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["creds"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
    else:
        st.error("No credentials found. Provide creds.json locally or set Streamlit secrets.")
        st.stop()

    sheet_file = client.open("call_audit_1")
    sheet = sheet_file.sheet1
    data = sheet.get_all_records()

    df = pd.DataFrame(data)

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

    return df


try:
    df = load_data()
except Exception as e:
    st.error(f"Could not load data from Google Sheets: {e}")
    st.stop()

# ---------- Sidebar filters ----------
st.sidebar.header("Filters")
if "date" in df.columns:
    min_date, max_date = (df["date"].min(), df["date"].max())
    date_range = st.sidebar.date_input("Date range", value=(min_date, max_date))
else:
    date_range = None

clinics = st.sidebar.multiselect("Clinic", sorted(df["clinic_name"].dropna().unique())) if "clinic_name" in df.columns else []
doctors = st.sidebar.multiselect("Doctor", sorted(df["doctor"].dropna().unique())) if "doctor" in df.columns else []

avg_value = st.sidebar.number_input("Avg visit value ($)", value=200.0, step=10.0)
monthly_fee = st.sidebar.number_input("Monthly fee ($)", value=100.0, step=10.0)

q = df.copy()
if date_range and isinstance(date_range, (list, tuple)) and len(date_range) == 2 and "date" in q.columns:
    q = q[(q["date"] >= date_range[0]) & (q["date"] <= date_range[1])]
if clinics:
    q = q[q["clinic_name"].isin(clinics)]
if doctors:
    q = q[q["doctor"].isin(doctors)]

# ---------- Greeting Banner ----------
served_today = int((df["date"] == pd.Timestamp.utcnow().date()).sum()) if "date" in df.columns else 0
booked = int(q[(q["outcome"] == "BOOKED")].shape[0]) if "outcome" in q.columns else 0
recovered_revenue = booked * avg_value
roi_multiple = (recovered_revenue - monthly_fee) if monthly_fee > 0 else np.nan

st.markdown(
    f"""
    <div class="banner">
        🌞 Good morning, Dr [Name]! <br>
        We served <b>{served_today}</b> patients today. <br>
        🎉 Your net ROI generated is <b>${roi_multiple:,.0f}</b>. Keep shining! ✨
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- KPI Cards ----------
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"<div class='metric-card'>💰 Net ROI<br><span class='metric-value'>${roi_multiple:,.0f}</span></div>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<div class='metric-card'>📞 Calls Received<br><span class='metric-value'>{q.shape[0]:,}</span></div>", unsafe_allow_html=True)
with c3:
    call_handling_pct = float((q["success"].mean() * 100) if "success" in q.columns and len(q) else 0.0)
    st.markdown(f"<div class='metric-card'>🤝 Call Handling %<br><span class='metric-value'>{call_handling_pct:,.1f}%</span></div>", unsafe_allow_html=True)

# ---------- Charts ----------
st.markdown("#### 📈 Trend (Attempts vs Booked)")
if "outcome" in q.columns and "date" in q.columns:
    trend = q.groupby("date").agg(
        attempts=("outcome", "size"),
        booked=("outcome", lambda s: (s == "BOOKED").sum())
    ).reset_index()
    if not trend.empty:
        fig1 = px.line(
            trend, x="date", y=["attempts", "booked"], 
            markers=True, 
            color_discrete_sequence=["#e53935", "#fbc02d"]
        )
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.info("No data for selected filters.")

st.markdown("#### 🔥 Demand Heatmap (Attempts by Weekday × Hour)")
if "weekday" in q.columns and "hour" in q.columns:
    heat = q.groupby(["weekday", "hour"]).size().reset_index(name="attempts")
    wk_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    heat["weekday"] = pd.Categorical(heat["weekday"], categories=wk_order, ordered=True)
    heat = heat.sort_values(["weekday", "hour"])
    if not heat.empty:
        fig2 = px.density_heatmap(
            heat, x="hour", y="weekday", z="attempts", 
            nbinsx=24, color_continuous_scale="YlOrRd"
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No attempts to show in heatmap.")

# ---------- Operations Table ----------
st.markdown("#### 📋 Operations (latest 500)")
ops_cols = [c for c in ["ts_utc", "clinic_name", "doctor", "outcome", "latency_ms", "booking_id", "error_code", "preferred_dt_local"] if c in q.columns]
ops = q.sort_values("ts_utc", ascending=False).head(500)[ops_cols] if "ts_utc" in q.columns else q.head(500)
st.dataframe(ops, use_container_width=True)

st.download_button("⬇️ Download filtered CSV", data=q.to_csv(index=False), file_name="filtered_calls.csv", mime="text/csv")






