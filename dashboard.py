import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="Predicto Dashboard", layout="wide")

# === Header ===
st.title("📊 Predicto Ads Dashboard")

# === Date Selection ===
today = datetime.today()
yesterday = today - timedelta(days=1)

def format_date(dt):
    return dt.strftime("%Y-%m-%d")

def_date = format_date(yesterday)
date = st.date_input("Select date", yesterday)
date_str = format_date(date)

# === Fetching data from Flask API ===
API_URL = f"https://e8a7-35-230-163-243.ngrok-free.app/ads?date={date_str}"
try:
    response = requests.get(API_URL)
    data = response.json()
except Exception as e:
    st.error(f"Error fetching data: {e}")
    st.stop()

# === Convert to DataFrame ===
df = pd.DataFrame(data)

if df.empty:
    st.warning("No data found for selected date.")
    st.stop()

# === Processing ===
df["Spend"] = df["spend"].astype(float)
if "revenue" in df.columns:
    df["Revenue"] = df["revenue"].astype(float)
else:
    df["Revenue"] = 0.0
df["ROAS"] = (df["Revenue"] / df["Spend"]).replace([float("inf"), -float("inf")], 0).fillna(0)
df["Profit"] = df["Revenue"] - df["Spend"]

# === Display Columns ===
columns_to_display = ["ad_name", "status", "daily_budget", "Spend", "Revenue", "ROAS", "Profit"]
df_display = df[columns_to_display].copy()
df_display.rename(columns={
    "ad_name": "Ad Name",
    "status": "Status",
    "daily_budget": "Budget ($)",
    "Spend": "Spend ($)",
    "Revenue": "Revenue ($)",
    "ROAS": "ROAS",
    "Profit": "Profit ($)"
}, inplace=True)

# === Filter by Account ID ===
accounts = df["account_id"].unique().tolist()
selected_account = st.selectbox("Filter by account", ["All"] + accounts)

if selected_account != "All":
    df_display = df_display[df["account_id"] == selected_account]

# === Display Main Table ===
st.subheader("📋 Ads Overview")
st.dataframe(df_display.style.format({
    "Budget ($)": "${:,.2f}",
    "Spend ($)": "${:,.2f}",
    "Revenue ($)": "${:,.2f}",
    "ROAS": "{:.0%}",
    "Profit ($)": "${:,.2f}"
}))

# === Summary Row ===
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

# === Action Placeholder ===
st.markdown("---")
st.markdown("### 🛠️ Actions (coming soon)")
st.warning("Pause/change budgets will be added in the next step.")
