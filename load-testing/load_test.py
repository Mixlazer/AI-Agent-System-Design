#!/usr/bin/env python3
"""
Load Testing Script for LLM Balancer
Duration: 30 minutes
Rate: ~10 requests per minute
Total: ~300 requests
"""

import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
import aiohttp
import statistics
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class TestResult:
    timestamp: str
    provider: str
    model: str
    latency: float
    status: int
    success: bool
    prompt_length: int
    complexity: str = "unknown"
    response: str = ""
    error: str = ""


@dataclass
class TestStats:
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    latencies: List[float] = field(default_factory=list)
    by_provider: Dict[str, Dict[str, Any]] = field(default_factory=lambda: defaultdict(lambda: {"count": 0, "latencies": []}))
    by_model: Dict[str, Dict[str, Any]] = field(default_factory=lambda: defaultdict(lambda: {"count": 0, "latencies": []}))


# Test prompts of varying complexity
TEST_PROMPTS = [
    {"complexity": "low", "prompt": "What is 2+2?"},
    {"complexity": "low", "prompt": "Hello, how are you?"},
    {"complexity": "low", "prompt": "Name the capital of France."},
    {"complexity": "medium", "prompt": "Explain quantum mechanics in simple terms."},
    {"complexity": "medium", "prompt": "Write a Python function to calculate fibonacci numbers."},
    {"complexity": "medium", "prompt": "Compare Python and JavaScript for web development."},
    {"complexity": "high", "prompt": "Write a comprehensive analysis of machine learning approaches to natural language processing."},
    {"complexity": "high", "prompt": "Create a detailed business plan for a SaaS startup in the AI space."},
    {"complexity": "streaming", "prompt": "Write a creative story about AI becoming sentient.", "stream": True},
]


