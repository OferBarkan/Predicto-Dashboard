import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="Predicto Dashboard", layout="wide")

# === General Header ===
st.title("📊 Predicto Ads Dashboard")

# === Date Selection ===
today = datetime.today()
yesterday = today - timedelta(days=1)

def format_date(dt):
    return dt.strftime("%Y-%m-%d")

def_date = format_date(yesterday)
date = st.date_input("Select date", yesterday)
date_str = format_date(date)

# === Fetch Data from Flask API ===
API_URL = f"https://e8a7-35-230-163-243.ngrok-free.app/ads?date={date_str}"
try:
    response = requests.get(API_URL)
    response.raise_for_status()
    data = response.json()
except Exception as e:
    st.error(f"Error fetching data: {e}")
    st.stop()

# === Process Data ===
df = pd.DataFrame(data)

if df.empty:
    st.warning("No data found for the selected date.")
    st.stop()

# === Type Conversion and Calculations ===
df["spend"] = pd.to_numeric(df.get("spend", 0), errors="coerce").fillna(0)
df["revenue"] = pd.to_numeric(df.get("revenue", 0), errors="coerce").fillna(0)
df["ROAS"] = (df["revenue"] / df["spend"]).replace([float("inf"), -float("inf")], 0).fillna(0)
df["Profit"] = df["revenue"] - df["spend"]

# === Display Columns ===
columns_to_display = ["ad_name", "status", "daily_budget", "spend", "revenue", "ROAS", "Profit"]
df_display = df[columns_to_display].copy()
df_display.rename(columns={
    "ad_name": "Ad Name",
    "status": "Status",
    "daily_budget": "Budget ($)",
    "spend": "Spend ($)",
    "revenue": "Revenue ($)",
    "ROAS": "ROAS",
    "Profit": "Profit ($)"
}, inplace=True)

# === Filter by Account ===
accounts = df["account_id"].dropna().unique().tolist()
selected_account = st.selectbox("Filter by account", ["All"] + accounts)

if selected_account != "All":
    df_display = df_display[df["account_id"] == selected_account]

# === Main Table ===
st.subheader("📋 Ads Overview")
st.dataframe(df_display.style.format({
    "Budget ($)": "${:,.2f}",
    "Spend ($)": "${:,.2f}",
    "Revenue ($)": "${:,.2f}",
    "ROAS": "{:.0%}",
    "Profit ($)": "${:,.2f}"
}))

# === Summary ===
total_spend = df_display["Spend ($)"].sum()
total_revenue = df_display["Revenue ($)"].sum()
total_profit = df_display["Profit ($)"].sum()
total_roas = (total_revenue / total_spend) if total_spend != 0 else 0

st.markdown("---")
st.markdown("### 🔢 Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Spend", f"${total_spend:,.2f}")
col2.metric("Total Revenue", f"${total_revenue:,.2f}")
col3.metric("Profit", f"${total_profit:,.2f}", delta=f"{(total_profit/total_spend)*100:.1f}%" if total_spend else None)
col4.metric("True ROAS", f"{total_roas:.0%}")

# === Future Controls ===
st.markdown("---")
st.markdown("### 🛠️ Actions (coming soon)")
st.warning("Turning off ads or budget updates will be available in the next version.")
