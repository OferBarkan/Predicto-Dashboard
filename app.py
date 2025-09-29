import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adset import AdSet
import json
import math

# ============== UI & PAGE CONFIG ==============
st.set_page_config(page_title="Predicto Ads Dashboard", layout="wide")
st.title("Predicto Ads Dashboard")

# ============== DATA CONNECTIONS ==============
# Google Sheets
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)

# Facebook API
FacebookAdsApi.init(
    st.secrets["FB_APP_ID"],
    st.secrets["FB_APP_SECRET"],
    st.secrets["FB_ACCESS_TOKEN"]
)

# Read sheets
spreadsheet_id = "1n6-m2FidDQBTksrLRAEcc9J3qwy8sfsSrEpfC_fZSoY"
sheet = client.open_by_key(spreadsheet_id)
roas_df = pd.DataFrame(sheet.worksheet("ROAS").get_all_records())
man_df  = pd.DataFrame(sheet.worksheet("Manual Control").get_all_records())

# ============== DATE PICKER: SINGLE vs RANGE ==============
def ymd(d): 
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%Y-%m-%d")

today = datetime.today().date()

view_mode = st.radio("Date scope", ["Single day", "Date range"], horizontal=True)

if view_mode == "Single day":
    # Keep existing behavior
    date = st.date_input("Select Date", today)
    if isinstance(date, tuple):
        # user cleared; guard
        st.stop()
    date = pd.to_datetime(date).date()
    date_str      = ymd(date)
    prev_day_str  = ymd(date - timedelta(days=1))
    prev2_day_str = ymd(date - timedelta(days=2))

    # Filter ROAS to specific date
    df = roas_df[roas_df["Date"] == date_str].copy()
    if df.empty:
        st.warning("No data available for the selected date.")
        st.stop()

    show_dbf = True

else:
    # Date range with quick presets
    preset = st.selectbox(
        "Quick ranges",
        ["Last 7 days", "Last 14 days", "Last 30 days", "This month", "Last month", "Custom"]
    )

    if preset == "This month":
        start = today.replace(day=1)
        end   = today
    elif preset == "Last month":
        first_this = today.replace(day=1)
        last_prev  = first_this - timedelta(days=1)
        start = last_prev.replace(day=1)
        end   = last_prev
    elif preset == "Last 7 days":
        start = today - timedelta(days=6)
        end   = today
    elif preset == "Last 14 days":
        start = today - timedelta(days=13)
        end   = today
    elif preset == "Last 30 days":
        start = today - timedelta(days=29)
        end   = today
    else:
        start_end = st.date_input("Pick date range", (today - timedelta(days=6), today))
        if not isinstance(start_end, (list, tuple)) or len(start_end) != 2:
            st.stop()
        start, end = start_end
        start = pd.to_datetime(start).date()
        end   = pd.to_datetime(end).date()

    start_str, end_str = ymd(start), ymd(end)
    df = roas_df[(roas_df["Date"] >= start_str) & (roas_df["Date"] <= end_str)].copy()
    if df.empty:
        st.warning("No data available for the selected range.")
        st.stop()

    
# ============== CALCULATIONS (PER MODE) ==============
# Normalize numeric
df["Spend (USD)"]   = pd.to_numeric(df["Spend (USD)"], errors="coerce").fillna(0)
df["Revenue (USD)"] = pd.to_numeric(df["Revenue (USD)"], errors="coerce").fillna(0)

if show_dbf:
    # Attach DBF and 2DBF from previous days (as in your original app)
    roas_prev = roas_df[roas_df["Date"] == prev_day_str][
        ["Ad Name", "Custom Channel ID", "Search Style ID", "ROAS"]
    ].rename(columns={"ROAS": "DBF"})

    roas_prev2 = roas_df[roas_df["Date"] == prev2_day_str][
        ["Ad Name", "Custom Channel ID", "Search Style ID", "ROAS"]
    ].rename(columns={"ROAS": "2DBF"})

    for col in ["Ad Name", "Custom Channel ID", "Search Style ID"]:
        df[col]        = df[col].astype(str).str.strip()
        roas_prev[col] = roas_prev[col].astype(str).str.strip()
        roas_prev2[col]= roas_prev2[col].astype(str).str.strip()

    df = df.merge(roas_prev,  on=["Ad Name", "Custom Channel ID", "Search Style ID"], how="left")
    df = df.merge(roas_prev2, on=["Ad Name", "Custom Channel ID", "Search Style ID"], how="left")

else:
    # Aggregate across multiple days
    group_cols = ["Ad Name", "Custom Channel ID", "Search Style ID"]
    df = (
        df.groupby(group_cols, as_index=False)[["Spend (USD)", "Revenue (USD)"]]
          .sum()
    )
    # No DBF/2DBF in range mode (keep columns to avoid key errors later if you wish)
    df["DBF"]  = None
    df["2DBF"] = None

