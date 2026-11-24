from dotenv import load_dotenv
load_dotenv()

import os
from google import genai
from google.genai import types

proxy = os.getenv("GEMINI_PROXY", "").strip()
print("PROXY:", proxy or "(خالی)")

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(
        client_args={"proxy": proxy} if proxy else {},
    ),
)
r = client.models.generate_content(model="gemini-2.5-flash", contents="سلام")
print(r.text)