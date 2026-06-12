"""AI model settings dialog (Chrome-style)."""

import json

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTextEdit, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar, QWidget, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

import requests
from app.secure_storage import encrypt_api_key, decrypt_api_key, is_key_encrypted


# Provider presets
PROVIDER_PRESETS = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash", "deepseek-v4-pro"],
        "model_list_api": "/models",
    },
    "硅基流动": {
        "base_url": "https://api.siliconflow.cn",
        "models": [
            "Qwen/Qwen2-72B-Instruct",
            "deepseek-ai/DeepSeek-V2-Chat",
            "THUDM/glm-4-9b-chat",
            "meta-llama/Meta-Llama-3.1-8B-Instruct"
        ],
        "model_list_api": "/v1/models",
    },
    "Ollama (本地)": {
        "base_url": "http://localhost:11434",
        "models": ["llama3.2", "qwen2.5", "qwen2.5-coder", "deepseek-r1"],
        "model_list_api": "/api/tags",
    },
    "自定义": {
        "base_url": "",
        "models": [],
        "model_list_api": "",
    },
}

CHROME_STYLE = """
    QDialog { background: #ffffff; }
    QLabel#sectionTitle {
        font-size: 13px; font-weight: bold; color: #202124; padding: 4px 0;
    }
    QListWidget::item:selected {
        background: #e8f0fe; color: #1a73e8;
    }
    QFrame#divider { background: #e0e0e0; max-height: 1px; }
"""


class ModelListFetcher(QThread):
    """Background thread to fetch available models from provider."""

    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, base_url: str, api_key: str, provider: str, parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.provider = provider

    def run(self):
        try:
            preset = PROVIDER_PRESETS.get(self.provider)
            api_path = preset.get("model_list_api", "") if preset else ""
            if not api_path:
                self.finished.emit(preset.get("models", []) if preset else [])
                return

            # Validate base_url before constructing URL
            if not self.base_url:
                self.error.emit("接口地址为空，请先选择或填写服务商地址。")
                return
            if not self.base_url.startswith(("http://", "https://")):
                self.error.emit(
                    f"接口地址格式错误: '{self.base_url}'，"
                    f"必须以 http:// 或 https:// 开头。"
                )
                return

            url = f"{self.base_url}{api_path}"
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            resp = requests.get(url, headers=headers, timeout=15)

            if resp.status_code != 200:
                self.error.emit(f"HTTP {resp.status_code}: {resp.text[:100]}")
                return

            data = resp.json()
            models = []

            if self.provider == "Ollama (本地)":
                # Ollama returns {"models": [{"name": "..."}]}
                for m in data.get("models", []):
                    models.append(m.get("name", ""))
            elif self.provider == "DeepSeek":
                # DeepSeek returns {"data": [{"id": "..."}]}
                for m in data.get("data", []):
                    models.append(m.get("id", ""))
            elif self.provider == "硅基流动":
                # SiliconFlow returns {"data": [{"id": "..."}]}
                for m in data.get("data", []):
                    models.append(m.get("id", ""))

            if models:
                self.finished.emit(sorted(models))
            else:
                self.finished.emit(preset.get("models", []) if preset else [])

        except requests.ConnectionError:
            self.error.emit("无法连接到服务商，请检查接口地址和网络连接。")
        except requests.Timeout:
            self.error.emit("请求超时。")
        except Exception as e:
            self.error.emit(str(e))


