"""
Agent runner for executing PhoneAgent in background thread.
"""

import json
import logging
import time
import traceback
from typing import Optional, Dict, List, Any
from pathlib import Path

from PyQt5.QtCore import QObject, QThread, QCoreApplication, pyqtSignal

# Create logger
logger = logging.getLogger(__name__)

# Runtime configuration
_RUNTIME_CONFIG = {"matcher_threshold": 0.6, "tag": "ql_ck"}

from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig
from phone_agent.model import ModelConfig

# Import golden path components
try:
    from gui.utils.golden_path_repository import GoldenPathRepository
    from gui.utils.task_matcher import TaskMatcher
    from gui.utils.experience_injector import ExperienceInjector
    GOLDEN_PATH_AVAILABLE = True
except ImportError:
    GOLDEN_PATH_AVAILABLE = False


class AgentRunner(QObject):
    """Runs PhoneAgent in a background thread and emits signals for UI updates."""

    # Signals for UI updates
    thinking_received = pyqtSignal(str)  # Thinking process text (for real-time display)
    action_received = pyqtSignal(dict)  # Action dictionary
    step_completed = pyqtSignal(int, bool, str, str, str)  # step_number, success, message, screenshot_path, thinking
    task_completed = pyqtSignal(str)  # Final message
    error_occurred = pyqtSignal(str)  # Error message
    progress_updated = pyqtSignal(str)  # Progress message

    def __init__(
        self,
        base_url: str,
        model_name: str,
        api_key: str,
        device_id: Optional[str] = None,
        max_steps: int = 100,
        lang: str = "cn",
        notify: bool = False,
        task_logger=None,
        device_mode: str = "android",  # "android" or "harmonyos"
        parent=None,
    ):
        """
        Initialize the agent runner.

        Args:
            base_url: Model API base URL
            model_name: Model name
            api_key: API key
            device_id: Optional device ID
            max_steps: Maximum steps per task
            lang: Language (cn or en)
            notify: Enable device notifications
            task_logger: Optional TaskLogger instance for golden path integration
            device_mode: Device mode ("android" for ADB, "harmonyos" for HDC)
            parent: Parent QObject
        """
        super().__init__(parent)

        self.base_url = base_url
        self.model_name = model_name
        self.api_key = api_key
        self.device_id = device_id
        self.max_steps = max_steps
        self.lang = lang
        self.notify = notify
        self.task_logger = task_logger
        self.device_mode = device_mode

        self._agent: Optional[PhoneAgent] = None
        self._should_stop = False
        self._current_task: Optional[str] = None
        
        # Golden path components
        self._golden_path_repo: Optional[GoldenPathRepository] = None
        self._task_matcher: Optional[TaskMatcher] = None
        self._experience_injector: Optional[ExperienceInjector] = None
        self._matched_golden_path: Optional[Dict] = None
        self._golden_path_id: Optional[int] = None
        self._experience_messages: List[Dict[str, Any]] = []  # 经验消息（包含错误截图）
        
        # 状态机模式：步骤计数器和强制执行
        self._current_step_index: int = 0  # 当前应该执行的步骤索引（从0开始）
        self._golden_path_steps: List[Dict] = []  # 黄金路径的 action_sop
        self._strict_mode: bool = False  # 是否启用严格模式（强制按步骤执行）
        self._replay_mode: bool = False  # 是否启用直接回放模式（完全绕过模型）
        
        # Initialize golden path components if available
        if GOLDEN_PATH_AVAILABLE and task_logger:
            try:
                db_path = str(Path(task_logger.log_dir) / "tasks.db")
                self._golden_path_repo = GoldenPathRepository(db_path)
                self._task_matcher = TaskMatcher(self._golden_path_repo)
                self._experience_injector = ExperienceInjector(db_path)
            except Exception as e:
                print(f"Failed to initialize golden path components: {e}")

    def setup_agent(self):
        """Set up the PhoneAgent instance."""
        model_config = ModelConfig(
            base_url=self.base_url,
            model_name=self.model_name,
            api_key=self.api_key,
        )

        # Create thinking callback that emits signal in real-time
        def thinking_callback(thinking_chunk: str):
            """Callback for real-time thinking updates."""
            # Emit signal directly - Qt handles thread-safe delivery via QueuedConnection
            # The signal will be delivered to the main thread automatically
            if thinking_chunk and thinking_chunk.strip():  # Only emit if there's actual content
                self.thinking_received.emit(thinking_chunk)
                # NOTE: Removed msleep - it blocks the worker thread unnecessarily
                # Qt signals are already thread-safe and queued

        agent_config = AgentConfig(
            max_steps=self.max_steps,
            device_id=self.device_id,
            verbose=True,
            lang=self.lang,
            notify=self.notify,
            gui_mode=True,  # Enable GUI mode to disable terminal output
            thinking_callback=thinking_callback,  # Pass callback for streaming
            device_mode=self.device_mode,  # Pass device mode for HarmonyOS support
        )

        # Create custom logger that emits signals
        def log_callback(message: str):
            """Log callback that emits progress signal."""
            self.progress_updated.emit(message)

        self._agent = PhoneAgent(
            model_config=model_config,
            agent_config=agent_config,
        )

    def run_task(self, task: str):
        """
        Run a task with the agent.
        
        执行流程分为两个阶段：
        第一阶段：匹配黄金路径 → 调用模型学习 → 输出学习结论
        第二阶段：将学习结论 + 原始任务 → 传给模型执行

        Args:
            task: Task description
        """
        if self._agent is None:
            self.setup_agent()

        self._current_task = task
        self._should_stop = False
        self._matched_golden_path = None
        self._golden_path_id = None
        self._experience_messages = []
        
        # 重置状态机
        self._current_step_index = 0
        self._golden_path_steps = []
        self._strict_mode = False
        self._replay_mode = False

        try:
            self.progress_updated.emit(f"开始执行任务: {task}")
            
            # ========== 匹配黄金路径 ==========
            if self._task_matcher:
                self.progress_updated.emit("🔍 正在查找匹配的黄金路径...")
                matched_path = self._task_matcher.find_matching_path(task)
                
                if matched_path:
                    self._matched_golden_path = matched_path
                    self._golden_path_id = matched_path.get('id')
                    
                    # 判断匹配方式：快捷命令 vs 语义相似度
                    shortcut_cmd = matched_path.get('shortcut_command', '')
                    if shortcut_cmd and shortcut_cmd.strip() == task.strip():
                        # 快捷命令精确匹配
                        self.progress_updated.emit(
                            f"✅ 快捷命令匹配: 「{shortcut_cmd}」\n"
                            f"   路径: {matched_path['task_pattern']}\n"
                            f"   成功率: {matched_path.get('success_rate', 0):.1%}\n"
                            f"   使用次数: {matched_path.get('usage_count', 0)}"
                        )
                    else:
                        # 语义相似度匹配
                        similarity = self._task_matcher.semantic_similarity(
                            task, matched_path['task_pattern']
                        )
                        self.progress_updated.emit(
                            f"✅ 找到匹配的黄金路径 (相似度: {similarity:.1%})\n"
                            f"   路径: {matched_path['task_pattern']}\n"
                            f"   成功率: {matched_path.get('success_rate', 0):.1%}\n"
                            f"   使用次数: {matched_path.get('usage_count', 0)}"
                        )
                    
                    # 显示约束信息
                    forbidden = matched_path.get('forbidden', [])
                    correct_path = matched_path.get('correct_path', [])
                    hints = matched_path.get('hints', [])
                    
                    if forbidden or correct_path or hints:
                        self.progress_updated.emit("📋 已加载执行约束:")
                        if forbidden:
                            self.progress_updated.emit("   禁止操作: " + ", ".join(forbidden[:3]))
                        if correct_path:
                            self.progress_updated.emit("   正确步骤: " + str(len(correct_path)) + " 步")
                        if hints:
                            self.progress_updated.emit("   关键提示: " + str(len(hints)) + " 条")
                    
                    # ========== 构建经验消息（包含错误截图）==========
                    if self._experience_injector:
                        self.progress_updated.emit("📚 正在加载历史错误经验...")
                        self._experience_messages = self._experience_injector.build_experience_messages(
                            matched_path,
                            include_screenshots=True
                        )
                        if self._experience_messages:
                            # 统计经验消息
                            error_count = sum(1 for m in self._experience_messages 
                                            if m.get('role') == 'user' and '历史错误记录' in str(m.get('content', '')))
                            self.progress_updated.emit(f"   📸 已加载 {error_count} 条错误示例（含截图）")
                        else:
                            self.progress_updated.emit("   ℹ️ 无历史错误截图")
                    
                    # ========== 加载 action_sop 启用状态机模式 ==========
                    action_sop = matched_path.get('action_sop', [])
                    # 确保 action_sop 是列表格式
                    if isinstance(action_sop, str):
                        try:
                            action_sop = json.loads(action_sop)
                        except:
                            action_sop = []
                    
                    if action_sop and isinstance(action_sop, list) and len(action_sop) > 0:
                        # 检查 action_sop 是否包含有效的动作数据
                        valid_actions = [s for s in action_sop if s.get('action') and isinstance(s.get('action'), dict)]
                        if valid_actions:
                            self._golden_path_steps = valid_actions
                            self._strict_mode = True
                            self._replay_mode = True  # 启用直接回放模式
                            self._current_step_index = 0
                            self.progress_updated.emit(f"🔒 启用直接回放模式：共 {len(valid_actions)} 个预定义动作，将绕过模型决策")
                        else:
                            self.progress_updated.emit("   ℹ️ action_sop 无有效动作，使用提示词约束模式")
                    else:
                        self.progress_updated.emit("   ℹ️ 无预定义动作序列，使用提示词约束模式")
                else:
                    self.progress_updated.emit("ℹ️ 未找到匹配的黄金路径，将正常执行任务")
            
            # ========== 执行任务 ==========
            self.progress_updated.emit("🚀 开始执行任务...")
            
            # 根据模式选择执行方式
            if self._replay_mode and self._golden_path_steps:
                # 直接回放模式：绕过模型，直接执行黄金路径动作
                result, is_success = self._run_replay_mode(task)
            else:
                # 正常模式：使用模型决策
                result, is_success = self._run_task_with_capture(task)
            
            # Update golden path usage count and success rate if used
            # Do this atomically to ensure consistency
            if self._golden_path_repo and self._golden_path_id:
                logger.info(f"更新黄金路径统计: ID={self._golden_path_id}, 成功={is_success}")
                self._golden_path_repo.increment_usage(self._golden_path_id)
                self._update_golden_path_success_rate(is_success)
                logger.info(f"✓ 黄金路径统计已更新")
            
            if self._should_stop:
                self.progress_updated.emit("任务已停止")
                self.error_occurred.emit("任务被用户停止")
            elif is_success:
                # Only emit task_completed if task actually succeeded
                self.task_completed.emit(result)
            else:
                # If task failed, emit error instead of completion
                # Only emit once to avoid duplication
                self.error_occurred.emit(result)

        except Exception as e:
            error_msg = f"任务执行出错: {str(e)}"
            self.error_occurred.emit(error_msg)
            self.progress_updated.emit(f"错误详情:\n{traceback.format_exc()}")
            
            # Update golden path usage count and success rate on error
            # This ensures we track failures even when exceptions occur
            if self._golden_path_repo and self._golden_path_id:
                logger.error(f"任务异常，更新黄金路径统计: ID={self._golden_path_id}, 成功=False")
                self._golden_path_repo.increment_usage(self._golden_path_id)
                self._update_golden_path_success_rate(False)
                logger.info(f"✓ 黄金路径统计已更新（失败）")
        finally:
            # Clear current task to indicate we're done
            self._current_task = None
            self._matched_golden_path = None
            self._golden_path_id = None

    def _run_replay_mode(self, task: str) -> tuple[str, bool]:
        """
        直接回放模式：绕过模型决策，直接按黄金路径的 action_sop 执行动作。
        
        这是 ChatGPT 思路中"状态机 + LLM"架构的简化实现：
        - 动作选择权完全在本地（黄金路径）
        - 不依赖模型的动作决策
        - 模型只在需要时用于屏幕理解（可选）
        
        Args:
            task: Task description (用于日志记录)
            
        Returns:
            Tuple of (result_message, is_success)
        """
        from phone_agent.actions import ActionHandler
        from phone_agent.device_manager import DeviceManager, DeviceMode
        
        self.progress_updated.emit("🎬 进入直接回放模式...")
        
        # 初始化设备管理器和动作处理器
        try:
            device_mode = DeviceMode.HARMONYOS if self.device_mode == "harmonyos" else DeviceMode.ANDROID
            device_manager = DeviceManager(mode=device_mode, device_id=self.device_id)
            action_handler = ActionHandler(
                device_id=self.device_id,
                device_manager=device_manager,
            )
        except Exception as e:
            return (f"初始化设备失败: {e}", False)
        
        total_steps = len(self._golden_path_steps)
        self.progress_updated.emit(f"📋 共 {total_steps} 个步骤待执行")
        
        # 逐步执行黄金路径动作
        for step_idx, step_data in enumerate(self._golden_path_steps):
            if self._should_stop:
                return ("任务被用户停止", False)
            
            step_num = step_idx + 1
            action = step_data.get('action', {})
            
            if not action:
                self.progress_updated.emit(f"⚠️ 步骤 {step_num} 无有效动作，跳过")
                continue
            
            # 获取动作描述
            action_type = action.get('action', 'unknown')
            action_desc = self._format_action_for_display(action)
            
            self.progress_updated.emit(f"▶ 执行步骤 {step_num}/{total_steps}: {action_desc}")
            
            # 截图获取屏幕尺寸
            try:
                screenshot = device_manager.get_screenshot()
                screen_width = screenshot.width
                screen_height = screenshot.height
            except Exception as e:
                self.progress_updated.emit(f"⚠️ 截图失败: {e}，使用默认尺寸")
                screen_width = 1080
                screen_height = 2400
            
            # 执行动作
            try:
                # 确保动作有 _metadata
                if '_metadata' not in action:
                    action['_metadata'] = 'do'
                
                result = action_handler.execute(action, screen_width, screen_height)
                
                if result.success:
                    self.progress_updated.emit(f"   ✅ 步骤 {step_num} 成功")
                    # 发送步骤完成信号
                    self.step_completed.emit(step_num, True, result.message or "", "", "")
                    self.action_received.emit(action)
                else:
                    self.progress_updated.emit(f"   ❌ 步骤 {step_num} 失败: {result.message}")
                    self.step_completed.emit(step_num, False, result.message or "", "", "")
                    # 继续执行，不中断
                
                # 检查是否是 finish 动作
                if action.get('_metadata') == 'finish' or result.should_finish:
                    return (result.message or "任务完成", True)
                
            except Exception as e:
                self.progress_updated.emit(f"   ❌ 步骤 {step_num} 执行异常: {e}")
                self.step_completed.emit(step_num, False, str(e), "", "")
                # 继续执行，不中断
            
            # 步骤间延迟，等待界面响应
            QThread.currentThread().msleep(500)
        
        # 所有步骤执行完成
        self.progress_updated.emit(f"🎉 全部 {total_steps} 个步骤执行完成")
        return (f"黄金路径回放完成，共执行 {total_steps} 步", True)
    
    def _format_action_for_display(self, action: dict) -> str:
        """格式化动作用于显示"""
        action_type = action.get('action', 'unknown')
        
        if action_type == 'Tap':
            element = action.get('element', action.get('point', [0, 0]))
            if isinstance(element, list) and len(element) >= 2:
                return f"点击 ({element[0]}, {element[1]})"
            return "点击屏幕"
        elif action_type == 'Type':
            text = action.get('text', '')
            return f"输入「{text[:20]}{'...' if len(text) > 20 else ''}」"
        elif action_type == 'Launch':
            return f"打开应用「{action.get('app', '')}」"
        elif action_type == 'Swipe':
            return "滑动屏幕"
        elif action_type == 'Back':
            return "返回"
        elif action_type == 'Home':
            return "回到桌面"
        elif action_type == 'Wait':
            return "等待"
        else:
            return f"{action_type}"

    def _run_task_with_capture(self, task: str) -> tuple[str, bool]:
        """
        Run task and capture thinking/actions by manually stepping through.

        Args:
            task: Task description

        Returns:
            Tuple of (result_message, is_success)
        """
        if self._agent is None:
            raise RuntimeError("Agent not initialized")

        # Reset agent state
        self._agent.reset()
        
        # Emit initial progress
        self.progress_updated.emit("正在初始化任务...")
        
        # 注入经验消息到 agent 上下文（如果有）
        if self._experience_messages:
            self.progress_updated.emit("📚 正在注入历史经验到对话上下文...")
            self._inject_experience_to_agent()
            self.progress_updated.emit(f"   ✅ 已注入 {len(self._experience_messages)} 条经验消息")
        
        # Build enhanced prompt with golden path hints
        enhanced_task = self._build_enhanced_prompt(task)
        
        if enhanced_task != task:
            self.progress_updated.emit("📝 已添加黄金路径步骤到任务描述")
            # 显示增强后的任务（截取前200字符）
            display_task = enhanced_task[:200] + "..." if len(enhanced_task) > 200 else enhanced_task
            self.progress_updated.emit(f"   📋 增强任务: {display_task}")

        # First step
        try:
            self.progress_updated.emit("正在执行步骤 1...")
            # Small delay to allow signal delivery to main thread
            QThread.currentThread().msleep(20)
            step_result = self._agent.step(enhanced_task)
            # Emit step info immediately after first step
            self._emit_step_info(step_result, 1)
            # Allow signal delivery
            QThread.currentThread().msleep(20)
        except Exception as e:
            error_msg = f"步骤 1 执行出错: {str(e)}"
            self.error_occurred.emit(error_msg)
            self.progress_updated.emit(f"错误详情:\n{traceback.format_exc()}")
            raise

        # Check if step failed (success=False means error occurred)
        if not step_result.success:
            error_msg = step_result.message or "步骤执行失败"
            # Remove "Model error: " prefix if present for cleaner error display
            if error_msg.startswith("Model error: "):
                error_msg = error_msg[13:]  # Remove "Model error: " prefix
            # Don't emit error here, let run_task handle it to avoid duplication
            return (error_msg, False)

        if step_result.finished or self._should_stop:
            return (step_result.message or "任务完成", step_result.success)

        # Continue stepping
        step_num = 2
        while step_num <= self.max_steps and not self._should_stop:
            try:
                # Emit progress before each step
                self.progress_updated.emit(f"正在执行步骤 {step_num}...")
                
                # Small delay to allow signal delivery to main thread
                QThread.currentThread().msleep(20)
                
                # Execute step (this will trigger streaming callbacks during model request)
                step_result = self._agent.step()
                
                # Check if step failed
                if not step_result.success:
                    error_msg = step_result.message or f"步骤 {step_num} 执行失败"
                    # Remove "Model error: " prefix if present for cleaner error display
                    if error_msg.startswith("Model error: "):
                        error_msg = error_msg[13:]  # Remove "Model error: " prefix
                    # Don't emit error here, let run_task handle it to avoid duplication
                    return (error_msg, False)
                
                # Emit step info immediately after execution
                self._emit_step_info(step_result, step_num)
                
                # Allow signal delivery
                QThread.currentThread().msleep(20)

                if step_result.finished:
                    return (step_result.message or "任务完成", step_result.success)

                step_num += 1
            except Exception as e:
                error_msg = f"步骤 {step_num} 执行出错: {str(e)}"
                self.error_occurred.emit(error_msg)
                self.progress_updated.emit(f"错误详情:\n{traceback.format_exc()}")
                raise

        return ("达到最大步数限制", True)

    def _emit_step_info(self, step_result, step_num: int):
        """
        Emit signals for step information.

        Args:
            step_result: StepResult object
            step_num: Step number
        """
        # Note: Thinking is already emitted in real-time via streaming callback
        # We don't need to emit it again here to avoid duplication
        # The streaming callback handles real-time thinking updates

        # Emit action
        if step_result.action:
            self.action_received.emit(step_result.action)

            # Format action for display
            action_type = step_result.action.get("_metadata", "unknown")
            action_name = step_result.action.get("action", "N/A")
            action_display = f"🎯 执行动作 (步骤 {step_num}): {action_type} - {action_name}"

            if action_type == "do":
                action_json = json.dumps(
                    step_result.action, ensure_ascii=False, indent=2
                )
                self.progress_updated.emit(f"{action_display}\n{action_json}")
            elif action_type == "finish":
                message = step_result.action.get("message", "")
                self.progress_updated.emit(f"{action_display}: {message}")

        # Emit step completion with complete thinking from step_result
        status = "✅ 成功" if step_result.success else "❌ 失败"
        self.step_completed.emit(
            step_num, 
            step_result.success, 
            step_result.message or "", 
            step_result.screenshot_path or "",
            step_result.thinking or ""  # Pass complete thinking directly
        )
        # Also emit as progress
        if step_result.message:
            self.progress_updated.emit(f"{status} (步骤 {step_num}): {step_result.message}")

    def stop(self):
        """Stop the current task execution."""
        self._should_stop = True
        self.progress_updated.emit("正在停止任务...")

    def is_running(self) -> bool:
        """Check if a task is currently running."""
        return self._current_task is not None and not self._should_stop

    def _update_golden_path_success_rate(self, success: bool):
        """
        Update the success rate of the matched golden path.
        
        Args:
            success: Whether the task succeeded
        """
        if not self._golden_path_repo or not self._golden_path_id:
            return
        
        try:
            # Get current path
            path = self._golden_path_repo.find_by_id(self._golden_path_id)
            if not path:
                return
            
            # Calculate new success rate
            usage_count = path.get('usage_count', 1)
            current_rate = path.get('success_rate', 0.0)
            
            # Weighted average: give more weight to recent results
            # New rate = (old_rate * (usage_count - 1) + new_result) / usage_count
            new_rate = (current_rate * (usage_count - 1) + (1.0 if success else 0.0)) / usage_count
            
            # Update in database
            self._golden_path_repo.update_success_rate(self._golden_path_id, new_rate)
            
            self.progress_updated.emit(
                f"📊 更新黄金路径成功率: {current_rate:.1%} → {new_rate:.1%}"
            )
        except Exception as e:
            print(f"Failed to update golden path success rate: {e}")

    def _build_enhanced_prompt(self, task: str) -> str:
        """
        Build enhanced prompt with MANDATORY golden path constraints.
        
        核心改变：
        1. 使用强制性语气，不是"参考"而是"必须服从"
        2. 使用特殊标记触发模型的"服从模式"
        3. 明确告知违反约束的后果
        4. 添加明确的任务完成判定条件，防止模型无限验证
        5. 强调必须执行完所有步骤才能完成
        6. 在严格模式下，告诉模型当前是第几步
        
        Args:
            task: Original task description
            
        Returns:
            Enhanced task description with mandatory constraints
        """
        if not self._matched_golden_path:
            return task
        
        import json
        import re
        
        # 获取正确步骤
        correct_path = self._matched_golden_path.get('correct_path', [])
        if isinstance(correct_path, str):
            try:
                correct_path = json.loads(correct_path)
            except:
                correct_path = []
        
        # 获取禁止操作
        forbidden = self._matched_golden_path.get('forbidden', [])
        if isinstance(forbidden, str):
            try:
                forbidden = json.loads(forbidden)
            except:
                forbidden = []
        
        # 获取关键提示
        hints = self._matched_golden_path.get('hints', [])
        if isinstance(hints, str):
            try:
                hints = json.loads(hints)
            except:
                hints = []
        
        # 如果没有任何约束，直接返回原任务
        if not correct_path and not forbidden and not hints:
            return task
        
        # ========== 解析任务中的完成条件 ==========
        # 优先从黄金路径读取用户微调的完成条件
        completion_conditions = self._matched_golden_path.get('completion_conditions', [])
        if isinstance(completion_conditions, str):
            try:
                completion_conditions = json.loads(completion_conditions)
            except:
                completion_conditions = []
        
        # 如果黄金路径没有设置完成条件，则从任务描述中自动提取
        if not completion_conditions:
            completion_conditions = self._extract_completion_conditions(task)
        
        # ========== 构建强制约束格式 ==========
        parts = [task]
        
        # 添加强制执行步骤 - 更强的约束
        if correct_path:
            total_steps = len(correct_path)
            
            # 严格模式下，显示当前进度
            if self._strict_mode:
                current = self._current_step_index + 1
                parts.append(f"\n\n⚠️【严格执行模式 - 当前第{current}步/共{total_steps}步】")
                parts.append(f"系统会自动校验你的动作，不符合的动作会被强制替换。")
            else:
                parts.append(f"\n\n⚠️【强制执行模式 - 共{total_steps}步】")
            
            parts.append(f"你必须严格按以下顺序执行全部{total_steps}个步骤，每次只执行一步：")
            for i, step in enumerate(correct_path, 1):
                step_clean = re.sub(r'^\d+\.\s*', '', str(step))
                if step_clean:
                    # 标记当前步骤
                    if self._strict_mode and i == self._current_step_index + 1:
                        parts.append(f"  ▶ 第{i}步：{step_clean} 【当前应执行】")
                    else:
                        parts.append(f"  第{i}步：{step_clean}")
            
            # 强调必须执行完所有步骤
            parts.append(f"\n🚫【禁止提前完成】")
            parts.append(f"- 你必须执行完全部{total_steps}步才能调用finish")
            parts.append(f"- 即使你认为任务已完成，也必须继续执行剩余步骤")
            parts.append(f"- 不要自己判断任务是否完成，严格按步骤执行")
            parts.append(f"- 不要用Wait替代任何步骤，每一步都必须执行实际操作")
        
        # 添加绝对禁止操作
        if forbidden:
            parts.append("\n❌【绝对禁止 - 违反将导致任务失败】")
            for f in forbidden:
                f = str(f).strip()
                if not f:
                    continue
                # 统一格式
                if f.startswith('不要') or f.startswith('不允许') or f.startswith('禁止'):
                    parts.append(f"  × {f}")
                elif f.startswith('不'):
                    parts.append(f"  × {f}")
                # 跳过提示性信息
                elif any(kw in f for kw in ['要返回', '要点击', '应该', '需要', '就是', '说明', '表示', '显示']):
                    continue
                else:
                    parts.append(f"  × 不要{f}")
        
        # 添加关键提示
        if hints:
            parts.append("\n💡【关键提示】")
            for h in hints:
                h = str(h).strip()
                if h:
                    # 清理提示前缀
                    h_clean = h.replace("位置提示: ", "").replace("判断条件: ", "")
                    parts.append(f"  • {h_clean}")
        
        # ========== 添加任务完成判定条件（关键！）==========
        if completion_conditions:
            parts.append("\n【任务完成判定 - 立即停止条件】")
            parts.append("当你观察到以下任意一个条件满足时，必须立即调用finish结束任务，不要继续验证或执行其他操作：")
            for i, cond in enumerate(completion_conditions, 1):
                parts.append(f"  {i}. {cond}")
            parts.append("⚠️ 看到条件满足就停止！不要再滚动、不要再点击、不要再验证！")
        
        # 添加强制声明
        parts.append("\n【重要】这是经过验证的正确路径。你现在是执行器，不是规划者。严格复现上述步骤，不要自己思考更好的方案。")
        parts.append("【停止原则】一旦观察到任务目标已达成（如看到成功标志），立即finish，不要多做任何操作。")
        
        enhanced_task = '\n'.join(parts)
        
        # 记录日志
        logger.info(f"已构建强制约束提示词：{len(correct_path)} 个步骤，{len(forbidden)} 个禁止操作，{len(hints)} 个提示，{len(completion_conditions)} 个完成条件")
        
        return enhanced_task
    
    def _extract_completion_conditions(self, task: str) -> List[str]:
        """
        从任务描述中提取完成条件。
        
        识别模式：
        - "如果显示XXX，说明YYY成功"
        - "如果看到XXX，表示完成"
        - "当XXX时，无需执行后续"
        - "XXX说明签到成功"
        
        Args:
            task: 任务描述
            
        Returns:
            完成条件列表
        """
        import re
        
        conditions = []
        
        # 模式1: "如果显示/看到XXX，说明/表示YYY成功/完成"
        pattern1 = r'如果(?:显示|看到|出现)[「"\'"]?([^「"\'",，。]+)[「"\'"]?[,，]?\s*(?:说明|表示|则).*?(?:成功|完成|无需)'
        matches1 = re.findall(pattern1, task)
        for m in matches1:
            conditions.append(f"屏幕上显示「{m.strip()}」")
        
        # 模式2: 直接提取关键标志词 "已签" "明天" 等
        if '已签' in task:
            conditions.append("看到「已签」文字")
        if '签到成功' in task:
            conditions.append("看到「签到成功」提示")
        
        # 模式3: "无需执行后续任务" 前面的条件
        pattern3 = r'([^,，。]+?)(?:说明|表示).*?无需执行'
        matches3 = re.findall(pattern3, task)
        for m in matches3:
            m = m.strip()
            if m and len(m) < 30:  # 避免匹配过长的内容
                conditions.append(f"观察到：{m}")
        
        # 去重
        conditions = list(dict.fromkeys(conditions))
        
        return conditions

    def _inject_experience_to_agent(self):
        """
        将经验消息注入到 agent 的对话上下文中。
        
        这些消息会在系统提示词之后、用户任务之前插入，
        让模型"看到"之前的错误场景和纠正。
        """
        if not self._agent or not self._experience_messages:
            return
        
        # 先添加系统消息（如果还没有）
        if not self._agent._context:
            from phone_agent.model.client import MessageBuilder
            self._agent._context.append(
                MessageBuilder.create_system_message(self._agent.agent_config.system_prompt)
            )
        
        # 注入经验消息
        for msg in self._experience_messages:
            self._agent._context.append(msg)
        
        logger.info(f"已注入 {len(self._experience_messages)} 条经验消息到 agent 上下文")

    def get_matched_golden_path(self) -> Optional[Dict]:
        """
        Get the currently matched golden path.
        
        Returns:
            Golden path dictionary or None
        """
        return self._matched_golden_path



