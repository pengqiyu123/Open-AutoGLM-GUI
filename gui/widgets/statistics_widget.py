"""
Statistics Widget - 统计仪表板

显示任务执行统计、黄金路径使用情况和错误模式分析。
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QTableWidget, QTableWidgetItem, QGroupBox,
    QHeaderView, QPushButton, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from typing import Optional


class StatisticsWidget(QWidget):
    """统计仪表板 Widget"""
    
    # 信号
    refresh_requested = pyqtSignal()
    
    def __init__(self, task_logger=None, parent=None):
        """
        初始化统计 Widget
        
        Args:
            task_logger: TaskLogger 实例
            parent: 父 Widget
        """
        super().__init__(parent)
        self.task_logger = task_logger
        self._init_ui()
        
        # 初始加载数据
        if self.task_logger:
            self.refresh_statistics()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        
        # 标题和刷新按钮
        header_layout = QHBoxLayout()
        title_label = QLabel("📊 统计仪表板")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh_statistics)
        header_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(header_layout)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        
        # 上半部分：总体统计
        overview_group = self._create_overview_section()
        splitter.addWidget(overview_group)
        
        # 中间部分：黄金路径统计
        golden_path_group = self._create_golden_path_section()
        splitter.addWidget(golden_path_group)
        
        # 下半部分：错误模式统计
        error_pattern_group = self._create_error_pattern_section()
        splitter.addWidget(error_pattern_group)
        
        # 设置分割器比例
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)
        
        layout.addWidget(splitter)
    
    def _create_overview_section(self) -> QGroupBox:
        """创建总体统计区域"""
        group = QGroupBox("总体统计")
        layout = QHBoxLayout(group)
        
        # 创建统计卡片
        self.total_tasks_label = self._create_stat_card("总任务数", "0", "📋")
        self.success_rate_label = self._create_stat_card("成功率", "0%", "✅")
        self.avg_steps_label = self._create_stat_card("平均步骤数", "0", "👣")
        self.golden_paths_label = self._create_stat_card("黄金路径数", "0", "⭐")
        
        layout.addWidget(self.total_tasks_label)
        layout.addWidget(self.success_rate_label)
        layout.addWidget(self.avg_steps_label)
        layout.addWidget(self.golden_paths_label)
        
        return group
    
    def _create_stat_card(self, title: str, value: str, icon: str) -> QWidget:
        """创建统计卡片"""
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(card)
        
        # 图标和标题
        header_layout = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #666; font-size: 12px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # 数值
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #333;")
        value_label.setObjectName("value_label")
        layout.addWidget(value_label)
        
        return card
    
    def _create_golden_path_section(self) -> QGroupBox:
        """创建黄金路径统计区域"""
        group = QGroupBox("黄金路径管理")
        layout = QVBoxLayout(group)
        
        # 按钮栏
        btn_layout = QHBoxLayout()
        
        self.view_path_btn = QPushButton("👁️ 查看详情")
        self.view_path_btn.clicked.connect(self._view_golden_path_details)
        btn_layout.addWidget(self.view_path_btn)
        
        self.test_prompt_btn = QPushButton("🧪 测试提示词")
        self.test_prompt_btn.setStyleSheet("background-color: #2196F3; color: white;")
        self.test_prompt_btn.clicked.connect(self._test_golden_path_prompt)
        btn_layout.addWidget(self.test_prompt_btn)
        
        self.delete_path_btn = QPushButton("🗑️ 删除选中")
        self.delete_path_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.delete_path_btn.clicked.connect(self._delete_selected_golden_path)
        btn_layout.addWidget(self.delete_path_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 创建表格
        self.golden_path_table = QTableWidget()
        self.golden_path_table.setColumnCount(6)
        self.golden_path_table.setHorizontalHeaderLabels([
            "ID", "任务模式", "难度", "成功率", "使用次数", "最后更新"
        ])
        
        # 设置表格属性
        self.golden_path_table.horizontalHeader().setStretchLastSection(True)
        self.golden_path_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.golden_path_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.golden_path_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.golden_path_table.setAlternatingRowColors(True)
        self.golden_path_table.setColumnWidth(0, 50)  # ID 列窄一点
        
        # 右键菜单
        self.golden_path_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.golden_path_table.customContextMenuRequested.connect(self._show_golden_path_context_menu)
        
        layout.addWidget(self.golden_path_table)
        
        return group
    
    def _show_golden_path_context_menu(self, position):
        """显示黄金路径右键菜单"""
        from PyQt5.QtWidgets import QMenu, QAction
        
        menu = QMenu()
        
        view_action = QAction("👁️ 查看详情", self)
        view_action.triggered.connect(self._view_golden_path_details)
        menu.addAction(view_action)
        
        test_action = QAction("🧪 测试提示词", self)
        test_action.triggered.connect(self._test_golden_path_prompt)
        menu.addAction(test_action)
        
        menu.addSeparator()
        
        delete_action = QAction("🗑️ 删除", self)
        delete_action.triggered.connect(self._delete_selected_golden_path)
        menu.addAction(delete_action)
        
        menu.exec_(self.golden_path_table.viewport().mapToGlobal(position))
    
    def _get_selected_golden_path_id(self) -> Optional[int]:
        """获取选中的黄金路径 ID"""
        selected_row = self.golden_path_table.currentRow()
        if selected_row < 0:
            return None
        id_item = self.golden_path_table.item(selected_row, 0)
        if id_item:
            return int(id_item.text())
        return None
    
    def _view_golden_path_details(self):
        """查看黄金路径详情"""
        from PyQt5.QtWidgets import QMessageBox, QDialog, QTextEdit, QDialogButtonBox
        import json
        
        path_id = self._get_selected_golden_path_id()
        if path_id is None:
            QMessageBox.information(self, "提示", "请先选择一条黄金路径")
            return
        
        # 从数据库获取详情
        try:
            from pathlib import Path
            from gui.utils.golden_path_repository import GoldenPathRepository
            
            db_path = str(Path(self.task_logger.log_dir) / "tasks.db")
            repo = GoldenPathRepository(db_path)
            path_data = repo.find_by_id(path_id)
            
            if not path_data:
                QMessageBox.warning(self, "错误", "未找到该黄金路径")
                return
            
            # 创建详情对话框
            dialog = QDialog(self)
            dialog.setWindowTitle(f"黄金路径详情 - ID {path_id}")
            dialog.setMinimumSize(600, 500)
            
            layout = QVBoxLayout(dialog)
            
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            
            # 格式化显示
            details = []
            details.append(f"ID: {path_id}")
            details.append(f"任务模式: {path_data.get('task_pattern', '')}")
            details.append(f"难度: {path_data.get('difficulty', '')}")
            details.append(f"成功率: {path_data.get('success_rate', 0):.1%}")
            details.append(f"使用次数: {path_data.get('usage_count', 0)}")
            details.append(f"可重放: {'是' if path_data.get('can_replay') else '否'}")
            details.append("")
            details.append("=" * 50)
            details.append("自然语言 SOP:")
            details.append(path_data.get('natural_sop', '无'))
            details.append("")
            details.append("=" * 50)
            details.append("动作 SOP:")
            action_sop = path_data.get('action_sop', [])
            if isinstance(action_sop, str):
                try:
                    action_sop = json.loads(action_sop)
                except:
                    pass
            details.append(json.dumps(action_sop, ensure_ascii=False, indent=2))
            details.append("")
            details.append("=" * 50)
            details.append("常见错误:")
            common_errors = path_data.get('common_errors', [])
            if isinstance(common_errors, str):
                try:
                    common_errors = json.loads(common_errors)
                except:
                    pass
            for i, err in enumerate(common_errors, 1):
                details.append(f"{i}. 错误: {err.get('error', '')[:100]}...")
                details.append(f"   纠正: {err.get('correction', '')}")
            
            text_edit.setPlainText("\n".join(details))
            layout.addWidget(text_edit)
            
            btn_box = QDialogButtonBox(QDialogButtonBox.Close)
            btn_box.rejected.connect(dialog.reject)
            layout.addWidget(btn_box)
            
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"获取详情失败: {e}")
    
    def _test_golden_path_prompt(self):
        """测试黄金路径生成的提示词"""
        from PyQt5.QtWidgets import QMessageBox, QDialog, QTextEdit, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel
        import json
        
        path_id = self._get_selected_golden_path_id()
        if path_id is None:
            QMessageBox.information(self, "提示", "请先选择一条黄金路径")
            return
        
        try:
            from pathlib import Path
            from gui.utils.golden_path_repository import GoldenPathRepository
            
            db_path = str(Path(self.task_logger.log_dir) / "tasks.db")
            repo = GoldenPathRepository(db_path)
            path_data = repo.find_by_id(path_id)
            
            if not path_data:
                QMessageBox.warning(self, "错误", "未找到该黄金路径")
                return
            
            # 生成提示词
            prompt = self._generate_test_prompt(path_data)
            
            # 创建测试对话框
            dialog = QDialog(self)
            dialog.setWindowTitle(f"🧪 提示词测试 - {path_data.get('task_pattern', '')[:30]}")
            dialog.setMinimumSize(700, 600)
            
            layout = QVBoxLayout(dialog)
            
            # 说明
            info_label = QLabel("以下是将注入到模型的提示词内容，用于指导模型执行任务：")
            info_label.setStyleSheet("color: #666; margin-bottom: 10px;")
            layout.addWidget(info_label)
            
            # 提示词显示区域
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setPlainText(prompt)
            text_edit.setStyleSheet("""
                QTextEdit {
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 12px;
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    padding: 10px;
                    border-radius: 5px;
                }
            """)
            layout.addWidget(text_edit)
            
            # 统计信息
            stats_layout = QHBoxLayout()
            
            forbidden_count = len(path_data.get('forbidden', []))
            correct_count = len(path_data.get('correct_path', []))
            hints_count = len(path_data.get('hints', []))
            
            stats_label = QLabel(
                f"📊 统计: 禁止操作 {forbidden_count} 条 | "
                f"正确步骤 {correct_count} 步 | "
                f"关键提示 {hints_count} 条 | "
                f"总字符数 {len(prompt)}"
            )
            stats_label.setStyleSheet("color: #888; font-size: 11px;")
            stats_layout.addWidget(stats_label)
            stats_layout.addStretch()
            
            layout.addLayout(stats_layout)
            
            # 按钮
            btn_layout = QHBoxLayout()
            
            copy_btn = QPushButton("📋 复制到剪贴板")
            copy_btn.clicked.connect(lambda: self._copy_to_clipboard(prompt))
            btn_layout.addWidget(copy_btn)
            
            btn_layout.addStretch()
            
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.reject)
            btn_layout.addWidget(close_btn)
            
            layout.addLayout(btn_layout)
            
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"生成提示词失败: {e}")
    
    def _generate_test_prompt(self, path_data: dict) -> str:
        """
        生成测试提示词 - 与 agent_runner._build_enhanced_prompt() 保持一致
        
        关键：把约束直接融入任务描述中，模仿用户直接输入的格式。
        复杂格式（警告、标题等）会被模型忽略，简单的逗号分隔格式更有效。
        """
        task = path_data.get('task_pattern', '未知任务')
        
        # 获取约束信息
        forbidden = path_data.get('forbidden', [])
        hints = path_data.get('hints', [])
        common_errors = path_data.get('common_errors', [])
        
        # 如果没有任何约束，直接返回原任务
        if not forbidden and not hints and not common_errors:
            return f"任务: {task}\n\n（无约束条件）"
        
        # 构建约束列表 - 简单的编号格式
        constraints = []
        constraint_num = 1
        
        # 添加禁止操作
        if forbidden:
            for f in forbidden:
                constraints.append(f"{constraint_num}.{f}")
                constraint_num += 1
        elif common_errors:
            for error in common_errors[:3]:
                correction = error.get('correction', '')
                if correction:
                    constraints.append(f"{constraint_num}.{correction}")
                    constraint_num += 1
        
        # 添加提示信息
        if hints:
            for h in hints:
                # 移除"位置提示:"等前缀
                h_clean = h.replace("位置提示: ", "").replace("判断条件: ", "")
                constraints.append(f"{constraint_num}.{h_clean}")
                constraint_num += 1
        
        # 生成最终提示词 - 模仿用户输入格式
        if constraints:
            enhanced_task = f"{task},{','.join(constraints)}"
        else:
            enhanced_task = task
        
        # 显示格式化的预览
        preview_parts = []
        preview_parts.append("【实际注入的提示词】")
        preview_parts.append(enhanced_task)
        preview_parts.append("")
        preview_parts.append("=" * 50)
        preview_parts.append("")
        preview_parts.append("【约束条件分解】")
        preview_parts.append(f"原始任务: {task}")
        preview_parts.append("")
        if constraints:
            preview_parts.append("约束列表:")
            for c in constraints:
                preview_parts.append(f"  {c}")
        else:
            preview_parts.append("（无约束条件）")
        
        return '\n'.join(preview_parts)
    
    def _copy_to_clipboard(self, text: str):
        """复制文本到剪贴板"""
        from PyQt5.QtWidgets import QApplication, QMessageBox
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(self, "成功", "已复制到剪贴板")

    def _delete_selected_golden_path(self):
        """删除选中的黄金路径"""
        from PyQt5.QtWidgets import QMessageBox
        
        path_id = self._get_selected_golden_path_id()
        if path_id is None:
            QMessageBox.information(self, "提示", "请先选择一条黄金路径")
            return
        
        # 获取任务模式用于确认
        selected_row = self.golden_path_table.currentRow()
        pattern_item = self.golden_path_table.item(selected_row, 1)
        pattern = pattern_item.text() if pattern_item else "未知"
        
        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除以下黄金路径吗？\n\n"
            f"ID: {path_id}\n"
            f"任务模式: {pattern}\n\n"
            "此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # 执行删除
        try:
            from pathlib import Path
            from gui.utils.golden_path_repository import GoldenPathRepository
            
            db_path = str(Path(self.task_logger.log_dir) / "tasks.db")
            repo = GoldenPathRepository(db_path)
            
            if repo.delete(path_id):
                QMessageBox.information(self, "成功", f"已删除黄金路径 ID {path_id}")
                self.refresh_statistics()
            else:
                QMessageBox.warning(self, "失败", "删除失败")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除失败: {e}")
    
    def _create_error_pattern_section(self) -> QGroupBox:
        """创建错误模式统计区域"""
        group = QGroupBox("常见错误模式")
        layout = QVBoxLayout(group)
        
        # 创建表格
        self.error_pattern_table = QTableWidget()
        self.error_pattern_table.setColumnCount(4)
        self.error_pattern_table.setHorizontalHeaderLabels([
            "任务模式", "错误描述", "纠正方法", "出现次数"
        ])
        
        # 设置表格属性
        self.error_pattern_table.horizontalHeader().setStretchLastSection(True)
        self.error_pattern_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.error_pattern_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.error_pattern_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.error_pattern_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.error_pattern_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.error_pattern_table)
        
        return group
    
    def refresh_statistics(self):
        """刷新统计数据"""
        if not self.task_logger:
            return
        
        try:
            # 更新总体统计
            self._update_overview_stats()
            
            # 更新黄金路径表格
            self._update_golden_path_table()
            
            # 更新错误模式表格
            self._update_error_pattern_table()
            
        except Exception as e:
            print(f"刷新统计数据失败: {e}")
    
    def _update_overview_stats(self):
        """更新总体统计"""
        try:
            conn = self.task_logger._get_conn()
            cur = conn.cursor()
            
            # 总任务数
            cur.execute("SELECT COUNT(*) FROM tasks")
            total_tasks = cur.fetchone()[0]
            
            # 成功率
            cur.execute("""
                SELECT COUNT(*) FROM tasks 
                WHERE final_status = 'SUCCESS'
            """)
            success_count = cur.fetchone()[0]
            success_rate = (success_count / total_tasks * 100) if total_tasks > 0 else 0
            
            # 平均步骤数
            cur.execute("SELECT AVG(total_steps) FROM tasks WHERE total_steps > 0")
            avg_steps = cur.fetchone()[0] or 0
            
            # 黄金路径数
            cur.execute("SELECT COUNT(*) FROM golden_paths")
            golden_paths_count = cur.fetchone()[0]
            
            conn.close()
            
            # 更新 UI
            self._update_stat_card(self.total_tasks_label, str(total_tasks))
            self._update_stat_card(self.success_rate_label, f"{success_rate:.1f}%")
            self._update_stat_card(self.avg_steps_label, f"{avg_steps:.1f}")
            self._update_stat_card(self.golden_paths_label, str(golden_paths_count))
            
        except Exception as e:
            print(f"更新总体统计失败: {e}")
    
    def _update_stat_card(self, card: QWidget, value: str):
        """更新统计卡片的值"""
        value_label = card.findChild(QLabel, "value_label")
        if value_label:
            value_label.setText(value)
    
    def _update_golden_path_table(self):
        """更新黄金路径表格"""
        try:
            conn = self.task_logger._get_conn()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, task_pattern, difficulty, success_rate, 
                       usage_count, updated_at
                FROM golden_paths
                ORDER BY usage_count DESC, success_rate DESC
                LIMIT 50
            """)
            
            rows = cur.fetchall()
            conn.close()
            
            # 清空表格
            self.golden_path_table.setRowCount(0)
            
            # 填充数据
            for row_data in rows:
                row_position = self.golden_path_table.rowCount()
                self.golden_path_table.insertRow(row_position)
                
                # ID
                self.golden_path_table.setItem(
                    row_position, 0, 
                    QTableWidgetItem(str(row_data[0]))
                )
                
                # 任务模式
                self.golden_path_table.setItem(
                    row_position, 1, 
                    QTableWidgetItem(row_data[1] or "")
                )
                
                # 难度
                difficulty = row_data[2] or "medium"
                difficulty_item = QTableWidgetItem(
                    {"simple": "简单", "medium": "中等", "complex": "复杂"}.get(difficulty, difficulty)
                )
                if difficulty == "simple":
                    difficulty_item.setForeground(QColor("#4CAF50"))
                elif difficulty == "complex":
                    difficulty_item.setForeground(QColor("#F44336"))
                self.golden_path_table.setItem(row_position, 2, difficulty_item)
                
                # 成功率
                success_rate = row_data[3] or 0.0
                success_item = QTableWidgetItem(f"{success_rate * 100:.1f}%")
                if success_rate >= 0.8:
                    success_item.setForeground(QColor("#4CAF50"))
                elif success_rate < 0.5:
                    success_item.setForeground(QColor("#F44336"))
                self.golden_path_table.setItem(row_position, 3, success_item)
                
                # 使用次数
                usage_count = row_data[4] or 0
                self.golden_path_table.setItem(
                    row_position, 4,
                    QTableWidgetItem(str(usage_count))
                )
                
                # 最后更新
                updated_at = row_data[5] or ""
                if updated_at:
                    # 只显示日期部分
                    updated_at = updated_at.split()[0] if ' ' in updated_at else updated_at
                self.golden_path_table.setItem(
                    row_position, 5,
                    QTableWidgetItem(updated_at)
                )
            
        except Exception as e:
            print(f"更新黄金路径表格失败: {e}")
    
    def _update_error_pattern_table(self):
        """更新错误模式表格"""
        try:
            conn = self.task_logger._get_conn()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT task_pattern, error_description, correction, frequency
                FROM error_patterns
                ORDER BY frequency DESC
                LIMIT 50
            """)
            
            rows = cur.fetchall()
            conn.close()
            
            # 清空表格
            self.error_pattern_table.setRowCount(0)
            
            # 填充数据
            for row_data in rows:
                row_position = self.error_pattern_table.rowCount()
                self.error_pattern_table.insertRow(row_position)
                
                # 任务模式
                self.error_pattern_table.setItem(
                    row_position, 0,
                    QTableWidgetItem(row_data[0] or "")
                )
                
                # 错误描述（截取前50字符）
                error_desc = row_data[1] or ""
                if len(error_desc) > 50:
                    error_desc = error_desc[:50] + "..."
                self.error_pattern_table.setItem(
                    row_position, 1,
                    QTableWidgetItem(error_desc)
                )
                
                # 纠正方法
                correction = row_data[2] or ""
                self.error_pattern_table.setItem(
                    row_position, 2,
                    QTableWidgetItem(correction)
                )
                
                # 出现次数
                frequency = row_data[3] or 0
                frequency_item = QTableWidgetItem(str(frequency))
                if frequency >= 5:
                    frequency_item.setForeground(QColor("#F44336"))
                self.error_pattern_table.setItem(
                    row_position, 3,
                    frequency_item
                )
            
        except Exception as e:
            print(f"更新错误模式表格失败: {e}")
