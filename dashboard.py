import streamlit as st
import pandas as pd
import requests
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adset import AdSet

# === הגדרות ראשוניות ===
access_token = 'EAAOOQ3qqHXwBO6ZAMZCpwltJ5lDnxPurZBvimJaE747ZBZC8dvBPJphaMhVeOrHeTU1hhsRjogSIc7SQDZChKLSfVc2W5vceXNncM1CwLgIFdIPeaIOZBvmMaKHnFnM2XyGmB9BiQvBZC3I8oNL2HtplT2cU0Hs4nHrazprClGTIhHY0X9U9u2EOUjy98nFUcYoZD'
app_id = '1000845402054012'
app_secret = '516290b16501656af88b98e57ae27da7'
FacebookAdsApi.init(app_id, app_secret, access_token)

ad_account_ids = [
    'act_624390568489861',
    'act_1541121412758033',
    'act_3655774171206770',
    'act_357895322715732',
    'act_171104891520748'
]

# === פונקציה להבאת נתונים ===
def fetch_ad_data(account_id):
    account = AdAccount(account_id)
    adsets = account.get_ad_sets(fields=[
        AdSet.Field.name,
        AdSet.Field.status,
        AdSet.Field.daily_budget,
        AdSet.Field.effective_status
    ])
    
    rows = []
    for adset in adsets:
        rows.append({
            'Account': account_id,
            'Ad Set Name': adset[AdSet.Field.name],
            'Status': adset[AdSet.Field.status],
            'Budget (USD)': float(adset[AdSet.Field.daily_budget]) / 100 if adset[AdSet.Field.daily_budget] else 0,
        })
    return pd.DataFrame(rows)

# === תצוגה ===
st.title("Predicto Ads Dashboard")

all_data = pd.DataFrame()
for acc in ad_account_ids:
    try:
        df = fetch_ad_data(acc)
        all_data = pd.concat([all_data, df], ignore_index=True)
    except Exception as e:
        st.warning(f"שגיאה ב-account {acc}: {e}")

st.dataframe(all_data)