# Post-calcs
df["ROAS"]   = df["Revenue (USD)"] / df["Spend (USD)"]
df["ROAS"]   = df["ROAS"].replace([float("inf"), -float("inf")], 0).fillna(0)
df["Profit (USD)"] = df["Revenue (USD)"] - df["Spend (USD)"]

def clean_roas_column(series):
    return (
        series.astype(str)
        .str.replace("%", "", regex=False)
        .str.strip()
        .replace("", "0")
        .astype(float) / 100
    )

if show_dbf:
    df["DBF"]  = clean_roas_column(df["DBF"])
    df["2DBF"] = clean_roas_column(df["2DBF"])

# ============== MERGE MANUAL CONTROL & META FIELDS ==============
# Budget
man_df["Current Budget (ILS)"] = pd.to_numeric(man_df["Current Budget (ILS)"], errors="coerce").fillna(0)
df = df.merge(
    man_df[["Ad Name", "Ad Set ID", "Ad Status", "Current Budget (ILS)", "New Budget", "New Status", "Current Status"]],
    on="Ad Name",
    how="left"
)
df["Current Budget"] = df["Current Budget (ILS)"]

# Style ID
df["Style ID"] = df["Ad Name"].astype(str).str.split("-").str[0]
df = df.sort_values(by=["Style ID", "Ad Name"])

# Category: the word between _(MT_)?[M/R]_ and next underscore
df["Category"] = (
    df["Ad Name"].astype(str)
      .str.extract(r'_(?:MT_)?[MR]_([^_]+)_', expand=False)
      .fillna("UNKNOWN")
)

# Domain: token after -ch<digits>_ until next underscore (e.g., MT/FM)
df["Domain"] = (
    df["Ad Name"].astype(str)
      .str.extract(r'-ch\d+_([^_]+)_', expand=False)
      .fillna("UNKNOWN")
)

# ============== SUMMARY (TOP METRICS) ==============
st.markdown("---")
st.markdown("### Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Spend",   f"${df['Spend (USD)'].sum():,.2f}")
col2.metric("Total Revenue", f"${df['Revenue (USD)'].sum():,.2f}")
col3.metric("Total Profit",  f"${df['Profit (USD)'].sum():,.2f}")
total_roas = df["Revenue (USD)"].sum() / df["Spend (USD)"].sum() if df["Spend (USD)"].sum() else 0
col4.metric("Total ROAS", f"{total_roas:.0%}")

# ============== FILTERS ROW ==============
st.subheader("Ad Set Control Panel")

# Four narrow filter columns + spacer
c_style, c_status, c_cat, c_dom, _spacer = st.columns([1, 1, 1, 1, 4])

with c_style:
    selected_style = st.selectbox(
        "Filter by Style ID",
        ["All"] + sorted(df["Style ID"].dropna().astype(str).unique()),
        index=0,
        key="filter_style"
    )

with c_status:
    # Compute "Status For Filter" from (New Status if exists) else (Current Status)
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
    category_options = ["All"] + sorted(df["Category"].dropna().astype(str).unique())
    selected_category = st.selectbox(
        "Filter by Category",
        category_options,
        index=0,
        key="filter_category"
    )

with c_dom:
    domain_options = ["All"] + sorted(df["Domain"].dropna().astype(str).unique())
    selected_domain = st.selectbox(
        "Filter by Domain",
        domain_options,
        index=0,
        key="filter_domain"
    )

# Apply filters
if selected_style != "All":
    df = df[df["Style ID"] == selected_style]

if status_filter == "ACTIVE only":
    df = df[df["Status For Filter"] == "ACTIVE"]
elif status_filter == "PAUSED only":
    df = df[df["Status For Filter"] == "PAUSED"]

if selected_category != "All":
    df = df[df["Category"] == selected_category]

if selected_domain != "All":
    df = df[df["Domain"] == selected_domain]

# ============== ROAS CELL FORMATTER ==============
def format_roas(val):
    try:
        if pd.isna(val): 
            return ""
        val = float(val)
    except:
        return ""
    color = "#B31B1B" if val < 0.7 else "#FDC1C5" if val < 0.95 else "#FBEEAC" if val < 1.10 else "#93C572" if val < 1.4 else "#019529"
    return f"<div style='background-color:{color}; padding:4px 8px; border-radius:4px; text-align:center; color:black'><b>{val:.0%}</b></div>"

# ============== TABLE HEADERS (DYNAMIC) ==============
if show_dbf:
    header_cols = st.columns([3, 0.8, 0.8, 0.8, 1, 1, 1, 1, 1, 1, 0.8, 1])
    headers = ["Ad Name", "Spend", "Revenue", "Profit", "ROAS", "DBF", "2DBF", "Current Budget", "New Budget", "New Status", "Action", "AdSet Status"]
else:
    header_cols = st.columns([3, 0.8, 0.8, 0.8, 1, 1, 1, 1, 0.8, 1])
    headers = ["Ad Name", "Spend", "Revenue", "Profit", "ROAS", "Current Budget", "New Budget", "New Status", "Action", "AdSet Status"]

