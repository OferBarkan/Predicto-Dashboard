import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2 import service_account

# התחברות לפי קובץ מקומי שהועלה לריפו
creds = service_account.Credentials.from_service_account_file(".streamlit/credentials.json")
client = gspread.authorize(creds)
sheet = client.open_by_key("1n6-m2FidDQBTksrLRAEccJj3qwy8sfsfEpFC_ZSoV")

# === הגדרת העמוד ===
st.set_page_config(page_title="Predicto Dashboard", layout="wide")
st.title("📊 Predicto Ads Dashboard")

# === תאריך ברירת מחדל ===
today = datetime.today()
yesterday = today - timedelta(days=1)

def format_date(dt):
    return dt.strftime("%Y-%m-%d")

def_date = format_date(yesterday)
date = st.date_input("Select date", yesterday)
date_str = format_date(date)

# === שליפת טאב ROAS ===
try:
    ws = sheet.worksheet("ROAS")
    df = pd.DataFrame(ws.get_all_records())
except Exception as e:
    st.error(f"שגיאה בגישה ל-Google Sheets: {e}")
    st.stop()

# === סינון לפי תאריך ===
df = df[df["Date"] == date_str]
if df.empty:
    st.warning("לא נמצאו נתונים לתאריך שבחרת.")
    st.stop()

# === חישובים ===
df["Spend (USD)"] = pd.to_numeric(df.get("Spend (USD)", 0), errors="coerce").fillna(0)
df["Revenue (USD)"] = pd.to_numeric(df.get("Revenue (USD)", 0), errors="coerce").fillna(0)
df["ROAS"] = (df["Revenue (USD)"] / df["Spend (USD)"]).replace([float("inf"), -float("inf")], 0).fillna(0)
df["Profit (USD)"] = df["Revenue (USD)"] - df["Spend (USD)"]

# === הצגה בטבלה ===
display_cols = ["Ad Name", "Spend (USD)", "Revenue (USD)", "Profit (USD)", "ROAS"]
st.subheader("📋 Ads Overview")
st.dataframe(df[display_cols].style.format({
    "Spend (USD)": "${:,.2f}",
    "Revenue (USD)": "${:,.2f}",
    "Profit (USD)": "${:,.2f}",
    "ROAS": "{:.0%}"
}))

# === סיכום כולל ===
st.markdown("---")
st.markdown("### 🔢 Summary")
total_spend = df["Spend (USD)"].sum()
total_revenue = df["Revenue (USD)"].sum()
total_profit = df["Profit (USD)"].sum()
total_roas = (total_revenue / total_spend) if total_spend != 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Spend", f"${total_spend:,.2f}")
col2.metric("Total Revenue", f"${total_revenue:,.2f}")
col3.metric("Profit", f"${total_profit:,.2f}", delta=f"{(total_profit/total_spend)*100:.1f}%" if total_spend else None)
col4.metric("True ROAS", f"{total_roas:.0%}")