class AiSettingsDialog(QDialog):
    """AI model settings dialog with Chrome-style UI."""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = dict(config)
        self.setWindowTitle("AI 模型设置")
        self.setMinimumSize(560, 640)
        self.setStyleSheet(CHROME_STYLE)
        self._model_fetcher = None
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(24, 20, 24, 20)

        # Title
        title = QLabel("AI 模型设置")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 400; color: #202124; "
            "margin-bottom: 4px;"
        )
        layout.addWidget(title)
        desc = QLabel("配置 AI 摘要服务的连接参数")
        desc.setStyleSheet("font-size: 13px; color: #5f6368; margin-bottom: 16px;")
        layout.addWidget(desc)

        # === Provider section ===
        layout.addWidget(self._section_title("服务商"))

        provider_row = QHBoxLayout()
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(list(PROVIDER_PRESETS.keys()))
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.provider_combo.setMinimumWidth(200)
        provider_row.addWidget(self.provider_combo)
        provider_row.addStretch()
        layout.addLayout(provider_row)

        # Base URL (auto-filled)
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("接口地址将自动填充")
        self.base_url_input.textChanged.connect(self._mark_dirty)
        layout.addWidget(self.base_url_input)
        layout.addSpacing(20)

        # === API Key section ===
        layout.addWidget(self._section_title("API Key"))

        key_row = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("输入 API 密钥")
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.textChanged.connect(self._mark_dirty)
        self.key_input.textChanged.connect(self._on_key_changed)
        key_row.addWidget(self.key_input, 1)

        self.toggle_btn = QPushButton("👁")
        self.toggle_btn.setObjectName("icon")
        self.toggle_btn.setToolTip("显示/隐藏 API Key")
        self.toggle_btn.setFixedWidth(40)
        self.toggle_btn.clicked.connect(self._toggle_key_visibility)
        key_row.addWidget(self.toggle_btn)
        layout.addLayout(key_row)

        key_hint = QLabel("DeepSeek / 硅基流动的 API Key 以 sk- 开头")
        key_hint.setStyleSheet("font-size: 12px; color: #5f6368; margin-top: 2px;")
        layout.addWidget(key_hint)

        # Validate + Save buttons
        key_btn_row = QHBoxLayout()
        self.validate_btn = QPushButton("验证 Key")
        self.validate_btn.setObjectName("secondary")
        self.validate_btn.clicked.connect(self._validate_key)
        key_btn_row.addWidget(self.validate_btn)

        self.save_key_btn = QPushButton("保存 Key")
        self.save_key_btn.setObjectName("primary")
        self.save_key_btn.clicked.connect(self._save_key)
        key_btn_row.addWidget(self.save_key_btn)

        self.key_status = QLabel("")
        self.key_status.setStyleSheet("font-size: 12px; color: #5f6368;")
        key_btn_row.addWidget(self.key_status)
        key_btn_row.addStretch()
        layout.addLayout(key_btn_row)
        layout.addSpacing(20)

        # === Model list section ===
        divider = QFrame()
        divider.setObjectName("divider")
        layout.addWidget(divider)
        layout.addSpacing(12)

        model_header = QHBoxLayout()
        model_header.addWidget(self._section_title("可用模型"))
        model_header.addStretch()

        self.refresh_btn = QPushButton("🔄 刷新列表")
        self.refresh_btn.setObjectName("icon")
        self.refresh_btn.setToolTip("从服务商获取最新模型列表")
        self.refresh_btn.clicked.connect(self._fetch_models)
        model_header.addWidget(self.refresh_btn)

        # Search filter
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索模型...")
        self.search_input.setFixedWidth(180)
        self.search_input.setStyleSheet(
            "padding: 6px 10px; border: 1px solid #dadce0; "
            "border-radius: 4px; font-size: 12px;"
        )
        self.search_input.textChanged.connect(self._filter_models)
        model_header.addWidget(self.search_input)

        layout.addLayout(model_header)

        self.model_progress = QProgressBar()
        self.model_progress.setVisible(False)
        layout.addWidget(self.model_progress)

        self.model_list = QListWidget()
        self.model_list.setMinimumHeight(150)
        self.model_list.itemSelectionChanged.connect(self._on_model_selected)
        layout.addWidget(self.model_list)

        self.model_empty = QLabel("点击「刷新列表」获取可用模型")
        self.model_empty.setStyleSheet("color: #5f6368; font-size: 12px; padding: 4px 0;")
        layout.addWidget(self.model_empty)
        layout.addSpacing(20)

        # === Test section (connectivity only) ===
        divider2 = QFrame()
        divider2.setObjectName("divider")
        layout.addWidget(divider2)
        layout.addSpacing(12)

        layout.addWidget(self._section_title("网络连通性测试"))

        test_hint = QLabel("点击下方按钮验证当前配置的网络连接状态，无需发送完整搜索请求。")
        test_hint.setStyleSheet("font-size: 12px; color: #5f6368; margin-bottom: 8px;")
        test_hint.setWordWrap(True)
        layout.addWidget(test_hint)

        test_btn_row = QHBoxLayout()
        self.ping_btn = QPushButton("🌐 测试连接")
        self.ping_btn.setObjectName("primary")
        self.ping_btn.clicked.connect(self._test_connectivity)
        test_btn_row.addWidget(self.ping_btn)

        self.test_status = QLabel("")
        self.test_status.setStyleSheet("font-size: 12px; color: #5f6368;")
        test_btn_row.addWidget(self.test_status)
        test_btn_row.addStretch()
        layout.addLayout(test_btn_row)

        self.test_output = QTextEdit()
        self.test_output.setReadOnly(True)
        self.test_output.setPlaceholderText("网络连通性测试结果将在此处显示...")
        self.test_output.setMaximumHeight(100)
        self.test_output.setStyleSheet(
            "border: 1px solid #dadce0; border-radius: 4px; "
            "font-size: 13px; padding: 6px; background: #f8f9fa;"
        )
        layout.addWidget(self.test_output)
        layout.addSpacing(16)

        # === Bottom buttons ===
        divider3 = QFrame()
        divider3.setObjectName("divider")
        layout.addWidget(divider3)
        layout.addSpacing(12)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("secondary")
        cancel_btn.clicked.connect(self.reject)
        bottom_row.addWidget(cancel_btn)

        self.save_btn = QPushButton("保存并关闭")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self._save_and_close)
        bottom_row.addWidget(self.save_btn)

        layout.addLayout(bottom_row)
        layout.addStretch()
        self.setLayout(layout)

    def _section_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def _load_config(self):
        """Load current config into UI."""
        provider = self.config.get("ai_provider", "DeepSeek")
        idx = self.provider_combo.findText(provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        else:
            self.provider_combo.setCurrentIndex(0)
        # Only set base_url if non-empty; _on_provider_changed already set it
        saved_url = self.config.get("ai_base_url", "")
        if saved_url:
            self.base_url_input.setText(saved_url)
        raw_key = self.config.get("ai_key", self.config.get("api_key", ""))
        if raw_key and is_key_encrypted(raw_key):
            raw_key = decrypt_api_key(raw_key)
        self.key_input.setText(raw_key)

        # Load saved models
        saved_model = self.config.get("ai_model", "")
        preset = PROVIDER_PRESETS.get(provider)
        if preset:
            self.model_list.clear()
            for m in preset["models"]:
                item = QListWidgetItem(m)
                if m == saved_model:
                    item.setSelected(True)
                self.model_list.addItem(item)

    def _on_provider_changed(self, provider: str):
        """Auto-fill base URL and model list when provider changes."""
        preset = PROVIDER_PRESETS.get(provider)
        if not preset:
            return
        if preset["base_url"]:
            self.base_url_input.setText(preset["base_url"])
        self.model_list.clear()
        for m in preset["models"]:
            self.model_list.addItem(m)
        # Try to auto-fetch models
        if preset["model_list_api"]:
            self._fetch_models()

    def _toggle_key_visibility(self):
        """Toggle API Key visibility."""
        if self.key_input.echoMode() == QLineEdit.Password:
            self.key_input.setEchoMode(QLineEdit.Normal)
            self.toggle_btn.setText("🙈")
        else:
            self.key_input.setEchoMode(QLineEdit.Password)
            self.toggle_btn.setText("👁")

    def _mark_dirty(self):
        """Mark that unsaved changes exist."""
        if hasattr(self, '_saved'):
            self._saved = False

    def _validate_key(self):
        """Validate API key format."""
        key = self.key_input.text().strip()
        if not key:
            self.key_status.setText("⚠ 请输入 API Key")
            self.key_status.setStyleSheet("font-size: 12px; color: #ea4335;")
            return

        provider = self.provider_combo.currentText()
        base_url = self.base_url_input.text().strip()

        self.validate_btn.setEnabled(False)
        self.validate_btn.setText("验证中...")
        self.key_status.setText("⏳ 正在验证...")
        self.key_status.setStyleSheet("font-size: 12px; color: #5f6368;")

        # Test by fetching model list
        self._model_fetcher = ModelListFetcher(base_url, key, provider)
        self._model_fetcher.finished.connect(self._on_validation_success)
        self._model_fetcher.error.connect(self._on_validation_fail)
        self._model_fetcher.start()

    def _on_validation_success(self, models: list):
        self.validate_btn.setEnabled(True)
        self.validate_btn.setText("验证 Key")
        if models:
            self.key_status.setText(f"✓ 验证成功（找到 {len(models)} 个模型）")
            self.key_status.setStyleSheet("font-size: 12px; color: #34a853;")
            # Update model list
            self.model_list.clear()
            for m in models:
                self.model_list.addItem(m)
            self._check_model_empty()
        else:
            self.key_status.setText("✓ 验证成功")
            self.key_status.setStyleSheet("font-size: 12px; color: #34a853;")

    def _on_validation_fail(self, error: str):
        self.validate_btn.setEnabled(True)
        self.validate_btn.setText("验证 Key")
        self.key_status.setText(f"✗ 验证失败: {error[:40]}")
        self.key_status.setStyleSheet("font-size: 12px; color: #ea4335;")

    def _save_key(self):
        """Save the API key."""
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "提示", "请输入 API Key")
            return
        # Store in both ai_key and api_key for backward compatibility
        self.config["api_key"] = encrypt_api_key(key)
        self.config["ai_key"] = encrypt_api_key(key)
        self._saved = True
        self.key_status.setText("✓ Key 已保存")
        self.key_status.setStyleSheet("font-size: 12px; color: #34a853;")

    def _on_key_changed(self):
        """Auto-fetch models when API key is entered."""
        key = self.key_input.text().strip()
        if key and len(key) > 10:
            # Debounce: only fetch if key looks valid (starts with sk- or is long enough)
            if hasattr(self, '_fetch_timer') and self._fetch_timer:
                self._fetch_timer.stop()
            from PyQt5.QtCore import QTimer
            self._fetch_timer = QTimer(self)
            self._fetch_timer.setSingleShot(True)
            self._fetch_timer.timeout.connect(self._auto_fetch_models)
            self._fetch_timer.start(800)  # 800ms debounce

    def _auto_fetch_models(self):
        """Auto-fetch models after API key input debounce."""
        provider = self.provider_combo.currentText()
        base_url = self.base_url_input.text().strip()
        api_key = self.key_input.text().strip()
        preset = PROVIDER_PRESETS.get(provider)
        if preset and preset.get("model_list_api") and base_url and api_key:
            self._do_fetch_models(base_url, api_key, provider)

    def _do_fetch_models(self, base_url: str, api_key: str, provider: str):
        """Internal method to actually fetch models."""
        self.refresh_btn.setEnabled(False)
        self.model_progress.setVisible(True)
        self.model_progress.setRange(0, 0)
        self.model_empty.setText("正在获取模型列表...")

        self._model_fetcher = ModelListFetcher(base_url, api_key, provider)
        self._model_fetcher.finished.connect(self._on_models_fetched)
        self._model_fetcher.error.connect(self._on_models_error)
        self._model_fetcher.start()

    def _fetch_models(self):
        """Fetch available models from the provider API."""
        provider = self.provider_combo.currentText()
        base_url = self.base_url_input.text().strip()
        api_key = self.key_input.text().strip()

        preset = PROVIDER_PRESETS.get(provider)
        if not preset or not preset.get("model_list_api"):
            QMessageBox.information(self, "提示", "该服务商不支持自动获取模型列表，请手动输入。")
            return

        self._do_fetch_models(base_url, api_key, provider)

    def _on_models_fetched(self, models: list):
        self.refresh_btn.setEnabled(True)
        self.model_progress.setVisible(False)
        self.model_list.clear()
        for m in models:
            self.model_list.addItem(m)
        self._check_model_empty()

    def _on_models_error(self, error: str):
        self.refresh_btn.setEnabled(True)
        self.model_progress.setVisible(False)
        self.model_empty.setText(f"⚠ 获取失败: {error}")
        self.model_empty.setStyleSheet("font-size: 12px; color: #ea4335; padding: 4px 0;")

    def _filter_models(self, text: str):
        """Filter model list by search text."""
        for i in range(self.model_list.count()):
            item = self.model_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _on_model_selected(self):
        """Handle model selection."""
        selected = self.model_list.selectedItems()
        if selected:
            self._check_model_empty()

    def _check_model_empty(self):
        """Update empty state label."""
        if self.model_list.count() == 0:
            self.model_empty.setText("暂无可用模型")
            self.model_empty.setStyleSheet("color: #5f6368; font-size: 12px; padding: 4px 0;")
            self.model_empty.setVisible(True)
        else:
            self.model_empty.setVisible(False)

    def _test_connectivity(self):
        """Test network connectivity to the AI provider (no full search)."""
        base_url = self.base_url_input.text().strip()
        api_key = self.key_input.text().strip()

        if not base_url:
            QMessageBox.warning(self, "提示", "请先填写接口地址")
            return

        self.ping_btn.setEnabled(False)
        self.ping_btn.setText("测试中...")
        self.test_status.setText("⏳ 正在测试网络连接...")
        self.test_status.setStyleSheet("font-size: 12px; color: #5f6368;")
        self.test_output.clear()

        # Connectivity test in background thread
        self._ping_thread = _ConnectivityWorker(base_url, api_key)
        self._ping_thread.finished.connect(self._on_connectivity_result)
        self._ping_thread.error.connect(self._on_connectivity_error)
        self._ping_thread.start()

    def _on_connectivity_result(self, message: str):
        self.ping_btn.setEnabled(True)
        self.ping_btn.setText("🌐 测试连接")
        self.test_status.setText("✓ 连接成功")
        self.test_status.setStyleSheet("font-size: 12px; color: #34a853;")
        self.test_output.setPlainText(message)

    def _on_connectivity_error(self, error: str):
        self.ping_btn.setEnabled(True)
        self.ping_btn.setText("🌐 测试连接")
        self.test_status.setText("✗ 连接失败")
        self.test_status.setStyleSheet("font-size: 12px; color: #ea4335;")
        self.test_output.setPlainText(f"连接失败: {error}")

    def _save_and_close(self):
        """Save all settings and close dialog."""
        # Save the API key
        if self.key_input.text().strip():
            self.config["api_key"] = encrypt_api_key(self.key_input.text().strip())
            self.config["ai_key"] = encrypt_api_key(self.key_input.text().strip())

        # Save provider config
        self.config["ai_provider"] = self.provider_combo.currentText()
        self.config["ai_base_url"] = self.base_url_input.text().strip()

        # Save selected model
        selected = self.model_list.selectedItems()
        if selected:
            self.config["ai_model"] = selected[0].text()

        self._saved = True
        self.accept()

    def get_config(self) -> dict:
        """Return the modified config."""
        return self.config


