"""
app_cache.py

Streamlit-free replacement for ``st.cache_data`` used by the data/logic modules.

Matches the parts of ``st.cache_data`` the app relies on:
  * ``@cache_data()`` and ``@cache_data(ttl=seconds)``
  * the cache key is the call's arguments (bound to the signature, defaults applied);
    arguments whose name starts with an underscore are NOT part of the key
  * every hit returns a fresh copy, so callers can mutate results safely
  * ``fn.clear()`` clears one function; :func:`clear_all` clears every cache
    (the equivalent of ``st.cache_data.clear()``)

Single process, thread-safe. No Streamlit import.
"""

import copy
import functools
import inspect
import pickle
import threading
import time
from typing import Any, Callable, Optional

_registry: "list[_Cache]" = []
_registry_lock = threading.Lock()


class _Cache:
    def __init__(self, fn: Callable, ttl: Optional[float]):
        self.fn = fn
        self.ttl = ttl
        self.sig = inspect.signature(fn)
        self.entries: "dict[Any, tuple[float, Any]]" = {}
        self.lock = threading.Lock()
        self.key_locks: "dict[Any, threading.Lock]" = {}

    def key(self, args: tuple, kwargs: dict) -> Any:
        bound = self.sig.bind(*args, **kwargs)
        bound.apply_defaults()
        items = tuple((k, v) for k, v in bound.arguments.items() if not k.startswith("_"))
        try:
            return pickle.dumps(items)
        except Exception:
            return repr(items)

    def clear(self) -> None:
        with self.lock:
            self.entries.clear()

    def call(self, args: tuple, kwargs: dict) -> Any:
        key = self.key(args, kwargs)
        with self.lock:
            key_lock = self.key_locks.setdefault(key, threading.Lock())
        # One computation per key at a time; others wait and then hit the cache.
        with key_lock:
            with self.lock:
                hit = self.entries.get(key)
            if hit is not None and (self.ttl is None or time.monotonic() - hit[0] <= self.ttl):
                return copy.deepcopy(hit[1])
            value = self.fn(*args, **kwargs)
            with self.lock:
                self.entries[key] = (time.monotonic(), value)
            return copy.deepcopy(value)


def cache_data(ttl: Optional[float] = None) -> Callable:
    """Decorator factory; use as ``@cache_data()`` or ``@cache_data(ttl=300)``."""

    def decorator(fn: Callable) -> Callable:
        cache = _Cache(fn, ttl)
        with _registry_lock:
            _registry.append(cache)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            return cache.call(args, kwargs)

        wrapper.clear = cache.clear  # type: ignore[attr-defined]
        return wrapper

    return decorator


def clear_all() -> None:
    """Clear every cache created with :func:`cache_data`."""
    with _registry_lock:
        caches = list(_registry)
    for cache in caches:
        cache.clear()
