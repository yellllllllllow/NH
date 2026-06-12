"""News display panel with card layout.

Each search result displays:
  ┌──────────────────────┬──────────────────────┐
  │ Left:                │ Right:               │
  │ Original + Translation│ AI Summary           │
  └──────────────────────┴──────────────────────┘
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea, QFrame, QComboBox, QSplitter,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, pyqtSignal
import webbrowser
from app.ai_service_monitor import ai_monitor


class NewsCard(QFrame):
    """A single news article card with 2x2 content layout."""

    summarize_clicked = pyqtSignal(str)
    translate_clicked = pyqtSignal(str, str)  # text, language_pair
    card_clicked = pyqtSignal(dict)  # article data for detail view

    def __init__(self, article: dict, parent=None):
        super().__init__(parent)
        self.article = article
        self._summary_content = ""
        self._translation_content = ""
        self._build_ui()

    def _build_ui(self):
        """Build the 2x2 grid layout."""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(8)

        # === Header: source badge + date + title ===
        header = QHBoxLayout()
        source_badge = QLabel(self.article.get("source", "Unknown"))
        source_badge.setStyleSheet(
            "background-color: #e8f0fe; color: #1a73e8; "
            "padding: 2px 10px; border-radius: 10px; "
            "font-size: 11px; font-weight: bold;"
        )
        date_str = self.article.get("published", "")
        if date_str:
            date_str = date_str[:10]
        date_label = QLabel(date_str)
        date_label.setStyleSheet("color: #999; font-size: 11px;")

        # Translate to Chinese badge
        lang_hint = QLabel("🌐 翻译中文")
        lang_hint.setStyleSheet(
            "color: #34a853; font-size: 11px; font-weight: bold;"
        )
        lang_hint.setVisible(False)
        self.lang_hint = lang_hint

        header.addWidget(source_badge)
        header.addWidget(date_label)
        header.addSpacing(8)
        header.addWidget(lang_hint)
        header.addStretch()
        main_layout.addLayout(header)

        # Title
        title = QLabel(self.article.get("title", ""))
        title.setWordWrap(True)
        title.setStyleSheet("color: #1a1a1a; font-size: 14px; font-weight: bold;")
        main_layout.addWidget(title)

        # === 2x2 Content Grid using QSplitter ===
        grid = QSplitter(Qt.Horizontal)
        grid.setHandleWidth(2)

        # Left column (original + translation)
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 6, 0)
        left_layout.setSpacing(6)

        # Left Top: Original Content
        left_top = QWidget()
        left_top_layout = QVBoxLayout(left_top)
        left_top_layout.setContentsMargins(0, 0, 0, 0)
        left_top_layout.setSpacing(2)

        left_top_header = QLabel("📄 原文内容")
        left_top_header.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #5f6368; "
            "padding: 2px 0;"
        )
        left_top_layout.addWidget(left_top_header)

        self.original_text = QTextEdit()
        self.original_text.setPlainText(
            self.article.get("summary", self.article.get("title", ""))
        )
        self.original_text.setReadOnly(True)
        self.original_text.setMaximumHeight(120)
        self.original_text.setStyleSheet(
            "background: #f8f9fa; border: 1px solid #e8eaed; "
            "border-radius: 4px; padding: 6px; color: #3c4043; "
            "font-size: 12px;"
        )
        left_top_layout.addWidget(self.original_text)

        left_layout.addWidget(left_top)

        # Left Bottom: Translation
        left_bottom = QWidget()
        left_bottom_layout = QVBoxLayout(left_bottom)
        left_bottom_layout.setContentsMargins(0, 0, 0, 0)
        left_bottom_layout.setSpacing(2)

        left_bottom_header_row = QHBoxLayout()
        left_bottom_title = QLabel("🌍 译文内容")
        left_bottom_title.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #5f6368; "
            "padding: 2px 0;"
        )
        left_bottom_header_row.addWidget(left_bottom_title)
        left_bottom_header_row.addStretch()

        self.translate_btn = QPushButton("🔄 翻译")
        self.translate_btn.setCursor(Qt.PointingHandCursor)
        self.translate_btn.setFixedHeight(24)
        self.translate_btn.setStyleSheet(
            "QPushButton { background: #34a853; color: white; border: none; "
            "padding: 2px 12px; border-radius: 10px; font-size: 10px; }"
            "QPushButton:hover { background: #2d9249; }"
            "QPushButton:disabled { background: #c4c7c5; }"
        )
        self.translate_btn.clicked.connect(self._on_translate_clicked)
        left_bottom_header_row.addWidget(self.translate_btn)
        left_bottom_layout.addLayout(left_bottom_header_row)

        self.translation_text = QTextEdit()
        self.translation_text.setPlaceholderText("点击「翻译」按钮获取中文译文...")
        self.translation_text.setReadOnly(True)
        self.translation_text.setMaximumHeight(100)
        self.translation_text.setStyleSheet(
            "background: #f0faf0; border: 1px solid #ceead6; "
            "border-radius: 4px; padding: 6px; color: #3c4043; "
            "font-size: 12px;"
        )
        left_bottom_layout.addWidget(self.translation_text)

        left_layout.addWidget(left_bottom)
        grid.addWidget(left_col)

        # Right column (AI summary + related)
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(6)

        # Right Top: AI Summary
        right_top = QWidget()
        right_top_layout = QVBoxLayout(right_top)
        right_top_layout.setContentsMargins(0, 0, 0, 0)
        right_top_layout.setSpacing(2)

        right_top_header_row = QHBoxLayout()
        right_top_title = QLabel("🤖 AI 汇总")
        right_top_title.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #5f6368; "
            "padding: 2px 0;"
        )
        right_top_header_row.addWidget(right_top_title)
        right_top_header_row.addStretch()

        self.summarize_btn = QPushButton("✨ 生成摘要")
        self.summarize_btn.setCursor(Qt.PointingHandCursor)
        self.summarize_btn.setFixedHeight(24)
        self.summarize_btn.setStyleSheet(
            "QPushButton { background: #1a73e8; color: white; border: none; "
            "padding: 2px 12px; border-radius: 10px; font-size: 10px; }"
            "QPushButton:hover { background: #1557b0; }"
            "QPushButton:disabled { background: #c4c7c5; }"
        )
        self.summarize_btn.clicked.connect(self._on_summarize_clicked)
        right_top_header_row.addWidget(self.summarize_btn)
        right_top_layout.addLayout(right_top_header_row)

        self.summary_text = QTextEdit()
        self.summary_text.setPlaceholderText("点击「生成摘要」获取 AI 分析总结...")
        self.summary_text.setReadOnly(True)
        self.summary_text.setMaximumHeight(100)
        self.summary_text.setStyleSheet(
            "background: #f0f4ff; border: 1px solid #d2e3fc; "
            "border-radius: 4px; padding: 6px; color: #3c4043; "
            "font-size: 12px;"
        )
        right_top_layout.addWidget(self.summary_text)

        right_layout.addWidget(right_top)

        right_layout.addStretch()
        grid.addWidget(right_col)

        # Set equal splitter sizes
        grid.setSizes([400, 400])
        main_layout.addWidget(grid)

        # === Bottom action bar ===
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        open_btn = QPushButton("🌐 阅读原文")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(lambda: webbrowser.open(self.article.get("url", "")))
        open_btn.setStyleSheet(
            "QPushButton { background: #1a73e8; color: white; border: none; "
            "padding: 5px 16px; border-radius: 4px; font-size: 11px; }"
            "QPushButton:hover { background: #1557b0; }"
        )

        copy_btn = QPushButton("📋 复制链接")
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.clicked.connect(self._copy_link)
        copy_btn.setStyleSheet(
            "QPushButton { background: #f1f3f4; color: #3c4043; border: none; "
            "padding: 5px 16px; border-radius: 4px; font-size: 11px; }"
            "QPushButton:hover { background: #e8eaed; }"
        )

        action_bar.addWidget(open_btn)
        action_bar.addWidget(copy_btn)
        action_bar.addStretch()

        main_layout.addLayout(action_bar)

        self.setLayout(main_layout)
        self.setStyleSheet(
            "NewsCard { background: white; border: 1px solid #e0e0e0; "
            "border-radius: 8px; }"
            "NewsCard:hover { border-color: #1a73e8; }"
        )

    def _copy_link(self):
        """Copy article URL to clipboard."""
        from PyQt5.QtWidgets import QApplication
        url = self.article.get("url", "")
        if url:
            clipboard = QApplication.clipboard()
            clipboard.setText(url)

    def _on_summarize_clicked(self):
        """Handle summarize button click."""
        self.summarize_btn.setEnabled(False)
        self.summarize_btn.setText("生成中...")
        self.summary_text.setPlainText("⏳ 正在生成 AI 摘要...")
        text = self.article.get("summary", self.article.get("title", ""))
        self.summarize_clicked.emit(text)

    def _on_translate_clicked(self):
        """Handle translate button click."""
        self.translate_btn.setEnabled(False)
        self.translate_btn.setText("翻译中...")
        self.translation_text.setPlainText("⏳ 正在翻译...")
        text = self.article.get("summary", self.article.get("title", ""))
        self.translate_clicked.emit(text, "en:zh")

    def set_summary(self, summary: str):
        """Set AI summary text."""
        self._summary_content = summary
        self.summary_text.setPlainText(summary)
        self.summarize_btn.setEnabled(True)
        self.summarize_btn.setText("✅ 已生成")

    def set_summary_error(self, error: str):
        """Show summary error."""
        self.summary_text.setPlainText(f"❌ 摘要生成失败: {error}")
        self.summarize_btn.setEnabled(True)
        self.summarize_btn.setText("✨ 重试")

    def set_translation(self, translation: str):
        """Set translation text."""
        self._translation_content = translation
        self.translation_text.setPlainText(translation)
        self.translate_btn.setEnabled(True)
        self.translate_btn.setText("✅ 已翻译")
        self.lang_hint.setVisible(True)

    def set_translation_error(self, error: str):
        """Show translation error."""
        self.translation_text.setPlainText(f"❌ 翻译失败: {error}")
        self.translate_btn.setEnabled(True)
        self.translate_btn.setText("🔄 重试")

    def set_ai_available(self, available: bool):
        """Enable or disable AI-dependent buttons on this card.

        Called by NewsPanel when AI service availability changes.
        Content fetching and display remain completely unaffected.
        """
        self.summarize_btn.setEnabled(available)
        self.translate_btn.setEnabled(available)
        if not available:
            self.summarize_btn.setText("✨ AI 离线")
            self.translate_btn.setText("🔄 AI 离线")
        else:
            self.summarize_btn.setText("✨ 生成摘要")
            self.translate_btn.setText("🔄 翻译")


class NewsPanel(QWidget):
    """Panel displaying news articles in enhanced card layout."""

    summarize_requested = pyqtSignal(str)
    translate_requested = pyqtSignal(str, str)  # text, language_pair

    def __init__(self, parent=None):
        super().__init__(parent)
        self.articles = []
        self.cards = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 8)

        self.count_label = QLabel("0 条新闻")
        self.count_label.setStyleSheet("color: #666; font-size: 13px;")

        # Source filter
        self.source_filter = QComboBox()
        self.source_filter.addItem("所有来源", "")
        self.source_filter.setMinimumWidth(160)
        self.source_filter.setStyleSheet(
            "QComboBox { padding: 4px 8px; border: 1px solid #dadce0; "
            "border-radius: 4px; font-size: 12px; }"
        )
        self.source_filter.currentIndexChanged.connect(self._on_filter_changed)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["按时间排序", "按来源排序"])
        self.sort_combo.currentIndexChanged.connect(self._on_sort)

        toolbar.addWidget(self.count_label)
        toolbar.addSpacing(12)
        toolbar.addWidget(QLabel("来源筛选:"))
        toolbar.addWidget(self.source_filter)
        toolbar.addStretch()
        toolbar.addSpacing(12)
        toolbar.addWidget(QLabel("排序:"))
        toolbar.addWidget(self.sort_combo)
        layout.addLayout(toolbar)

        # Scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: #f5f5f5; }")

        self.container = QWidget()
        self.card_layout = QVBoxLayout(self.container)
        self.card_layout.setSpacing(12)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.addStretch()

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)
        self.setLayout(layout)

    def set_ai_available(self, available: bool):
        """Enable or disable AI features on all cards.

        AI service status changed — update every card's buttons.
        Content fetching remains completely unaffected.
        """
        for card in self.cards:
            card.set_ai_available(available)

    def set_articles(self, articles: list):
        """Display a list of article dicts."""
        self.articles = list(articles)
        self._update_source_filter()
        self._render()

    def _update_source_filter(self):
        """Populate source filter with available sources."""
        self.source_filter.blockSignals(True)
        current = self.source_filter.currentData()
        self.source_filter.clear()
        self.source_filter.addItem("所有来源", "")

        sources = set()
        for a in self.articles:
            s = a.get("source", "")
            if s:
                sources.add(s)
        for s in sorted(sources):
            self.source_filter.addItem(f"📰 {s}", s)

        # Restore selection
        if current:
            idx = self.source_filter.findData(current)
            if idx >= 0:
                self.source_filter.setCurrentIndex(idx)
        self.source_filter.blockSignals(False)

    def _on_filter_changed(self, idx: int):
        """Filter articles by source."""
        selected_source = self.source_filter.itemData(idx)
        if selected_source:
            filtered = [a for a in self.articles if a.get("source") == selected_source]
            self._render(filtered)
        else:
            self._render(self.articles)

    def _render(self, articles=None):
        """Render articles as enhanced cards."""
        self._clear_cards()
        self.cards = []

        display = articles if articles is not None else self.articles
        self.count_label.setText(f"{len(display)} 条新闻")
        ai_available = ai_monitor.is_available()

        for article in display:
            card = NewsCard(article)
            card.summarize_clicked.connect(self.summarize_requested)
            card.translate_clicked.connect(self.translate_requested)
            card.set_ai_available(ai_available)
            self.card_layout.insertWidget(
                self.card_layout.count() - 1, card
            )
            self.cards.append(card)

    def get_displayed_articles(self) -> list:
        """Return currently displayed articles (after filtering)."""
        return [card.article for card in self.cards]

    def get_card_by_article(self, article_text: str) -> NewsCard:
        """Find a NewsCard by article text content."""
        for card in self.cards:
            text = card.article.get("summary", card.article.get("title", ""))
            if text == article_text:
                return card
        return None

    def _clear_cards(self):
        while self.card_layout.count() > 1:
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_sort(self, index):
        if index == 0:
            self.articles.sort(
                key=lambda a: a.get("published", ""), reverse=True
            )
        elif index == 1:
            self.articles.sort(key=lambda a: a.get("source", ""))
        self._update_source_filter()
        self._render()
