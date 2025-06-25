import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

# === התחברות ל-Google Sheets דרך secrets ===
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = st.secrets["GOOGLE_SHEETS_CREDENTIALS"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

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

# === הצגת טבלה ===
st.subheader("🧾 טבלת מודעות")
cols = ["Ad Name", "Spend (USD)", "Revenue (USD)", "Profit (USD)", "ROAS"]
st.dataframe(df[cols].style.format({
    "Spend (USD)": "${:,.2f}",
    "Revenue (USD)": "${:,.2f}",
    "Profit (USD)": "${:,.2f}",
    "ROAS": "{:.0%}"
}))

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
