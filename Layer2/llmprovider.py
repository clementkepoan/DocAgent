import os
from openai import OpenAI
from dotenv import load_dotenv

# The client automatically picks up the OPENAI_API_KEY environment variable

load_dotenv()


class LLMProvider:
    def generate(self, prompt: str) -> str:


        client = OpenAI(api_key=os.environ.get("DEEPSEEK_KEY"), base_url="https://api.deepseek.com")

        response = client.chat.completions.create(
            model="deepseek-chat", # Example model, use the latest available
            messages=[{"role": "user", "content": prompt}]
        )

        # Dummy LLM behavior
        return f"[LLM OUTPUT]\n{response.choices[0].message.content}"
    

if __name__ == "__main__":
    llm = LLMProvider()
    prompt = "Write a short description of a Python function that adds two numbers."
    output = llm.generate(prompt)
    print(output)



