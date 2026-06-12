"""Prompt template management dialog."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextEdit, QListWidget, QSplitter,
    QMessageBox, QWidget, QGroupBox, QDialogButtonBox
)
from PyQt5.QtCore import Qt


class PromptDialog(QDialog):
    """Dialog for managing summarization prompt templates."""

    def __init__(self, prompt_manager, parent=None):
        super().__init__(parent)
        self.prompt_manager = prompt_manager
        self.setWindowTitle("Prompt 管理")
        self.setMinimumSize(700, 500)
        self._build_ui()
        self._load_prompts()

    def _build_ui(self):
        main_layout = QVBoxLayout()

        # Splitter: left list, right editor
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - prompt list
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("Prompt 模板列表:"))

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self.list_widget)

        list_btn_layout = QHBoxLayout()
        add_btn = QPushButton("+ 新建")
        add_btn.clicked.connect(self._add_prompt)
        add_btn.setStyleSheet(
            "QPushButton { background: #34a853; color: white; border: none; "
            "padding: 5px 12px; border-radius: 4px; }"
        )
        del_btn = QPushButton("🗑 删除")
        del_btn.clicked.connect(self._delete_prompt)
        del_btn.setStyleSheet(
            "QPushButton { background: #ea4335; color: white; border: none; "
            "padding: 5px 12px; border-radius: 4px; }"
        )
        reset_btn = QPushButton("↺ 恢复默认")
        reset_btn.clicked.connect(self._reset_defaults)
        reset_btn.setStyleSheet(
            "QPushButton { background: #fbbc04; color: #333; border: none; "
            "padding: 5px 12px; border-radius: 4px; }"
        )
        list_btn_layout.addWidget(add_btn)
        list_btn_layout.addWidget(del_btn)
        list_btn_layout.addWidget(reset_btn)
        left_layout.addLayout(list_btn_layout)

        left_widget.setLayout(left_layout)

        # Right panel - editor
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.addWidget(QLabel("编辑 Prompt:"))

        edit_group = QGroupBox()
        edit_layout = QVBoxLayout()

        edit_layout.addWidget(QLabel("名称:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("例如: 简洁摘要")
        edit_layout.addWidget(self.name_input)

        edit_layout.addWidget(QLabel("描述:"))
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("简短描述此模板的用途")
        edit_layout.addWidget(self.desc_input)

        edit_layout.addWidget(QLabel("Prompt 内容 (使用 {article_text} 作为文章内容占位符):"))
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText(
            "请用2-3句话简洁概括以下新闻内容：\n\n{article_text}"
        )
        self.content_edit.setMinimumHeight(180)
        edit_layout.addWidget(self.content_edit)

        edit_group.setLayout(edit_layout)
        right_layout.addWidget(edit_group)

        # Save button
        self.save_btn = QPushButton("💾 保存修改")
        self.save_btn.clicked.connect(self._save_current)
        self.save_btn.setStyleSheet(
            "QPushButton { background: #1a73e8; color: white; border: none; "
            "padding: 8px 20px; border-radius: 4px; font-size: 13px; }"
            "QPushButton:hover { background: #1557b0; }"
        )
        right_layout.addWidget(self.save_btn)
        right_layout.addStretch()

        right_widget.setLayout(right_layout)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([250, 450])
        main_layout.addWidget(splitter)

        # Bottom close button
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(
            "QPushButton { background: #f1f3f4; color: #333; border: none; "
            "padding: 8px 30px; border-radius: 4px; }"
        )
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

    def _load_prompts(self):
        self.list_widget.clear()
        self.prompts = self.prompt_manager.get_all()
        for p in self.prompts:
            self.list_widget.addItem(f"{p['name']}  ({p['description']})")
        if self.prompts:
            self.list_widget.setCurrentRow(0)

    def _on_select(self, row):
        if 0 <= row < len(self.prompts):
            p = self.prompts[row]
            self._current_id = p["id"]
            self.name_input.setText(p["name"])
            self.desc_input.setText(p.get("description", ""))
            self.content_edit.setPlainText(p["content"])

    def _save_current(self):
        if not hasattr(self, '_current_id') or not self._current_id:
            QMessageBox.warning(self, "提示", "请先选择一个 Prompt 模板。")
            return
        name = self.name_input.text().strip()
        content = self.content_edit.toPlainText().strip()
        desc = self.desc_input.text().strip()
        if not name or not content:
            QMessageBox.warning(self, "提示", "名称和内容不能为空。")
            return
        self.prompt_manager.update(self._current_id, name, content, desc)
        self._load_prompts()
        QMessageBox.information(self, "成功", "Prompt 模板已更新。")

    def _add_prompt(self):
        name = "新建模板"
        content = "请总结以下内容：\n\n{article_text}"
        p = self.prompt_manager.add(name, content)
        self._load_prompts()
        for i, item in enumerate(self.prompts):
            if item["id"] == p["id"]:
                self.list_widget.setCurrentRow(i)
                break
        self.content_edit.setFocus()

    def _delete_prompt(self):
        if not hasattr(self, '_current_id'):
            return
        confirm = QMessageBox.question(
            self, "确认删除", "确定要删除此 Prompt 模板吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.prompt_manager.delete(self._current_id)
            self._load_prompts()

    def _reset_defaults(self):
        confirm = QMessageBox.question(
            self, "确认恢复", "将恢复所有默认 Prompt 模板，自定义模板将被覆盖。确定？",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.prompt_manager.reset_defaults()
            self._load_prompts()
            QMessageBox.information(self, "成功", "已恢复默认 Prompt 模板。")
