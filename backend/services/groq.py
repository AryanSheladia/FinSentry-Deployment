"""Local settings shared by the evidence explanation client."""
import os

DEFAULT_GROQ_MODEL="openai/gpt-oss-20b"
GROQ_ENDPOINT="https://api.groq.com/openai/v1/chat/completions"


class GroqSettings:
    def __init__(self,api_key=None,model=None,transport=None):
        self.api_key=api_key if api_key is not None else os.getenv("GROQ_API_KEY","")
        self.model=model or os.getenv("GROQ_MODEL",DEFAULT_GROQ_MODEL)
        self.timeout=min(60.,max(1.,float(os.getenv("GROQ_TIMEOUT_SECONDS","20"))))
        self.transport=transport
