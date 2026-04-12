#!/usr/bin/env python3
"""Quick 5-minute test before full 30-minute test."""

import asyncio
import sys
from load_test import LoadTester


async def main():
    print("=" * 60)
    print("QUICK TEST (5 minutes)")
    print("Features: Response capture + Complexity detection (rnj-1:8b-cloud)")
    print("=" * 60)
    
    tester = LoadTester()
    
    try:
        await tester.run_load_test(
            duration_minutes=5, 
            requests_per_minute=10,
            models=["minimax/minimax-m2.5:free", "gemma4:31b-cloud", "google/gemma-4-E2B-it"]
        )
        success_rate = tester.stats.successful / tester.stats.total_requests * 100
        
        # Print sample responses
        print("\n" + "=" * 60)
        print("SAMPLE RESPONSES (first 3 successful):")
        print("=" * 60)
        successful_results = [r for r in tester.results if r.success][:3]
        for i, r in enumerate(successful_results, 1):
            print(f"\n[{i}] Model: {r.model} | Complexity: {r.complexity}")
            print(f"    Prompt: {r.prompt_length} chars")
            print(f"    Response: {r.response[:150]}...")
        
        print("\n" + "=" * 60)
        if success_rate >= 90:
            print(f"✓ PASSED: {success_rate:.1f}% success rate")
            print("Run full test: python load_test.py")
            return 0
        else:
            print(f"✗ FAILED: {success_rate:.1f}% success rate")
            return 1
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return 130


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
