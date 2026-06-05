"""Test Azure provider connectivity"""
import sys, httpx, asyncio
sys.path.insert(0, r"C:\Users\Farhan\Desktop\agent swarm")
from swarm.config import SwarmConfig


async def test_model(client, endpoint, api_key, model_key, deployment):
    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2024-08-01-preview"
    body = {
        "messages": [{"role": "user", "content": "Say hello in one word"}],
        "max_tokens": 50,
    }
    resp = await client.post(url, headers={"api-key": api_key, "Content-Type": "application/json"}, json=body)
    print(f"  {model_key} (deploy={deployment}): {resp.status_code}")
    if resp.status_code != 200:
        print(f"    Error: {resp.text[:300]}")
    else:
        content = resp.json()["choices"][0]["message"]["content"]
        print(f"    OK: {content[:100]}")
    return resp.status_code == 200


async def main():
    cfg = SwarmConfig.from_opencode_config()
    if "azure-openai" not in cfg.providers:
        print("No Azure provider found")
        return

    pc = cfg.providers["azure-openai"]
    endpoint = pc.endpoint.rstrip("/")
    print(f"Endpoint: {endpoint}")
    print(f"Models in config: {list(pc.models.keys())}")

    async with httpx.AsyncClient(timeout=30) as client:
        results = []
        for model_key, model_cfg in pc.models.items():
            if isinstance(model_cfg, dict):
                deployment = model_cfg.get("deployment", model_key)
            else:
                deployment = model_key
            ok = await test_model(client, endpoint, pc.api_key, model_key, deployment)
            results.append((model_key, ok))

    print("\nWorking models:")
    for name, ok in results:
        if ok:
            print(f"  - {name}")
    print("\nFailed models:")
    for name, ok in results:
        if not ok:
            print(f"  - {name}")


if __name__ == "__main__":
    asyncio.run(main())
