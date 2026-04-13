#!/usr/bin/env python3
"""Test LLM request through balancer."""
import urllib.request
import urllib.error
import json
import sys

print("Testing LLM request through balancer...")

data = json.dumps({
    "model": "mock-llama-7b",
    "messages": [{"role": "user", "content": "Say hello in 2 sentences"}],
    "stream": False
}).encode('utf-8')

req = urllib.request.Request(
    "http://localhost:8081/v1/chat/completions",
    data=data,
    headers={
        "Authorization": "Bearer agent-default-token",
        "Content-Type": "application/json"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode('utf-8'))
        text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        provider = resp.headers.get('x-selected-provider', 'N/A')
        latency = resp.headers.get('x-provider-latency-ms', 'N/A')
        print(f"Status: {resp.status}")
        print(f"Provider: {provider}")
        print(f"Latency: {latency}ms")
        print(f"Response: {text[:200]}")
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8')
    print(f"HTTP Error {e.code}: {body[:300]}")
except Exception as e:
    print(f"Exception: {e}")
    sys.exit(1)
