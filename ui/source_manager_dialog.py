"""News source management dialog.

Provides UI for:
- Viewing all sources with connection status
- Adding custom sources
- Editing/removing sources
- Testing source connections
- Switching default source
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QListWidget, QListWidgetItem,
    QMessageBox, QProgressBar, QWidget, QFrame, QCheckBox,
    QGroupBox, QFormLayout, QTextEdit, QSplitter,
    QDialogButtonBox, QTabWidget, QSpacerItem, QSizePolicy,
    QAbstractItemView,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush, QIcon

from typing import List, Optional, Dict
import sys
import os

# Ensure project root is importable
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from app.news_sources import (
    NewsSource, SourceType, SourceStatus,
    load_sources, save_sources, get_source_by_id,
    is_valid_url, generate_source_id, BUILT_IN_SOURCES,
)
from app.multi_fetcher import fetch_from_source, FetchResult


# ── Connection test worker thread ─────────────────────────────────────────

class ConnectionTestWorker(QThread):
    """Background thread for testing a source connection."""
    finished = pyqtSignal(str, bool, str)  # source_id, success, message

    def __init__(self, source: NewsSource, api_key: str = ""):
        super().__init__()
        self.source = source
        self.api_key = api_key

    def run(self):
        try:
            result = fetch_from_source(
                self.source, query="test", page_size=1,
                api_key=self.api_key,
            )
            if result.success:
                msg = f"连接成功！响应时间: {result.elapsed_ms}ms" + (
                    f"，获取到 {len(result.articles)} 条文章" if result.articles else ""
                )
                self.finished.emit(self.source.id, True, msg)
            else:
                self.finished.emit(
                    self.source.id, False,
                    f"连接失败: {result.error_message}"
                )
        except Exception as e:
            self.finished.emit(self.source.id, False, str(e)[:100])


# ── Source Manager Dialog ─────────────────────────────────────────────────

class SourceManagerDialog(QDialog):
    """Dialog for managing news sources."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sources = load_sources()
        self.current_source_id: Optional[str] = None
        self._test_workers: List[ConnectionTestWorker] = []
        self._dirty = False
        self.api_key = ""
        self.selected_source_id = ""

        self.setWindowTitle("新闻源管理")
        self.setMinimumSize(780, 600)
        self.setStyleSheet("""
            QDialog { background: #ffffff; }
            QGroupBox {
                font-weight: bold; border: 1px solid #e0e0e0;
                border-radius: 6px; margin-top: 12px; padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px; padding: 0 6px;
            }
        """)
        self._build_ui()
        self._populate_source_list()

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("新闻源管理")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 500; color: #202124;"
        )
        layout.addWidget(title)

        desc = QLabel("管理新闻来源，添加自定义源，测试连接状态。")
        desc.setStyleSheet("font-size: 13px; color: #5f6368; margin-bottom: 8px;")
        layout.addWidget(desc)

        # Main splitter
        splitter = QSplitter(Qt.Horizontal)

        # ── Left panel: Source list ──
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(6)

        left_layout.addWidget(QLabel("可用新闻源"))
        self.source_list = QListWidget()
        self.source_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.source_list.currentRowChanged.connect(self._on_source_selected)
        self.source_list.setMinimumWidth(240)
        left_layout.addWidget(self.source_list)

        # Source list buttons
        list_btn_row = QHBoxLayout()
        self.add_btn = QPushButton("+ 添加")
        self.add_btn.clicked.connect(self._add_source)
        self.remove_btn = QPushButton("删除")
        self.remove_btn.setEnabled(False)
        self.remove_btn.clicked.connect(self._remove_source)
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setEnabled(False)
        self.test_btn.clicked.connect(self._test_connection)
        self.test_all_btn = QPushButton("测试全部")
        self.test_all_btn.clicked.connect(self._test_all)

        list_btn_row.addWidget(self.add_btn)
        list_btn_row.addWidget(self.remove_btn)
        list_btn_row.addWidget(self.test_btn)
        list_btn_row.addWidget(self.test_all_btn)
        left_layout.addLayout(list_btn_row)

        splitter.addWidget(left_panel)

        # ── Right panel: Source detail ──
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        # Detail group
        detail_group = QGroupBox("源配置")
        detail_form = QFormLayout(detail_group)
        detail_form.setSpacing(8)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("新闻源名称（如: BBC News）")
        detail_form.addRow("名称:", self.name_input)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("API 或网站 URL")
        detail_form.addRow("URL:", self.url_input)

        self.rss_input = QLineEdit()
        self.rss_input.setPlaceholderText("RSS Feed URL（可选）")
        detail_form.addRow("RSS:", self.rss_input)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["API (REST)", "RSS Feed", "Web"])
        detail_form.addRow("类型:", self.type_combo)

        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("简短描述（可选）")
        detail_form.addRow("描述:", self.desc_input)

        self.enabled_check = QCheckBox("启用此新闻源")
        self.enabled_check.setChecked(True)
        detail_form.addRow("", self.enabled_check)

        right_layout.addWidget(detail_group)

        # Status display
        self.status_label = QLabel("选择一个源查看详情")
        self.status_label.setStyleSheet(
            "padding: 8px; background: #f8f9fa; border-radius: 4px;"
            "font-size: 12px; color: #5f6368;"
        )
        self.status_label.setWordWrap(True)
        right_layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: none; background: #e0e0e0;"
            "height: 6px; border-radius: 3px; }"
            "QProgressBar::chunk { background: #1a73e8; border-radius: 3px; }"
        )
        right_layout.addWidget(self.progress_bar)

        detail_group.setEnabled(False)
        right_layout.addStretch()

        splitter.addWidget(right_panel)
        splitter.setSizes([300, 450])
        layout.addWidget(splitter, 1)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.save_btn = QPushButton("保存配置")
        self.save_btn.clicked.connect(self._save_all)
        self.save_btn.setStyleSheet(
            "QPushButton { background: #1a73e8; color: white; border: none;"
            "padding: 8px 24px; border-radius: 4px; font-size: 13px; }"
            "QPushButton:hover { background: #1557b0; }"
        )

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(
            "QPushButton { background: #f1f3f4; color: #3c4043; border: none;"
            "padding: 8px 24px; border-radius: 4px; font-size: 13px; }"
            "QPushButton:hover { background: #e8eaed; }"
        )

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _populate_source_list(self):
        """Populate the source list with all sources."""
        self.source_list.blockSignals(True)
        self.source_list.clear()

        for source in self.sources:
            item = QListWidgetItem()
            status_icon = self._status_emoji(source.status)
            item.setText(f"{status_icon} {source.name}")
            item.setData(Qt.UserRole, source.id)
            item.setToolTip(
                f"类型: {source.type.value}\n"
                f"URL: {source.url}\n"
                f"状态: {source.status.value}\n"
                f"{source.description}"
            )

            # Color based on status
            if source.status == SourceStatus.ONLINE:
                item.setForeground(QColor("#34a853"))
            elif source.status == SourceStatus.OFFLINE:
                item.setForeground(QColor("#ea4335"))

            self.source_list.addItem(item)

        self.source_list.blockSignals(False)
        if self.source_list.count() > 0:
            self.source_list.setCurrentRow(0)

    def _status_emoji(self, status: SourceStatus) -> str:
        if status == SourceStatus.ONLINE:
            return "🟢"
        elif status == SourceStatus.OFFLINE:
            return "🔴"
        return "⚪"

    def _on_source_selected(self, row: int):
        """Handle source selection in the list."""
        if row < 0 or row >= len(self.sources):
            self._clear_detail()
            return

        source = self.sources[row]
        self.current_source_id = source.id

        # Enable detail editing
        detail_group = self.findChild(QGroupBox, "")
        # Enable buttons
        self.remove_btn.setEnabled(not self._is_builtin(source))
        self.test_btn.setEnabled(True)

        # Populate detail fields
        self.name_input.setText(source.name)
        self.url_input.setText(source.url)
        self.rss_input.setText(source.rss_feed_url)

        type_idx = 0
        if source.type == SourceType.RSS:
            type_idx = 1
        elif source.type == SourceType.WEB:
            type_idx = 2
        self.type_combo.setCurrentIndex(type_idx)

        self.desc_input.setText(source.description)
        self.enabled_check.setChecked(source.enabled)

        # Enable detail group
        for child in self.findChildren(QGroupBox):
            child.setEnabled(True)

        # Update status
        status_text = (
            f"源: {source.name}\n"
            f"类型: {source.type.value}\n"
            f"状态: {self._status_emoji(source.status)} {source.status.value}\n"
            f"需要API Key: {'是' if source.requires_api_key else '否'}\n"
            f"回退优先级: {source.fallback_order}"
        )
        if source.last_checked:
            from datetime import datetime
            checked_time = datetime.fromtimestamp(source.last_checked)
            status_text += f"\n上次检测: {checked_time.strftime('%Y-%m-%d %H:%M')}"
        self.status_label.setText(status_text)

    def _clear_detail(self):
        """Clear detail fields."""
        self.name_input.clear()
        self.url_input.clear()
        self.rss_input.clear()
        self.desc_input.clear()
        self.enabled_check.setChecked(True)
        self.type_combo.setCurrentIndex(0)
        self.status_label.setText("选择一个源查看详情")
        self.remove_btn.setEnabled(False)
        self.test_btn.setEnabled(False)

    def _is_builtin(self, source: NewsSource) -> bool:
        """Check if source is a built-in source."""
        return any(s.id == source.id for s in BUILT_IN_SOURCES)

    def _add_source(self):
        """Add a custom news source."""
        # Create a new custom source with defaults
        new_id = generate_source_id("custom_source")
        new_source = NewsSource(
            id=new_id,
            name="新新闻源",
            type=SourceType.RSS,
            url="https://",
            enabled=True,
        )
        self.sources.append(new_source)
        self._populate_source_list()
        # Select the new source
        for i, s in enumerate(self.sources):
            if s.id == new_id:
                self.source_list.setCurrentRow(i)
                break
        self._dirty = True

    def _remove_source(self):
        """Remove the currently selected source."""
        if not self.current_source_id:
            return

        source = get_source_by_id(self.sources, self.current_source_id)
        if not source:
            return

        if self._is_builtin(source):
            QMessageBox.information(self, "提示", "内置源不能删除，可以禁用。")
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除新闻源「{source.name}」吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.sources = [s for s in self.sources if s.id != source.id]
            self._populate_source_list()
            self._dirty = True

    def _test_connection(self):
        """Test connection to the currently selected source."""
        if not self.current_source_id:
            return

        source = get_source_by_id(self.sources, self.current_source_id)
        if not source:
            return

        # Save current edits to the source
        self._apply_edits(source)

        self.test_btn.setEnabled(False)
        self.test_btn.setText("测试中...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_label.setText(f"正在测试 {source.name} 连接...")

        worker = ConnectionTestWorker(source, self.api_key)
        worker.finished.connect(self._on_test_complete)
        self._test_workers.append(worker)
        worker.start()

    def _on_test_complete(self, source_id: str, success: bool, message: str):
        """Handle connection test result."""
        self.test_btn.setEnabled(True)
        self.test_btn.setText("测试连接")
        self.progress_bar.setVisible(False)

        # Update source status
        source = get_source_by_id(self.sources, source_id)
        if source:
            from datetime import datetime
            source.status = SourceStatus.ONLINE if success else SourceStatus.OFFLINE
            source.last_checked = datetime.now().timestamp()
            self._dirty = True

        # Update display
        if success:
            self.status_label.setText(f"✅ {message}")
            self.status_label.setStyleSheet(
                "padding: 8px; background: #e6f4ea; border-radius: 4px;"
                "font-size: 12px; color: #1e7e34;"
            )
        else:
            self.status_label.setText(f"❌ {message}")
            self.status_label.setStyleSheet(
                "padding: 8px; background: #fce8e6; border-radius: 4px;"
                "font-size: 12px; color: #c5221f;"
            )

        # Refresh list to update status indicators
        self._populate_source_list()

    def _test_all(self):
        """Test all enabled sources."""
        self.test_all_btn.setEnabled(False)
        self.test_all_btn.setText("全部测试中...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        self._test_results = []
        enabled_sources = [s for s in self.sources if s.enabled]

        self._test_queue = list(enabled_sources)
        self._test_next()

    def _test_next(self):
        """Test the next source in the queue."""
        if not self._test_queue:
            self._on_all_tests_done()
            return

        source = self._test_queue.pop(0)
        self.status_label.setText(f"正在测试 {source.name}...")

        worker = ConnectionTestWorker(source, self.api_key)
        worker.finished.connect(lambda sid, ok, msg: self._on_one_test_done(sid, ok, msg))
        self._test_workers.append(worker)
        worker.start()

    def _on_one_test_done(self, source_id: str, success: bool, message: str):
        """Handle one test result in the batch."""
        source = get_source_by_id(self.sources, source_id)
        if source:
            from datetime import datetime
            source.status = SourceStatus.ONLINE if success else SourceStatus.OFFLINE
            source.last_checked = datetime.now().timestamp()
            self._dirty = True
            self._test_results.append((source.name, success, message))

        # Continue testing
        self._test_next()

    def _on_all_tests_done(self):
        """Handle all tests complete."""
        self.test_all_btn.setEnabled(True)
        self.test_all_btn.setText("测试全部")
        self.progress_bar.setVisible(False)

        online = sum(1 for r in self._test_results if r[1])
        offline = len(self._test_results) - online

        status_msg = f"测试完成: {online} 个在线, {offline} 个离线"
        self.status_label.setText(f"📊 {status_msg}")
        self.status_label.setStyleSheet(
            "padding: 8px; background: #f8f9fa; border-radius: 4px;"
            "font-size: 12px; color: #5f6368;"
        )

        self._populate_source_list()

    def _apply_edits(self, source: NewsSource):
        """Apply current UI edits to a source object."""
        source.name = self.name_input.text().strip() or source.name
        source.url = self.url_input.text().strip() or source.url
        source.rss_feed_url = self.rss_input.text().strip()

        type_map = {0: SourceType.API, 1: SourceType.RSS, 2: SourceType.WEB}
        source.type = type_map.get(self.type_combo.currentIndex(), SourceType.RSS)

        source.description = self.desc_input.text().strip()
        source.enabled = self.enabled_check.isChecked()

    def _save_all(self):
        """Save all sources to config file."""
        # Apply any pending edits
        if self.current_source_id:
            source = get_source_by_id(self.sources, self.current_source_id)
            if source:
                self._apply_edits(source)

        if save_sources(self.sources):
            self._dirty = False
            QMessageBox.information(self, "保存成功", "新闻源配置已保存。")
        else:
            QMessageBox.warning(self, "保存失败", "无法写入配置文件。")

    def get_selected_source_id(self) -> str:
        """Return the currently selected source ID (set from outside)."""
        return self.selected_source_id

    def set_api_key(self, api_key: str):
        """Set the API key for testing sources that require it."""
        self.api_key = api_key
