import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adset import AdSet

# === Auth ===
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

# === Facebook Init ===
access_token = "..."  # שים כאן את הטוקן שלך
app_id = "..."        # האפליקציה שלך
app_secret = "..."    # הסוד
FacebookAdsApi.init(app_id, app_secret, access_token)

# === Load Sheet ===
spreadsheet_id = "1n6-m2FidDQBTksrLRAEcc9J3qwy8sfsSrEpfC_fZSoY"
sheet = client.open_by_key(spreadsheet_id)
roas_df = pd.DataFrame(sheet.worksheet("ROAS").get_all_records())
control_df = pd.DataFrame(sheet.worksheet("Manual Control").get_all_records())

# === Filter by Date ===
yesterday = datetime.today() - timedelta(days=1)
date = st.date_input("Select date", yesterday)
date_str = date.strftime('%Y-%m-%d')

df = roas_df[roas_df["Date"] == date_str]
control = control_df[control_df["Date"] == date_str]
df = df.merge(control, on=["Date", "Ad Name"], how="left", suffixes=('', '_ctrl'))

if df.empty:
    st.warning("No data for selected date.")
    st.stop()

# === Set Page ===
st.set_page_config(layout="wide")
st.title("📊 Predicto Ads Dashboard")

# === Table Display ===
st.markdown("### ✏️ Editable Control Table")

# Set defaults
if "updates" not in st.session_state:
    st.session_state["updates"] = {}

def update_row(i, adset_id, new_budget, new_status):
    try:
        AdSet(adset_id).api_update({
            "daily_budget": int(new_budget * 100),
            "status": new_status
        })
        st.success(f"Updated {adset_id}")
    except Exception as e:
        st.error(f"Failed to update {adset_id}: {e}")

# Build editable table
for i, row in df.iterrows():
    st.write(f"##### {row['Ad Name']}")
    cols = st.columns([2, 2, 2, 2, 2, 1])
    
    cols[0].write(f"Spend: ${row['Spend (USD)']:,.2f}")
    cols[1].write(f"Revenue: ${row['Revenue (USD)']:,.2f}")
    cols[2].write(f"Profit: ${row['Profit (USD)']:,.2f}")
    try:
        roas_val = float(row['Revenue (USD)']) / float(row['Spend (USD)'])
        cols[3].write(f"ROAS: {roas_val:.0%}")
    except:
        cols[3].write("ROAS: N/A")

    new_budget = cols[4].number_input(
        "New Budget (ILS)", value=float(row.get("Current Budget (ILS)", 0)),
        key=f"budget_{i}"
    )
    new_status = cols[5].selectbox(
        "New Status", options=["ACTIVE", "PAUSED"],
        index=0 if row.get("Current Status", "ACTIVE") == "ACTIVE" else 1,
        key=f"status_{i}"
    )
    if cols[5].button("Apply", key=f"apply_{i}"):
        update_row(i, str(row["Ad Set ID"]).replace("'", ""), new_budget, new_status)
