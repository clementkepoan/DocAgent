class LLMProvider:
    def generate(self, prompt: str) -> str:
        # Dummy LLM behavior
        return f"[LLM OUTPUT]\n{prompt}"
