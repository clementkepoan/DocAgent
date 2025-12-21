import os
from openai import OpenAI
from dotenv import load_dotenv



load_dotenv()


class LLMProvider:
    def generate(self, prompt: str) -> str:


        client = OpenAI(api_key=os.environ.get("DEEPSEEK_KEY"), base_url="https://api.deepseek.com")

        response = client.chat.completions.create(
            model="deepseek-chat", # Example model, use the latest available
            messages=[{"role": "user", "content": prompt}]
        )

        # Dummy LLM behavior
        return response.choices[0].message.content
    





