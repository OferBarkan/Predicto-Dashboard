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
roas_ws = sheet.worksheet("ROAS")
man_ws = sheet.worksheet("Manual Control")
roas_df = pd.DataFrame(roas_ws.get_all_records())
man_df = pd.DataFrame(man_ws.get_all_records())

# === הגדרות דשבורד ===
st.set_page_config(page_title="Predicto Ads Dashboard", layout="wide")
st.title("Predicto Ads Dashboard")

# === בחירת תאריך ===
yesterday = datetime.today() - timedelta(days=1)
date = st.date_input("Select Date", yesterday)
date_str = date.strftime("%Y-%m-%d")
today_str = datetime.today().strftime("%Y-%m-%d")

# === סינון נתונים לפי תאריך נבחר ===
df = roas_df[roas_df["Date"] == date_str].copy()
if df.empty:
    st.warning("No data available for the selected date.")
    st.stop()

# === הצמדת נתוני יום קודם (DBF) לכל תאריך נבחר ===
prev_day = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)
prev_day_str = prev_day.strftime("%Y-%m-%d")

roas_prev = roas_df[roas_df["Date"] == prev_day_str][[
    "Ad Name", "Custom Channel ID", "Search Style ID", "ROAS"
]].rename(columns={"ROAS": "DBF"})

for col in ["Ad Name", "Custom Channel ID", "Search Style ID"]:
    df[col] = df[col].astype(str).str.strip()
    roas_prev[col] = roas_prev[col].astype(str).str.strip()

df = df.merge(
    roas_prev,
    on=["Ad Name", "Custom Channel ID", "Search Style ID"],
    how="left"
)

# === חישובים ===
df["Spend (USD)"] = pd.to_numeric(df["Spend (USD)"], errors="coerce").fillna(0)
df["Revenue (USD)"] = pd.to_numeric(df["Revenue (USD)"], errors="coerce").fillna(0)
df["ROAS"] = (df["Revenue (USD)"] / df["Spend (USD)"]).replace([float("inf"), -float("inf")], 0)
df["Profit (USD)"] = df["Revenue (USD)"] - df["Spend (USD)"]

man_df["Current Budget (ILS)"] = pd.to_numeric(man_df["Current Budget (ILS)"], errors="coerce").fillna(0)
df = df.merge(
    man_df[["Ad Name", "Ad Set ID", "Current Budget (ILS)", "New Budget", "New Status"]],
    on="Ad Name",
    how="left"
)
df["Current Budget"] = df["Current Budget (ILS)"]

# === חילוץ Style ID ===
df["Style ID"] = df["Ad Name"].str.split("-").str[0]
df = df.sort_values(by=["Style ID", "Ad Name"], ascending=[True, True])

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

# === סינון לפי Style ID ===
st.subheader("Ad Set Control Panel")
style_options = ["All"] + sorted(df["Style ID"].unique())
selected_style = st.selectbox("Filter by Style ID", style_options)

if selected_style != "All":
    df = df[df["Style ID"] == selected_style]

# === כותרות טבלה ===
header_cols = st.columns([2, 1, 1, 1, 1, 1, 1.5, 1.5, 1])
headers = ["Ad Name", "Spend", "Revenue", "Profit", "ROAS", "DBF", "Current Budget", "New Budget", "New Status", "Action"]
for col, title in zip(header_cols, headers):
    col.markdown(f"**{title}**")

# === טבלת שורות ===
for i, row in df.iterrows():
    cols = st.columns([2, 1, 1, 1, 1, 1, 1.2, 1.2, 1, 0.8])

    cols[0].markdown(row["Ad Name"])
    cols[1].markdown(f"${row['Spend (USD)']:.2f}")
    cols[2].markdown(f"${row['Revenue (USD)']:.2f}")
    cols[3].markdown(f"${row['Profit (USD)']:.2f}")

    roas = row["ROAS"]
    if roas < 0.7:
        roas_color = "#B31B1B"
    elif roas < 0.95:
        roas_color = "#FDC1C5"
    elif roas < 1.10:
        roas_color = "#FBEEAC"
    elif roas < 1.40:
        roas_color = "#93C572"
    else:
        roas_color = "#019529"
    cols[4].markdown(
        f"<div style='background-color:{roas_color}; padding:4px 8px; border-radius:4px; text-align:center; color:black'><b>{roas:.0%}</b></div>",
        unsafe_allow_html=True,
    )

    try:
        dbf_val = str(row["DBF"]).replace("%", "").strip()
        dbf_val = float(dbf_val) / 100
        cols[5].markdown(f"{dbf_val:.0%}")
    except:
        cols[5].markdown("")

    cols[6].markdown(f"{row['Current Budget']:.1f}")

    try:
        default_budget = float(row.get("New Budget", 0))
    except:
        default_budget = 0.0

    new_budget = cols[7].number_input(" ", value=default_budget, step=1.0, key=f"budget_{i}", label_visibility="collapsed")
    new_status = cols[8].selectbox(" ", options=["ACTIVE", "PAUSED"], index=0, key=f"status_{i}", label_visibility="collapsed")

    if cols[9].button("Apply", key=f"apply_{i}"):
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

# === סיכום ל-Style ===
if selected_style != "All":
    style_df = df
    style_spend = style_df["Spend (USD)"].sum()
    style_revenue = style_df["Revenue (USD)"].sum()
    style_profit = style_df["Profit (USD)"].sum()
    style_roas = style_revenue / style_spend if style_spend else 0

    if style_roas < 0.7:
        roas_color = "#B31B1B"
    elif style_roas < 0.95:
        roas_color = "#FDC1C5"
    elif style_roas < 1.10:
        roas_color = "#FBEEAC"
    elif style_roas < 1.40:
        roas_color = "#93C572"
    else:
        roas_color = "#019529"

    st.markdown(
        f"""
        <div style="margin-top:1rem; padding:0.5rem 1rem; font-size:16px;">
        <span style="font-weight:bold;">📘 Summary for Style ID</span>
        <span style="background-color:#FFA500; color:black; padding:2px 6px; border-radius:4px; font-weight:bold;">{selected_style}</span>
        — Spend: ${style_spend:.2f}, Revenue: ${style_revenue:.2f}, Profit: ${style_profit:.2f},
        <span style="background-color:{roas_color}; color:black; padding:2px 6px; border-radius:4px;"><b>{style_roas:.0%}</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )
