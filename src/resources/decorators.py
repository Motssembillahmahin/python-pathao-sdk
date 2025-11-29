"""
Decorator implementations for cross-cutting concerns in the store management package.
"""

import asyncio
import functools
import time
import logging
from typing import Any, Callable, Optional, TypeVar, ParamSpec
from collections import OrderedDict

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def validate_not_empty(*param_names: str):
    """
    Validate that specified parameters are not empty strings.

    Usage:
        @validate_not_empty('name', 'address')
        def create_store(name: str, address: str):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            for param_name in param_names:
                value = bound_args.arguments.get(param_name)
                if not value or (isinstance(value, str) and not value.strip()):
                    raise ValueError(f"Parameter '{param_name}' cannot be empty")

            return func(*args, **kwargs)

        return wrapper

    return decorator


def validate_length(min_len: Optional[int] = None, max_len: Optional[int] = None):
    """
    Validate string parameter length.

    Usage:
        @validate_length(min_len=3, max_len=50)
        def set_name(self, name: str):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)

            for param_name, param_value in bound_args.arguments.items():
                if param_name != "self" and isinstance(param_value, str):
                    length = len(param_value)
                    if min_len and length < min_len:
                        raise ValueError(
                            f"{param_name} must be at least {min_len} characters (got {length})"
                        )
                    if max_len and length > max_len:
                        raise ValueError(
                            f"{param_name} must be at most {max_len} characters (got {length})"
                        )
                    break

            return func(*args, **kwargs)

        return wrapper

    return decorator


def sanitize_input(*param_names: str):
    """
    Sanitize string inputs by stripping whitespace and normalizing.

    Usage:
        @sanitize_input('name', 'address')
        def create_store(name: str, address: str):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            for param_name in param_names:
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    if isinstance(value, str):
                        bound_args.arguments[param_name] = " ".join(value.split())

            return func(*bound_args.args, **bound_args.kwargs)

        return wrapper

    return decorator


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    Retry function on failure with exponential backoff.

    Usage:
        @retry(max_attempts=3, delay=1.0, backoff=2.0)
        async def api_call():
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(
                            f"Failed after {max_attempts} attempts",
                            extra={
                                "function": func.__name__,
                                "error": str(e),
                                "attempts": attempt,
                            },
                        )
                        raise

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed, retrying in {current_delay}s",
                        extra={
                            "function": func.__name__,
                            "error": str(e),
                            "attempt": attempt,
                            "delay": current_delay,
                        },
                    )

                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

            raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts:
                        logger.error(f"Failed after {max_attempts} attempts: {e}")
                        raise

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed, retrying..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff

            raise last_exception

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def timeout(seconds: float):
    """
    Add timeout to async function.

    Usage:
        @timeout(30.0)
        async def long_running_task():
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                logger.error(
                    f"Function {func.__name__} timed out after {seconds}s",
                    extra={"function": func.__name__, "timeout": seconds},
                )
                raise TimeoutError(f"{func.__name__} timed out after {seconds} seconds")

        return wrapper

    return decorator


class TTLCache:
    """Simple time-based cache"""

    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self.cache = OrderedDict()
        self.timestamps = {}

    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            if time.time() - self.timestamps[key] < self.ttl:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None

    def set(self, key: str, value: Any):
        self.cache[key] = value
        self.timestamps[key] = time.time()

        # Limit cache size
        if len(self.cache) > 1000:
            oldest = next(iter(self.cache))
            del self.cache[oldest]
            del self.timestamps[oldest]


