import asyncio
import itertools
import logging
import random
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import deque

from .config import ProviderConfig, settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class QueuedRequest:
    """Represents a request in the queue waiting for a provider"""
    id: str
    model: str
    complexity: str
    payload: Any
    future: asyncio.Future
    enqueue_time: float


class RoundRobinSelector:
    def __init__(self, providers: List[ProviderConfig]):
        self._cycle = itertools.cycle(providers)

    def select(self, providers: List[ProviderConfig]) -> ProviderConfig:
        for _ in range(len(providers)):
            p = next(self._cycle)
            if p in providers:
                return p
        return providers[0]


class WeightedSelector:
    def select(self, providers: List[ProviderConfig]) -> ProviderConfig:
        weights = [p.weight for p in providers]
        return random.choices(providers, weights=weights, k=1)[0]


class SmartLLMBalancer:
    """
    Advanced LLM Balancer with:
    - Complexity-based routing
    - Request queuing
    - Smart fallback logic
    - Queue threshold management
    """
    
    # Model complexity mapping (lower number = more powerful)
    MODEL_COMPLEXITY = {
        "minimax/minimax-m2.5:free": 0,  # Most powerful
        "gemma4:31b-cloud": 1,            # Medium
        "google/gemma-4-E2B-it": 2,       # Simplest
    }
    
    # Complexity thresholds for fallback
    QUEUE_THRESHOLD = 10  # When queue >= 10, allow weak models to answer complex queries
    
    def __init__(self):
        self._providers: Dict[str, ProviderConfig] = {}
        self._model_index: Dict[str, List[str]] = {}  # model -> [provider_names]
        self._rr_selectors: Dict[str, RoundRobinSelector] = {}
        self._weighted_selector = WeightedSelector()
        self._lock = asyncio.Lock()
        
        # Request queue
        self._request_queue: deque[QueuedRequest] = deque()
        self._queue_event = asyncio.Event()
        self._active_requests: Dict[str, int] = {}  # provider -> count
        
        self._load()
        
        # Start queue processor
        self._queue_processor_task = None
    
    def start_queue_processor(self):
        """Start the background queue processor"""
        if self._queue_processor_task is None:
            self._queue_processor_task = asyncio.create_task(self._process_queue())
            logger.info("Queue processor started")
    
    def _load(self):
        for p in settings.providers:
            self._providers[p.name] = p
            for m in p.models:
                self._model_index.setdefault(m, []).append(p.name)
        # build per-model round-robin selectors
        for model, pnames in self._model_index.items():
            provs = [self._providers[n] for n in pnames]
            self._rr_selectors[model] = RoundRobinSelector(provs)
        
        logger.info(f"Loaded {len(self._providers)} providers")
        for name, provider in self._providers.items():
            logger.info(f"  - {name}: priority={provider.priority}, models={provider.models}")
    
    def detect_complexity(self, payload: Dict) -> str:
        """
        Detect request complexity based on prompt length and content.
        """
        messages = payload.get("messages", [])
        full_prompt = " ".join([m.get("content", "") for m in messages])
        prompt_len = len(full_prompt)
        
        # Detect complexity indicators
        has_code = any(kw in full_prompt.lower() for kw in [
            "code", "function", "algorithm", "implement", "write a"
        ])
        has_analysis = any(kw in full_prompt.lower() for kw in [
            "analyze", "design", "architecture", "system", "distributed",
            "comprehensive", "detailed", "explain in depth"
        ])
        
        if prompt_len > 500 or (has_analysis and prompt_len > 300):
            return "high"
        elif prompt_len > 100 or has_code or (has_analysis and prompt_len > 150):
            return "medium"
        else:
            return "low"
    
    def get_provider_for_complexity(self, complexity: str, queue_size: int) -> Optional[ProviderConfig]:
        """
        Select provider based on complexity with fallback logic.
        
        Logic:
        - high complexity: priority 0 (most powerful)
        - medium complexity: priority 1
        - low complexity: priority 2 (simplest)
        
        Fallback:
        - If target provider busy, try next lower priority
        - If queue >= 10, allow any provider for any complexity
        """
        # Sort providers by priority (0 = highest/most powerful)
        sorted_providers = sorted(
            self._providers.values(), 
            key=lambda p: p.priority
        )
        
        if not sorted_providers:
            return None
        
        # Emergency mode: queue too big, any provider can handle anything
        if queue_size >= self.QUEUE_THRESHOLD:
            logger.warning(f"Queue size {queue_size} >= threshold {self.QUEUE_THRESHOLD}, entering emergency mode")
            return sorted_providers[0]  # Use most powerful available
        
        # Normal routing based on complexity
        target_priority = {
            "high": 0,    # Most powerful
            "medium": 1,  # Medium
            "low": 2      # Simplest
        }.get(complexity, 1)
        
        # Find provider with target priority or fallback to next available
        for p in sorted_providers:
            if p.priority == target_priority:
                logger.info(f"Selected provider {p.name} (priority={p.priority}) for {complexity} complexity")
                return p
        
        # Fallback: find next available with higher priority number (less powerful)
        for p in sorted_providers:
            if p.priority > target_priority:
                logger.info(f"Fallback to provider {p.name} (priority={p.priority}) for {complexity} complexity")
                return p
        
        # Last resort: use most powerful
        logger.info(f"Last resort: using most powerful provider {sorted_providers[0].name}")
        return sorted_providers[0]
    
    def estimate_queue_size(self) -> int:
        """Estimate current queue size based on active requests"""
        return len(self._request_queue) + sum(self._active_requests.values())
    
    async def select_provider(self, model: str, payload: Dict = None) -> Optional[ProviderConfig]:
        """
        Smart provider selection with complexity detection.
        """
        async with self._lock:
            queue_size = self.estimate_queue_size()
            
            # If model specified and exists in our index, use it
            if model and model in self._model_index:
                # Check if this is a complexity-aware request
                if payload:
                    complexity = self.detect_complexity(payload)
                    provider = self.get_provider_for_complexity(complexity, queue_size)
                    if provider:
                        logger.info(f"Routing {complexity} complexity request to {provider.name} (queue={queue_size})")
                        return provider
                
                # Fallback to standard routing
                pnames = self._model_index[model]
                providers = [self._providers[n] for n in pnames if n in self._providers]
                if providers:
                    if settings.balancer_strategy == "weighted":
                        return self._weighted_selector.select(providers)
                    selector = self._rr_selectors.get(model)
                    if selector is None:
                        selector = RoundRobinSelector(providers)
                        self._rr_selectors[model] = selector
                    return selector.select(providers)
            
            # No specific model, use complexity-based routing
            if payload:
                complexity = self.detect_complexity(payload)
                return self.get_provider_for_complexity(complexity, queue_size)
            
            # Last fallback: any available provider
            if self._providers:
                return list(self._providers.values())[0]
            
            return None
    
    async def enqueue_request(self, request_id: str, model: str, payload: Dict) -> asyncio.Future:
        """
        Enqueue a request for later processing when provider is available.
        """
        future = asyncio.get_event_loop().create_future()
        complexity = self.detect_complexity(payload)
        
        queued_req = QueuedRequest(
            id=request_id,
            model=model,
            complexity=complexity,
            payload=payload,
            future=future,
            enqueue_time=time.time()
        )
        
        async with self._lock:
            self._request_queue.append(queued_req)
            queue_size = len(self._request_queue)
        
        logger.info(f"Request {request_id} enqueued (complexity={complexity}, queue_size={queue_size})")
        self._queue_event.set()  # Wake up queue processor
        
        return future
    
    async def _process_queue(self):
        """Background task to process queued requests"""
        while True:
            try:
                await self._queue_event.wait()
                
                async with self._lock:
                    if not self._request_queue:
                        self._queue_event.clear()
                        continue
                    
                    request = self._request_queue.popleft()
                
                # Try to find provider for this request
                provider = await self.select_provider(request.model, request.payload)
                
                if provider:
                    wait_time = time.time() - request.enqueue_time
                    logger.info(f"Processing queued request {request.id} after {wait_time:.2f}s wait")
                    request.future.set_result(provider)
                else:
                    # Re-queue if no provider available
                    async with self._lock:
                        self._request_queue.appendleft(request)
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Queue processing error: {e}")
                await asyncio.sleep(1)
    
    def track_active_request(self, provider_name: str, delta: int = 1):
        """Track active requests per provider"""
        self._active_requests[provider_name] = self._active_requests.get(provider_name, 0) + delta
        if self._active_requests[provider_name] <= 0:
            self._active_requests.pop(provider_name, None)
    
    def get_queue_stats(self) -> Dict:
        """Get current queue statistics"""
        return {
            "queue_size": len(self._request_queue),
            "active_requests": dict(self._active_requests),
            "total_pending": self.estimate_queue_size()
        }

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        return self._providers.get(name)

    def list_providers(self) -> List[ProviderConfig]:
        return list(self._providers.values())

    def list_models(self) -> Dict[str, List[str]]:
        return dict(self._model_index)


# Global balancer instance
balancer = SmartLLMBalancer()
