from functools import wraps
from time import time
from typing import Dict, Optional


_metrics: Dict[str, list] = {}


def record_metric(name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
    if name not in _metrics:
        _metrics[name] = []
    _metrics[name].append({"value": value, "tags": tags or {}, "timestamp": time()})


def get_metrics(name: Optional[str] = None) -> Dict:
    if name:
        return {name: _metrics.get(name, [])}
    return _metrics


def clear_metrics() -> None:
    _metrics.clear()


def track_latency(metric_name: str):
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                latency = time() - start
                record_metric(f"{metric_name}.latency", latency)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                latency = time() - start
                record_metric(f"{metric_name}.latency", latency)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator
