import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("CEREBRAS_API_KEY")
if not api_key:
    print("No key")
else:
    r = requests.get('https://api.cerebras.ai/v1/models', headers={'Authorization': f'Bearer {api_key}'})
    print(r.json())
