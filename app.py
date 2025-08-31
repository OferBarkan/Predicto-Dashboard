import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adset import AdSet
import json
import math

# התחברות ל-Google Sheets
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

# קריאת גיליונות
spreadsheet_id = "1n6-m2FidDQBTksrLRAEcc9J3qwy8sfsSrEpfC_fZSoY"
sheet = client.open_by_key(spreadsheet_id)
roas_df = pd.DataFrame(sheet.worksheet("ROAS").get_all_records())
man_df = pd.DataFrame(sheet.worksheet("Manual Control").get_all_records())

# הגדרות דשבורד
st.set_page_config(page_title="Predicto Ads Dashboard", layout="wide")
st.title("Predicto Ads Dashboard")

# בחירת תאריך
yesterday = datetime.today() - timedelta(days=1)
date = st.date_input("Select Date", yesterday)
date_str = date.strftime("%Y-%m-%d")
prev_day_str = (date - timedelta(days=1)).strftime("%Y-%m-%d")
prev2_day_str = (date - timedelta(days=2)).strftime("%Y-%m-%d")

# סינון ROAS לתאריך נבחר
df = roas_df[roas_df["Date"] == date_str].copy()
if df.empty:
    st.warning("No data available for the selected date.")
    st.stop()

# הצמדת DBF ו-2DBF
roas_prev = roas_df[roas_df["Date"] == prev_day_str][["Ad Name", "Custom Channel ID", "Search Style ID", "ROAS"]].rename(columns={"ROAS": "DBF"})
roas_prev2 = roas_df[roas_df["Date"] == prev2_day_str][["Ad Name", "Custom Channel ID", "Search Style ID", "ROAS"]].rename(columns={"ROAS": "2DBF"})

for col in ["Ad Name", "Custom Channel ID", "Search Style ID"]:
    df[col] = df[col].astype(str).str.strip()
    roas_prev[col] = roas_prev[col].astype(str).str.strip()
    roas_prev2[col] = roas_prev2[col].astype(str).str.strip()

df = df.merge(roas_prev, on=["Ad Name", "Custom Channel ID", "Search Style ID"], how="left")
df = df.merge(roas_prev2, on=["Ad Name", "Custom Channel ID", "Search Style ID"], how="left")

# חישובים
df["Spend (USD)"] = pd.to_numeric(df["Spend (USD)"], errors="coerce").fillna(0)
df["Revenue (USD)"] = pd.to_numeric(df["Revenue (USD)"], errors="coerce").fillna(0)
df["ROAS"] = df["Revenue (USD)"] / df["Spend (USD)"]
df["ROAS"] = df["ROAS"].replace([float("inf"), -float("inf")], 0).fillna(0)
df["Profit (USD)"] = df["Revenue (USD)"] - df["Spend (USD)"]

def clean_roas_column(series):
    return (
        series.astype(str)
        .str.replace("%", "", regex=False)
        .str.strip()
        .replace("", "0")
        .astype(float) / 100
    )

df["DBF"] = clean_roas_column(df["DBF"])
df["2DBF"] = clean_roas_column(df["2DBF"])

# תקציב
man_df["Current Budget (ILS)"] = pd.to_numeric(man_df["Current Budget (ILS)"], errors="coerce").fillna(0)
df = df.merge(
    man_df[["Ad Name", "Ad Set ID", "Ad Status", "Current Budget (ILS)", "New Budget", "New Status", "Current Status"]],
    on="Ad Name",
    how="left"
)
df["Current Budget"] = df["Current Budget (ILS)"]

# חילוץ סגנון
df["Style ID"] = df["Ad Name"].str.split("-").str[0]
df = df.sort_values(by=["Style ID", "Ad Name"])

# פונקציית עיצוב ROAS
def format_roas(val):
    try:
        if pd.isna(val): return ""
        val = float(val)
    except: return ""
    color = "#B31B1B" if val < 0.7 else "#FDC1C5" if val < 0.95 else "#FBEEAC" if val < 1.10 else "#93C572" if val < 1.4 else "#019529"
    return f"<div style='background-color:{color}; padding:4px 8px; border-radius:4px; text-align:center; color:black'><b>{val:.0%}</b></div>"

