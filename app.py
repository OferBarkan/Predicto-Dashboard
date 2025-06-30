import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adset import AdSet
import json

# === התחברות ל-Google Sheets דרך secrets ===
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

# === התחברות ל-Facebook API ===
FacebookAdsApi.init(
    st.secrets["FB_APP_ID"],
    st.secrets["FB_APP_SECRET"],
    st.secrets["FB_ACCESS_TOKEN"]
)

# === פרטי הגיליון ===
spreadsheet_id = "1n6-m2FidDQBTksrLRAEcc9J3qwy8sfsSrEpfC_fZSoY"
sheet = client.open_by_key(spreadsheet_id)
# טאב ROAS
roas_ws = sheet.worksheet("ROAS")
roas_data = roas_ws.get_all_records()
roas_df = pd.DataFrame(roas_data)

# טאב Manual Control
manual_ws = sheet.worksheet("Manual Control")
manual_data = manual_ws.get_all_records()
man_df = pd.DataFrame(manual_data)

# מיזוג לפי Ad Name
merged_df = roas_df.merge(
    man_df[["Ad Name", "Ad Set ID", "Current Budget", "New Budget", "New Status"]],
    on="Ad Name",
    how="left"
)

# === הגדרות הדשבורד ===
st.set_page_config(page_title="Predicto Ads Dashboard", layout="wide")
st.title("Predicto Ads Dashboard")

# === בחירת תאריך ===
yesterday = datetime.today() - timedelta(days=1)
date = st.date_input("Select Date", yesterday)
date_str = date.strftime("%Y-%m-%d")

# === סינון לפי תאריך ===
df = merged_df[merged_df["Date"] == date_str]
if df.empty:
    st.warning("No data available for the selected date.")
    st.stop()

# === חישובים ===
df["Spend (USD)"] = pd.to_numeric(df["Spend (USD)"], errors="coerce").fillna(0)
df["Revenue (USD)"] = pd.to_numeric(df["Revenue (USD)"], errors="coerce").fillna(0)
df["ROAS"] = (df["Revenue (USD)"] / df["Spend (USD)"]).replace([float("inf"), -float("inf")], 0)
df["Profit (USD)"] = df["Revenue (USD)"] - df["Spend (USD)"]

# === הצגת טבלה עם שדות ניתנים לעריכה ===
st.subheader("Ad Set Control Panel")

header_cols = st.columns([2, 1, 1, 1, 1, 1, 1.5, 1.5, 1])
headers = ["Ad Name", "Spend", "Revenue", "Profit", "ROAS", "Current Budget", "New Budget", "New Status", "Action"]
for col, title in zip(header_cols, headers):
    col.markdown(f"**{title}**")

for i, row in df.iterrows():
    col1, col2, col3, col4, col5, col6, col7, col8, col9 = st.columns([2, 1, 1, 1, 1, 1, 1.5, 1.5, 1])

    col1.markdown(row["Ad Name"])
    col2.markdown(f"${row['Spend (USD)']:.2f}")
    col3.markdown(f"${row['Revenue (USD)']:.2f}")
    col4.markdown(f"${row['Profit (USD)']:.2f}")
    col5.markdown(f"{row['ROAS']:.0%}")
    col6.markdown(f"{row['Current Budget']:.1f}")

    try:
        default_budget = float(row.get("New Budget", 0))
    except:
        default_budget = 0.0

    new_budget = col7.number_input(
        label=" ",
        value=default_budget,
        step=1.0,
        key=f"budget_{i}",
        label_visibility="collapsed"
    )
    new_status = col8.selectbox(
        label=" ",
        options=["ACTIVE", "PAUSED"],
        index=0,
        key=f"status_{i}",
        label_visibility="collapsed"
    )

    if col9.button("Apply", key=f"apply_{i}"):
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
                st.success(f"✔️ Updated {row['Ad Name']}")
            else:
                st.warning(f"⚠️ No valid updates provided for {row['Ad Name']}")
        except Exception as e:
            st.error(f"❌ Failed to update {row['Ad Name']}: {e}")

# === סיכום כולל ===
st.markdown("---")
st.markdown("### Daily Summary")
total_spend = df["Spend (USD)"].sum()
total_revenue = df["Revenue (USD)"].sum()
total_profit = df["Profit (USD)"].sum()
total_roas = total_revenue / total_spend if total_spend else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Spend", f"${total_spend:,.2f}")
col2.metric("Total Revenue", f"${total_revenue:,.2f}")
col3.metric("Total Profit", f"${total_profit:,.2f}")
col4.metric("Total ROAS", f"{total_roas:.0%}")
