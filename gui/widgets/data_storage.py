"""Data storage & history overview widgets for Open-AutoGLM GUI."""

import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional, List, Tuple

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QFont
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QTextEdit,
)

from phone_agent.config.apps import APP_PACKAGES


def _get_logs_dir() -> Path:
    """Get the logs directory (always in Open-AutoGLM-main/)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe (dist/GUI.exe)
        # Go up from dist/ to Open-AutoGLM-main/
        return Path(sys.executable).parent.parent / "logs"
    else:
        # Running as script - gui/widgets/data_storage.py
        # Go up to Open-AutoGLM-main/
        return Path(__file__).parent.parent.parent / "logs"


LOG_DIR = _get_logs_dir()
DB_PATH = LOG_DIR / "tasks.db"


class DataStorageWidget(QWidget):
    """Summary view for local task logs and entry to detailed history."""

    def __init__(self, task_logger=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.task_logger = task_logger
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create tab widget
        tab_widget = QTabWidget()
        
        # Tab 1: Data overview (existing functionality)
        overview_tab = self._create_overview_tab()
        tab_widget.addTab(overview_tab, "数据概览")
        
        # Tab 2: Task review (new functionality)
        if self.task_logger:
            from gui.widgets.task_review import TaskReviewWidget
            review_tab = TaskReviewWidget(self.task_logger)
            tab_widget.addTab(review_tab, "任务回顾")
        
        # Tab 3: Statistics dashboard (new functionality)
        if self.task_logger:
            from gui.widgets.statistics_widget import StatisticsWidget
            statistics_tab = StatisticsWidget(self.task_logger)
            tab_widget.addTab(statistics_tab, "统计分析")
        
        layout.addWidget(tab_widget)
    
    def _create_overview_tab(self) -> QWidget:
        """Create the data overview tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Summary group
        summary_group = QGroupBox("数据概览")
        summary_layout = QVBoxLayout()

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        summary_layout.addWidget(self.status_label)

        stats_font = QFont()
        stats_font.setPointSize(10)

        self.total_tasks_label = QLabel("总任务数: -")
        self.total_tasks_label.setFont(stats_font)
        summary_layout.addWidget(self.total_tasks_label)

        self.success_rate_label = QLabel("成功率: -")
        self.success_rate_label.setFont(stats_font)
        summary_layout.addWidget(self.success_rate_label)

        self.last_task_time_label = QLabel("最近任务时间: -")
        self.last_task_time_label.setFont(stats_font)
        summary_layout.addWidget(self.last_task_time_label)

        # Buttons
        btn_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("刷新统计")
        self.refresh_btn.clicked.connect(self.refresh_stats)
        btn_layout.addWidget(self.refresh_btn)

        self.open_folder_btn = QPushButton("打开日志文件夹")
        self.open_folder_btn.clicked.connect(self.open_log_folder)
        btn_layout.addWidget(self.open_folder_btn)

        self.detail_btn = QPushButton("查看详细")
        self.detail_btn.clicked.connect(self.show_history_dialog)
        btn_layout.addWidget(self.detail_btn)

        btn_layout.addStretch()
        summary_layout.addLayout(btn_layout)

        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)

        # Hint area
        hint_group = QGroupBox("说明")
        hint_layout = QVBoxLayout()

        hint_text = QLabel(
            "电脑版 GUI 会将每次运行任务写入本地 SQLite 数据库，用于后续：\n"
            "• 分析最优路径、统计成功率与耗时\n"
            "• 生成日志驱动的训练数据，微调 AutoGLM-Phone-9B\n"
            "数据仅保存在本机，不会自动上传。"
        )
        hint_text.setWordWrap(True)
        hint_layout.addWidget(hint_text)

        hint_group.setLayout(hint_layout)
        layout.addWidget(hint_group)

        # App-based success summary
        app_group = QGroupBox("按软件归纳成功案例（仅成功任务）")
        app_layout = QVBoxLayout()

        # Grid container for app summary: only app name + success count
        self.app_grid_container = QWidget()
        self.app_grid_layout = QGridLayout(self.app_grid_container)
        self.app_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.app_grid_layout.setSpacing(6)
        app_layout.addWidget(self.app_grid_container)

        app_group.setLayout(app_layout)
        layout.addWidget(app_group)

        layout.addStretch()

        # Initial refresh
        self.refresh_stats()
        
        return tab

    # --- Data access helpers ---

    def _connect_db(self) -> Optional[sqlite3.Connection]:
        """Try to connect to tasks.db; return None if not exists or error."""
        try:
            if not DB_PATH.exists():
                return None
            # Use thread-safe connection settings with timeout
            conn = sqlite3.connect(
                str(DB_PATH),
                check_same_thread=False,
                timeout=5.0
            )
            conn.execute("PRAGMA journal_mode=WAL")
            return conn
        except Exception:
            return None

    def _load_summary(self) -> Optional[Tuple[int, int, Optional[str]]]:
        """
        Load (total_tasks, success_tasks, last_timestamp) from tasks table.
        Returns None if db or table not ready.
        """
        conn = self._connect_db()
        if conn is None:
            return None

        try:
            cur = conn.cursor()
            # Count total tasks
            cur.execute("SELECT COUNT(*) FROM tasks")
            row = cur.fetchone()
            if not row:
                return (0, 0, None)
            total = int(row[0])

            # Count success tasks
            cur.execute(
                "SELECT COUNT(*) FROM tasks WHERE final_status = 'SUCCESS'"
            )
            row = cur.fetchone()
            success = int(row[0]) if row else 0

            # Latest timestamp
            cur.execute(
                "SELECT MAX(timestamp) FROM tasks"
            )
            row = cur.fetchone()
            last_ts = row[0] if row and row[0] is not None else None

            return (total, success, last_ts)
        except sqlite3.Error:
            return None
        finally:
            conn.close()

    # --- UI actions ---

    def refresh_stats(self) -> None:
        """Refresh summary statistics from database."""
        summary = self._load_summary()
        if summary is None:
            # Database not ready
            self.status_label.setText(
                "当前还没有可用的任务日志。\n"
                "请先在中间面板配置好模型和设备，执行一次任务后再查看。"
            )
            self.total_tasks_label.setText("总任务数: 0")
            self.success_rate_label.setText("成功率: -")
            self.last_task_time_label.setText("最近任务时间: -")
            self.detail_btn.setEnabled(False)
            return

        total, success, last_ts = summary
        self.total_tasks_label.setText(f"总任务数: {total}")
        if total > 0:
            rate = success * 100.0 / float(total)
            self.success_rate_label.setText(f"成功率: {rate:.1f}%")
            self.status_label.setText("本地已记录任务运行日志，可用于后续分析与训练。")
            self.detail_btn.setEnabled(True)
        else:
            self.success_rate_label.setText("成功率: -")
            self.status_label.setText("尚无任务记录，请先执行一次任务。")
            self.detail_btn.setEnabled(False)

        self.last_task_time_label.setText(
            f"最近任务时间: {last_ts if last_ts else '-'}"
        )

        # Refresh per-app success summary
        self._refresh_app_summary()

    def _refresh_app_summary(self) -> None:
        """Refresh success-case summary grouped by app/software."""
        conn = self._connect_db()
        if conn is None:
            self._clear_app_grid()
            return

        try:
            cur = conn.cursor()
            # Only consider successful tasks
            cur.execute(
                """
                SELECT task_description, timestamp
                FROM tasks
                WHERE final_status = 'SUCCESS'
                """
            )
            rows = cur.fetchall()
        except sqlite3.Error:
            conn.close()
            self.app_table.setRowCount(0)
            self.view_app_cases_btn.setEnabled(False)
            return

        conn.close()

        # Build mapping: app_name -> (count, last_timestamp)
        app_summary: dict[str, Tuple[int, Optional[str]]] = {}
        if rows:
            app_names = list(APP_PACKAGES.keys())
            for desc, ts in rows:
                desc_text = desc or ""
                matched_apps = set()
                for app_name in app_names:
                    if app_name and app_name in desc_text:
                        matched_apps.add(app_name)
                for app_name in matched_apps:
                    count, last_ts = app_summary.get(app_name, (0, None))
                    count += 1
                    # Use lexicographical compare for timestamps in same format
                    if not last_ts or (ts and ts > last_ts):
                        last_ts = ts
                    app_summary[app_name] = (count, last_ts)

        # Populate grid
        if not app_summary:
            self._clear_app_grid()
            return

        sorted_items = sorted(
            app_summary.items(),
            key=lambda item: item[1][0],
            reverse=True,
        )

        self._clear_app_grid()

        # Simple grid: each cell is a button with "app name + success count"
        max_columns = 4
        row = 0
        col = 0
        for app_name, (count, _last_ts) in sorted_items:
            btn = QPushButton(f"{app_name}\n{count} 次成功")
            btn.setProperty("app_name", app_name)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumSize(90, 60)
            btn.clicked.connect(self._on_app_button_clicked)
            self.app_grid_layout.addWidget(btn, row, col)

            col += 1
            if col >= max_columns:
                col = 0
                row += 1

    def _clear_app_grid(self) -> None:
        """Remove all widgets from the app summary grid."""
        if not hasattr(self, "app_grid_layout"):
            return
        while self.app_grid_layout.count():
            item = self.app_grid_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _on_app_button_clicked(self) -> None:
        """Handle click on an app summary button."""
        sender = self.sender()
        if not isinstance(sender, QPushButton):
            return
        app_name = sender.property("app_name")
        if not isinstance(app_name, str) or not app_name:
            return
        self.show_app_success_cases(app_name)

    def open_log_folder(self) -> None:
        """Open the logs directory in system file explorer."""
        try:
            LOG_DIR.mkdir(exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_DIR.resolve())))
        except Exception as e:
            QMessageBox.critical(
                self,
                "打开失败",
                f"无法打开日志文件夹: {e}",
            )

    def show_history_dialog(self) -> None:
        """Open dialog showing recent task history."""
        conn = self._connect_db()
        if conn is None:
            QMessageBox.information(
                self,
                "无数据",
                "当前还没有任务记录。",
            )
            return

        try:
            cur = conn.cursor()
            # 最近 100 条任务，按时间倒序
            cur.execute(
                """
                SELECT session_id, timestamp, task_description,
                       final_status, total_steps, total_time,
                       device_id, model_name
                FROM tasks
                ORDER BY timestamp DESC
                LIMIT 100
                """
            )
            rows = cur.fetchall()
        except sqlite3.Error as e:
            conn.close()
            QMessageBox.critical(
                self,
                "读取失败",
                f"读取历史记录时出错: {e}",
            )
            return

        dialog = TaskHistoryDialog(rows, parent=self)
        dialog.exec_()
        conn.close()

    def show_app_success_cases(self, app_name: str) -> None:
        """Show successful cases for the given app/software."""
        app_name = (app_name or "").strip()
        if not app_name:
            QMessageBox.information(
                self,
                "无效软件",
                "选中的软件名称无效。",
            )
            return

        conn = self._connect_db()
        if conn is None:
            QMessageBox.information(
                self,
                "无数据",
                "当前还没有任务记录。",
            )
            return

        try:
            cur = conn.cursor()
            # Only successful tasks whose description mentions this app
            cur.execute(
                """
                SELECT session_id, timestamp, task_description,
                       final_status, total_steps, total_time,
                       device_id, model_name
                FROM tasks
                WHERE final_status = 'SUCCESS'
                  AND task_description LIKE ?
                ORDER BY timestamp DESC
                """,
                (f"%{app_name}%",),
            )
            rows = cur.fetchall()
        except sqlite3.Error as e:
            conn.close()
            QMessageBox.critical(
                self,
                "读取失败",
                f"读取软件成功案例时出错: {e}",
            )
            return

        conn.close()

        if not rows:
            QMessageBox.information(
                self,
                "暂无成功案例",
                f"当前还没有关于「{app_name}」的成功任务记录。",
            )
            return

        dialog = TaskHistoryDialog(rows, parent=self)
        dialog.setWindowTitle(f"成功案例 - {app_name}")
        dialog.exec_()


