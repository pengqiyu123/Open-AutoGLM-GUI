"""Agent runner for executing PhoneAgent in background thread."""

import json
import logging
import time
import traceback
from typing import Optional, Dict, List, Any
from pathlib import Path

from PyQt5.QtCore import QObject, QThread, QCoreApplication, pyqtSignal

# Create logger
logger = logging.getLogger(__name__)

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

        try:
            self.progress_updated.emit(f"开始执行任务: {task}")
            
            # ========== 匹配黄金路径 ==========
            if self._task_matcher:
                self.progress_updated.emit("🔍 正在查找匹配的黄金路径...")
                matched_path = self._task_matcher.find_matching_path(task)
                
                if matched_path:
                    self._matched_golden_path = matched_path
                    self._golden_path_id = matched_path.get('id')
                    
                    # 显示匹配信息
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
                else:
                    self.progress_updated.emit("ℹ️ 未找到匹配的黄金路径，将正常执行任务")
            
            # ========== 执行任务 ==========
            self.progress_updated.emit("🚀 开始执行任务...")
            
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
            self.progress_updated.emit("📝 已添加黄金路径提示到任务描述")

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
        Build enhanced prompt with golden path constraints.
        
        关键：把约束直接融入任务描述中，模仿用户直接输入的格式。
        
        Args:
            task: Original task description
            
        Returns:
            Enhanced task description with constraints
        """
        if not self._matched_golden_path:
            return task
        
        # 获取约束信息
        forbidden = self._matched_golden_path.get('forbidden', [])
        hints = self._matched_golden_path.get('hints', [])
        common_errors = self._matched_golden_path.get('common_errors', [])
        
        # 如果没有任何约束，直接返回原任务
        if not forbidden and not hints and not common_errors:
            return task
        
        # 构建约束列表
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
        
        # 把约束直接融入任务描述，模仿用户输入格式
        if constraints:
            return f"{task},{','.join(constraints)}"
        
        return task

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