# סיכום כולל
st.markdown("---")
st.markdown("### Daily Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Spend", f"${df['Spend (USD)'].sum():,.2f}")
col2.metric("Total Revenue", f"${df['Revenue (USD)'].sum():,.2f}")
col3.metric("Total Profit", f"${df['Profit (USD)'].sum():,.2f}")
total_roas = df["Revenue (USD)"].sum() / df["Spend (USD)"].sum() if df["Spend (USD)"].sum() else 0
col4.metric("Total ROAS", f"{total_roas:.0%}")

# --- Category from Ad Name ---
# לוכד את המילה שבין _MT_[M/R]_ לבין ה-underscore הבא (למשל Typing / PhD / Teeth)
df["Category"] = (
    df["Ad Name"].astype(str)
      .str.extract(r'_(?:MT_)?[MR]_([^_]+)_', expand=False)
      .fillna("UNKNOWN")
)
# === Filters row (אחרי המטריקות ולפני טבלת הכותרות) ===
st.subheader("Ad Set Control Panel")

# שלוש עמודות צרות לפילטרים + מרווח גדול
c_style, c_status, c_cat, _ = st.columns([1, 1, 1, 5])

with c_style:
    selected_style = st.selectbox(
        "Filter by Style ID",
        ["All"] + sorted(df["Style ID"].unique()),
        index=0,
        key="filter_style"
    )

with c_status:
    # "Status For Filter" כבר מחושב אצלך; אם לא, ודא שהוא קיים כאן
    df["Status For Filter"] = (
        df["New Status"].astype(str).str.upper().str.strip()
          .replace({"": None, "NAN": None})
    ).fillna(df["Current Status"].astype(str).str.upper().str.strip())

    status_filter = st.selectbox(
        "Filter by Ad Set Status",
        ["All", "ACTIVE only", "PAUSED only"],
        index=0,
        key="filter_status"
    )

with c_cat:
    category_options = ["All"] + sorted(df["Category"].unique())
    selected_category = st.selectbox(
        "Filter by Category",
        category_options,
        index=0,
        key="filter_category"
    )

# החלת הסינונים
if selected_style != "All":
    df = df[df["Style ID"] == selected_style]

if status_filter == "ACTIVE only":
    df = df[df["Status For Filter"] == "ACTIVE"]
elif status_filter == "PAUSED only":
    df = df[df["Status For Filter"] == "PAUSED"]

if selected_category != "All":
    df = df[df["Category"] == selected_category]


# כותרות
header_cols = st.columns([3, 0.8, 0.8, 0.8, 1, 1, 1, 1, 1, 1, 0.8, 1])
headers = ["Ad Name", "Spend", "Revenue", "Profit", "ROAS", "DBF", "2DBF", "Current Budget", "New Budget", "New Status", "Action", "AdSet Status"]
for col, title in zip(header_cols, headers):
    col.markdown(f"**{title}**")


batched_changes = []  # נאסוף רק שורות עם שינוי

