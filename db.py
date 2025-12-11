import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    # Fail gracefully or warn if env vars are missing, but for now let's raise/print
    print("Warning: SUPABASE_URL or SUPABASE_KEY not set in environment.")
    print(f"DEBUG: URL={url}, KEY={key}")

supabase: Client = create_client(url or "", key or "")
