"""Log viewer widget with color coding and auto-scroll."""

from datetime import datetime
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextOption
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LogViewer(QWidget):
    """Custom log viewer widget with color coding and search functionality."""

    # Color definitions for different log levels
    COLORS = {
        "thinking": QColor(100, 150, 255),  # Light blue
        "action": QColor(255, 200, 100),  # Orange
        "success": QColor(100, 255, 100),  # Green
        "error": QColor(255, 100, 100),  # Red
        "info": QColor(200, 200, 200),  # Light gray
        "system": QColor(150, 150, 255),  # Light purple
        "default": QColor(255, 255, 255),  # White
    }

    def __init__(self, parent=None):
        """Initialize the log viewer."""
        super().__init__(parent)

        self._setup_ui()
        self._auto_scroll = True
        self._current_thinking_active = False  # Track if we're in a thinking stream

    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索日志...")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_clear_btn = QPushButton("清除")
        search_clear_btn.clicked.connect(self._clear_search)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_clear_btn)
        layout.addLayout(search_layout)

        # Log text area
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        font = QFont("Consolas", 9)
        self.text_edit.setFont(font)
        # Wrap text within the log area to avoid horizontal overflow
        self.text_edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.text_edit.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.text_edit)

        # Control buttons
        control_layout = QHBoxLayout()
        self.clear_btn = QPushButton("清空日志")
        self.clear_btn.clicked.connect(self.clear)
        self.auto_scroll_btn = QPushButton("自动滚动: 开")
        self.auto_scroll_btn.clicked.connect(self._toggle_auto_scroll)
        control_layout.addWidget(self.clear_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.auto_scroll_btn)
        layout.addLayout(control_layout)

    def _toggle_auto_scroll(self):
        """Toggle auto-scroll mode."""
        self._auto_scroll = not self._auto_scroll
        self.auto_scroll_btn.setText(
            f"自动滚动: {'开' if self._auto_scroll else '关'}"
        )

    def _on_search_changed(self, text: str):
        """Handle search text changes."""
        if not text:
            # Clear highlighting
            cursor = self.text_edit.textCursor()
            cursor.select(QTextCursor.Document)
            format = QTextCharFormat()
            format.setBackground(QColor(255, 255, 255))
            cursor.setCharFormat(format)
            return

        # Highlight search matches
        document = self.text_edit.document()
        cursor = QTextCursor(document)
        format = QTextCharFormat()
        format.setBackground(QColor(255, 255, 0))  # Yellow highlight

        cursor.beginEditBlock()
        while not cursor.isNull() and not cursor.atEnd():
            cursor = document.find(text, cursor)
            if not cursor.isNull():
                cursor.mergeCharFormat(format)
        cursor.endEditBlock()

    def _clear_search(self):
        """Clear search input."""
        self.search_input.clear()

    def _append_text(self, text: str, log_type: str = "default"):
        """Append text with specified log type color."""
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)

        # Set color format
        format = QTextCharFormat()
        color = self.COLORS.get(log_type, self.COLORS["default"])
        format.setForeground(color)
        cursor.setCharFormat(format)

        # Append text
        cursor.insertText(text)

        # Auto-scroll if enabled
        if self._auto_scroll:
            self.text_edit.ensureCursorVisible()
        
        # Force immediate UI update for real-time display
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

    def log_thinking(self, message: str, is_incremental: bool = False):
        """
        Log thinking process with support for incremental updates.
        
        Args:
            message: Thinking content to log
            is_incremental: If True, append to current thinking without timestamp/prefix.
                          If False, start a new thinking entry with timestamp.
        """
        if is_incremental and self._current_thinking_active:
            # Append to current thinking without timestamp/prefix
            self._append_text(message, "thinking")
        else:
            # Start new thinking entry
            if self._current_thinking_active:
                # End previous thinking if still active
                self._append_text("\n", "thinking")
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            self._append_text(f"[{timestamp}] 💭 ", "thinking")
            self._append_text(message, "thinking")
            self._current_thinking_active = True

    def log_action(self, message: str):
        """Log action execution."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._append_text(f"[{timestamp}] 🎯 {message}\n", "action")

    def log_success(self, message: str):
        """Log success message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._append_text(f"[{timestamp}] ✅ {message}\n", "success")

    def log_error(self, message: str):
        """Log error message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._append_text(f"[{timestamp}] ❌ {message}\n", "error")

    def log_info(self, message: str):
        """Log info message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._append_text(f"[{timestamp}] ℹ️ {message}\n", "info")

    def log_system(self, message: str):
        """Log system message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._append_text(f"[{timestamp}] 🔧 {message}\n", "system")

    def log_raw(self, message: str, log_type: str = "default"):
        """Log raw message with custom type."""
        self._append_text(f"{message}\n", log_type)

    def clear(self):
        """Clear all logs."""
        self.text_edit.clear()
        self._current_thinking_active = False

    def get_text(self) -> str:
        """Get all log text."""
        return self.text_edit.toPlainText()

