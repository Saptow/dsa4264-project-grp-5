# OneMap API token: load email and password from .env (see project root)
import os
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load .env from project root (parent of data_processing/)
load_dotenv(Path.cwd().parent / ".env")
email = os.getenv("EMAIL")
password = os.getenv("PASSWORD")
if not email or not password:
    raise ValueError("Set EMAIL and PASSWORD in your .env file (project root)")

url = "https://www.onemap.gov.sg/api/auth/post/getToken"
payload = {"email": email, "password": password}
response = requests.request("POST", url, json=payload)
json_response = response.json()
API_KEY = json_response["access_token"]
expiry_timestamp = int(json_response["expiry_timestamp"])
expiry_time = datetime.utcfromtimestamp(expiry_timestamp).strftime('%Y-%m-%d %H:%M')
print(f"API key retrieved! Expires on: {expiry_time}")
print(f"API key =  {API_KEY}")