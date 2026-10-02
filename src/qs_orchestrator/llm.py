import os
import httpx


def complete(system: str, prompt: str) -> str:
    base = os.environ["LLM_BASE_URL"].rstrip("/")
    key = os.environ["LLM_API_KEY"]
    model = os.environ["LLM_MODEL"]
    response = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        },
        timeout=180.0,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]
