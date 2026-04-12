#!/usr/bin/env python3
"""
Advanced Load Test for LLM Balancer
- 10 minutes duration
- Sinusoidal load pattern (day/night cycle)
- 2/3 complex queries
- Smart complexity routing
- Real-time response display
"""

import asyncio
import aiohttp
import json
import math
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
import sys


@dataclass
class TestResult:
    timestamp: str
    provider: str
    model: str
    latency: float
    status: int
    success: bool
    prompt_length: int
    complexity: str
    prompt: str
    response: str
    error: str = ""


@dataclass
class TestStats:
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    latencies: List[float] = field(default_factory=list)
    by_provider: Dict[str, int] = field(default_factory=lambda: {"openrouter": 0, "ollama": 0, "vllm": 0})
    by_complexity: Dict[str, int] = field(default_factory=lambda: {"low": 0, "medium": 0, "high": 0})


class AdvancedLoadTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[TestResult] = []
        self.stats = TestStats()
        self.start_time: Optional[datetime] = None
        self.queue_size = 0  # Simulated queue tracking
        
        # Prompts by complexity
        self.prompts = {
            "low": [
                "What is 2+2?",
                "Say hello",
                "What day is today?",
                "Tell me a joke",
                "Hello world",
            ],
            "medium": [
                "Write a Python function to calculate fibonacci numbers.",
                "Explain the difference between REST and GraphQL.",
                "How does a blockchain work?",
                "What are the benefits of microservices?",
                "Write a SQL query to find duplicates.",
            ],
            "high": [
                """Design a distributed system for a high-frequency trading platform.
                Requirements:
                - Handle 1M transactions per second
                - 99.99% uptime SLA
                - Sub-millisecond latency
                - Global deployment across 5 regions
                - Real-time risk assessment
                - Regulatory compliance (MiFID II)
                Consider network topology, data consistency, failover strategies, and monitoring.""",
                
                """Analyze the architectural trade-offs between consistency and availability 
                in distributed databases using the CAP theorem. Compare Apache Cassandra, 
                MongoDB, and Google Spanner with specific benchmarks and real-world failure 
                scenarios. Include detailed performance metrics and recovery procedures.""",
                
                """Implement a complete machine learning pipeline for natural language processing
                that includes: data preprocessing, tokenization, model training with distributed
                computing, hyperparameter tuning, model serving at scale, A/B testing,
                and continuous monitoring. Provide performance benchmarks and cost analysis.""",
                
                """Write a comprehensive security audit framework for a fintech application
                handling cryptocurrency transactions. Cover: threat modeling, penetration testing,
                smart contract auditing, key management, multi-signature schemes, cold storage,
                incident response, and compliance with SOC2 and ISO 27001.""",
                
                """Create a detailed analysis of Kubernetes scheduling algorithms including
                the default scheduler, custom schedulers, and placement policies. Compare
                performance across different cluster sizes (10, 100, 1000 nodes) with
                real-world workload patterns. Include resource utilization graphs and scaling recommendations.""",
            ]
        }

    def get_sinusoidal_rpm(self, minute: float, base_rpm: float = 17.5, amplitude: float = 12.5) -> float:
        """
        Sinusoidal load pattern simulating day/night cycle
        base_rpm = 17.5 (average between 5 and 30)
        amplitude = 12.5 (variation range)
        
        Range: 5 to 30 requests per minute
        Period: 10 minutes (full cycle)
        """
        period = 10  # 10 minutes for full cycle
        rpm = base_rpm + amplitude * math.sin(2 * math.pi * minute / period)
        return max(5, min(30, rpm))  # Clamp between 5-30

    def select_complexity(self) -> str:
        """2/3 high complexity, 1/3 split between low and medium"""
        rand = random.random()
        if rand < 0.67:  # 67% high complexity
            return "high"
        elif rand < 0.83:  # 16% medium
            return "medium"
        else:  # 17% low
            return "low"

    def get_prompt(self, complexity: str) -> str:
        return random.choice(self.prompts[complexity])

    def get_model_for_complexity(self, complexity: str, queue_size: int = 0) -> str:
        """
        Smart routing based on complexity:
        - high: priority 0 (openrouter - most powerful)
        - medium: priority 1 (ollama - medium)
        - low: priority 2 (vllm - simplest)
        
        Fallback rules:
        - If high model busy and queue < 10: use medium
        - If medium busy: use low
        - If queue >= 10: allow low to answer anything
        """
        if complexity == "high":
            if queue_size >= 10:
                # Emergency mode - any model can respond
                return random.choice([
                    "minimax/minimax-m2.5:free",
                    "gemma4:31b-cloud",
                    "google/gemma-4-E2B-it"
                ])
            # Try priority 0 (most powerful), fallback to 1, then 2
            return "minimax/minimax-m2.5:free"
        elif complexity == "medium":
            if queue_size >= 10:
                return "google/gemma-4-E2B-it"
            return "gemma4:31b-cloud"
        else:  # low
            return "google/gemma-4-E2B-it"

    async def send_request(self, session: aiohttp.ClientSession, minute: float) -> TestResult:
        complexity = self.select_complexity()
        prompt = self.get_prompt(complexity)
        model = self.get_model_for_complexity(complexity, self.queue_size)
        
        start = datetime.now()
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": 512 if complexity == "low" else 1024 if complexity == "medium" else 2048
        }
        
        try:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=300)  # 5 min timeout for complex queries
            ) as resp:
                elapsed = (datetime.now() - start).total_seconds()
                
                if resp.status == 200:
                    data = await resp.json()
                    response_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    # Extract provider from response headers or model
                    provider = self._extract_provider(model)
                    
                    # Print response to terminal
                    self._print_response(complexity, model, prompt, response_text, elapsed)
                    
                    return TestResult(
                        timestamp=start.isoformat(),
                        provider=provider,
                        model=model,
                        latency=elapsed,
                        status=resp.status,
                        success=True,
                        prompt_length=len(prompt),
                        complexity=complexity,
                        prompt=prompt[:100] + "..." if len(prompt) > 100 else prompt,
                        response=response_text[:200] + "..." if len(response_text) > 200 else response_text
                    )
                else:
                    text = await resp.text()
                    return TestResult(
                        timestamp=start.isoformat(),
                        provider="error",
                        model=model,
                        latency=elapsed,
                        status=resp.status,
                        success=False,
                        prompt_length=len(prompt),
                        complexity=complexity,
                        prompt=prompt[:100] + "...",
                        response="",
                        error=text[:200]
                    )
                    
        except asyncio.TimeoutError:
            elapsed = (datetime.now() - start).total_seconds()
            return TestResult(
                timestamp=start.isoformat(),
                provider="timeout",
                model=model,
                latency=elapsed,
                status=0,
                success=False,
                prompt_length=len(prompt),
                complexity=complexity,
                prompt=prompt[:100] + "...",
                response="",
                error="Request timeout"
            )
        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds()
            return TestResult(
                timestamp=start.isoformat(),
                provider="error",
                model=model,
                latency=elapsed,
                status=0,
                success=False,
                prompt_length=len(prompt),
                complexity=complexity,
                prompt=prompt[:100] + "...",
                response="",
                error=str(e)[:200]
            )

    def _extract_provider(self, model: str) -> str:
        """Determine provider from model name"""
        if "minimax" in model:
            return "openrouter"
        elif model == "gemma4:31b-cloud":
            return "ollama"
        elif "gemma-4-E2B" in model or "WeDLM" in model:
            return "vllm"
        return "unknown"

    def _print_response(self, complexity: str, model: str, prompt: str, response: str, latency: float):
        """Print response to terminal in real-time"""
        complexity_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}
        
        print(f"\n{'='*80}")
        print(f"{complexity_emoji.get(complexity, '⚪')} [{complexity.upper()}] Model: {model} | Latency: {latency:.2f}s")
        print(f"{'='*80}")
        print(f"Prompt: {prompt[:150]}{'...' if len(prompt) > 150 else ''}")
        print(f"{'-'*80}")
        print(f"Response: {response[:300]}{'...' if len(response) > 300 else ''}")
        print(f"{'='*80}\n")
        sys.stdout.flush()

    async def run_load_test(self, duration_minutes: int = 10):
        print(f"\n{'='*80}")
        print(f"ADVANCED LOAD TEST - {duration_minutes} minutes")
        print(f"Load Pattern: Sinusoidal (5-30 RPM, day/night cycle)")
        print(f"Complexity: 67% HIGH | 16% MEDIUM | 17% LOW")
        print(f"{'='*80}\n")
        
        self.start_time = datetime.now()
        
        async with aiohttp.ClientSession() as session:
            end_time = asyncio.get_event_loop().time() + (duration_minutes * 60)
            
            while asyncio.get_event_loop().time() < end_time:
                elapsed_minutes = (asyncio.get_event_loop().time() - (end_time - duration_minutes * 60)) / 60
                target_rpm = self.get_sinusoidal_rpm(elapsed_minutes)
                
                # Calculate requests for this minute
                requests_this_minute = int(target_rpm)
                interval = 60.0 / max(1, requests_this_minute)
                
                print(f"\n[Minute {elapsed_minutes:.1f}] Target: {target_rpm:.1f} RPM | Requests: {requests_this_minute}")
                print(f"Queue size estimate: {self.queue_size}")
                
                # Send requests for this minute
                tasks = []
                for i in range(requests_this_minute):
                    task = asyncio.create_task(self.send_request(session, elapsed_minutes))
                    tasks.append(task)
                    if i < requests_this_minute - 1:
                        await asyncio.sleep(interval)
                
                # Collect results
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        print(f"Error: {result}")
                        continue
                    self.results.append(result)
                    self._update_stats(result)
                
                # Update queue size estimate (successful requests reduce queue)
                pending = sum(1 for r in self.results[-20:] if not r.success)
                self.queue_size = max(0, pending)
                
                # Print minute summary
                self._print_minute_summary(elapsed_minutes, target_rpm)
        
        self._print_final_stats()
        self._save_results()

    def _update_stats(self, result: TestResult):
        self.stats.total_requests += 1
        if result.success:
            self.stats.successful += 1
            self.stats.latencies.append(result.latency)
            self.stats.by_provider[result.provider] = self.stats.by_provider.get(result.provider, 0) + 1
            self.stats.by_complexity[result.complexity] += 1
        else:
            self.stats.failed += 1

    def _print_minute_summary(self, minute: float, rpm: float):
        recent = [r for r in self.results if r.success][-10:]
        if recent:
            avg_latency = statistics.mean([r.latency for r in recent])
            print(f"  [Summary] Avg latency: {avg_latency:.2f}s | Success: {self.stats.successful}/{self.stats.total_requests}")

    def _print_final_stats(self):
        print(f"\n{'='*80}")
        print("FINAL STATISTICS")
        print(f"{'='*80}")
        print(f"Total requests: {self.stats.total_requests}")
        print(f"Successful: {self.stats.successful} ({100*self.stats.successful/self.stats.total_requests:.1f}%)")
        print(f"Failed: {self.stats.failed} ({100*self.stats.failed/self.stats.total_requests:.1f}%)")
        
        if self.stats.latencies:
            print(f"\nLATENCY:")
            print(f"  Mean: {statistics.mean(self.stats.latencies):.2f}s")
            print(f"  Median: {statistics.median(self.stats.latencies):.2f}s")
            sorted_lat = sorted(self.stats.latencies)
            p95_idx = int(len(sorted_lat) * 0.95)
            p99_idx = int(len(sorted_lat) * 0.99)
            print(f"  P95: {sorted_lat[p95_idx]:.2f}s")
            print(f"  P99: {sorted_lat[p99_idx]:.2f}s")
        
        print(f"\nBY PROVIDER:")
        for provider, count in self.stats.by_provider.items():
            pct = 100 * count / max(1, self.stats.successful)
            print(f"  {provider}: {count} ({pct:.1f}%)")
        
        print(f"\nBY COMPLEXITY:")
        for comp, count in self.stats.by_complexity.items():
            pct = 100 * count / max(1, self.stats.successful)
            print(f"  {comp}: {count} ({pct:.1f}%)")
        
        print(f"{'='*80}\n")

    def _save_results(self):
        filename = f"advanced_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump([{
                "timestamp": r.timestamp,
                "provider": r.provider,
                "model": r.model,
                "latency": r.latency,
                "status": r.status,
                "success": r.success,
                "prompt_length": r.prompt_length,
                "complexity": r.complexity,
                "prompt": r.prompt,
                "response": r.response,
                "error": r.error
            } for r in self.results], f, indent=2)
        print(f"Results saved to: {filename}")


async def main():
    tester = AdvancedLoadTester()
    await tester.run_load_test(duration_minutes=10)


if __name__ == "__main__":
    asyncio.run(main())
