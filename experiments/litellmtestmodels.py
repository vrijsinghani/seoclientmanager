import dotenv
import os
import requests

data=""
API_BASE_URL = 'https://litellm.neuralami.ai'

LITELLM_MASTER_KEY='sk-H6WNsJZ26q9k0JByI3HUSA' # seomanager dev
if not data:
    url = f'{API_BASE_URL}/models'
    headers = {'accept': 'application/json', 'Authorization': f'Bearer {LITELLM_MASTER_KEY}'}
    print(f"url: {url}, headers: {headers}")

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()['data']
        # Sort the data by 'id' in ascending order
        data.sort(key=lambda x: x['id'])
    else:
        pass
#print([item['id'] for item in data])