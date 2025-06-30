import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
import json
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adset import AdSet

# === התחברות ל-Google Sheets דרך secrets ===
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

# התחברות ל-Facebook API
FacebookAdsApi.init(
    st.secrets["FB_APP_ID"],
    st.secrets["FB_APP_SECRET"],
    st.secrets["FB_ACCESS_TOKEN"]
)

# === פרטי הגיליון ===
spreadsheet_id = "1n6-m2FidDQBTksrLRAEcc9J3qwy8sfsSrEpfC_fZSoY"
sheet = client.open_by_key(spreadsheet_id)
ws = sheet.worksheet("Manual Control")
data = ws.get_all_records()
df = pd.DataFrame(data)

# === הגדרות הדשבורד ===
st.set_page_config(page_title="Predicto Ads Dashboard", layout="wide")
st.title("📊 Predicto Ads Dashboard")

# === בחירת תאריך ===
yesterday = datetime.today() - timedelta(days=1)
date = st.date_input("Select date", yesterday)
date_str = date.strftime("%Y-%m-%d")

# === סינון לפי תאריך ===
df = df[df["Date"] == date_str]
if df.empty:
    st.warning("No data for selected date.")
    st.stop()

# === טבלת עריכה ===
st.markdown("### ✏️ Editable Control Table")

for i, row in df.iterrows():
    st.markdown(f"**{row['Ad Name']}**")
    col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 1, 1, 1, 2, 2, 1])
    col1.metric("Spend", f"${row['Current Budget']:.2f}")
    col2.metric("Revenue", f"${row.get('Revenue (USD)', 0):.2f}")
    col3.metric("Profit", f"${row.get('Profit (USD)', 0):.2f}")
    col4.metric("ROAS", f"{row.get('ROAS', 0):.0%}")

    try:
        default_budget = float(row.get("New Budget", 0))
    except (ValueError, TypeError):
        default_budget = 0.0

    new_budget = col5.number_input(
        "New Budget (ILS)",
        value=default_budget,
        step=1.0,
        key=f"budget_{i}"
    )

    new_status = col6.selectbox(
        "New Status",
        options=["ACTIVE", "PAUSED"],
        index=0 if row.get("New Status") != "PAUSED" else 1,
        key=f"status_{i}"
    )

    if col7.button("Apply", key=f"apply_{i}"):
        adset_id = str(row['Ad Set ID']).replace("'", "")
        try:
            adset = AdSet(adset_id)
            if new_status:
                adset.api_update(params={"status": new_status})
            if new_budget:
                adset.api_update(params={"daily_budget": int(float(new_budget) * 100)})
            st.success(f"✅ Updated {row['Ad Name']}")
        except Exception as e:
            st.error(f"❌ Error updating {row['Ad Name']}: {e}")