for col, title in zip(header_cols, headers):
    col.markdown(f"**{title}**")

# ============== ROWS + ACTIONS ==============
batched_changes = []  # collect only changed rows

for i, row in df.iterrows():
    if show_dbf:
        cols = st.columns([3, 0.8, 0.8, 0.8, 1, 1, 1, 1, 1, 1, 0.8, 1])
    else:
        cols = st.columns([3, 0.8, 0.8, 0.8, 1, 1, 1, 1, 0.8, 1])

    # Base cells
    cols[0].markdown(row.get("Ad Name", ""))
    cols[1].markdown(f"${float(row.get('Spend (USD)', 0)):.2f}")
    cols[2].markdown(f"${float(row.get('Revenue (USD)', 0)):.2f}")
    cols[3].markdown(f"${float(row.get('Profit (USD)', 0)):.2f}")
    cols[4].markdown(format_roas(row.get("ROAS", 0)), unsafe_allow_html=True)

    if show_dbf:
        cols[5].markdown(format_roas(row.get("DBF", None)),  unsafe_allow_html=True)
        cols[6].markdown(format_roas(row.get("2DBF", None)), unsafe_allow_html=True)
        cols[7].markdown(f"{float(row.get('Current Budget', 0)):.1f}")
        budget_col_i        = 8
        status_col_i        = 9
        action_col_i        = 10
        status_badge_col_i  = 11
    else:
        cols[5].markdown(f"{float(row.get('Current Budget', 0)):.1f}")
        budget_col_i        = 6
        status_col_i        = 7
        action_col_i        = 8
        status_badge_col_i  = 9

    # Inputs
    try:
        default_budget = float(row.get("New Budget", 0)) if pd.notna(row.get("New Budget", 0)) else 0.0
    except:
        default_budget = 0.0

    new_budget = cols[budget_col_i].number_input(" ", value=default_budget, step=1.0,
                                                 key=f"budget_{i}", label_visibility="collapsed")

    cur_status = str(row.get("Current Status", "ACTIVE")).upper().strip()
    status_index = 0 if cur_status == "ACTIVE" else 1
    new_status = cols[status_col_i].selectbox(" ", options=["ACTIVE", "PAUSED"], index=status_index,
                                              key=f"status_{i}", label_visibility="collapsed")

    # Detect changes
    current_budget = float(row.get("Current Budget", 0) or 0)
    budget_changed = (new_budget > 0) and (abs(new_budget - current_budget) >= 0.5)
    status_changed = (new_status != cur_status)

    update_params = {}
    if budget_changed:
        # Facebook expects "minor units"
        update_params["daily_budget"] = int(round(new_budget * 100))
    if status_changed:
        update_params["status"] = new_status

    adset_id = str(row.get("Ad Set ID", "")).strip().replace("'", "")

    # Add to batch only if something changed
    if adset_id and update_params:
        batched_changes.append({
            "adset_id": adset_id,
            "ad_name": row.get("Ad Name", ""),
            "params": update_params
        })

    # Row-level Apply
    if cols[action_col_i].button("Apply", key=f"apply_{i}"):
        try:
            if adset_id and update_params:
                AdSet(adset_id).api_update(params=update_params)
                st.success(f"✔️ Updated {row.get('Ad Name','')}")
            else:
                st.warning(f"⚠️ No valid updates for {row.get('Ad Name','')}")
        except Exception as e:
            st.error(f"❌ Failed to update {row.get('Ad Name','')}: {e}")

    # Status badge
    status = cur_status
    color = "#D4EDDA" if status == "ACTIVE" else "#5c5b5b" if status == "PAUSED" else "#666666"
    cols[status_badge_col_i].markdown(
        f"<div style='background-color:{color}; padding:4px 8px; border-radius:4px; text-align:center; color:black'><b>{status}</b></div>",
        unsafe_allow_html=True
    )

# ============== TOTALS ROW ==============
sum_spend  = float(df["Spend (USD)"].sum())
sum_rev    = float(df["Revenue (USD)"].sum())
sum_profit = float(df["Profit (USD)"].sum())
sum_roas   = (sum_rev / sum_spend) if sum_spend else 0

st.markdown("—")  # thin divider

if show_dbf:
    sum_cols = st.columns([2, 1, 1, 1, 1, 1, 1, 1.2, 1.2, 1, 0.8, 1])
else:
    sum_cols = st.columns([2, 1, 1, 1, 1, 1.2, 1.2, 1, 0.8, 1])

sum_cols[0].markdown("**Total (filtered)**")
sum_cols[1].markdown(f"**${sum_spend:,.2f}**")
sum_cols[2].markdown(f"**${sum_rev:,.2f}**")
sum_cols[3].markdown(f"**${sum_profit:,.2f}**")
sum_cols[4].markdown(format_roas(sum_roas), unsafe_allow_html=True)
for idx in range(5, len(sum_cols)):
    sum_cols[idx].markdown("")

# ============== APPLY ALL (BATCH) ==============
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
