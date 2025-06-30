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
manual_df = pd.DataFrame(manual_data)

# מיזוג לפי Ad Name
df = roas_df.merge(
    manual_df[["Ad Name", "Ad Set ID", "New Budget", "New Status"]],
    on="Ad Name",
    how="left"
)


# === הגדרות הדשבורד ===
st.set_page_config(page_title="Predicto Ads Dashboard", layout="wide")
st.title("📊 Predicto Ads Dashboard")

# === בחירת תאריך ===
yesterday = datetime.today() - timedelta(days=1)
date = st.date_input("בחר תאריך", yesterday)
date_str = date.strftime("%Y-%m-%d")

# === סינון לפי תאריך ===
df = df[df["Date"] == date_str]
if df.empty:
    st.warning("אין נתונים לתאריך שנבחר.")
    st.stop()

# === חישובים ===
df["Spend (USD)"] = pd.to_numeric(df["Spend (USD)"], errors="coerce").fillna(0)
df["Revenue (USD)"] = pd.to_numeric(df["Revenue (USD)"], errors="coerce").fillna(0)
df["ROAS"] = (df["Revenue (USD)"] / df["Spend (USD)"]).replace([float("inf"), -float("inf")], 0)
df["Profit (USD)"] = df["Revenue (USD)"] - df["Spend (USD)"]

# === הצגת טבלה עם שדות ניתנים לעריכה ===
st.subheader("✏️ Editable Ads Table")
editable_data = []

for i, row in df.iterrows():
    col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 1, 1, 1, 1.5, 1.5, 1])
    col1.markdown(f"**{row['Ad Name']}**")
    col2.metric("Spend", f"${row['Spend (USD)']:.2f}")
    col3.metric("Revenue", f"${row['Revenue (USD)']:.2f}")
    col4.metric("Profit", f"${row['Profit (USD)']:.2f}")
    
    try:
        default_budget = float(row.get("New Budget", 0))
    except:
        default_budget = 0.0

    new_budget = col5.number_input("New Budget (ILS)", value=default_budget, step=1.0, key=f"budget_{i}")
    new_status = col6.selectbox("New Status", ["ACTIVE", "PAUSED"], index=0, key=f"status_{i}")

    if col7.button("Apply", key=f"apply_{i}"):
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
st.markdown("### 🧮 סיכום יומי")
total_spend = df["Spend (USD)"].sum()
total_revenue = df["Revenue (USD)"].sum()
total_profit = df["Profit (USD)"].sum()
total_roas = total_revenue / total_spend if total_spend else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("סך הוצאה", f"${total_spend:,.2f}")
col2.metric("סך הכנסה", f"${total_revenue:,.2f}")
col3.metric("רווח", f"${total_profit:,.2f}")
col4.metric("ROAS כולל", f"{total_roas:.0%}")