class TaskHistoryDialog(QDialog):
    """Dialog for viewing recent task history and simple step details."""

    def __init__(self, task_rows: List[tuple], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.task_rows = task_rows
        self.setWindowTitle("任务历史记录")
        self.setMinimumSize(900, 500)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            [
                "时间",
                "任务描述",
                "状态",
                "步骤数",
                "耗时(秒)",
                "设备ID",
                "模型",
                "会话ID",
            ]
        )
        self.table.setRowCount(len(self.task_rows))
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        for row_idx, row in enumerate(self.task_rows):
            session_id, timestamp, desc, status, steps, total_time, device_id, model_name = row
            values = [
                timestamp or "",
                desc or "",
                status or "",
                str(steps) if steps is not None else "",
                f"{total_time:.2f}" if total_time is not None else "",
                device_id or "",
                model_name or "",
                session_id or "",
            ]
            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(val)
                if col_idx in (2,):  # status
                    if status == "SUCCESS":
                        item.setForeground(Qt.green)
                    elif status == "FAILED":
                        item.setForeground(Qt.red)
                self.table.setItem(row_idx, col_idx, item)

        self.table.resizeColumnsToContents()
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()

        self.view_steps_btn = QPushButton("查看步骤详情")
        self.view_steps_btn.clicked.connect(self._show_steps_for_selected)
        btn_layout.addWidget(self.view_steps_btn)

        self.delete_btn = QPushButton("🗑️ 删除选中")
        self.delete_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.delete_btn.clicked.connect(self._delete_selected_task)
        btn_layout.addWidget(self.delete_btn)

        btn_layout.addStretch()

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        btn_layout.addWidget(button_box)

        layout.addLayout(btn_layout)

    def _get_selected_session_id(self) -> Optional[str]:
        selected = self.table.currentRow()
        if selected < 0:
            return None
        session_item = self.table.item(selected, 7)  # session_id column
        if not session_item:
            return None
        return session_item.text() or None

    def _delete_selected_task(self) -> None:
        """Delete the selected task and its steps from database."""
        session_id = self._get_selected_session_id()
        if not session_id:
            QMessageBox.information(
                self,
                "未选择任务",
                "请先选择一条任务记录。",
            )
            return

        # Get task description for confirmation
        selected_row = self.table.currentRow()
        desc_item = self.table.item(selected_row, 1)
        task_desc = desc_item.text() if desc_item else "未知任务"

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除以下任务及其所有步骤吗？\n\n"
            f"任务: {task_desc[:50]}...\n"
            f"会话ID: {session_id[:20]}...\n\n"
            f"此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Delete from database
        try:
            conn = sqlite3.connect(
                str(DB_PATH),
                check_same_thread=False,
                timeout=5.0
            )
            conn.execute("PRAGMA journal_mode=WAL")
            cur = conn.cursor()

            # Delete steps first (foreign key)
            cur.execute("DELETE FROM steps WHERE session_id = ?", (session_id,))
            steps_deleted = cur.rowcount

            # Delete task
            cur.execute("DELETE FROM tasks WHERE session_id = ?", (session_id,))
            task_deleted = cur.rowcount

            conn.commit()
            conn.close()

            # Remove from table
            self.table.removeRow(selected_row)

            QMessageBox.information(
                self,
                "删除成功",
                f"已删除任务及 {steps_deleted} 个步骤记录。"
            )

        except sqlite3.Error as e:
            QMessageBox.critical(
                self,
                "删除失败",
                f"删除任务时出错: {e}",
            )

    def _show_steps_for_selected(self) -> None:
        session_id = self._get_selected_session_id()
        if not session_id:
            QMessageBox.information(
                self,
                "未选择任务",
                "请先选择一条任务记录。",
            )
            return

        # Read steps from database
        try:
            conn = sqlite3.connect(
                str(DB_PATH),
                check_same_thread=False,
                timeout=5.0
            )
            conn.execute("PRAGMA journal_mode=WAL")
            cur = conn.cursor()
            cur.execute(
                """
                SELECT step_num, action, action_params, execution_time,
                       success, message, thinking
                FROM steps
                WHERE session_id = ?
                ORDER BY step_num ASC
                """,
                (session_id,),
            )
            rows = cur.fetchall()
            conn.close()
        except sqlite3.Error as e:
            QMessageBox.critical(
                self,
                "读取失败",
                f"读取步骤详情时出错: {e}",
            )
            return

        if not rows:
            QMessageBox.information(
                self,
                "无步骤记录",
                "该任务没有可用的步骤详情。",
            )
            return

        # Simple text dialog to show steps
        dlg = QDialog(self)
        dlg.setWindowTitle(f"步骤详情 - {session_id}")
        dlg.setMinimumSize(800, 500)

        vbox = QVBoxLayout(dlg)
        text = QTextEdit()
        text.setReadOnly(True)

        lines = []
        for step_num, action_json, params_json, exec_time, success, message, thinking in rows:
            status = "✅" if success else "❌"
            header = (
                f"步骤 {step_num} {status} 耗时: {exec_time:.2f} 秒"
                if exec_time is not None
                else f"步骤 {step_num} {status}"
            )
            lines.append("=" * 80)
            lines.append(header)
            lines.append("-" * 80)

            # Thinking content (most important for understanding model reasoning)
            if thinking:
                # Collapse excessive newlines/whitespace into single spaces for compact display
                normalized_thinking = re.sub(r"\s+", " ", thinking).strip()
                lines.append("💭 思考过程:")
                lines.append(normalized_thinking)
                lines.append("")

            # Message
            if message:
                lines.append(f"📝 消息: {message}")
                lines.append("")

            # Action details
            if action_json:
                try:
                    action_obj = json.loads(action_json)
                    action_type = action_obj.get("_metadata", "unknown")
                    action_name = action_obj.get("action", "N/A")
                    lines.append(f"🎯 动作类型: {action_type} - {action_name}")
                    if params_json:
                        lines.append(f"📋 参数: {params_json}")
                    else:
                        lines.append(f"📋 完整动作: {action_json}")
                except Exception:
                    lines.append(f"🎯 动作: {action_json}")
                lines.append("")

            lines.append("")  # blank line between steps

        text.setPlainText("\n".join(lines))
        vbox.addWidget(text)

        close_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_box.rejected.connect(dlg.reject)
        vbox.addWidget(close_box)

        dlg.exec_()


