"""Shared DeepSeek LLM client for all agents.
Reads API key ONLY from .env file — ignores system environment variables."""

import os
import json
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

def _read_env_file():
    """Parse .env file manually — ignores system environment variables."""
    if not os.path.exists(ENV_PATH):
        return {}
    env_vars = {}
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                env_vars[key.strip()] = value.strip().strip('"').strip("'")
    return env_vars

_client = None

def get_client():
    global _client
    if _client is None:
        env = _read_env_file()
        api_key = env.get("DEEPSEEK_API_KEY", "")
        if not api_key or api_key == "your_deepseek_api_key_here":
            raise RuntimeError(
                "DEEPSEEK_API_KEY not set in .env file. "
                "Add your key to the .env file as: DEEPSEEK_API_KEY=sk-..."
            )
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )
    return _client

def call_agent(system_prompt, user_message, model="deepseek-chat", temperature=0.3, expect_json=True):
    """Call DeepSeek API. Set expect_json=False for plain text responses."""
    client = get_client()
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=temperature,
    )
    if expect_json:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    if expect_json:
        return json.loads(content)
    return content
