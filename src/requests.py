import ssl
import gzip
import json
import time
import zlib
import random
import socket
import http.client
from io import BytesIO
from functools import wraps
from typing import Optional, Tuple
from src import info, silent_error, error, RATE_LIMIT_INTERVAL, CF_IDENTIFIER, CF_API_TOKEN

class HTTPException(Exception):
    pass

def decompress_data(data, content_encoding):
    if content_encoding == 'gzip':
        return gzip.GzipFile(fileobj=BytesIO(data)).read()
    if content_encoding == 'deflate':
        return zlib.decompress(data)
    return data

def cloudflare_gateway_request(method: str, endpoint: str, body: Optional[str] = None, timeout: int = 10) -> Tuple[int, dict]:
    context = ssl.create_default_context()
    conn = http.client.HTTPSConnection("api.cloudflare.com", context=context, timeout=timeout)
    url = f"/client/v4/accounts/{CF_IDENTIFIER}/gateway{endpoint}"
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip, deflate"
    }

    try:
        conn.request(method, url, body, headers)
        response = conn.getresponse()
        data = decompress_data(response.read(), response.getheader('Content-Encoding'))
        if response.status >= 400:
            error_message = (
                f"Request failed: {response.status} {response.reason}, "
                f"Body: {data.decode('utf-8', errors='ignore')} "
                f"for url: https://api.cloudflare.com{url}"
            )
            (error if response.status in [400, 403, 404] else silent_error)(error_message)
            raise HTTPException(error_message)
        return response.status, json.loads(data.decode('utf-8'))

    except (http.client.HTTPException, ssl.SSLError, socket.timeout, OSError) as e:
        error_message = f"Network error occurred: {e}"
        info(error_message)
        raise HTTPException(error_message)
    except json.JSONDecodeError:
        raise HTTPException("Failed to decode JSON response")
    finally:
        conn.close()

def retry_if_exception_type(exceptions):
    return lambda e: isinstance(e, exceptions)

def retry(stop=None, wait=None, retry=None, after=None, before_sleep=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt_number = 0
            while True:
                attempt_number += 1
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if retry and not retry(e): raise
                    if after: after({'attempt_number': attempt_number, 'outcome': e})
                    if stop and stop(attempt_number): raise
                    if before_sleep: before_sleep({'attempt_number': attempt_number})
                    time.sleep(wait(attempt_number) if wait else 1)
        return wrapper
    return decorator

retry_config = {
    'stop': lambda _: False,
    'wait': lambda attempt: min(1 * (2 ** random.uniform(0, attempt - 1)), 10),
    'retry': retry_if_exception_type((HTTPException,)),
    'before_sleep': lambda state: info(f"Sleeping before next retry ({state['attempt_number']})")
}

class RateLimiter:
    def __init__(self, interval):
        self.interval = interval
        self.timestamp = time.time()

    def wait_for_next_request(self):
        sleep_time = max(0, self.interval - (time.time() - self.timestamp))
        if sleep_time > 0: time.sleep(sleep_time)
        self.timestamp = time.time()

rate_limiter = RateLimiter(RATE_LIMIT_INTERVAL)

def rate_limited_request(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        rate_limiter.wait_for_next_request()
        return func(*args, **kwargs)
    return wrapper