class LoadTester:
    def __init__(self, base_url: str = "http://localhost:8000", ollama_url: str = "http://localhost:8003"):
        self.base_url = base_url
        self.ollama_url = ollama_url
        self.results: List[TestResult] = []
        self.stats = TestStats()
        self.start_time: datetime = None
        self.end_time: datetime = None
        self.use_ollama_classifier = True
    
    async def detect_complexity(self, session: aiohttp.ClientSession, prompt: str) -> str:
        """Detect prompt complexity using rnj-1:8b-cloud or fallback to length-based heuristic"""
        if self.use_ollama_classifier:
            try:
                classifier_prompt = f"""Analyze the complexity of this question and respond with ONLY ONE word: LOW, MEDIUM, or HIGH.

Question: {prompt}

Complexity:"""
                
                payload = {
                    "model": "rnj-1:8b-cloud",
                    "messages": [{"role": "user", "content": classifier_prompt}],
                    "temperature": 0.1,
                    "max_tokens": 10
                }
                
                async with session.post(
                    f"{self.ollama_url}/v1/chat/completions",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip().upper()
                        
                        if "LOW" in content:
                            return "low"
                        elif "MEDIUM" in content:
                            return "medium"
                        elif "HIGH" in content:
                            return "high"
            except Exception as e:
                print(f"  [Classifier] Ollama rnj-1:8b-cloud unavailable: {e}")
                self.use_ollama_classifier = False
        
        # Fallback to length-based heuristic
        length = len(prompt)
        if length < 30:
            return "low"
        elif length < 80:
            return "medium"
        else:
            return "high"

    async def send_request(self, session: aiohttp.ClientSession, prompt_data: Dict[str, Any], model: str) -> TestResult:
        start_time = time.time()
        prompt = prompt_data["prompt"]
        
        # Detect complexity
        complexity = await self.detect_complexity(session, prompt)
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if prompt_data.get("stream"):
            payload["stream"] = True
        
        try:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                response_text = ""
                if prompt_data.get("stream"):
                    async for chunk in response.content:
                        pass
                else:
                    response_text = await response.text()
                    try:
                        data = json.loads(response_text)
                        response_content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        # Truncate for logging
                        response_text = response_content[:200] + "..." if len(response_content) > 200 else response_content
                    except:
                        response_text = response_text[:200]
                
                latency = time.time() - start_time
                provider = response.headers.get("X-Provider", "unknown")
                
                return TestResult(
                    timestamp=datetime.now().isoformat(),
                    provider=provider,
                    model=model,
                    latency=latency,
                    status=response.status,
                    success=response.status == 200,
                    prompt_length=len(prompt),
                    complexity=complexity,
                    response=response_text,
                    error="" if response.status == 200 else await response.text()
                )
        except asyncio.TimeoutError:
            return TestResult(
                timestamp=datetime.now().isoformat(),
                provider="timeout",
                model=model,
                latency=time.time() - start_time,
                status=504,
                success=False,
                prompt_length=len(prompt_data["prompt"]),
                error="Request timeout"
            )
        except Exception as e:
            return TestResult(
                timestamp=datetime.now().isoformat(),
                provider="error",
                model=model,
                latency=time.time() - start_time,
                status=0,
                success=False,
                prompt_length=len(prompt_data["prompt"]),
                error=str(e)
            )

    def _update_stats(self, result: TestResult):
        self.stats.total_requests += 1
        if result.success:
            self.stats.successful += 1
            self.stats.latencies.append(result.latency)
            self.stats.by_provider[result.provider]["count"] += 1
            self.stats.by_provider[result.provider]["latencies"].append(result.latency)
            self.stats.by_model[result.model]["count"] += 1
            self.stats.by_model[result.model]["latencies"].append(result.latency)
        else:
            self.stats.failed += 1

    def _print_progress(self, request_count: int):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rps = request_count / elapsed if elapsed > 0 else 0
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Requests: {request_count} | Success: {self.stats.successful} | Failed: {self.stats.failed} | RPS: {rps:.2f}")

    def _print_final_stats(self):
        print(f"\n--- FINAL STATISTICS ---")
        print(f"Total requests: {self.stats.total_requests}")
        print(f"Successful: {self.stats.successful} ({100*self.stats.successful/self.stats.total_requests:.1f}%)")
        print(f"Failed: {self.stats.failed} ({100*self.stats.failed/self.stats.total_requests:.1f}%)")
        
        if self.stats.latencies:
            print(f"\n--- LATENCY ---")
            print(f"Mean: {statistics.mean(self.stats.latencies):.2f}s")
            print(f"Median: {statistics.median(self.stats.latencies):.2f}s")
            print(f"P95: {sorted(self.stats.latencies)[int(len(self.stats.latencies)*0.95)]:.2f}s")
        
        print(f"\n--- BY PROVIDER ---")
        for provider, data in sorted(self.stats.by_provider.items()):
            print(f"  {provider}: {data['count']} requests")
        
        # Complexity distribution
        print(f"\n--- BY COMPLEXITY ---")
        by_complexity = {"low": 0, "medium": 0, "high": 0}
        for r in self.results:
            if r.complexity in by_complexity:
                by_complexity[r.complexity] += 1
        for comp, count in sorted(by_complexity.items()):
            print(f"  {comp}: {count} requests")
        
        # Sample responses
        print(f"\n--- SAMPLE RESPONSES (first 3) ---")
        successful = [r for r in self.results if r.success][:3]
        for i, r in enumerate(successful, 1):
            print(f"\n[{i}] {r.model} | Complexity: {r.complexity} | Latency: {r.latency:.2f}s")
            print(f"    Response: {r.response[:200]}...")

    def _save_results(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"results_{timestamp}.json"
        with open(results_file, "w") as f:
            json.dump([r.__dict__ for r in self.results], f, indent=2)
        print(f"\nResults saved to: {results_file}")

    async def run_load_test(self, duration_minutes: int = 30, requests_per_minute: int = 10, models: List[str] = None):
        if models is None:
            models = ["minimax/minimax-m2.5:free", "gemma4:31b-cloud"]
        
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(minutes=duration_minutes)
        interval_seconds = 60 / requests_per_minute
        
        print(f"=" * 60)
        print(f"LOAD TEST: {duration_minutes} min, {requests_per_minute} req/min")
        print(f"=" * 60)
        
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=20)
        async with aiohttp.ClientSession(connector=connector) as session:
            request_count = 0
            next_report_time = self.start_time + timedelta(minutes=1)
            
            while datetime.now() < self.end_time:
                prompt_data = random.choice(TEST_PROMPTS)
                model = random.choice(models)
                result = await self.send_request(session, prompt_data, model)
                self.results.append(result)
                self._update_stats(result)
                request_count += 1
                
                if datetime.now() >= next_report_time:
                    self._print_progress(request_count)
                    next_report_time += timedelta(minutes=1)
                
                await asyncio.sleep(interval_seconds)
        
        print(f"\n{'=' * 60}")
        print(f"LOAD TEST COMPLETED")
        print(f"{'=' * 60}")
        self._print_final_stats()
        self._save_results()


async def main():
    tester = LoadTester()
    await tester.run_load_test(
        duration_minutes=30, 
        requests_per_minute=10,
        models=["minimax/minimax-m2.5:free", "gemma4:31b-cloud", "google/gemma-4-E2B-it"]
    )


if __name__ == "__main__":
    asyncio.run(main())
