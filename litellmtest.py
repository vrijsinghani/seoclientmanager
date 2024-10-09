import openai
client = openai.OpenAI(
    api_key="sk-4048081138",
    base_url="http://192.168.30.100:8000" # LiteLLM Proxy is OpenAI compatible, Read More: https://docs.litellm.ai/docs/proxy/user_keys
)
response = client.chat.completions.create(
    model="openai/gpt-4o-mini", # model to send to the proxy
    messages = [
        {
            "role": "user",
            "content": "this is a test request, write a short poem"
        }
    ]
)

print(response)