import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional

class ConnectionWarmer:
    """
    Manages an HTTP session with pre-warmed TCP and TLS 1.3 connections.
    Ensures connection reuse to reduce handshake latency to 0 ms at firing time.
    """

    def __init__(self, target_host: str = "https://obs.itu.edu.tr", user_agent: Optional[str] = None):
        self.target_host = target_host
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        )
        self.session = self._create_optimized_session()
        self.last_warm_time = 0.0

    def _create_optimized_session(self) -> requests.Session:
        session = requests.Session()
        
        # Configure connection pool
        adapter = HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=Retry(total=2, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        })
        return session

    def warm_up(self, endpoint: str = "/ogrenci/") -> float:
        """
        Sends a lightweight HEAD or GET request to pre-establish TCP & TLS.
        Returns the handshake + response latency in milliseconds.
        """
        url = f"{self.target_host.rstrip('/')}/{endpoint.lstrip('/')}"
        t_start = time.perf_counter()
        try:
            self.session.head(url, timeout=3.0)
        except Exception:
            try:
                self.session.get(url, timeout=3.0)
            except Exception:
                pass
        latency_ms = (time.perf_counter() - t_start) * 1000.0
        self.last_warm_time = time.time()
        return latency_ms

    def ensure_warm(self, max_idle_seconds: float = 15.0) -> None:
        """
        Refreshes the connection if it has been idle for more than max_idle_seconds.
        """
        if (time.time() - self.last_warm_time) > max_idle_seconds:
            self.warm_up()
