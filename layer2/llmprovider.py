import os
import asyncio
from openai import AsyncOpenAI, OpenAI
from dotenv import load_dotenv



load_dotenv()


class LLMProvider:
    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_KEY")
        self.base_url = "https://api.deepseek.com"
    
    def generate(self, prompt: str) -> str:
        """Synchronous LLM call"""
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content
    
    async def generate_async(self, prompt: str) -> str:
        """Asynchronous LLM call for parallel processing"""
        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content
    





