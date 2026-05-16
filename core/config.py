from supabase import create_client, Client

SUPABASE_URL = "https://bcrztgtuoiexafijgtvw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJjcnp0Z3R1b2lleGFmaWpndHZ3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNTg2NTgsImV4cCI6MjA4ODYzNDY1OH0.OWv0Ure8c1tth87oMtRN--Z_YFQKAQ7mphQjD9uDQis"
SECRET_KEY = "HIEN_PRO_SECRET_KEY"
ALGORITHM = "HS256"

# Khởi tạo Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
