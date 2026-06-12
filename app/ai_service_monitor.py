"""AI Service health monitor for graceful degradation.

Provides a shared singleton to track AI service availability across the
application. When the AI service is unavailable, AI features (translate,
summarize, aggregate) should be disabled while content fetching continues
to function normally.

Usage:
    from app.ai_service_monitor import ai_monitor

    # Check AI status
    if ai_monitor.is_available():
        # Do AI operation
    else:
        # Show "AI unavailable" message

    # Trigger a health check
    ai_monitor.check()
"""

import os
import socket
import time
from threading import Lock
from typing import Callable, Optional


class AiServiceMonitor:
    """Monitors AI service health and provides availability status.

    Thread-safe singleton. Uses a simple connectivity test to determine
    if the configured AI service is reachable.
    """

    def __init__(self):
        self._available = False
        self._status_text = "未检测"
        self._last_check: float = 0.0
        self._last_error: str = ""
        self._lock = Lock()
        self._api_key: str = ""
        self._base_url: str = ""
        self._model: str = ""
        self._on_change_callback: Optional[Callable[[bool], None]] = None

    def configure(self, api_key: str, base_url: str, model: str) -> None:
        """Update AI service configuration."""
        with self._lock:
            self._api_key = api_key
            self._base_url = base_url
            self._model = model

    def set_on_change(self, callback: Callable[[bool], None]) -> None:
        """Register callback for availability changes."""
        with self._lock:
            self._on_change_callback = callback

    def is_available(self) -> bool:
        """Return whether AI service is currently available."""
        with self._lock:
            return self._available

    def get_status_text(self) -> str:
        """Return human-readable status text."""
        with self._lock:
            return self._status_text

    def get_last_error(self) -> str:
        """Return last error message."""
        with self._lock:
            return self._last_error

    def get_last_check_time(self) -> float:
        """Return timestamp of last health check."""
        with self._lock:
            return self._last_check

    def check(self) -> bool:
        """Perform a health check on the configured AI service.

        Tests connectivity by attempting to reach the base URL.
        Does NOT send any search content or execute a full search request.
        Only validates network reachability.

        Returns:
            bool: True if AI service is reachable, False otherwise.
        """
        import requests

        with self._lock:
            api_key = self._api_key
            base_url = self._base_url
            self._last_check = time.time()

        # If no API key configured, AI is unavailable
        if not api_key or not base_url:
            with self._lock:
                self._available = False
                self._status_text = "AI 未配置"
                self._last_error = "未配置 API Key 或接口地址"
                cb = self._on_change_callback
            if cb:
                cb(False)
            return False

        try:
            # Clean base URL before testing
            url = base_url.rstrip('/')

            # Quick test: HEAD request to base URL with short timeout
            # This validates network reachability without any payload
            resp = requests.head(
                url,
                headers={"User-Agent": "AI-News-Agent/1.0"},
                timeout=5,
            )

            with self._lock:
                self._available = True
                self._status_text = f"AI 可用 ({resp.status_code})"
                self._last_error = ""
                cb = self._on_change_callback
            if cb:
                cb(True)
            return True

        except requests.ConnectionError:
            # Fallback: try a TCP socket test if HEAD fails
            try:
                host = url.split("://")[1].split("/")[0].split(":")[0]
                port = 443
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    with self._lock:
                        self._available = True
                        self._status_text = "AI 可用 (TCP)"
                        self._last_error = ""
                        cb = self._on_change_callback
                    if cb:
                        cb(True)
                    return True
                raise ConnectionError(f"TCP connect to {host}:{port} failed (code {result})")
            except Exception as fallback_err:
                with self._lock:
                    self._available = False
                    self._status_text = "AI 不可用"
                    self._last_error = f"连接失败: {str(fallback_err)[:80]}"
                    cb = self._on_change_callback
                if cb:
                    cb(False)
                return False

        except Exception as e:
            with self._lock:
                self._available = False
                self._status_text = "AI 不可用"
                self._last_error = str(e)[:100]
                cb = self._on_change_callback
            if cb:
                cb(False)
            return False

    def check_lightweight(self) -> bool:
        """Lightweight check - only tests if API key is configured.

        Does not make any network request. Use this for the fast path
        (e.g., button state initialization).

        Returns True if key and base_url are configured.
        """
        with self._lock:
            return bool(self._api_key) and bool(self._base_url)


# Module-level singleton
ai_monitor = AiServiceMonitor()
