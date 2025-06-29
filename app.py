import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adset import AdSet

# === Streamlit Page Setup ===
st.set_page_config(page_title="Predicto Ads Dashboard", layout="wide")
st.title("📊 Predicto Ads Dashboard")

# === Google Sheets Auth ===
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

# === Facebook API Init ===
access_token = "EAAOOQ3qqHXwBO6ZAMZCpwltJ5lDnxPurZBvimJaE747ZBZC8dvBPJphaMhVeOrHeTU1hhsRjogSIc7SQDZChKLSfVc2W5vceXNncM1CwLgIFdIPeaIOZBvmMaKHnFnM2XyGmB9BiQvBZC3I8oNL2HtplT2cU0Hs4nHrazprClGTIhHY0X9U9u2EOUjy98nFUcYoZD"
app_id = "1000845402054012"
app_secret = "516290b16501656af88b98e57ae27da7"
FacebookAdsApi.init(app_id, app_secret, access_token)

# === Load ROAS Sheet ===
spreadsheet_id = "1n6-m2FidDQBTksrLRAEcc9J3qwy8sfsSrEpfC_fZSoY"
sheet = client.open_by_key(spreadsheet_id)
roas_ws = sheet.worksheet("ROAS")
roas_data = pd.DataFrame(roas_ws.get_all_records())

# === Date Filter ===
yesterday = datetime.today() - timedelta(days=1)
selected_date = st.date_input("Select Date", yesterday)
date_str = selected_date.strftime("%Y-%m-%d")

df = roas_data[roas_data["Date"] == date_str]
if df.empty:
    st.warning("No data for selected date.")
    st.stop()

# === Calculations ===
df["Spend (USD)"] = pd.to_numeric(df["Spend (USD)"], errors="coerce").fillna(0)
df["Revenue (USD)"] = pd.to_numeric(df["Revenue (USD)"], errors="coerce").fillna(0)
df["ROAS"] = (df["Revenue (USD)"] / df["Spend (USD)"]).replace([float("inf"), -float("inf")], 0)
df["Profit (USD)"] = df["Revenue (USD)"] - df["Spend (USD)"]

# === Display ROAS Table ===
st.subheader("📋 Ads Overview")
roas_cols = ["Ad Name", "Spend (USD)", "Revenue (USD)", "Profit (USD)", "ROAS"]
st.dataframe(df[roas_cols].style.format({
    "Spend (USD)": "${:,.2f}",
    "Revenue (USD)": "${:,.2f}",
    "Profit (USD)": "${:,.2f}",
    "ROAS": "{:.0%}"
}))

# === Summary ===
st.markdown("---")
st.markdown("### 🔢 Daily Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Spend", f"${df['Spend (USD)'].sum():,.2f}")
col2.metric("Total Revenue", f"${df['Revenue (USD)'].sum():,.2f}")
col3.metric("Profit", f"${df['Profit (USD)'].sum():,.2f}")
col4.metric("True ROAS", f"{(df['Revenue (USD)'].sum() / df['Spend (USD)'].sum() if df['Spend (USD)'].sum() else 0):.0%}")

# === Load Manual Control Tab ===
st.markdown("---")
st.subheader("🎛️ Manual Control")

try:
    control_ws = sheet.worksheet("Manual Control")
    control_df = pd.DataFrame(control_ws.get_all_records())
except Exception as e:
    st.error("Couldn't load 'Manual Control' tab.")
    st.stop()

# === Row-by-row controls ===
for i, row in control_df.iterrows():
    ad_name = row["Ad Name"]
    adset_id = str(row["Ad Set ID"]).replace("'", "")
    current_status = row.get("Current Status", "UNKNOWN")
    current_budget = row.get("Current Budget (ILS)", 0)

    st.markdown("----")
    st.markdown(f"#### 📣 {ad_name}")
    c1, c2, c3 = st.columns([3, 3, 2])

    with c1:
        new_budget = st.number_input("New Budget (ILS)", min_value=0.0, value=float(current_budget), key=f"budget_{i}")

    with c2:
        new_status = st.selectbox("New Status", options=["ACTIVE", "PAUSED"], index=0 if current_status == "ACTIVE" else 1, key=f"status_{i}")

    with c3:
        if st.button("Apply", key=f"apply_{i}"):
            try:
                AdSet(adset_id).api_update({
                    "daily_budget": int(new_budget * 100),  # ILS to agorot
                    "status": new_status
                })
                st.success(f"✅ Updated: {ad_name}")
            except Exception as e:
                st.error(f"❌ Failed to update {ad_name}: {e}")
