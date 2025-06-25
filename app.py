import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

creds = Credentials.from_service_account_info(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
client = gspread.authorize(creds)

spreadsheet_id = "1n6-m2FidDQBTksrLRAEccJj3qwy8sfsfEpFC_ZSoV"
sheet = client.open_by_key(spreadsheet_id)
worksheet = sheet.worksheet("ROAS")
data = worksheet.get_all_records()

st.write("✅ הצלחה! הנתונים:")
st.dataframe(data)
