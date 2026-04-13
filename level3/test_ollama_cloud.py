#!/usr/bin/env python3
import httpx
import os

key = os.getenv("OLLAMA_API_KEY", "")
print(f"Key available: {bool(key)}")
print(f"Key prefix: {key[:20]}..." if key else "NO KEY")

# Test with Bearer header
r = httpx.post(
    "https://ollama.com/api/chat",
    json={"model": "rnj-1:8b-cloud", "messages": [{"role": "user", "content": "Hi"}], "stream": False},
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    timeout=15
)
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:300]}")
