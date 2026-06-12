"""AI News Agent - Entry point.

An AI-powered news aggregation client with:
1. News aggregation with AI summarization
2. Prompt template management
3. AI model configuration (DeepSeek / SiliconFlow / Ollama)
"""

import sys
import os

# Ensure the project root is on sys.path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt


def init_qt_plugins():
    """Ensure Qt platform plugins can be found."""
    base = ""
    if hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    elif hasattr(sys, 'frozen'):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    candidates = [
        os.path.join(base, '_internal', 'PyQt5', 'Qt5', 'plugins'),
        os.path.join(base, 'PyQt5', 'Qt5', 'plugins'),
        os.path.join(base, '_internal', 'plugins'),
        os.path.join(base, 'plugins'),
    ]
    for path in candidates:
        if os.path.exists(path):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = path
            break


def main():
    init_qt_plugins()

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

    app = QApplication(sys.argv)
    app.setStyleSheet("""
        QToolTip {
            background: #333; color: white; border: none;
            padding: 4px; font-size: 12px;
        }
    """)

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
