import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="Predicto Dashboard", layout="wide")

# === הגדרות כלליות ===
st.title("📊 Predicto Ads Dashboard")
st.markdown("""עקוב אחרי ביצועי המודעות שלך בזמן אמת והפעל או השבת מודעות לפי צורך.""")

# === הגדרות תאריך ===
today = datetime.today()
yesterday = today - timedelta(days=1)
def format_date(dt):
    return dt.strftime("%Y-%m-%d")

def_date = format_date(yesterday)
date = st.date_input("Select date", yesterday)
date_str = format_date(date)

# === שליפת נתונים מהשרת Flask ===
API_URL = f"https://e8a7-35-230-163-243.ngrok-free.app/ads?date={date_str}"
try:
    response = requests.get(API_URL)
    data = response.json()
except Exception as e:
    st.error(f"שגיאה בשליפת הנתונים: {e}")
    st.stop()

# === עיבוד הנתונים ===
df = pd.DataFrame(data)

if df.empty:
    st.warning("לא נמצאו נתונים ליום הנבחר.")
    st.stop()

# === חישובים נוספים ===
df["Spend"] = df["spend"].astype(float)
df["Revenue"] = df.get("revenue", 0).astype(float)
df["ROAS"] = (df["Revenue"] / df["Spend"]).replace([float("inf"), -float("inf")], 0).fillna(0)
df["Profit"] = df["Revenue"] - df["Spend"]

# === בחירת עמודות להצגה ===
columns_to_display = ["ad_name", "status", "daily_budget", "Spend", "Revenue", "ROAS", "Profit"]
df_display = df[columns_to_display]
df_display.rename(columns={
    "ad_name": "Ad Name",
    "status": "Status",
    "daily_budget": "Budget ($)",
    "Spend": "Spend ($)",
    "Revenue": "Revenue ($)",
    "ROAS": "ROAS",
    "Profit": "Profit ($)"
}, inplace=True)

# === סינון לפי חשבון ===
accounts = df["account_id"].unique().tolist()
selected_account = st.selectbox("Filter by account", ["All"] + accounts)

if selected_account != "All":
    df_display = df_display[df["account_id"] == selected_account]

# === טבלה ראשית ===
st.subheader("📋 Ads Overview")
st.dataframe(df_display.style.format({
    "Budget ($)": "${:,.2f}",
    "Spend ($)": "${:,.2f}",
    "Revenue ($)": "${:,.2f}",
    "ROAS": "{:.0%}",
    "Profit ($)": "${:,.2f}"
}))

# === שורת סיכום ===
total_spend = df_display["Spend ($)"].sum()
total_revenue = df_display["Revenue ($)"].sum()
total_profit = df_display["Profit ($)"].sum()
total_roas = (total_revenue / total_spend) if total_spend != 0 else 0

st.markdown("---")
st.markdown("### 🔢 Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Spend", f"${total_spend:,.2f}")
col2.metric("Total Revenue", f"${total_revenue:,.2f}")
col3.metric("Profit", f"${total_profit:,.2f}", delta=f"{(total_profit/total_spend)*100:.1f}%" if total_spend else None)
col4.metric("True ROAS", f"{total_roas:.0%}")

# === פעולות אקטיביות (לשלב הבא) ===
st.markdown("---")
st.markdown("### 🛠️ Actions (לא פעיל עדיין)")
st.warning("כיבוי/שינוי תקציב יתווספו בשלב הבא.")
