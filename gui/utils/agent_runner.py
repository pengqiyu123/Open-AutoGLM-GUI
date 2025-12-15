"""Agent runner for executing PhoneAgent in background thread."""

import json
import time
import traceback
from typing import Optional

from PyQt5.QtCore import QObject, QThread, QCoreApplication, pyqtSignal

from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig
from phone_agent.model import ModelConfig


class AgentRunner(QObject):
    """Runs PhoneAgent in a background thread and emits signals for UI updates."""

    # Signals for UI updates
    thinking_received = pyqtSignal(str)  # Thinking process text
    action_received = pyqtSignal(dict)  # Action dictionary
    step_completed = pyqtSignal(int, bool, str)  # step_number, success, message
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

        self._agent: Optional[PhoneAgent] = None
        self._should_stop = False
        self._current_task: Optional[str] = None

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
                # Small delay to ensure signal is queued and processed
                QThread.currentThread().msleep(5)

        agent_config = AgentConfig(
            max_steps=self.max_steps,
            device_id=self.device_id,
            verbose=True,
            lang=self.lang,
            notify=self.notify,
            gui_mode=True,  # Enable GUI mode to disable terminal output
            thinking_callback=thinking_callback,  # Pass callback for streaming
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

        Args:
            task: Task description
        """
        if self._agent is None:
            self.setup_agent()

        self._current_task = task
        self._should_stop = False

        try:
            self.progress_updated.emit(f"开始执行任务: {task}")

            # We need to intercept the agent's execution to capture thinking and actions
            # Since PhoneAgent doesn't expose callbacks, we'll need to run it and
            # capture output from the step method or modify the agent
            # For now, let's use a wrapper that calls step() manually

            result, is_success = self._run_task_with_capture(task)
            
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
        finally:
            # Clear current task to indicate we're done
            self._current_task = None

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

        # First step
        try:
            self.progress_updated.emit("正在执行步骤 1...")
            # Small delay to allow signal delivery to main thread
            QThread.currentThread().msleep(20)
            step_result = self._agent.step(task)
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

        # Emit step completion
        status = "✅ 成功" if step_result.success else "❌ 失败"
        self.step_completed.emit(
            step_num, step_result.success, step_result.message or ""
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

