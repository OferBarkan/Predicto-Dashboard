import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adset import AdSet
import json

# Google Sheets auth
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

# Facebook API auth
FacebookAdsApi.init(
    st.secrets["FB_APP_ID"],
    st.secrets["FB_APP_SECRET"],
    st.secrets["FB_ACCESS_TOKEN"]
)

# Sheet setup
spreadsheet_id = "1n6-m2FidDQBTksrLRAEcc9J3qwy8sfsSrEpfC_fZSoY"
sheet = client.open_by_key(spreadsheet_id)
roas_ws = sheet.worksheet("ROAS")
manual_ws = sheet.worksheet("Manual Control")

roas_df = pd.DataFrame(roas_ws.get_all_records())
manual_df = pd.DataFrame(manual_ws.get_all_records())

# Merge on Ad Name
df = roas_df.merge(
    manual_df[["Ad Name", "Ad Set ID", "New Budget", "New Status"]],
    on="Ad Name",
    how="left"
)

# Dashboard setup
st.set_page_config(page_title="Predicto Ads Dashboard", layout="wide")
st.title("Predicto Ads Dashboard")

# Date selection
yesterday = datetime.today() - timedelta(days=1)
date = st.date_input("Select Date", yesterday)
date_str = date.strftime("%Y-%m-%d")

# Filter by date
df = df[df["Date"] == date_str]
if df.empty:
    st.warning("No data found for selected date.")
    st.stop()

# Calculations
df["Spend (USD)"] = pd.to_numeric(df["Spend (USD)"], errors="coerce").fillna(0)
df["Revenue (USD)"] = pd.to_numeric(df["Revenue (USD)"], errors="coerce").fillna(0)
df["ROAS"] = (df["Revenue (USD)"] / df["Spend (USD)"]).replace([float("inf"), -float("inf")], 0)
df["Profit (USD)"] = df["Revenue (USD)"] - df["Spend (USD)"]

# Editable table
st.subheader("Ad Set Control Panel")
for i, row in df.iterrows():
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 1, 1, 1, 1, 1, 1, 1])
    col1.text(row["Ad Name"])
    col2.text(f"${row['Spend (USD)']:.2f}")
    col3.text(f"${row['Revenue (USD)']:.2f}")
    col4.text(f"${row['Profit (USD)']:.2f}")
    col5.text(f"{row['ROAS']:.0%}")

    try:
        default_budget = float(row.get("New Budget", 0))
    except:
        default_budget = 0.0

    new_budget = col6.number_input("New Budget", value=default_budget, step=1.0, key=f"budget_{i}")
    new_status = col7.selectbox("New Status", ["ACTIVE", "PAUSED"], index=0, key=f"status_{i}")

    if col8.button("Apply", key=f"apply_{i}"):
        adset_id = str(row.get("Ad Set ID", "")).strip().replace("'", "")
        try:
            adset = AdSet(adset_id)
            update_params = {}

            if new_budget > 0:
                update_params["daily_budget"] = int(new_budget * 100)

            if new_status:
                update_params["status"] = new_status

            if update_params:
                adset.api_update(params=update_params)
                st.success(f"Updated {row['Ad Name']}")
            else:
                st.warning(f"No updates provided for {row['Ad Name']}")
        except Exception as e:
            st.error(f"Failed to update {row['Ad Name']}: {e}")

# Summary
st.markdown("---")
st.markdown("### Daily Summary")
total_spend = df["Spend (USD)"].sum()
total_revenue = df["Revenue (USD)"].sum()
total_profit = df["Profit (USD)"].sum()
total_roas = total_revenue / total_spend if total_spend else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Spend", f"${total_spend:,.2f}")
col2.metric("Total Revenue", f"${total_revenue:,.2f}")
col3.metric("Profit", f"${total_profit:,.2f}")
col4.metric("Overall ROAS", f"{total_roas:.0%}")
