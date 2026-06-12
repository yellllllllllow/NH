"""Prompt template management system."""

import json
import os
from typing import List, Dict, Optional


DEFAULT_PROMPTS = [
    {
        "id": "concise",
        "name": "简洁摘要",
        "content": "请用2-3句话简洁概括以下新闻内容，突出核心信息。\n\n{article_text}",
        "description": "简洁明了，适用于快速浏览"
    },
    {
        "id": "detailed",
        "name": "详细分析",
        "content": "请详细分析以下新闻，包括：1) 核心事件 2) 背景信息 3) 潜在影响。\n\n{article_text}",
        "description": "深入分析，适用于深度阅读"
    },
    {
        "id": "chinese",
        "name": "中文翻译摘要",
        "content": "请将以下英文新闻翻译成中文，并用3-4句话概括核心内容。\n\n{article_text}",
        "description": "中英翻译+摘要，适用于非英语用户"
    },
    {
        "id": "keypoints",
        "name": "要点列表",
        "content": "请将以下新闻提炼为3-5个关键要点，用列表形式输出。\n\n{article_text}",
        "description": "要点式阅读，快速获取关键信息"
    },
]


class PromptManager:
    """Manages prompt templates with CRUD operations."""

    def __init__(self, prompts_path: str = None):
        if prompts_path is None:
            prompts_path = self._default_path()
        self.prompts_path = prompts_path
        self.prompts: List[Dict] = []
        self._load()

    @staticmethod
    def _default_path() -> str:
        if hasattr(sys, 'frozen'):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, 'prompts.json')

    def _load(self):
        if os.path.exists(self.prompts_path):
            try:
                with open(self.prompts_path, 'r', encoding='utf-8') as f:
                    self.prompts = json.load(f)
                return
            except (json.JSONDecodeError, TypeError):
                pass
        self.prompts = list(DEFAULT_PROMPTS)
        self._save()

    def _save(self):
        with open(self.prompts_path, 'w', encoding='utf-8') as f:
            json.dump(self.prompts, f, indent=2, ensure_ascii=False)

    def get_all(self) -> List[Dict]:
        return list(self.prompts)

    def get_by_id(self, prompt_id: str) -> Optional[Dict]:
        for p in self.prompts:
            if p["id"] == prompt_id:
                return dict(p)
        return None

    def add(self, name: str, content: str, description: str = "") -> Dict:
        import uuid
        new_id = str(uuid.uuid4())[:8]
        prompt = {
            "id": new_id,
            "name": name,
            "content": content,
            "description": description
        }
        self.prompts.append(prompt)
        self._save()
        return prompt

    def update(self, prompt_id: str, name: str = None,
               content: str = None, description: str = None) -> bool:
        for p in self.prompts:
            if p["id"] == prompt_id:
                if name is not None:
                    p["name"] = name
                if content is not None:
                    p["content"] = content
                if description is not None:
                    p["description"] = description
                self._save()
                return True
        return False

    def delete(self, prompt_id: str) -> bool:
        self.prompts = [p for p in self.prompts if p["id"] != prompt_id]
        self._save()
        return True

    def reset_defaults(self):
        self.prompts = list(DEFAULT_PROMPTS)
        self._save()

    def format_prompt(self, prompt_id: str, article_text: str) -> str:
        prompt = self.get_by_id(prompt_id)
        if not prompt:
            prompt = self.prompts[0]
        return prompt["content"].replace("{article_text}", article_text)


import sys  # noqa: E402
