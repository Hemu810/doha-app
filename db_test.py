import pymssql
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Read credentials
server = os.getenv("DB_SERVER")
port = os.getenv("DB_PORT", "1433")
user = os.getenv("DB_USERNAME")
password = os.getenv("DB_PASSWORD")
database = os.getenv("DB_DATABASE")

try:
    print(f"Connecting to {server}:{port} as {user}...")
    conn = pymssql.connect(server=server, port=int(port), user=user, password=password, database=database, timeout=10)
    cursor = conn.cursor()
    cursor.execute("SELECT TOP 1 name FROM sys.tables")
    row = cursor.fetchone()
    if row:
        print(f"✅ Connected successfully. First table name: {row[0]}")
    else:
        print("✅ Connected, but no tables found.")
    conn.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")