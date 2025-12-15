"""Main window for Open-AutoGLM GUI application."""

import json
from typing import Optional

from PyQt5.QtCore import QObject, QSettings, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.utils.agent_runner import AgentRunner
from gui.utils.system_checker import check_model_api, run_all_checks, CheckResult
from gui.widgets.log_viewer import LogViewer
from phone_agent.adb import ADBConnection, list_devices


class ModelAPICheckWorker(QThread):
    """后台线程用于执行模型 API 检查"""
    finished = pyqtSignal(bool, object)  # success, CheckResult

    def __init__(self, base_url: str, model_name: str, api_key: str):
        super().__init__()
        self.base_url = base_url
        self.model_name = model_name
        self.api_key = api_key

    def run(self):
        """执行 API 检查"""
        try:
            result = check_model_api(self.base_url, self.model_name, self.api_key)
            self.finished.emit(result.success, result)
        except Exception as e:
            # 如果检查函数本身抛出异常，创建一个错误结果
            error_result = CheckResult(
                success=False,
                message=f"检查异常: {str(e)}",
                details=str(e),
            )
            self.finished.emit(False, error_result)


class MainWindow(QWidget):
    """Main window for the Open-AutoGLM GUI application."""

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        self.settings = QSettings("Open-AutoGLM", "GUI")
        self.adb_connection = ADBConnection()
        self.agent_runner: Optional[AgentRunner] = None
        self.agent_thread: Optional[QThread] = None
        self.selected_device_id: Optional[str] = None
        # Track checking status for each check type
        self.check_status: dict[str, bool] = {}  # True if checking, False otherwise
        self.check_timers: dict[str, QTimer] = {}  # Store timers for quick checks
        self.check_threads: dict[str, object] = {}  # Store thread references for slow checks
        # Track thinking stream state for incremental updates
        self._thinking_stream_active = False

        self._setup_ui()
        self._load_settings()
        self._setup_timers()
        self._connect_signals()
        self._init_check_status()

    def _setup_ui(self):
        """Set up the UI layout."""
        self.setWindowTitle("Open-AutoGLM GUI")
        self.setMinimumSize(1200, 800)

        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Configuration
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # Middle panel - Task execution
        middle_panel = self._create_middle_panel()
        splitter.addWidget(middle_panel)

        # Right panel - Log viewer
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        # Set splitter sizes (30%, 30%, 40%)
        splitter.setSizes([300, 300, 400])

        main_layout.addWidget(splitter)

    def _create_left_panel(self) -> QWidget:
        """Create the left configuration panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # Model configuration group
        model_group = QGroupBox("模型配置")
        model_layout = QVBoxLayout()

        # Preset selection
        preset_label = QLabel("预设配置:")
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["自定义", "智谱-Phone"])
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        model_layout.addWidget(preset_label)
        model_layout.addWidget(self.preset_combo)

        # Base URL
        base_url_label = QLabel("Base URL:")
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("https://api-inference.modelscope.cn/v1")
        model_layout.addWidget(base_url_label)
        model_layout.addWidget(self.base_url_input)

        # Model name
        model_label = QLabel("Model 名称:")
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("ZhipuAI/AutoGLM-Phone-9B")
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_input)

        # API Key
        api_key_label = QLabel("API Key:")
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("输入你的 API Key")
        model_layout.addWidget(api_key_label)
        model_layout.addWidget(self.api_key_input)
        
        # Store original placeholder for restoration
        self.api_key_placeholder_default = "输入你的 API Key"

        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # Device configuration group
        device_group = QGroupBox("设备配置")
        device_layout = QVBoxLayout()

        # Device list
        device_list_label = QLabel("已连接设备:")
        self.device_list = QListWidget()
        self.device_list.setMaximumHeight(150)
        self.device_list.itemSelectionChanged.connect(self._on_device_selected)
        device_layout.addWidget(device_list_label)
        device_layout.addWidget(self.device_list)

        # Refresh button
        refresh_btn = QPushButton("刷新设备列表")
        refresh_btn.clicked.connect(self._refresh_devices)
        device_layout.addWidget(refresh_btn)

        # Remote connection (Wireless debugging)
        remote_label_layout = QHBoxLayout()
        remote_label = QLabel("无线调试 (IP:Port):")
        open_path_btn = QPushButton("打开路径")
        open_path_btn.setToolTip("查看手机中开启无线调试的路径说明")
        open_path_btn.clicked.connect(self._show_wireless_debug_path)
        remote_label_layout.addWidget(remote_label)
        remote_label_layout.addStretch()
        remote_label_layout.addWidget(open_path_btn)

        remote_layout = QHBoxLayout()
        self.remote_input = QLineEdit()
        self.remote_input.setPlaceholderText("192.168.1.100:5555")
        connect_btn = QPushButton("连接")
        connect_btn.clicked.connect(self._connect_remote)
        remote_layout.addWidget(self.remote_input)
        remote_layout.addWidget(connect_btn)
        device_layout.addLayout(remote_label_layout)
        device_layout.addLayout(remote_layout)

        device_group.setLayout(device_layout)
        layout.addWidget(device_group)

        # Environment check group
        check_group = QGroupBox("环境检查")
        check_layout = QVBoxLayout()

        # Individual check items
        check_items_layout = QVBoxLayout()
        
        # ADB 安装检查
        adb_item_layout = QHBoxLayout()
        self.adb_status_label = QLabel("ADB 安装")
        self.adb_check_btn = QPushButton("检查")
        self.adb_check_btn.clicked.connect(lambda: self._toggle_check("adb"))
        adb_item_layout.addWidget(self.adb_status_label)
        adb_item_layout.addStretch()
        adb_item_layout.addWidget(self.adb_check_btn)
        check_items_layout.addLayout(adb_item_layout)
        
        # 设备连接检查
        device_item_layout = QHBoxLayout()
        self.device_status_label = QLabel("设备连接")
        self.device_check_btn = QPushButton("检查")
        self.device_check_btn.clicked.connect(lambda: self._toggle_check("devices"))
        device_item_layout.addWidget(self.device_status_label)
        device_item_layout.addStretch()
        device_item_layout.addWidget(self.device_check_btn)
        check_items_layout.addLayout(device_item_layout)
        
        # ADB Keyboard 检查
        keyboard_item_layout = QHBoxLayout()
        self.keyboard_status_label = QLabel("ADB Keyboard")
        self.keyboard_check_btn = QPushButton("检查")
        self.keyboard_check_btn.clicked.connect(lambda: self._toggle_check("keyboard"))
        keyboard_item_layout.addWidget(self.keyboard_status_label)
        keyboard_item_layout.addStretch()
        keyboard_item_layout.addWidget(self.keyboard_check_btn)
        check_items_layout.addLayout(keyboard_item_layout)
        
        # 模型 API 检查
        api_item_layout = QHBoxLayout()
        self.api_status_label = QLabel("模型 API")
        self.api_check_btn = QPushButton("检查")
        self.api_check_btn.clicked.connect(lambda: self._toggle_check("model_api"))
        api_item_layout.addWidget(self.api_status_label)
        api_item_layout.addStretch()
        api_item_layout.addWidget(self.api_check_btn)
        check_items_layout.addLayout(api_item_layout)
        
        check_layout.addLayout(check_items_layout)
        
        # All check button
        self.check_all_btn = QPushButton("检查全部")
        self.check_all_btn.clicked.connect(self._run_all_environment_checks)
        check_layout.addWidget(self.check_all_btn)

        check_group.setLayout(check_layout)
        layout.addWidget(check_group)

        layout.addStretch()

        # Help button
        help_btn = QPushButton("📖 使用必读")
        help_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        help_btn.clicked.connect(self._show_usage_guide)
        layout.addWidget(help_btn)

        return panel

    def _create_middle_panel(self) -> QWidget:
        """Create the middle task execution panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # Task input group
        task_group = QGroupBox("任务输入")
        task_layout = QVBoxLayout()

        self.task_input = QTextEdit()
        self.task_input.setPlaceholderText("输入你的任务描述，例如：\n打开微信，对文件传输助手发送消息：部署成功")
        self.task_input.setMinimumHeight(200)
        task_layout.addWidget(self.task_input)

        task_group.setLayout(task_layout)
        layout.addWidget(task_group)

        # Control buttons
        control_layout = QHBoxLayout()

        self.start_btn = QPushButton("开始执行")
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.start_btn.clicked.connect(self._start_task)
        self.start_btn.setMinimumHeight(40)

        self.stop_btn = QPushButton("停止执行")
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        self.stop_btn.clicked.connect(self._stop_task)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(40)

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        layout.addLayout(control_layout)

        # Status display
        status_group = QGroupBox("任务状态")
        status_layout = QVBoxLayout()

        self.status_label = QLabel("状态: 空闲")
        self.status_label.setAlignment(Qt.AlignCenter)
        status_font = QFont()
        status_font.setPointSize(12)
        status_font.setBold(True)
        self.status_label.setFont(status_font)
        status_layout.addWidget(self.status_label)

        self.progress_label = QLabel("")
        self.progress_label.setWordWrap(True)
        status_layout.addWidget(self.progress_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        layout.addStretch()

        return panel

    def _create_right_panel(self) -> QWidget:
        """Create the right log viewer panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        log_group = QGroupBox("日志输出")
        log_layout = QVBoxLayout()

        self.log_viewer = LogViewer()
        log_layout.addWidget(self.log_viewer)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        return panel

    def _setup_timers(self):
        """Set up automatic refresh timers."""
        # Device list refresh timer (every 3 seconds)
        self.device_timer = QTimer()
        self.device_timer.timeout.connect(self._refresh_devices)
        self.device_timer.start(3000)  # 3 seconds

        # Initial device refresh
        self._refresh_devices()

    def _connect_signals(self):
        """Connect agent runner signals to UI slots."""
        # Signals will be connected when agent runner is created
    
    def _init_check_status(self):
        """Initialize check status labels."""
        if hasattr(self, 'adb_status_label'):
            self.adb_status_label.setText("ADB 安装: 未检查")
            self.device_status_label.setText("设备连接: 未检查")
            self.keyboard_status_label.setText("ADB Keyboard: 未检查")
            self.api_status_label.setText("模型 API: 未检查")

    def _load_settings(self):
        """Load saved settings."""
        self.base_url_input.setText(
            self.settings.value("base_url", "https://api-inference.modelscope.cn/v1")
        )
        self.model_input.setText(
            self.settings.value("model", "ZhipuAI/AutoGLM-Phone-9B")
        )
        self.api_key_input.setText(self.settings.value("api_key", ""))

    def _save_settings(self):
        """Save current settings."""
        self.settings.setValue("base_url", self.base_url_input.text())
        self.settings.setValue("model", self.model_input.text())
        self.settings.setValue("api_key", self.api_key_input.text())

    def _on_preset_changed(self, preset: str):
        """Handle preset configuration change."""
        if preset == "智谱-Phone":
            self.base_url_input.setText("https://api-inference.modelscope.cn/v1")
            self.model_input.setText("ZhipuAI/AutoGLM-Phone-9B")
            self.api_key_input.setPlaceholderText("ms-xxxxxx (ModelScope API Key 格式)")
        else:  # 自定义
            self.api_key_input.setPlaceholderText(self.api_key_placeholder_default)

    def _refresh_devices(self):
        """Refresh the device list."""
        try:
            devices = list_devices()
            
            # Block signals to prevent triggering selection event during refresh
            self.device_list.blockSignals(True)
            
            self.device_list.clear()

            for device in devices:
                if device.status == "device":
                    item_text = f"{device.device_id} ({device.connection_type.value})"
                    if device.model:
                        item_text += f" - {device.model}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, device.device_id)
                    self.device_list.addItem(item)

            # Restore selection if device still exists
            if self.selected_device_id:
                for i in range(self.device_list.count()):
                    item = self.device_list.item(i)
                    if item.data(Qt.UserRole) == self.selected_device_id:
                        self.device_list.setCurrentItem(item)
                        break
            
            # Unblock signals after refresh
            self.device_list.blockSignals(False)
        except Exception as e:
            self.device_list.blockSignals(False)
            self.log_viewer.log_error(f"刷新设备列表失败: {e}")

    def _on_device_selected(self):
        """Handle device selection."""
        current_item = self.device_list.currentItem()
        if current_item:
            new_device_id = current_item.data(Qt.UserRole)
            # Only log if device actually changed
            if new_device_id != self.selected_device_id:
                self.selected_device_id = new_device_id
                self.log_viewer.log_info(f"已选择设备: {self.selected_device_id}")
        else:
            if self.selected_device_id is not None:
                self.selected_device_id = None
                self.log_viewer.log_info("已取消选择设备")

    def _connect_remote(self):
        """Connect to remote device."""
        address = self.remote_input.text().strip()
        if not address:
            QMessageBox.warning(self, "警告", "请输入远程设备地址 (IP:Port)")
            return

        self.log_viewer.log_system(f"正在连接到远程设备: {address}")
        success, message = self.adb_connection.connect(address)
        if success:
            self.log_viewer.log_success(f"连接成功: {message}")
            self._refresh_devices()
        else:
            self.log_viewer.log_error(f"连接失败: {message}")

    def _update_check_result(
        self, check_name: str, status_label: QLabel, check_btn: QPushButton, result, check_type: str
    ):
        """Update UI with check result."""
        try:
            # Mark as not checking
            self.check_status[check_type] = False
            
            # Clean up timer if exists
            if check_type in self.check_timers:
                del self.check_timers[check_type]
            
            check_btn.setText("检查")
            if result.success:
                status_label.setText(f"{check_name}: ✅ 通过")
                status_label.setStyleSheet("color: green;")
                self.log_viewer.log_success(f"{check_name}: {result.message}")
            else:
                status_label.setText(f"{check_name}: ❌ 失败")
                status_label.setStyleSheet("color: red;")
                self.log_viewer.log_error(f"{check_name}: {result.message}")
                if result.solution:
                    self.log_viewer.log_info(f"解决方案: {result.solution}")
        except Exception as e:
            self.log_viewer.log_error(f"更新检查结果时出错: {str(e)}")
            self.check_status[check_type] = False
            check_btn.setText("检查")
            status_label.setText(f"{check_name}: ❌ 错误")
    
    def _update_check_error(
        self, check_name: str, status_label: QLabel, check_btn: QPushButton, check_type: str
    ):
        """Update UI with check error."""
        self.check_status[check_type] = False
        if check_type in self.check_timers:
            del self.check_timers[check_type]
        check_btn.setText("检查")
        status_label.setText(f"{check_name}: ❌ 错误")
        status_label.setStyleSheet("color: red;")
    
    def _on_model_api_check_finished(
        self, check_type: str, check_name: str, status_label: QLabel, 
        check_btn: QPushButton, success: bool, result: CheckResult
    ):
        """Handle model API check completion (called from main thread via signal)."""
        # Clean up thread reference
        if check_type in self.check_threads:
            del self.check_threads[check_type]
        
        # Update status
        self.check_status[check_type] = False
        
        # Update UI directly (we're already in main thread)
        check_btn.setText("检查")
        
        if success:
            status_label.setText(f"{check_name}: ✅ 通过")
            status_label.setStyleSheet("color: green;")
            self.log_viewer.log_success(f"{check_name}: {result.message}")
            # Display full response in log (like test_api.py)
            if result.details:
                self.log_viewer.log_info(f"详细信息:\n{result.details}")
        else:
            status_label.setText(f"{check_name}: ❌ 失败")
            status_label.setStyleSheet("color: red;")
            self.log_viewer.log_error(f"{check_name}: {result.message}")
            if result.details:
                self.log_viewer.log_error(f"错误详情: {result.details}")
            if result.solution:
                self.log_viewer.log_info(f"解决方案:\n{result.solution}")

    def _toggle_check(self, check_type: str):
        """Toggle check: start if not checking, stop if checking."""
        # Check if already checking
        if self.check_status.get(check_type, False):
            # Stop the check
            self._stop_check(check_type)
        else:
            # Start the check
            self._run_single_check(check_type)
    
    def _stop_check(self, check_type: str):
        """Stop a running check."""
        check_name_map = {
            "adb": "ADB 安装",
            "devices": "设备连接",
            "keyboard": "ADB Keyboard",
            "model_api": "模型 API",
        }
        check_name = check_name_map.get(check_type, check_type)
        
        # Get UI elements
        if check_type == "adb":
            status_label = self.adb_status_label
            check_btn = self.adb_check_btn
        elif check_type == "devices":
            status_label = self.device_status_label
            check_btn = self.device_check_btn
        elif check_type == "keyboard":
            status_label = self.keyboard_status_label
            check_btn = self.keyboard_check_btn
        elif check_type == "model_api":
            status_label = self.api_status_label
            check_btn = self.api_check_btn
        else:
            return
        
        # Cancel timer if exists (for quick checks)
        if check_type in self.check_timers:
            timer = self.check_timers[check_type]
            timer.stop()
            del self.check_timers[check_type]
        
        # Stop thread if exists (for slow checks like model API)
        if check_type in self.check_threads:
            thread = self.check_threads[check_type]
            if isinstance(thread, QThread):
                # For QThread, request termination
                thread.terminate()
                thread.wait(1000)  # Wait up to 1 second
                thread.deleteLater()
            del self.check_threads[check_type]
        
        # Mark as stopped
        self.check_status[check_type] = False
        
        # Update UI
        check_btn.setText("检查")
        status_label.setText(f"{check_name}: 已取消")
        status_label.setStyleSheet("color: orange;")
        self.log_viewer.log_system(f"{check_name} 检查已取消")

    def _run_single_check(self, check_type: str):
        """Run a single environment check using simple QTimer approach."""
        # Get UI elements and check function
        if check_type == "adb":
            status_label = self.adb_status_label
            check_btn = self.adb_check_btn
            check_name = "ADB 安装"
            from gui.utils.system_checker import check_adb_installation
            check_func = check_adb_installation
            is_slow_check = False
        elif check_type == "devices":
            status_label = self.device_status_label
            check_btn = self.device_check_btn
            check_name = "设备连接"
            from gui.utils.system_checker import check_devices
            check_func = check_devices
            is_slow_check = False
        elif check_type == "keyboard":
            status_label = self.keyboard_status_label
            check_btn = self.keyboard_check_btn
            check_name = "ADB Keyboard"
            from gui.utils.system_checker import check_adb_keyboard
            check_func = lambda: check_adb_keyboard(self.selected_device_id)
            is_slow_check = False
        elif check_type == "model_api":
            status_label = self.api_status_label
            check_btn = self.api_check_btn
            check_name = "模型 API"
            base_url = self.base_url_input.text().strip()
            model_name = self.model_input.text().strip()
            api_key = self.api_key_input.text().strip() or "EMPTY"
            if not base_url or not model_name:
                QMessageBox.warning(self, "警告", "请先配置 Base URL 和 Model 名称")
                return
            is_slow_check = True
        else:
            return

        # Mark as checking
        self.check_status[check_type] = True

        # Update UI to "checking" state
        check_btn.setText("终止")
        status_label.setText(f"{check_name}: 检查中...")
        self.log_viewer.log_system(f"开始检查 {check_name}...")

        if is_slow_check:
            # For slow checks (model API), use QThread (like test_api.py)
            # Get parameters for the check
            base_url = self.base_url_input.text().strip()
            model_name = self.model_input.text().strip()
            api_key = self.api_key_input.text().strip() or "EMPTY"
            
            # Create and start worker thread
            worker = ModelAPICheckWorker(base_url, model_name, api_key)
            worker.finished.connect(
                lambda success, result: self._on_model_api_check_finished(
                    check_type, check_name, status_label, check_btn, success, result
                )
            )
            self.check_threads[check_type] = worker
            worker.start()
        else:
            # For quick checks, use QTimer to delay execution slightly
            # This allows UI to update first
            def execute_check():
                try:
                    # Check if stopped
                    if not self.check_status.get(check_type, False):
                        return
                    
                    self.log_viewer.log_system(f"正在执行 {check_name} 检查...")
                    result = check_func()
                    
                    # Check if stopped before updating UI
                    if not self.check_status.get(check_type, False):
                        return
                    
                    self._update_check_result(check_name, status_label, check_btn, result, check_type)
                except Exception as e:
                    # Check if stopped
                    if not self.check_status.get(check_type, False):
                        return
                    
                    import traceback
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    error_details = traceback.format_exc()
                    self.log_viewer.log_error(f"{check_name} 检查异常: {error_msg}")
                    self.log_viewer.log_error(f"错误详情: {error_details}")
                    self._update_check_error(check_name, status_label, check_btn, check_type)

            # Delay by 10ms to allow UI to update
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(execute_check)
            timer.start(10)
            self.check_timers[check_type] = timer
    
    def _run_all_environment_checks(self):
        """Run all environment checks sequentially."""
        self.log_viewer.log_system("开始运行全部环境检查...")
        # Run checks one by one
        self._run_single_check("adb")
        # Use QTimer to chain the checks
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(1000, lambda: self._run_single_check("devices"))
        QTimer.singleShot(2000, lambda: self._run_single_check("keyboard"))
        QTimer.singleShot(3000, lambda: self._run_single_check("model_api"))


    def _validate_config(self, base_url: str, model_name: str, api_key: str) -> tuple[bool, str]:
        """
        Validate configuration before starting task.

        Args:
            base_url: Model API base URL
            model_name: Model name
            api_key: API key

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if base_url is empty
        if not base_url:
            return False, "Base URL 不能为空"

        # Validate URL format
        try:
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            if not parsed.scheme or not parsed.netloc:
                return False, f"Base URL 格式无效: {base_url}\n请使用完整 URL，例如: https://api-inference.modelscope.cn/v1"
        except Exception as e:
            return False, f"Base URL 解析失败: {str(e)}"

        # Check for localhost/127.0.0.1 and warn
        # Check both in the full URL and in the netloc (host:port)
        host = parsed.netloc.split(":")[0] if parsed.netloc else ""
        base_url_lower = base_url.lower()
        
        # Check for local addresses (127.x.x.x, localhost, ::1)
        # This includes 127.0.0.1:11434 format
        is_local = (
            "127.0.0.1" in base_url 
            or "localhost" in base_url_lower 
            or host in ("127.0.0.1", "localhost")
            or (host.startswith("127.") and len(host.split(".")) == 4)  # 127.x.x.x format
            or host == "localhost"
            or host == "::1"  # IPv6 localhost
        )
        
        if is_local:
            return False, (
                f"❌ 检测到本地地址: {base_url}\n\n"
                "⚠️ 此地址指向本地服务，但服务可能未运行。\n\n"
                "如果您使用 ModelScope 或智谱 BigModel，请使用以下地址：\n"
                "• ModelScope: https://api-inference.modelscope.cn/v1\n"
                "• 智谱 BigModel: https://open.bigmodel.cn/api/paas/v4\n\n"
                "如果您确实需要本地服务，请：\n"
                "1. 确保本地服务正在运行\n"
                "2. 检查服务地址和端口是否正确\n"
                "3. 确认服务可以正常访问\n\n"
                "💡 提示：请检查模型配置中的 Base URL 设置，或使用预设配置。"
            )

        # Check if model_name is empty
        if not model_name:
            return False, "Model 名称不能为空"

        # Validate API key format for specific presets
        preset = self.preset_combo.currentText()
        if preset == "智谱-Phone" and api_key:
            if not api_key.startswith("ms-"):
                return False, (
                    "API Key 格式不正确\n\n"
                    "智谱-Phone 预设需要使用 ModelScope API Key，格式为: ms-xxxxxx\n"
                    "请参考 使用必读.txt 获取免费 API Key"
                )

        return True, ""

    def _start_task(self):
        """Start task execution."""
        task = self.task_input.toPlainText().strip()
        if not task:
            QMessageBox.warning(self, "警告", "请输入任务描述")
            return

        base_url = self.base_url_input.text().strip()
        model_name = self.model_input.text().strip()
        api_key = self.api_key_input.text().strip()

        # Validate configuration
        is_valid, error_msg = self._validate_config(base_url, model_name, api_key)
        if not is_valid:
            QMessageBox.critical(self, "配置错误", error_msg)
            return

        # Save settings
        self._save_settings()

        # Create agent runner in a new thread
        self.agent_thread = QThread()
        self.agent_runner = AgentRunner(
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            device_id=self.selected_device_id,
            max_steps=100,
            lang="cn",
            notify=True,
        )
        self.agent_runner.moveToThread(self.agent_thread)

        # Connect signals with QueuedConnection to ensure thread-safe delivery
        self.agent_runner.thinking_received.connect(
            self._on_thinking_received, Qt.QueuedConnection
        )
        self.agent_runner.action_received.connect(
            self._on_action_received, Qt.QueuedConnection
        )
        self.agent_runner.step_completed.connect(
            self._on_step_completed, Qt.QueuedConnection
        )
        self.agent_runner.task_completed.connect(
            self._on_task_completed, Qt.QueuedConnection
        )
        self.agent_runner.error_occurred.connect(
            self._on_error_occurred, Qt.QueuedConnection
        )
        self.agent_runner.progress_updated.connect(
            self._on_progress_updated, Qt.QueuedConnection
        )

        # Connect thread signals - use lambda to capture task variable safely
        self.agent_thread.started.connect(
            lambda: self._run_task_in_thread(task)
        )
        self.agent_thread.finished.connect(self._on_thread_finished)

        # Update UI immediately before starting thread
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("状态: 运行中")
        self.status_label.setStyleSheet("color: #4CAF50;")
        self.log_viewer.log_system(f"开始执行任务: {task}")
        # Reset thinking stream state when starting new task
        self._thinking_stream_active = False
        
        # Force UI update before starting thread
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

        # Start thread
        self.agent_thread.start()
        
        # Force another UI update after starting thread
        QApplication.processEvents()

    def _run_task_in_thread(self, task: str):
        """Run task in the background thread (called from thread.started signal)."""
            try:
            # Emit initial progress immediately
                self.agent_runner.progress_updated.emit("任务已启动，正在初始化...")
            # Small delay to ensure signal is delivered and UI updates
            QThread.currentThread().msleep(100)
                # Start the task
                self.agent_runner.run_task(task)
            except Exception as e:
                # Emit error signal if task fails to start
                error_msg = f"任务启动失败: {str(e)}"
                self.agent_runner.error_occurred.emit(error_msg)
                import traceback
                self.agent_runner.progress_updated.emit(f"错误详情:\n{traceback.format_exc()}")
            finally:
                # Ensure thread exits after task completion or error
                # Use QMetaObject.invokeMethod for thread-safe quit
                from PyQt5.QtCore import QMetaObject, Qt
                QMetaObject.invokeMethod(
                    self.agent_thread,
                    "quit",
                    Qt.QueuedConnection
                )

    def _stop_task(self):
        """Stop task execution."""
        if not self.agent_runner or not self.agent_thread:
            return
        
        # Disable stop button immediately to prevent multiple clicks
        self.stop_btn.setEnabled(False)
        self.log_viewer.log_system("正在停止任务...")
        
        try:
            # Stop the agent runner (set flag to stop execution)
        if self.agent_runner:
            self.agent_runner.stop()
        
            # Request thread to quit gracefully
            if self.agent_thread and self.agent_thread.isRunning():
            self.agent_thread.quit()
                # Wait for thread to finish gracefully, with timeout
                if not self.agent_thread.wait(2000):  # Wait up to 2 seconds
                    # If thread doesn't quit gracefully, log warning but don't force terminate
                    # Force terminate can cause crashes
                    self.log_viewer.log_error("线程未能正常退出，请稍候...")
                    # Try one more time with shorter timeout
                    if not self.agent_thread.wait(1000):
                        # Only terminate as last resort, but this is dangerous
                        self.log_viewer.log_error("强制终止线程...")
                self.agent_thread.terminate()
                        self.agent_thread.wait(500)
        except Exception as e:
            # Catch any exceptions during stop to prevent crash
            self.log_viewer.log_error(f"停止任务时出错: {str(e)}")
            import traceback
            self.log_viewer.log_error(f"错误详情:\n{traceback.format_exc()}")
        finally:
            # Always update UI, even if stop failed
        self.start_btn.setEnabled(True)
        self.status_label.setText("状态: 已停止")
        self.status_label.setStyleSheet("color: #ff9800;")
        self.progress_label.setText("任务已停止")
        self.log_viewer.log_info("任务已停止")

    @pyqtSlot(str)
    def _on_thinking_received(self, thinking: str):
        """Handle thinking process update with incremental support."""
        # Log thinking immediately when received
        # Qt.QueuedConnection ensures this runs on main thread safely
        # Use incremental mode if we're already in a thinking stream
        is_incremental = self._thinking_stream_active
        if thinking:  # Only process if there's actual content
            self.log_viewer.log_thinking(thinking, is_incremental=is_incremental)
            # Mark that we're in a thinking stream
            self._thinking_stream_active = True
            # Force immediate UI update to show the thinking in real-time
            from PyQt5.QtWidgets import QApplication
            QApplication.processEvents()

    @pyqtSlot(dict)
    def _on_action_received(self, action: dict):
        """Handle action update."""
        action_json = json.dumps(action, ensure_ascii=False, indent=2)
        # Log action immediately when received
        # Qt.QueuedConnection ensures this runs on main thread safely
        self.log_viewer.log_action(action_json)

    @pyqtSlot(int, bool, str)
    def _on_step_completed(self, step_num: int, success: bool, message: str):
        """Handle step completion."""
        # Reset thinking stream state when step completes
        self._thinking_stream_active = False
        status = "成功" if success else "失败"
        self.log_viewer.log_info(f"步骤 {step_num} {status}: {message}")

    @pyqtSlot(str)
    def _on_task_completed(self, message: str):
        """Handle task completion."""
        self.log_viewer.log_success(f"✅ 任务完成: {message}")
        self.status_label.setText("状态: 已完成")
        self.status_label.setStyleSheet("color: #2196F3;")
        self.progress_label.setText(f"✅ {message}")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        # Clean up thread after task completion
        if self.agent_thread:
            self.agent_thread.quit()
            self.agent_thread.wait(1000)  # Wait up to 1 second
            self.agent_thread = None
            self.agent_runner = None

    def _parse_error_type(self, error: str) -> tuple[str, str]:
        """
        Parse error message and determine error type and help message.

        Args:
            error: Error message string

        Returns:
            Tuple of (error_type, help_message)
        """
        error_lower = error.lower()

        # Connection errors
        if "连接错误" in error or "cannot connect" in error_lower or "connect call failed" in error_lower:
            if "127.0.0.1" in error or "localhost" in error_lower:
                return (
                    "本地连接错误",
                    (
                        "无法连接到本地服务。\n\n"
                        "如果您使用 ModelScope 或智谱 BigModel，请：\n"
                        "1. 检查模型配置中的 Base URL\n"
                        "2. 确保使用正确的服务地址：\n"
                        "   - ModelScope: https://api-inference.modelscope.cn/v1\n"
                        "   - 智谱 BigModel: https://open.bigmodel.cn/api/paas/v4\n\n"
                        "如果您确实需要本地服务，请确保服务正在运行。"
                    )
                )
            else:
                return (
                    "网络连接错误",
                    (
                        "无法连接到模型服务。\n\n"
                        "请检查：\n"
                        "1. Base URL 是否正确\n"
                        "2. 网络连接是否正常\n"
                        "3. 防火墙设置是否阻止连接\n"
                        "4. 模型服务是否正在运行"
                    )
                )

        # Authentication errors
        if "认证错误" in error or "401" in error or "unauthorized" in error_lower or "api key" in error_lower:
            return (
                "认证错误",
                (
                    "API Key 验证失败。\n\n"
                    "请检查：\n"
                    "1. API Key 是否正确输入\n"
                    "2. API Key 是否已过期\n"
                    "3. API Key 格式是否正确（智谱-Phone 应为 ms- 开头）\n\n"
                    "请参考 使用必读.txt 重新获取 API Key"
                )
            )

        # API errors
        if "error code" in error_lower or "api error" in error_lower:
            return (
                "API 错误",
                (
                    "模型服务返回错误。\n\n"
                    "请检查：\n"
                    "1. Base URL 和 Model 名称是否正确\n"
                    "2. API Key 是否有效\n"
                    "3. 模型服务是否正常运行\n\n"
                    "如果问题持续，请查看详细错误信息。"
                )
            )

        # Default
        return ("错误", "任务执行过程中发生错误，请查看详细错误信息。")

    @pyqtSlot(str)
    def _on_error_occurred(self, error: str):
        """Handle error."""
        # Parse error type and get help message
        error_type, help_message = self._parse_error_type(error)

        # Log error with clear indication
        self.log_viewer.log_error(f"❌ {error_type}: {error}")
        self.status_label.setText("状态: 错误")
        self.status_label.setStyleSheet("color: #f44336;")
        
        # Truncate error message for progress label if too long
        display_error = error
        if len(display_error) > 100:
            display_error = display_error[:100] + "..."
        self.progress_label.setText(f"❌ {error_type}: {display_error}")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        # Show error message box for critical errors
        QMessageBox.critical(
            self,
            error_type,
            f"{error}\n\n{help_message}",
        )
        
        # Clean up thread after error
        if self.agent_thread:
            self.agent_thread.quit()
            self.agent_thread.wait(1000)  # Wait up to 1 second
            self.agent_thread = None
            self.agent_runner = None

    @pyqtSlot(str)
    def _on_progress_updated(self, progress: str):
        """Handle progress update."""
        self.progress_label.setText(progress)
        self.log_viewer.log_raw(progress, "info")
        # Qt.QueuedConnection ensures this runs on main thread safely

    def _on_thread_finished(self):
        """Handle thread finished."""
        # Clean up references safely
        try:
        if self.agent_runner:
            self.agent_runner.deleteLater()
        if self.agent_thread:
            self.agent_thread.deleteLater()
        except Exception as e:
            # Log but don't crash if cleanup fails
            try:
                self.log_viewer.log_error(f"清理线程资源时出错: {str(e)}")
            except:
                pass  # If log_viewer is also gone, just ignore
        finally:
            # Always clear references
        self.agent_thread = None
        self.agent_runner = None
            # Reset thinking stream state
            self._thinking_stream_active = False

    def _show_usage_guide(self):
        """Show the usage guide dialog."""
        import os
        from pathlib import Path
        
        # Get the path to 使用必读.txt
        current_dir = Path(__file__).parent.parent
        guide_file = current_dir / "使用必读.txt"
        
        # Read the file content
        try:
            if guide_file.exists():
                with open(guide_file, "r", encoding="utf-8") as f:
                    content = f.read()
            else:
                content = "文件未找到：使用必读.txt\n\n请确保文件存在于项目根目录。"
        except Exception as e:
            content = f"读取文件时出错：{str(e)}"
        
        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("使用必读 - 获取免费 API Key")
        dialog.setMinimumSize(700, 600)
        
        layout = QVBoxLayout(dialog)
        
        # Title
        title_label = QLabel("使用必读 - 获取免费 API Key")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Content text area
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(content)
        text_edit.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(text_edit)
        
        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(dialog.close)
        layout.addWidget(button_box)
        
        # Show dialog
        dialog.exec_()

    def _show_wireless_debug_path(self):
        """Show instructions for enabling wireless debugging (dialog style like usage guide)."""
        dialog = QDialog(self)
        dialog.setWindowTitle("无线调试路径")
        dialog.setMinimumSize(480, 320)

        layout = QVBoxLayout(dialog)

        title_label = QLabel("无线调试 - 开启与获取 IP:端口")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        content = (
            "请在手机上按以下路径操作：\n"
            "设置 > 开发者选项 > 无线调试 > IP地址\n\n"
            "步骤说明：\n"
            "1. 打开开发者选项（如未开启，请先在关于手机连续点击版本号启用）\n"
            "2. 进入“无线调试”\n"
            "3. 查看并复制显示的 IP:端口（例如 192.168.1.100:5555）\n"
            "4. 回到本界面，填写 IP:端口，点击“连接”\n\n"
            "提示：确保手机与电脑在同一局域网内。"
        )

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(content)
        text_edit.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(text_edit)

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(dialog.close)
        layout.addWidget(button_box)

        dialog.exec_()

    def closeEvent(self, event):
        """Handle window close event."""
        self._save_settings()
        
        # Stop any running task safely
        try:
        if self.agent_runner:
            self.agent_runner.stop()
        
        # Wait for thread to finish properly
        if self.agent_thread and self.agent_thread.isRunning():
            self.agent_thread.quit()
                if not self.agent_thread.wait(2000):  # Wait up to 2 seconds
                    # Don't force terminate on close - just log and continue
                    # Force terminate can cause crashes
                    pass
        
        # Clean up references
        if self.agent_runner:
            self.agent_runner.deleteLater()
        if self.agent_thread:
            self.agent_thread.deleteLater()
        except Exception as e:
            # Log but don't prevent window from closing
            try:
                self.log_viewer.log_error(f"关闭窗口时出错: {str(e)}")
            except:
                pass
        
        event.accept()

