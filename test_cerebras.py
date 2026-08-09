import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("CEREBRAS_API_KEY")
if not api_key:
    print("No key")
else:
    for model in ["llama3.1-70b", "llama3.1-8b"]:
        r = requests.post(
            'https://api.cerebras.ai/v1/chat/completions', 
            headers={'Authorization': f'Bearer {api_key}'},
            json={'model': model, 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 10}
        )
        print(f"{model}: {r.status_code}")