for i, row in df.iterrows():
    cols = st.columns([3, 0.8, 0.8, 0.8, 1, 1, 1, 1, 1, 1, 0.8, 1])
    cols[0].markdown(row["Ad Name"])
    cols[1].markdown(f"${row['Spend (USD)']:.2f}")
    cols[2].markdown(f"${row['Revenue (USD)']:.2f}")
    cols[3].markdown(f"${row['Profit (USD)']:.2f}")
    cols[4].markdown(format_roas(row["ROAS"]), unsafe_allow_html=True)
    cols[5].markdown(format_roas(row["DBF"]), unsafe_allow_html=True)
    cols[6].markdown(format_roas(row["2DBF"]), unsafe_allow_html=True)
    cols[7].markdown(f"{row['Current Budget']:.1f}")

    # קלטים
    try:
        default_budget = float(row.get("New Budget", 0)) if pd.notna(row.get("New Budget", 0)) else 0.0
    except:
        default_budget = 0.0

    new_budget = cols[8].number_input(" ", value=default_budget, step=1.0,
                                      key=f"budget_{i}", label_visibility="collapsed")
    cur_status = str(row.get("Current Status", "ACTIVE")).upper().strip()
    status_index = 0 if cur_status == "ACTIVE" else 1
    new_status = cols[9].selectbox(" ", options=["ACTIVE", "PAUSED"], index=status_index,
                                   key=f"status_{i}", label_visibility="collapsed")

    # זיהוי שינויים
    current_budget = float(row.get("Current Budget", 0) or 0)
    budget_changed = (new_budget > 0) and (abs(new_budget - current_budget) >= 0.5)
    status_changed = (new_status != cur_status)

    update_params = {}
    if budget_changed:
        update_params["daily_budget"] = int(round(new_budget * 100))  # פייסבוק ב"אגורות"
    if status_changed:
        update_params["status"] = new_status

    adset_id = str(row.get("Ad Set ID", "")).strip().replace("'", "")

    # נכניס ל-batch רק אם יש שינוי
    if adset_id and update_params:
        batched_changes.append({
            "adset_id": adset_id,
            "ad_name": row["Ad Name"],
            "params": update_params
        })

    # כפתור Apply לשורה
    if cols[10].button("Apply", key=f"apply_{i}"):
        try:
            if adset_id and update_params:
                AdSet(adset_id).api_update(params=update_params)
                st.success(f"✔️ Updated {row['Ad Name']}")
            else:
                st.warning(f"⚠️ No valid updates for {row['Ad Name']}")
        except Exception as e:
            st.error(f"❌ Failed to update {row['Ad Name']}: {e}")

    # תצוגת סטטוס
    status = cur_status
    color = "#D4EDDA" if status == "ACTIVE" else "#5c5b5b" if status == "PAUSED" else "#666666"
    cols[11].markdown(
        f"<div style='background-color:{color}; padding:4px 8px; border-radius:4px; text-align:center; color:black'><b>{status}</b></div>",
        unsafe_allow_html=True
    )


# חישוב סיכומים על התצוגה הנוכחית (אחרי כל הפילטרים)
sum_spend  = float(df["Spend (USD)"].sum())
sum_rev    = float(df["Revenue (USD)"].sum())
sum_profit = float(df["Profit (USD)"].sum())
sum_roas   = (sum_rev / sum_spend) if sum_spend else 0

st.markdown("—")  # קו מפריד דק
sum_cols = st.columns([2, 1, 1, 1, 1, 1, 1, 1.2, 1.2, 1, 0.8, 1])

# עמודות סיכום מיושרות תחת הטבלה
sum_cols[0].markdown("**Total (filtered)**")
sum_cols[1].markdown(f"**${sum_spend:,.2f}**")
sum_cols[2].markdown(f"**${sum_rev:,.2f}**")
sum_cols[3].markdown(f"**${sum_profit:,.2f}**")
sum_cols[4].markdown(format_roas(sum_roas), unsafe_allow_html=True)

# להשאיר את שאר העמודות ריקות (או להוסיף טקסט משלים אם תרצה)
for idx in [5,6,7,8,9,10,11]:
    sum_cols[idx].markdown("")

# Apply All
st.markdown("---")
with st.container():
    left, right = st.columns([3, 1])
    with left:
        st.caption(f"{len(batched_changes)} change(s) ready to apply")
        with st.expander("Show pending changes"):
            st.write([
                {"ad_name": x["ad_name"], **x["params"]}
                for x in batched_changes
            ])
    with right:
        if st.button("Apply All Changes"):
            successes, failures = 0, 0
            for upd in batched_changes:
                try:
                    AdSet(upd["adset_id"]).api_update(params=upd["params"])
                    successes += 1
                except Exception as e:
                    failures += 1
                    st.error(f"❌ {upd['ad_name']}: {e}")
            if successes:
                st.success(f"✔️ Applied {successes} update(s)")
            if failures:
                st.warning(f"⚠️ {failures} update(s) failed")
