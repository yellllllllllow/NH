"""Background worker threads for non-blocking operations."""

from PyQt5.QtCore import QThread, pyqtSignal


class NewsFetchWorker(QThread):
    """Background worker for fetching news without blocking the UI."""

    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, api_key: str, query: str, proxies: dict,
                 page_size: int = 10, timeout: int = 10):
        super().__init__()
        self.api_key = api_key
        self.query = query
        self.proxies = proxies
        self.page_size = page_size
        self.timeout = timeout

    def run(self):
        try:
            from .fetcher import fetch_news
            result = fetch_news(
                api_key=self.api_key,
                query=self.query,
                page_size=self.page_size,
                proxies=self.proxies,
                timeout=self.timeout,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ApiKeyCheckWorker(QThread):
    """Background worker for validating API key."""

    finished = pyqtSignal(object)

    def __init__(self, api_key: str, proxies: dict, timeout: int = 10):
        super().__init__()
        self.api_key = api_key
        self.proxies = proxies
        self.timeout = timeout

    def run(self):
        try:
            from .fetcher import validate_api_key
            result = validate_api_key(
                api_key=self.api_key,
                proxies=self.proxies,
                timeout=self.timeout,
            )
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit({"valid": False, "message": str(e)})


class SummarizeWorker(QThread):
    """Background worker for AI text summarization.

    Uses OpenAI-compatible chat completions API, supporting:
    - DeepSeek (https://api.deepseek.com)
    - 硅基流动 (https://api.siliconflow.cn)
    - Ollama (http://localhost:11434)
    - Any OpenAI-compatible API
    """

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, text: str, prompt_template: str,
                 api_key: str = "", base_url: str = "https://api.deepseek.com",
                 model: str = "deepseek-v4-flash", proxies: dict = None,
                 parent=None):
        super().__init__(parent)
        self.text = text
        self.prompt_template = prompt_template
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.proxies = proxies or {}

    def run(self):
        try:
            import requests

            prompt = self.prompt_template.replace("{article_text}", self.text)

            # Construct OpenAI-compatible chat completions request
            url = f"{self.base_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的新闻摘要助手，请根据用户的要求对新闻内容进行总结。"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 1024,
                "stream": False,
            }

            resp = requests.post(
                url,
                json=payload,
                headers=headers,
                proxies=self.proxies,
                timeout=60
            )

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")
                    self.finished.emit(content.strip())
                else:
                    self.finished.emit("[无返回内容]")
            else:
                error_detail = ""
                try:
                    err_data = resp.json()
                    error_detail = err_data.get("error", {}).get("message", "")
                except Exception:
                    error_detail = resp.text[:200]
                self.error.emit(
                    f"HTTP {resp.status_code}: {error_detail}"
                )

        except requests.ConnectionError:
            self.error.emit(
                f"无法连接到 {self.base_url}，请检查接口地址和网络连接。"
            )
        except requests.Timeout:
            self.error.emit("请求超时，AI 服务响应时间过长。")
        except Exception as e:
            self.error.emit(str(e))


class TranslateWorker(QThread):
    """Background worker for translating English text to Simplified Chinese.

    Uses OpenAI-compatible chat completions API to perform translation.
    """

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, text: str, api_key: str, base_url: str,
                 model: str, proxies: dict = None):
        super().__init__()
        self.text = text
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.proxies = proxies or {}

    def run(self):
        try:
            import requests

            url = f"{self.base_url}/v1/chat/completions"
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a professional translator. "
                                   "Translate the following English text "
                                   "to Simplified Chinese. Only output the "
                                   "translation, no explanations."
                    },
                    {
                        "role": "user",
                        "content": self.text
                    }
                ],
                "temperature": 0.1,
                "max_tokens": 2048,
                "stream": False,
            }

            resp = requests.post(
                url,
                json=payload,
                headers=headers,
                proxies=self.proxies,
                timeout=60
            )

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    content = message.get("content", "")
                    self.finished.emit(content.strip())
                else:
                    self.finished.emit("[无返回内容]")
            else:
                error_detail = ""
                try:
                    err_data = resp.json()
                    error_detail = err_data.get("error", {}).get("message", "")
                except Exception:
                    error_detail = resp.text[:200]
                self.error.emit(
                    f"HTTP {resp.status_code}: {error_detail}"
                )

        except requests.ConnectionError:
            self.error.emit(
                f"无法连接到 {self.base_url}，请检查接口地址和网络连接。"
            )
        except requests.Timeout:
            self.error.emit("请求超时，AI 服务响应时间过长。")
        except Exception as e:
            self.error.emit(str(e))


class MultiSourceFetchWorker(QThread):
    """Background worker for fetching news from multiple sources with fallback."""

    finished = pyqtSignal(object)  # list of articles
    error = pyqtSignal(str)
    progress = pyqtSignal(str, bool)  # message, is_success

    def __init__(self, query: str, page_size: int = 10,
                 primary_source_id: str = "",
                 api_key: str = "",
                 proxies: dict = None,
                 use_semantic_search: bool = True):
        super().__init__()
        self.query = query
        self.page_size = page_size
        self.primary_source_id = primary_source_id
        self.api_key = api_key
        self.proxies = proxies or {}
        self.use_semantic_search = use_semantic_search

    def run(self):
        try:
            from .multi_fetcher import fetch_with_fallback
            from .semantic_search import get_search_terms

            search_query = self.query
            if self.use_semantic_search and self.query:
                expanded = get_search_terms(self.query)
                if expanded:
                    for term in expanded:
                        if term.lower() != self.query.lower():
                            search_query = term
                            break
                    self.progress.emit(
                        f"语义搜索: '{self.query}' → '{search_query}'", True
                    )

            articles, results = fetch_with_fallback(
                query=search_query,
                page_size=self.page_size,
                primary_source_id=self.primary_source_id,
                api_key=self.api_key,
                proxies=self.proxies,
                progress_callback=self._on_progress,
            )

            if not articles and results:
                errors = [r.error_message for r in results if not r.success]
                if errors:
                    self.error.emit(
                        "所有新闻源均无法连接:\n" + "\n".join(errors[:5])
                    )
                else:
                    self.finished.emit([])
            else:
                self.finished.emit(articles)

        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, message: str, success: bool):
        self.progress.emit(message, success)
