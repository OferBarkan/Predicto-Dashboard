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
man_df = pd.DataFrame(manual_data)

# מיזוג לפי Ad Name
merged_df = roas_df.merge(
    man_df[["Ad Name", "Ad Set ID", "Current Budget (ILS)", "New Budget", "New Status"]],
    on="Ad Name",
    how="left"
)

# === הגדרות הדשבורד ===
st.set_page_config(page_title="Predicto Ads Dashboard", layout="wide")
st.title("Predicto Ads Dashboard")

# === בחירת תאריך ===
yesterday = datetime.today() - timedelta(days=1)
date = st.date_input("Select Date", yesterday)
date_str = date.strftime("%Y-%m-%d")

# === סינון לפי תאריך ===
df = merged_df[merged_df["Date"] == date_str]
if df.empty:
    st.warning("No data available for the selected date.")
    st.stop()

# === חישובים ===
df["Spend (USD)"] = pd.to_numeric(df["Spend (USD)"], errors="coerce").fillna(0)
df["Revenue (USD)"] = pd.to_numeric(df["Revenue (USD)"], errors="coerce").fillna(0)
df["ROAS"] = (df["Revenue (USD)"] / df["Spend (USD)"]).replace([float("inf"), -float("inf")], 0)
df["Profit (USD)"] = df["Revenue (USD)"] - df["Spend (USD)"]
df["Current Budget"] = pd.to_numeric(df["Current Budget (ILS)"], errors="coerce").fillna(0)

# === חילוץ Style ID ===
df["Style ID"] = df["Ad Name"].str.split("-").str[0]
df = df.sort_values(by=["Style ID", "ROAS"], ascending=[True, False])

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

# === בחר Style ID להצגה ===
st.subheader("Ad Set Control Panel")
style_options = ["All"] + sorted(df["Style ID"].unique())
selected_style = st.selectbox("Filter by Style ID", style_options)

if selected_style != "All":
    df = df[df["Style ID"] == selected_style]

# === כותרות הטבלה ===
header_cols = st.columns([2, 1, 1, 1, 1, 1, 1.5, 1.5, 1])
headers = ["Ad Name", "Spend", "Revenue", "Profit", "ROAS", "Current Budget", "New Budget", "New Status", "Action"]
for col, title in zip(header_cols, headers):
    col.markdown(f"**{title}**")

# === טבלת המודעות ===
for i, row in df.iterrows():
    col1, col2, col3, col4, col5, col6, col7, col8, col9 = st.columns([2, 1, 1, 1, 1, 1, 1.5, 1.5, 1])
    col1.markdown(row["Ad Name"])
    col2.markdown(f"${row['Spend (USD)']:.2f}")
    col3.markdown(f"${row['Revenue (USD)']:.2f}")
    col4.markdown(f"${row['Profit (USD)']:.2f}")

    roas = row['ROAS']
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
    col5.markdown(f"<div style='background-color:{roas_color}; padding:4px 8px; border-radius:4px; text-align:center; color:black'><b>{roas:.0%}</b></div>", unsafe_allow_html=True)

    col6.markdown(f"{row['Current Budget']:.1f}")

    try:
        default_budget = float(row.get("New Budget", 0))
    except:
        default_budget = 0.0

    new_budget = col7.number_input(" ", value=default_budget, step=1.0, key=f"budget_{i}", label_visibility="collapsed")
    new_status = col8.selectbox(" ", options=["ACTIVE", "PAUSED"], index=0, key=f"status_{i}", label_visibility="collapsed")

    if col9.button("Apply", key=f"apply_{i}"):
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

# === שורת סיכום לאחר הטבלה ===
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
        unsafe_allow_html=True
    )


