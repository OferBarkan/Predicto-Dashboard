import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad
import json

# === התחברות ל-Google Sheets ===
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
roas_df = pd.DataFrame(sheet.worksheet("ROAS").get_all_records())
man_df = pd.DataFrame(sheet.worksheet("Manual Control").get_all_records())

# === פונקציה לעיצוב ROAS ===
def format_roas(val):
    try:
        val = float(val)
    except (ValueError, TypeError):
        return ""
    color = "#B31B1B" if val < 0.7 else "#FDC1C5" if val < 0.95 else "#FBEEAC" if val < 1.10 else "#93C572" if val < 1.4 else "#019529"
    return f"<div style='background-color:{color}; padding:4px 8px; border-radius:4px; text-align:center; color:black'><b>{val:.0%}</b></div>"

# === הגדרות דשבורד ===
st.set_page_config(page_title="Predicto Ads Dashboard", layout="wide")
st.title("Predicto Ads Dashboard")

# === בחירת תאריך ===
yesterday = datetime.today() - timedelta(days=1)
date = st.date_input("Select Date", yesterday)
date_str = date.strftime("%Y-%m-%d")

# === סינון לפי תאריך נבחר ===
df = roas_df[roas_df["Date"] == date_str].copy()
if df.empty:
    st.warning("No data available for the selected date.")
    st.stop()

# === הוספת DBF ו-2DBF ===
prev_day = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)
prev_day_str = prev_day.strftime("%Y-%m-%d")
prev2_day_str = (prev_day - timedelta(days=1)).strftime("%Y-%m-%d")

roas_prev = roas_df[roas_df["Date"] == prev_day_str][["Ad Name", "Custom Channel ID", "Search Style ID", "ROAS"]].rename(columns={"ROAS": "DBF"})
roas_prev2 = roas_df[roas_df["Date"] == prev2_day_str][["Ad Name", "Custom Channel ID", "Search Style ID", "ROAS"]].rename(columns={"ROAS": "2DBF"})

for col in ["Ad Name", "Custom Channel ID", "Search Style ID"]:
    df[col] = df[col].astype(str).str.strip()
    roas_prev[col] = roas_prev[col].astype(str).str.strip()
    roas_prev2[col] = roas_prev2[col].astype(str).str.strip()

df = df.merge(roas_prev, on=["Ad Name", "Custom Channel ID", "Search Style ID"], how="left")
df = df.merge(roas_prev2, on=["Ad Name", "Custom Channel ID", "Search Style ID"], how="left")

# === חישובים ===
df["Spend (USD)"] = pd.to_numeric(df["Spend (USD)"], errors="coerce").fillna(0)
df["Revenue (USD)"] = pd.to_numeric(df["Revenue (USD)"], errors="coerce").fillna(0)
df["ROAS"] = (df["Revenue (USD)"] / df["Spend (USD)"]).replace([float("inf"), -float("inf")], 0)
df["Profit (USD)"] = df["Revenue (USD)"] - df["Spend (USD)"]

man_df["Current Budget (ILS)"] = pd.to_numeric(man_df["Current Budget (ILS)"], errors="coerce").fillna(0)
df = df.merge(
    man_df[["Ad Name", "Ad Set ID", "Ad Status", "Current Budget (ILS)", "New Budget", "New Status"]],
    on="Ad Name",
    how="left"
)
df["Current Budget"] = df["Current Budget (ILS)"]

# === חילוץ Style ID ===
df["Style ID"] = df["Ad Name"].str.split("-").str[0]
df = df.sort_values(by=["Style ID", "Ad Name"])

# === סיכום כולל ===
st.markdown("---")
st.markdown("### Daily Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Spend", f"${df['Spend (USD)'].sum():,.2f}")
col2.metric("Total Revenue", f"${df['Revenue (USD)'].sum():,.2f}")
col3.metric("Total Profit", f"${df['Profit (USD)'].sum():,.2f}")
col4.metric("Total ROAS", f"{(df['Revenue (USD)'].sum() / df['Spend (USD)'].sum()):.0%}" if df["Spend (USD)"].sum() else "0%")

# === סינון לפי Style ID ===
st.subheader("Ad Set Control Panel")
style_options = ["All"] + sorted(df["Style ID"].unique())
selected_style = st.selectbox("Filter by Style ID", style_options)
if selected_style != "All":
    df = df[df["Style ID"] == selected_style]

# === כותרות טבלה ===
header_cols = st.columns([2, 1, 1, 1, 1, 1, 1, 1.2, 1.2, 1, 0.8, 1])
headers = ["Ad Name", "Spend", "Revenue", "Profit", "ROAS", "DBF", "2DBF", "Current Budget", "New Budget", "New Status", "Action", "Ad Status"]
for col, title in zip(header_cols, headers):
    col.markdown(f"**{title}**")

# === שורות ===
for i, row in df.iterrows():
    cols = st.columns([2, 1, 1, 1, 1, 1, 1, 1.2, 1.2, 1, 0.8, 1])
    cols[0].markdown(row["Ad Name"])
    cols[1].markdown(f"${row['Spend (USD)']:.2f}")
    cols[2].markdown(f"${row['Revenue (USD)']:.2f}")
    cols[3].markdown(f"${row['Profit (USD)']:.2f}")
    cols[4].markdown(format_roas(row.get("ROAS")), unsafe_allow_html=True)
    cols[5].markdown(format_roas(row.get("DBF")), unsafe_allow_html=True)
    cols[6].markdown(format_roas(row.get("2DBF")), unsafe_allow_html=True)
    cols[7].markdown(f"{row['Current Budget']:.1f}")

    try:
        default_budget = float(row.get("New Budget", 0))
    except:
        default_budget = 0.0
    new_budget = cols[8].number_input(" ", value=default_budget, step=1.0, key=f"budget_{i}", label_visibility="collapsed")
    new_status = cols[9].selectbox(" ", options=["ACTIVE", "PAUSED"], index=0, key=f"status_{i}", label_visibility="collapsed")

    if cols[10].button("Apply", key=f"apply_{i}"):
        adset_id = str(row.get("Ad Set ID", "")).strip().replace("'", "")
        try:
            update_params = {}
            if new_budget > 0:
                adset = AdSet(adset_id)
                update_params["daily_budget"] = int(new_budget * 100)
                adset.api_update(params={"daily_budget": update_params["daily_budget"]})

            if new_status:
                ad_obj = Ad(adset_id)
                ad_obj.api_update(params={"status": new_status})

            st.success(f"✔️ Updated {row['Ad Name']}")
        except Exception as e:
            st.error(f"❌ Failed to update {row['Ad Name']}: {e}")

    status = str(row.get("Ad Status", "")).upper().strip()
    if status == "ACTIVE":
        color = "#D4EDDA"
    elif status == "PAUSED":
        color = "#5c5b5b"
    elif status == "DELETED":
        color = "#666666"
    else:
        color = "#FFFFFF"
    cols[11].markdown(
        f"<div style='background-color:{color}; padding:4px 8px; border-radius:4px; text-align:center; color:black'><b>{status}</b></div>",
        unsafe_allow_html=True
    )
