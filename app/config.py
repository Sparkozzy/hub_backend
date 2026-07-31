import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ghayhpwthdbmnpsptcnb.supabase.co")
DEFAULT_SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
PORT = int(os.getenv("PORT", 8000))
TIMEZONE_STR = os.getenv("TIMEZONE", "America/Sao_Paulo")
