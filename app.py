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
access_token = st.secrets["FB_ACCESS_TOKEN"]
app_id = st.secrets["FB_APP_ID"]
app_secret = st.secrets["FB_APP_SECRET"]
FacebookAdsApi.init(app_id, app_secret, access_token)

# === פרטי הגיליון ===
spreadsheet_id = "1n6-m2FidDQBTksrLRAEcc9J3qwy8sfsSrEpfC_fZSoY"
sheet = client.open_by_key(spreadsheet_id)
ws = sheet.worksheet("ROAS")
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

# === המרה מספרית וחישובים ===
df["Spend (USD)"] = pd.to_numeric(df["Spend (USD)"], errors="coerce").fillna(0)
df["Revenue (USD)"] = pd.to_numeric(df["Revenue (USD)"], errors="coerce").fillna(0)
df["Profit (USD)"] = df["Revenue (USD)"] - df["Spend (USD)"]
df["ROAS"] = (df["Revenue (USD)"] / df["Spend (USD)"]).replace([float("inf"), -float("inf")], 0)

# === עמודות שליטה חדשות ===
if "New Budget" not in st.session_state:
    st.session_state["New Budget"] = {}
if "New Status" not in st.session_state:
    st.session_state["New Status"] = {}

st.markdown("### ✏️ Editable Control Table")

for idx, row in df.iterrows():
    ad_name = row['Ad Name']
    adset_id = str(row['Ad Set ID']).replace("'", "")

    st.write(f"**{ad_name}**")
    cols = st.columns([1, 1, 1, 1, 2, 2, 1])
    cols[0].markdown(f"Spend: ${row['Spend (USD)']:.2f}")
    cols[1].markdown(f"Revenue: ${row['Revenue (USD)']:.2f}")
    cols[2].markdown(f"Profit: ${row['Profit (USD)']:.2f}")
    cols[3].markdown(f"ROAS: {row['ROAS']:.0%}")

    new_budget = cols[4].number_input(
        "New Budget (ILS)", min_value=0, value=st.session_state["New Budget"].get(adset_id, 0), key=f"budget_{adset_id}"
    )
    new_status = cols[5].selectbox(
        "New Status", ["ACTIVE", "PAUSED"], index=0 if st.session_state["New Status"].get(adset_id) != "PAUSED" else 1, key=f"status_{adset_id}"
    )

    if cols[6].button("Apply", key=f"apply_{adset_id}"):
        try:
            update_data = {}
            if new_budget > 0:
                update_data['daily_budget'] = int(new_budget * 100)
            if new_status:
                update_data['status'] = new_status
            adset = AdSet(adset_id)
            adset.api_update(params=update_data)
            st.success(f"✅ Updated {ad_name} (Ad Set ID {adset_id})")
        except Exception as e:
            st.error(f"❌ Failed to update {ad_name}: {e}")

# === טבלה מסכמת בסוף הדשבורד ===
st.markdown("---")
st.markdown("### 📋 Ads Overview Table")
view_df = df[["Ad Name", "Spend (USD)", "Revenue (USD)", "Profit (USD)", "ROAS"]].copy()
view_df["ROAS"] = view_df["ROAS"].map(lambda x: f"{x:.0%}")
st.dataframe(view_df.style.format({
    "Spend (USD)": "${:,.2f}",
    "Revenue (USD)": "${:,.2f}",
    "Profit (USD)": "${:,.2f}"
}))

# === סיכום כללי ===
st.markdown("---")
st.markdown("### 📊 Summary")
total_spend = df["Spend (USD)"].sum()
total_revenue = df["Revenue (USD)"].sum()
total_profit = df["Profit (USD)"].sum()
total_roas = total_revenue / total_spend if total_spend else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Spend", f"${total_spend:,.2f}")
c2.metric("Total Revenue", f"${total_revenue:,.2f}")
c3.metric("Profit", f"${total_profit:,.2f}")
c4.metric("Overall ROAS", f"{total_roas:.0%}")
