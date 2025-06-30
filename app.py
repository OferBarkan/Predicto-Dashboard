import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
import json
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adset import AdSet

# === התחברות ל-Google Sheets ===
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

# === התחברות ל-Facebook API ===
FacebookAdsApi.init(
    app_id=st.secrets["FB_APP_ID"],
    app_secret=st.secrets["FB_APP_SECRET"],
    access_token=st.secrets["FB_ACCESS_TOKEN"]
)

# === פרטי הגיליון ===
spreadsheet_id = "1n6-m2FidDQBTksrLRAEcc9J3qwy8sfsSrEpfC_fZSoY"
sheet = client.open_by_key(spreadsheet_id)

# === שליפת נתונים מהטאבים ===
roas_df = pd.DataFrame(sheet.worksheet("ROAS").get_all_records())
control_df = pd.DataFrame(sheet.worksheet("Manual Control").get_all_records())

# === הגדרות הדשבורד ===
st.set_page_config(page_title="Predicto Ads Dashboard", layout="wide")
st.title("📊 Predicto Ads Dashboard")

# === בחירת תאריך ===
yesterday = datetime.today() - timedelta(days=1)
date = st.date_input("Select date", yesterday)
date_str = date.strftime("%Y-%m-%d")

# === סינון ROAS לפי תאריך ===
df = roas_df[roas_df["Date"] == date_str].copy()
if df.empty:
    st.warning("No data found for the selected date.")
    st.stop()

# === חישובים ===
df["Spend (USD)"] = pd.to_numeric(df["Spend (USD)"], errors="coerce").fillna(0)
df["Revenue (USD)"] = pd.to_numeric(df["Revenue (USD)"], errors="coerce").fillna(0)
df["ROAS"] = (df["Revenue (USD)"] / df["Spend (USD)"]).replace([float("inf"), -float("inf")], 0).fillna(0)
df["Profit (USD)"] = df["Revenue (USD)"] - df["Spend (USD)"]

# === מיזוג עם Manual Control לפי Ad Name ===
df = df.merge(control_df[["Ad Name", "Ad Set ID", "New Budget", "New Status"]], on="Ad Name", how="left")

# === טבלת שליטה עם Apply לכל שורה ===
st.subheader("🛠️ Editable Control Table")

for i, row in df.iterrows():
    with st.container():
        st.markdown(f"**{row['Ad Name']}**")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Spend", f"${row['Spend (USD)']:.2f}")
        col2.metric("Revenue", f"${row['Revenue (USD)']:.2f}")
        col3.metric("Profit", f"${row['Profit (USD)']:.2f}")
        col4.metric("ROAS", f"{row['ROAS']:.0%}")

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

        new_status = col6.selectbox("New Status", ["ACTIVE", "PAUSED"], index=0 if row.get("New Status") == "ACTIVE" else 1, key=f"status_{i}")

        if st.button("Apply", key=f"apply_{i}"):
            try:
                adset_id = str(row["Ad Set ID"]).replace("'", "")
                adset = AdSet(adset_id)
                updates = {
                    "daily_budget": int(new_budget * 100),
                    "status": new_status
                }
                adset.api_update(params=updates)
                st.success(f"Updated {row['Ad Name']} successfully!")
            except Exception as e:
                st.error(f"Failed to update {row['Ad Name']}: {e}")

# === סיכום כולל ===
st.markdown("---")
st.markdown("### 🔢 Daily Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Spend", f"${df['Spend (USD)'].sum():,.2f}")
col2.metric("Total Revenue", f"${df['Revenue (USD)'].sum():,.2f}")
col3.metric("Profit", f"${df['Profit (USD)'].sum():,.2f}")
col4.metric("Overall ROAS", f"{(df['Revenue (USD)'].sum() / df['Spend (USD)'].sum()):.0%}")
