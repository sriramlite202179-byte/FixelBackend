import os
from supabase import create_client, Client, create_async_client, AsyncClient
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    # Fail gracefully or warn if env vars are missing, but for now let's raise/print
    print("Warning: SUPABASE_URL or SUPABASE_KEY not set in environment.")
    print(f"DEBUG: URL={url}, KEY={key}")

async def get_supabase():
    return await create_async_client(url or "", key or "")
