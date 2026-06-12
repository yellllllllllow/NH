"""Main window - Chrome-style UI with hamburger menu.

Changes v2.1:
- Removed source switcher from header (now a filter in content area)
- Integrated AES-256 encrypted API key storage
- Default model changed to deepseek-v4-flash
- Added translate support
- Added source filter to NewsPanel
"""

import json
import os
import sys

from PyQt5.QtWidgets import (
    QMainWindow, QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QMenu, QComboBox,
    QProgressBar, QMessageBox, QStatusBar, QAction
)
from PyQt5.QtCore import Qt, QPoint

from app.worker import (
    NewsFetchWorker, ApiKeyCheckWorker, SummarizeWorker,
    MultiSourceFetchWorker, TranslateWorker,
)
from app.prompts import PromptManager
from app.news_sources import load_sources, get_source_by_id
from app.semantic_search import get_search_terms
from app.secure_storage import encrypt_api_key, decrypt_api_key, is_key_encrypted
from app.ai_service_monitor import ai_monitor
from ui.news_panel import NewsPanel
from ui.prompt_dialog import PromptDialog
from ui.ai_settings_dialog import AiSettingsDialog
from ui.source_manager_dialog import SourceManagerDialog


CONFIG_FILE = "config.json"


def get_config_path() -> str:
    """Get config file path based on runtime context."""
    if hasattr(sys, 'frozen'):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, CONFIG_FILE)


def load_config() -> dict:
    """Load configuration from JSON file."""
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)

            # Decrypt API key if encrypted
            raw_key = cfg.get("api_key", "")
            if raw_key and is_key_encrypted(raw_key):
                decrypted = decrypt_api_key(raw_key)
                if decrypted:
                    cfg["api_key"] = decrypted
                    cfg["ai_key"] = decrypted

            # Backward compatibility: ensure ai_key from api_key
            if cfg.get("api_key") and not cfg.get("ai_key"):
                cfg["ai_key"] = cfg["api_key"]

            return cfg
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "api_key": "sk-0b78e1c816f94bc1865f94e367eb7064",
        "ai_key": "sk-0b78e1c816f94bc1865f94e367eb7064",
        "query": "川普",
        "page_size": 10,
        "ai_provider": "DeepSeek",
        "ai_base_url": "https://api.deepseek.com",
        "ai_model": "deepseek-v4-flash",
    }


def save_config(config: dict):
    """Save configuration to JSON file, encrypting sensitive fields."""
    cfg = dict(config)

    # Encrypt API key before saving
    raw_key = cfg.get("api_key", "")
    if raw_key and not is_key_encrypted(raw_key):
        cfg["api_key"] = encrypt_api_key(raw_key)
    raw_ai_key = cfg.get("ai_key", "")
    if raw_ai_key and not is_key_encrypted(raw_ai_key):
        cfg["ai_key"] = encrypt_api_key(raw_ai_key)

    path = get_config_path()
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"Failed to save config: {e}")