class _ConnectivityWorker(QThread):
    """Worker for testing network connectivity to AI provider."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, base_url: str, api_key: str = "", parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def run(self):
        try:
            import platform
            # Try HEAD request first (lightweight)
            headers = {"User-Agent": "NewsAgent/2.0"}
            try:
                resp = requests.head(self.base_url, headers=headers, timeout=10)
                result = (
                    f"✓ 网络连接成功\n"
                    f"  目标: {self.base_url}\n"
                    f"  状态码: {resp.status_code} {resp.reason}\n"
                    f"  响应头: Content-Type={resp.headers.get('Content-Type', 'N/A')}\n"
                    f"  主机: {platform.node()}"
                )
                self.finished.emit(result)
                return
            except requests.ConnectionError:
                # HEAD might fail on some servers, try GET
                pass

            # Fallback: GET root or models endpoint (lightweight)
            test_url = f"{self.base_url}/v1/models" if "deepseek" in self.base_url or "siliconflow" in self.base_url else self.base_url
            auth_headers = {"User-Agent": "NewsAgent/2.0"}
            if self.api_key:
                auth_headers["Authorization"] = f"Bearer {self.api_key}"

            resp = requests.get(test_url, headers=auth_headers, timeout=15)
            elapsed = resp.elapsed.total_seconds()

            result = (
                f"✓ 网络连接成功\n"
                f"  目标: {self.base_url}\n"
                f"  测试端点: {test_url}\n"
                f"  状态码: {resp.status_code} {resp.reason}\n"
                f"  响应时间: {elapsed:.2f}s\n"
                f"  主机: {platform.node()}"
            )
            self.finished.emit(result)

        except requests.ConnectionError:
            self.error.emit("无法连接到服务商，请检查接口地址和网络连接。")
        except requests.Timeout:
            self.error.emit("请求超时，服务商可能暂时不可用。")
        except Exception as e:
            self.error.emit(str(e))