def cache_result(ttl: int = 300, key_params: Optional[list[str]] = None):
    """
    Cache function results with TTL.

    Usage:
        @cache_result(ttl=300, key_params=['city_name'])
        async def get_city_id(self, city_name: str):
            ...
    """
    cache = TTLCache(ttl=ttl)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            if key_params:
                key_parts = [bound_args.arguments.get(p, "") for p in key_params]
            else:
                key_parts = [
                    str(v) for k, v in bound_args.arguments.items() if k != "self"
                ]

            cache_key = f"{func.__name__}:{':'.join(map(str, key_parts))}"

            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_value

            result = await func(*args, **kwargs)
            cache.set(cache_key, result)
            logger.debug(f"Cached result for {cache_key}")

            return result

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)

            if key_params:
                key_parts = [bound_args.arguments.get(p, "") for p in key_params]
            else:
                key_parts = [
                    str(v) for k, v in bound_args.arguments.items() if k != "self"
                ]

            cache_key = f"{func.__name__}:{':'.join(map(str, key_parts))}"

            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def log_execution(level: str = "INFO"):
    """
    Log function execution with parameters and result.

    Usage:
        @log_execution(level='INFO')
        async def create_store(self, store_data):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)

            params = {
                k: v
                for k, v in bound_args.arguments.items()
                if k not in ["self", "password", "api_key", "token"]
            }

            logger.log(
                getattr(logging, level.upper()),
                f"Executing {func.__name__}",
                extra={"function": func.__name__, "params": str(params)[:200]},
            )

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                logger.log(
                    getattr(logging, level.upper()),
                    f"Completed {func.__name__}",
                    extra={
                        "function": func.__name__,
                        "duration": f"{duration:.3f}s",
                        "success": True,
                    },
                )
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    f"Failed {func.__name__}",
                    extra={
                        "function": func.__name__,
                        "duration": f"{duration:.3f}s",
                        "error": str(e),
                        "success": False,
                    },
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            logger.log(getattr(logging, level.upper()), f"Executing {func.__name__}")
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.log(
                    getattr(logging, level.upper()),
                    f"Completed {func.__name__} in {duration:.3f}s",
                )
                return result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Failed {func.__name__} after {duration:.3f}s: {e}")
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def measure_time(func: Callable[P, T]) -> Callable[P, T]:
    """
    Measure and log execution time.

    Usage:
        @measure_time
        async def slow_operation():
            ...
    """

    @functools.wraps(func)
    async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start = time.time()
        result = await func(*args, **kwargs)
        duration = time.time() - start

        logger.info(
            f"{func.__name__} took {duration:.3f}s",
            extra={"function": func.__name__, "duration": duration},
        )
        return result

    @functools.wraps(func)
    def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        logger.info(f"{func.__name__} took {duration:.3f}s")
        return result

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


class RateLimiter:
    """Token bucket rate limiter"""

    def __init__(self, rate: int, per: float):
        self.rate = rate
        self.per = per
        self.allowance = rate
        self.last_check = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            current = time.time()
            time_passed = current - self.last_check
            self.last_check = current

            self.allowance += time_passed * (self.rate / self.per)
            if self.allowance > self.rate:
                self.allowance = self.rate

            if self.allowance < 1.0:
                sleep_time = (1.0 - self.allowance) * (self.per / self.rate)
                await asyncio.sleep(sleep_time)
                self.allowance = 0.0
            else:
                self.allowance -= 1.0


def rate_limit(calls: int, period: float):
    """
    Rate limit function calls (calls per period in seconds).

    Usage:
        @rate_limit(calls=100, period=60)  # 100 calls per minute
        async def api_request():
            ...
    """
    limiter = RateLimiter(calls, period)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            await limiter.acquire()
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def handle_errors(
    default_return: Any = None, log_errors: bool = True, raise_errors: tuple = ()
):
    """
    Handle errors gracefully with optional default return.

    Usage:
        @handle_errors(default_return=[], raise_errors=(ValidationError,))
        async def get_stores():
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except raise_errors:
                raise
            except Exception as e:
                if log_errors:
                    logger.error(
                        f"Error in {func.__name__}: {e}",
                        extra={"function": func.__name__, "error": str(e)},
                        exc_info=True,
                    )
                return default_return

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except raise_errors:
                raise
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                return default_return

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def convert_exceptions(from_exceptions: tuple, to_exception: type, message: str = None):
    """
    Convert one exception type to another.

    Usage:
        @convert_exceptions((KeyError, ValueError), ValidationError, "Invalid data")
        def process_data(data):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except from_exceptions as e:
                error_msg = message or str(e)
                logger.debug(
                    f"Converting {type(e).__name__} to {to_exception.__name__}"
                )
                raise to_exception(error_msg) from e

        return wrapper

    return decorator


def deprecated(reason: str, alternative: Optional[str] = None):
    """
    Mark function as deprecated.

    Usage:
        @deprecated("This method is deprecated", alternative="use_new_method")
        def old_method():
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import warnings

            msg = f"{func.__name__} is deprecated: {reason}"
            if alternative:
                msg += f". Use {alternative} instead."

            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            logger.warning(msg)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def async_to_sync(func: Callable[P, T]) -> Callable[P, T]:
    """
    Convert async function to sync (creates new event loop).

    Usage:
        @async_to_sync
        async def async_function():
            ...

        # Now can be called synchronously
        result = async_function()
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(func(*args, **kwargs))

    return wrapper


def run_in_executor(executor=None):
    """
    Run blocking function in executor.

    Usage:
        @run_in_executor()
        def blocking_operation():
            ...

        # Can be awaited
        result = await blocking_operation()
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            loop = asyncio.get_event_loop()
            partial_func = functools.partial(func, *args, **kwargs)
            return await loop.run_in_executor(executor, partial_func)

        return wrapper

    return decorator