class MainWindow(QMainWindow):
    """Main application window with Chrome-style interface."""

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.prompt_manager = PromptManager()
        self.current_articles = []
        self.fetch_worker = None
        self.summarize_worker = None
        self.translate_worker = None
        self.summarize_all_worker = None
        self.news_sources = load_sources()
        self.current_source_id = self.config.get("news_source", "")

        self.setWindowTitle("新闻助手")
        self.setGeometry(100, 100, 1100, 800)
        self.setStyleSheet("QMainWindow { background: #ffffff; }")
        self._build_ui()
        self._check_ai_service()

    # ── UI Component Factories ────────────────────────────────────────────

    def _make_menu_btn(self) -> QPushButton:
        btn = QPushButton("⋮")
        btn.setFixedSize(36, 36)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; "
            "border-radius: 4px; font-size: 20px; color: #5f6368; }"
            "QPushButton:hover { background: #f1f3f4; }"
        )
        btn.clicked.connect(self._show_menu)
        return btn

    def _make_search_input(self) -> QLineEdit:
        inp = QLineEdit()
        inp.setPlaceholderText("搜索新闻关键词...")
        inp.setText(self.config.get("query", "Artificial Intelligence"))
        inp.returnPressed.connect(self._fetch_news)
        inp.setStyleSheet(
            "QLineEdit { padding: 8px 12px; border: 1px solid #dadce0; "
            "border-radius: 4px; font-size: 13px; background: #ffffff; }"
            "QLineEdit:hover { border-color: #1a73e8; }"
            "QLineEdit:focus { border-color: #1a73e8; }"
        )
        return inp

    def _make_fetch_btn(self) -> QPushButton:
        btn = QPushButton("获取新闻")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton { background: #1a73e8; color: white; border: none; "
            "padding: 8px 24px; border-radius: 4px; "
            "font-size: 13px; font-weight: 500; }"
            "QPushButton:hover { background: #1557b0; }"
            "QPushButton:disabled { background: #c4c7c5; }"
        )
        btn.clicked.connect(self._fetch_news)
        return btn

    def _make_progress_bar(self) -> QProgressBar:
        bar = QProgressBar()
        bar.setVisible(False)
        bar.setFixedHeight(3)
        bar.setStyleSheet(
            "QProgressBar { border: none; background: #e0e0e0; "
            "height: 3px; border-radius: 1px; }"
            "QProgressBar::chunk { background: #1a73e8; border-radius: 1px; }"
        )
        return bar

    # ── UI Construction ──────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # === Content area ===
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(16, 12, 16, 8)

        # Search bar (with source filter integrated)
        search_bar = QHBoxLayout()
        search_bar.setSpacing(8)

        self.search_input = self._make_search_input()
        search_bar.addWidget(self.search_input, 1)

        self.fetch_btn = self._make_fetch_btn()
        search_bar.addWidget(self.fetch_btn)

        content_layout.addLayout(search_bar)

        # Source filter row (replaces header source switcher)
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.setContentsMargins(0, 6, 0, 4)

        source_label = QLabel("新闻源:")
        source_label.setStyleSheet("font-size: 12px; color: #5f6368;")
        filter_row.addWidget(source_label)

        self.source_filter_combo = QComboBox()
        self.source_filter_combo.setStyleSheet(
            "QComboBox { padding: 4px 8px; border: 1px solid #dadce0; "
            "border-radius: 4px; font-size: 12px; min-width: 160px; }"
            "QComboBox:hover { border-color: #1a73e8; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
        )
        self.source_filter_combo.currentIndexChanged.connect(self._on_source_changed)

        self.source_status_label = QLabel("")
        self.source_status_label.setFixedWidth(16)

        self._refresh_source_filter()

        filter_row.addWidget(self.source_filter_combo)
        filter_row.addWidget(self.source_status_label)

        # Summarize all button
        self.summarize_all_btn = QPushButton("📊 汇总所有")
        self.summarize_all_btn.setCursor(Qt.PointingHandCursor)
        self.summarize_all_btn.setStyleSheet(
            "QPushButton { background: #1a73e8; color: white; border: none; "
            "padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: 500; }"
            "QPushButton:hover { background: #1557b0; }"
            "QPushButton:disabled { background: #c4c7c5; color: #9aa0a6; }"
        )
        self.summarize_all_btn.clicked.connect(self._on_summarize_all)
        filter_row.addWidget(self.summarize_all_btn)

        # AI status indicator — shows AI service availability at a glance
        self.ai_status_label = QLabel("⚪ AI 检测中...")
        self.ai_status_label.setStyleSheet(
            "font-size: 11px; color: #5f6368; padding: 2px 8px;"
        )
        self.ai_status_label.setToolTip("正在检测 AI 服务可用性...")
        filter_row.addWidget(self.ai_status_label)

        # Model selector
        model_label = QLabel("模型:")
        model_label.setStyleSheet("font-size: 12px; color: #5f6368;")
        filter_row.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.setStyleSheet(
            "QComboBox { padding: 4px 8px; border: 1px solid #dadce0; "
            "border-radius: 4px; font-size: 12px; min-width: 140px; }"
            "QComboBox:hover { border-color: #1a73e8; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
        )
        self._refresh_model_combo()
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        filter_row.addWidget(self.model_combo)

        filter_row.addStretch()

        # Semantic search toggle
        self.semantic_toggle = QPushButton("🔍 语义搜索")
        self.semantic_toggle.setCheckable(True)
        self.semantic_toggle.setChecked(True)
        self.semantic_toggle.setCursor(Qt.PointingHandCursor)
        self.semantic_toggle.setStyleSheet(
            "QPushButton { background: #e8f0fe; color: #1a73e8; border: 1px solid #d2e3fc; "
            "padding: 4px 12px; border-radius: 12px; font-size: 11px; }"
            "QPushButton:checked { background: #1a73e8; color: white; }"
        )
        filter_row.addWidget(self.semantic_toggle)

        # Source manager button
        source_mgr_btn = QPushButton("⚙ 管理源")
        source_mgr_btn.setCursor(Qt.PointingHandCursor)
        source_mgr_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #5f6368; border: 1px solid #dadce0; "
            "padding: 4px 12px; border-radius: 12px; font-size: 11px; }"
            "QPushButton:hover { background: #f1f3f4; }"
        )
        source_mgr_btn.clicked.connect(self._open_source_manager)
        filter_row.addWidget(source_mgr_btn)

        # Menu button
        self.menu_btn = self._make_menu_btn()
        filter_row.addWidget(self.menu_btn)

        content_layout.addLayout(filter_row)
        content_layout.addSpacing(4)

        self.progress_bar = self._make_progress_bar()
        content_layout.addWidget(self.progress_bar)

        # News panel (with integrated source filter)
        self.news_panel = NewsPanel()
        self.news_panel.summarize_requested.connect(self._on_summarize_requested)
        self.news_panel.translate_requested.connect(self._on_translate_requested)
        content_layout.addWidget(self.news_panel, 1)

        layout.addWidget(content, 1)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet(
            "QStatusBar { background: #f8f9fa; border-top: 1px solid #e0e0e0; "
            "font-size: 12px; color: #5f6368; }"
        )
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    # ── Source Filter Management ─────────────────────────────────────────

    def _refresh_source_filter(self):
        """Reload sources into the filter combo."""
        self.source_filter_combo.blockSignals(True)
        self.source_filter_combo.clear()
        self.news_sources = load_sources()

        # Add "All sources" option
        self.source_filter_combo.addItem("所有源（自动回退）", "")

        for src in self.news_sources:
            if not src.enabled:
                continue
            label = src.name
            if src.status.value == "online":
                label = "🟢 " + label
            elif src.status.value == "offline":
                label = "🔴 " + label
            self.source_filter_combo.addItem(label, src.id)

        # Restore selection
        if self.current_source_id:
            idx = self.source_filter_combo.findData(self.current_source_id)
            if idx >= 0:
                self.source_filter_combo.setCurrentIndex(idx)

        self.source_filter_combo.blockSignals(False)
        self._update_source_status()

    def _on_source_changed(self, idx: int):
        """Handle source selection change."""
        src_id = self.source_filter_combo.itemData(idx) or ""
        self.current_source_id = src_id
        self.config["news_source"] = src_id
        save_config(self.config)
        self._update_source_status()

    def _update_source_status(self):
        """Update the source connection status indicator."""
        if not self.current_source_id:
            self.source_status_label.setText("🔄")
            self.source_status_label.setToolTip("自动回退模式")
            return
        src = get_source_by_id(self.news_sources, self.current_source_id)
        if src:
            if src.status.value == "online":
                self.source_status_label.setText("🟢")
                self.source_status_label.setToolTip(f"{src.name}: 在线")
            elif src.status.value == "offline":
                self.source_status_label.setText("🔴")
                self.source_status_label.setToolTip(f"{src.name}: 离线")
            else:
                self.source_status_label.setText("⚪")
                self.source_status_label.setToolTip(f"{src.name}: 未知")

    # ── Model Selector ────────────────────────────────────────────────────

    def _refresh_model_combo(self):
        """Populate model combo from config."""
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        # Add common models
        models = ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"]
        current = self.config.get("ai_model", "deepseek-v4-flash")
        for m in models:
            self.model_combo.addItem(m)

        # Add any saved model not in the list
        if current and current not in models:
            self.model_combo.addItem(current)

        idx = self.model_combo.findText(current)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        self.model_combo.blockSignals(False)

    def _on_model_changed(self, model: str):
        """Handle model selection change."""
        if model:
            self.config["ai_model"] = model
            save_config(self.config)
            self.status_bar.showMessage(f"已切换模型: {model}", 3000)

    # ── AI Service Monitor ────────────────────────────────────────────────

    def _on_ai_availability_changed(self, available: bool):
        """Called when AI service availability changes.

        Disables or enables all AI-dependent buttons accordingly.
        Content fetching remains completely unaffected.
        """
        self.summarize_all_btn.setEnabled(available)
        self.news_panel.set_ai_available(available)

        status = ai_monitor.get_status_text()
        if available:
            self.ai_status_label.setText("🟢 AI 在线")
            self.ai_status_label.setToolTip(
                f"AI 服务正常 | {status}"
            )
        else:
            error_info = ai_monitor.get_last_error()
            if ai_monitor.check_lightweight():
                self.ai_status_label.setText("🔴 AI 不可用")
                self.ai_status_label.setToolTip(
                    f"AI 服务连接失败.\n请在菜单「AI 模型设置」中检查配置.\n"
                    f"错误: {error_info or status}"
                )
            else:
                self.ai_status_label.setText("⚪ AI 未配置")
                self.ai_status_label.setToolTip(
                    f"请在菜单「AI 模型设置」中配置 API Key\n"
                    f"配置后 AI 功能（翻译/摘要/汇总）将自动启用"
                )

    def _check_ai_service(self):
        """Run AI service health check in background.

        Updates AI status label and button states based on result.
        Content fetching is NOT affected by AI availability.
        """
        api_key = self.config.get("api_key", "") or self.config.get("ai_key", "")
        base_url = self.config.get("ai_base_url", "https://api.deepseek.com")
        model = self.config.get("ai_model", "v4flash")

        ai_monitor.configure(api_key, base_url, model)
        ai_monitor.set_on_change(self._on_ai_availability_changed)
        ai_monitor.check()

    # ── Summarize All ─────────────────────────────────────────────────────

    def _on_summarize_all(self):
        """Summarize all displayed articles."""
        if not ai_monitor.is_available():
            self.status_bar.showMessage(
                "AI 服务不可用，请先在菜单中配置 API Key", 3000
            )
            self._check_ai_service()
            return
        articles = self.news_panel.get_displayed_articles()
        if not articles:
            self.status_bar.showMessage("没有可汇总的新闻", 3000)
            return

        api_key = self.config.get("api_key", "")
        base_url = self.config.get("ai_base_url", "https://api.deepseek.com")
        model = self.config.get("ai_model", "v4flash")

        if not api_key:
            api_key = self.config.get("ai_key", "")

        if not api_key or not base_url or not model:
            QMessageBox.warning(
                self, "AI 未配置",
                "请先在菜单「AI 模型设置」中配置服务商、接口地址和模型。"
            )
            return

        # Combine all articles into a single text
        combined = ""
        for i, a in enumerate(articles[:10], 1):
            title = a.get("title", "")
            summary = a.get("summary", "")
            combined += f"{i}. {title}\n{summary}\n\n"

        self.status_bar.showMessage("正在汇总所有新闻...")
        self.summarize_all_btn.setEnabled(False)
        self.summarize_all_btn.setText("汇总中...")

        prompt_template = "请对以下新闻进行综合汇总分析，提炼核心要点：\n\n{article_text}"

        self.summarize_all_worker = SummarizeWorker(
            text=combined,
            prompt_template=prompt_template,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        self.summarize_all_worker.finished.connect(self._on_summarize_all_done)
        self.summarize_all_worker.error.connect(self._on_summarize_all_error)
        self.summarize_all_worker.start()

    def _on_summarize_all_done(self, result: str):
        """Handle successful summarization of all articles."""
        self.status_bar.showMessage("汇总完成", 3000)
        self.summarize_all_btn.setEnabled(True)
        self.summarize_all_btn.setText("📊 汇总所有")
        QMessageBox.information(self, "新闻汇总结果", result)

    def _on_summarize_all_error(self, error_msg: str):
        """Handle summarization all error."""
        self.status_bar.showMessage("汇总失败", 5000)
        self.summarize_all_btn.setEnabled(True)
        self.summarize_all_btn.setText("📊 汇总所有")
        QMessageBox.critical(self, "汇总失败",
            f"新闻汇总失败:\n{error_msg}")

    # ── Menu ─────────────────────────────────────────────────────────────

    def _show_menu(self):
        """Display Chrome-style dropdown menu."""
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #ffffff; border: 1px solid #dadce0; "
            "border-radius: 8px; padding: 6px 0; }"
            "QMenu::item { padding: 8px 24px; font-size: 13px; "
            "color: #3c4043; min-width: 180px; }"
            "QMenu::item:selected { background: #f1f3f4; }"
            "QMenu::separator { height: 1px; background: #e0e0e0; "
            "margin: 4px 12px; }"
        )

        ai_action = QAction("AI 模型设置", self)
        ai_action.triggered.connect(self._open_ai_settings)
        menu.addAction(ai_action)

        prompt_action = QAction("Prompt 管理", self)
        prompt_action.triggered.connect(self._open_prompt_manager)
        menu.addAction(prompt_action)

        menu.addSeparator()

        source_action = QAction("新闻源管理", self)
        source_action.triggered.connect(self._open_source_manager)
        menu.addAction(source_action)

        menu.addSeparator()

        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        menu.addAction(about_action)

        btn_rect = self.menu_btn.rect()
        menu.exec_(self.menu_btn.mapToGlobal(
            btn_rect.bottomLeft() + QPoint(-btn_rect.width() + 180, 4)
        ))

    def _open_ai_settings(self):
        """Open AI model settings dialog."""
        dialog = AiSettingsDialog(self.config, self)
        if dialog.exec_() == QDialog.Accepted:
            self.config = dialog.get_config()
            save_config(self.config)
            self._refresh_model_combo()
            # Re-check AI service health after config changes
            self._check_ai_service()
            self.status_bar.showMessage("AI 模型设置已保存，正在检测 AI 服务...", 3000)
            if self.config.get("api_key"):
                self.status_bar.showMessage("API Key 已加密保存，正在检测 AI 服务...", 3000)

    def _open_prompt_manager(self):
        """Open prompt management dialog."""
        dialog = PromptDialog(self.prompt_manager, self)
        dialog.exec_()

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self, "关于 新闻助手",
            "<h3>新闻助手</h3>"
            "<p>智能新闻聚合与 AI 摘要工具</p>"
            "<p>版本: 2.1.0</p>"
            "<p>支持多新闻源自动切换</p>"
            "<p>支持 DeepSeek、硅基流动、Ollama 等 AI 服务商</p>"
            "<p>🔒 API Key 使用 AES-256-GCM 加密存储</p>"
        )

    def _open_source_manager(self):
        """Open the news source management dialog."""
        api_key = self.config.get("api_key", "")
        dialog = SourceManagerDialog(self)
        dialog.set_api_key(api_key)
        if dialog.exec_() == QDialog.Accepted:
            self._refresh_source_filter()
            self.status_bar.showMessage("新闻源配置已更新", 3000)

    # ── News Fetching ────────────────────────────────────────────────────

    def _fetch_news(self):
        """Fetch news from sources with semantic search support."""
        query = self.search_input.text().strip() or "Artificial Intelligence"
        api_key = self.config.get("api_key", "")
        page_size = self.config.get("page_size", 10)
        use_semantic = self.semantic_toggle.isChecked()

        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("获取中...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_bar.showMessage(
            f"正在获取新闻（语义搜索{'已' if use_semantic else '未'}启用）..."
        )

        # Get primary source ID
        idx = self.source_filter_combo.currentIndex()
        primary_id = self.source_filter_combo.itemData(idx) or ""

        self.fetch_worker = MultiSourceFetchWorker(
            query=query,
            page_size=page_size,
            primary_source_id=primary_id,
            api_key=api_key,
            proxies={},
            use_semantic_search=use_semantic,
        )
        self.fetch_worker.finished.connect(self._on_news_fetched)
        self.fetch_worker.error.connect(self._on_fetch_error)
        self.fetch_worker.progress.connect(self._on_fetch_progress)
        self.fetch_worker.start()

    def _on_fetch_progress(self, message: str, success: bool):
        """Handle fetch progress updates."""
        self.status_bar.showMessage(message, 2000)

    def _on_news_fetched(self, articles):
        """Handle successful news fetch."""
        self.progress_bar.setVisible(False)
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("获取新闻")

        if not articles:
            QMessageBox.information(
                self, "无结果",
                "所有新闻源均未找到相关文章。\n"
                "建议尝试修改搜索关键词或切换新闻源。"
            )
            self.status_bar.showMessage("未找到新闻", 3000)
            return

        # Update source status indicators
        self._refresh_source_filter()

        self.current_articles = articles
        self.news_panel.set_articles(articles)
        sources_used = set(a.get("source_id", "") for a in articles)
        source_names = set(a.get("source", "") for a in articles)
        status_msg = f"已加载 {len(articles)} 条新闻"
        if source_names:
            status_msg += f" (来源: {', '.join(list(source_names)[:3])})"
        self.status_bar.showMessage(status_msg, 5000)

    def _on_fetch_error(self, error_msg: str):
        """Handle fetch error."""
        self.progress_bar.setVisible(False)
        self.fetch_btn.setEnabled(True)
        self.fetch_btn.setText("获取新闻")
        QMessageBox.critical(self, "获取失败", error_msg)
        self.status_bar.showMessage("获取新闻失败", 5000)

    # ── AI Summarization ─────────────────────────────────────────────────

    def _on_summarize_requested(self, article_text: str):
        """Handle AI summarization request from a card."""
        if not ai_monitor.is_available():
            self.status_bar.showMessage("AI 摘要不可用 - 请先配置 API Key", 3000)
            self._check_ai_service()
            return
        api_key = self.config.get("api_key", "")
        base_url = self.config.get("ai_base_url", "https://api.deepseek.com")
        model = self.config.get("ai_model", "deepseek-chat")

        if not api_key:
            api_key = self.config.get("ai_key", "")

        if not base_url or not model:
            QMessageBox.warning(
                self, "AI 未配置",
                "请先在菜单「AI 模型设置」中配置服务商、接口地址和模型。"
            )
            return

        self.status_bar.showMessage("正在生成 AI 摘要...")

        prompts = self.prompt_manager.get_all()
        prompt = prompts[0] if prompts else {"content": "{article_text}"}
        prompt_template = prompt.get("content", "{article_text}")

        self.summarize_worker = SummarizeWorker(
            text=article_text,
            prompt_template=prompt_template,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        self.summarize_worker.finished.connect(
            lambda result, text=article_text: self._on_summarize_done(result, text)
        )
        self.summarize_worker.error.connect(
            lambda error, text=article_text: self._on_summarize_error(error, text)
        )
        self.summarize_worker.start()

    def _on_summarize_done(self, result: str, article_text: str):
        """Handle successful summarization."""
        self.status_bar.showMessage("AI 摘要生成完成", 3000)
        # Find the card and set summary
        card = self.news_panel.get_card_by_article(article_text)
        if card:
            card.set_summary(result)

    def _on_summarize_error(self, error_msg: str, article_text: str):
        """Handle summarization error."""
        self.status_bar.showMessage("AI 摘要生成失败", 5000)
        card = self.news_panel.get_card_by_article(article_text)
        if card:
            card.set_summary_error(error_msg)

    # ── Translation ──────────────────────────────────────────────────────

    def _on_translate_requested(self, text: str, lang_pair: str):
        """Handle translation request from a card."""
        if not ai_monitor.is_available():
            self.status_bar.showMessage("翻译不可用 - 请先配置 API Key", 3000)
            self._check_ai_service()
            return
        api_key = self.config.get("api_key", "")
        base_url = self.config.get("ai_base_url", "https://api.deepseek.com")
        model = self.config.get("ai_model", "deepseek-chat")

        if not api_key:
            api_key = self.config.get("ai_key", "")

        if not base_url or not model:
            QMessageBox.warning(
                self, "AI 未配置",
                "请先配置 AI 服务以使用翻译功能。"
            )
            return

        self.status_bar.showMessage("正在翻译...")

        self.translate_worker = TranslateWorker(
            text=text,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        self.translate_worker.finished.connect(
            lambda result, t=text: self._on_translate_done(result, t)
        )
        self.translate_worker.error.connect(
            lambda error, t=text: self._on_translate_error(error, t)
        )
        self.translate_worker.start()

    def _on_translate_done(self, result: str, article_text: str):
        """Handle successful translation."""
        self.status_bar.showMessage("翻译完成", 3000)
        card = self.news_panel.get_card_by_article(article_text)
        if card:
            card.set_translation(result)

    def _on_translate_error(self, error_msg: str, article_text: str):
        """Handle translation error."""
        self.status_bar.showMessage("翻译失败", 5000)
        card = self.news_panel.get_card_by_article(article_text)
        if card:
            card.set_translation_error(error_msg)
