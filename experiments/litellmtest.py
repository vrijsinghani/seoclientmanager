import openai
client = openai.OpenAI(
    api_key="sk-H6WNsJZ26q9k0JByI3HUSA",
    base_url="https://litellm.neuralami.ai" # LiteLLM Proxy is OpenAI compatible, Read More: https://docs.litellm.ai/docs/proxy/user_keys
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