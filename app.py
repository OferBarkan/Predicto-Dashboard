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

# === Load Sheets ===
spreadsheet_id = "1n6-m2FidDQBTksrLRAEcc9J3qwy8sfsSrEpfC_fZSoY"
sheet = client.open_by_key(spreadsheet_id)
roas_ws = sheet.worksheet("ROAS")
control_ws = sheet.worksheet("Manual Control")

# === Load data ===
roas_df = pd.DataFrame(roas_ws.get_all_records())
control_df = pd.DataFrame(control_ws.get_all_records())

# === Filter by date ===
yesterday = datetime.today() - timedelta(days=1)
selected_date = st.date_input("Select Date", yesterday)
date_str = selected_date.strftime("%Y-%m-%d")

df = roas_df[roas_df["Date"] == date_str]
control = control_df[control_df["Date"] == date_str]

if df.empty or control.empty:
    st.warning("No data for selected date.")
    st.stop()

# === Merge ROAS + Manual ===
df = df.merge(control, on=["Date", "Ad Name"], how="left", suffixes=('', '_ctrl'))

# === Display table with inline controls ===
st.markdown("### 🎛️ Ad Set Control Panel")

for i, row in df.iterrows():
    st.markdown("----")
    st.markdown(f"#### 📣 {row['Ad Name']}")

    col1, col2, col3 = st.columns([2, 2, 1])
    col1.metric("Spend", f"${row['Spend (USD)']:,.2f}")
    col1.metric("Revenue", f"${row['Revenue (USD)']:,.2f}")
    col2.metric("ROAS", f"{row['ROAS']:.0%}")
    col2.metric("Profit", f"${row['Profit (USD)']:,.2f}")

    current_budget = row.get("Current Budget (ILS)", 0)
    current_status = row.get("Current Status", "UNKNOWN")
    adset_id = str(row.get("Ad Set ID")).replace("'", "")

    col4, col5, col6 = st.columns([2, 2, 1])
    new_budget = col4.number_input("New Budget (ILS)", min_value=0.0, value=float(current_budget), key=f"budget_{i}")
    new_status = col5.selectbox("New Status", options=["ACTIVE", "PAUSED"], index=0 if current_status == "ACTIVE" else 1, key=f"status_{i}")

    if col6.button("Apply", key=f"apply_{i}"):
        try:
            AdSet(adset_id).api_update({
                "daily_budget": int(new_budget * 100),
                "status": new_status
            })
            st.success(f"✅ Updated {row['Ad Name']}")
        except Exception as e:
            st.error(f"❌ Failed: {e}")
