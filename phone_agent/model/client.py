"""Model client for AI inference using OpenAI-compatible API."""

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from openai import OpenAI, DefaultHttpxClient


@dataclass
class ModelConfig:
    """Configuration for the AI model."""

    base_url: str = "http://localhost:8000/v1"
    api_key: str = "EMPTY"
    model_name: str = "autoglm-phone-9b"
    max_tokens: int = 3000
    temperature: float = 0.0
    top_p: float = 0.85
    frequency_penalty: float = 0.2
    extra_body: dict[str, Any] = field(default_factory=dict)
    # Optional HTTP proxy settings. Default None.
    proxies: dict | None = None


@dataclass
class ModelResponse:
    """Response from the AI model."""

    thinking: str
    action: str
    raw_content: str


class ModelClient:
    """
    Client for interacting with OpenAI-compatible vision-language models.

    Args:
        config: Model configuration.
    """

    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()
        # Disable env proxies by default to avoid accidental localhost (e.g., 127.0.0.1:11434).
        if self.config.proxies is not None:
            http_client = DefaultHttpxClient(
                proxies=self.config.proxies,
                timeout=60.0,
            )
        else:
            http_client = DefaultHttpxClient(
                timeout=60.0,
                trust_env=False,
            )
        self.client = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            http_client=http_client,
        )

    def request(self, messages: list[dict[str, Any]]) -> ModelResponse:
        """
        Send a request to the model.

        Args:
            messages: List of message dictionaries in OpenAI format.

        Returns:
            ModelResponse containing thinking and action.

        Raises:
            Exception: If the request fails, with detailed error information.
        """
        try:
            response = self.client.chat.completions.create(
                messages=messages,
                model=self.config.model_name,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                frequency_penalty=self.config.frequency_penalty,
                extra_body=self.config.extra_body,
                stream=False,
            )

            raw_content = response.choices[0].message.content

            # Parse thinking and action from response
            thinking, action = self._parse_response(raw_content)

            return ModelResponse(thinking=thinking, action=action, raw_content=raw_content)

        except Exception as e:
            # Parse and format error information
            error_info = self._parse_error(e)
            raise Exception(error_info) from e

    def request_stream(
        self,
        messages: list[dict[str, Any]],
        thinking_callback: Callable[[str], None] | None = None,
    ):
        """
        Send a streaming request to the model and return stream iterator for async processing.

        Args:
            messages: List of message dictionaries in OpenAI format.
            thinking_callback: Optional callback (not used in async mode, kept for compatibility).

        Returns:
            Stream iterator from OpenAI API.

        Raises:
            Exception: If the request fails, with detailed error information.
        """
        try:
            stream = self.client.chat.completions.create(
                messages=messages,
                model=self.config.model_name,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                frequency_penalty=self.config.frequency_penalty,
                extra_body=self.config.extra_body,
                stream=True,
            )
            
            # Return stream iterator for async processing
            return stream
            
        except Exception as e:
            # Parse and format error information
            error_info = self._parse_error(e)
            raise Exception(error_info) from e
    
    def request_stream_sync(
        self,
        messages: list[dict[str, Any]],
        thinking_callback: Callable[[str], None] | None = None,
    ) -> ModelResponse:
        """
        Send a streaming request and process synchronously (legacy mode).
        
        This method processes the stream synchronously and is kept for backward compatibility.
        For real-time UI updates, use request_stream() with StreamingResponseProcessor instead.

        Args:
            messages: List of message dictionaries in OpenAI format.
            thinking_callback: Optional callback function to receive thinking chunks in real-time.

        Returns:
            ModelResponse containing thinking and action.

        Raises:
            Exception: If the request fails, with detailed error information.
        """
        try:
            stream = self.client.chat.completions.create(
                messages=messages,
                model=self.config.model_name,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                frequency_penalty=self.config.frequency_penalty,
                extra_body=self.config.extra_body,
                stream=True,
            )

            raw_content = ""
            action_started = False
            last_raw_content = ""  # Track previous content to detect marker appearance
            accumulated_thinking = ""  # Track accumulated thinking to filter out code
            thinking_buffer = ""  # Buffer for batching thinking chunks
            chunk_count = 0  # Debug: count chunks received

            # Process stream chunks
            # Add periodic yield to allow event processing
            chunk_processed = 0
            for chunk in stream:
                chunk_processed += 1
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        chunk_count += 1
                        content_chunk = delta.content
                        raw_content += content_chunk

                        # Check if we've reached the action part
                        if not action_started:
                            # Check for action markers in current content
                            marker_found = None
                            marker_pos = -1
                            
                            if "finish(message=" in raw_content and "finish(message=" not in last_raw_content:
                                marker_found = "finish(message="
                                marker_pos = raw_content.find("finish(message=")
                            elif "do(action=" in raw_content and "do(action=" not in last_raw_content:
                                marker_found = "do(action="
                                marker_pos = raw_content.find("do(action=")
                            
                            if marker_found:
                                # We just detected the marker in this chunk
                                # Extract thinking part before the marker
                                thinking_part = raw_content[:marker_pos].strip()
                                # Get only the new thinking content (since last check)
                                if len(thinking_part) > len(accumulated_thinking):
                                    new_thinking = thinking_part[len(accumulated_thinking):]
                                    # Add any buffered thinking (but clean it first)
                                    if thinking_buffer:
                                        # Clean buffer before adding
                                        cleaned_buffer = self._clean_thinking(thinking_buffer)
                                        if cleaned_buffer:
                                            new_thinking = cleaned_buffer + new_thinking
                                        thinking_buffer = ""
                                    # Clean up: remove any code-like patterns that might have leaked
                                    new_thinking = self._clean_thinking(new_thinking)
                                    # Additional check: ensure no code markers slipped through
                                    if "do(action" in new_thinking.lower() or "finish(message" in new_thinking.lower():
                                        # Remove everything from the marker onwards
                                        if "do(action" in new_thinking.lower():
                                            pos = new_thinking.lower().find("do(action")
                                            new_thinking = new_thinking[:pos].rstrip()
                                        if "finish(message" in new_thinking.lower():
                                            pos = new_thinking.lower().find("finish(message")
                                            new_thinking = new_thinking[:pos].rstrip()
                                    if new_thinking and new_thinking.strip() and thinking_callback:
                                        thinking_callback(new_thinking)
                                accumulated_thinking = thinking_part
                                action_started = True
                            else:
                                # Still in thinking part
                                accumulated_thinking += content_chunk
                                thinking_buffer += content_chunk
                                
                                # Send thinking chunks immediately for maximum real-time feel
                                # Send on every chunk or when buffer reaches small threshold
                                should_send = (
                                    len(thinking_buffer) >= 3 or  # Very low threshold (3 chars) for real-time updates
                                    '\n' in thinking_buffer or
                                    any(c in thinking_buffer for c in ['。', '，', '！', '？', '.', ',', '!', '?', '：', ':', '；', ';', ' '])
                                )
                                
                                if should_send:
                                    # Clean and send batched chunk
                                    cleaned_chunk = self._clean_thinking(thinking_buffer)
                                    if cleaned_chunk and thinking_callback:
                                        thinking_callback(cleaned_chunk)
                                    thinking_buffer = ""  # Clear buffer
                            
                            last_raw_content = raw_content
                            
                            # Periodically allow event processing (every 20 chunks)
                            # This helps prevent UI freezing during long streaming responses
                            if chunk_processed % 20 == 0:
                                try:
                                    import time
                                    time.sleep(0.001)  # 1ms sleep to allow event processing
                                except:
                                    pass
            
            # Send any remaining buffered thinking
            if thinking_buffer and not action_started and thinking_callback:
                cleaned_chunk = self._clean_thinking(thinking_buffer)
                if cleaned_chunk:
                    thinking_callback(cleaned_chunk)

            # Parse final response
            thinking, action = self._parse_response(raw_content)

            return ModelResponse(thinking=thinking, action=action, raw_content=raw_content)

        except Exception as e:
            # Parse and format error information
            error_info = self._parse_error(e)
            raise Exception(error_info) from e

    def _parse_error(self, error: Exception) -> str:
        """
        Parse error exception and return formatted error message.

        Args:
            error: The exception that occurred.

        Returns:
            Formatted error message string.
        """
        error_type = type(error).__name__
        error_str = str(error)

        # Try to extract error details from OpenAI exceptions
        if hasattr(error, "response") and error.response is not None:
            try:
                error_body = error.response.json() if hasattr(error.response, "json") else {}
                error_code = error_body.get("error", {}).get("code", "")
                error_message = error_body.get("error", {}).get("message", error_str)
                error_type_api = error_body.get("error", {}).get("type", "")
                request_id = error_body.get("request_id", "")

                # Format error message
                parts = [f"Error code: {error.response.status_code}"]
                if error_code:
                    parts.append(f"Code: {error_code}")
                if error_type_api:
                    parts.append(f"Type: {error_type_api}")
                if error_message:
                    parts.append(f"Message: {error_message}")
                if request_id:
                    parts.append(f"Request ID: {request_id}")

                return " - ".join(parts)
            except Exception:
                pass

        # For connection errors, provide more helpful message
        if "Connection" in error_type or "connect" in error_str.lower():
            if "127.0.0.1" in error_str or "localhost" in error_str.lower():
                return (
                    f"连接错误: 无法连接到本地服务\n"
                    f"详细信息: {error_str}\n\n"
                    f"请检查:\n"
                    f"1. Base URL 是否正确（应使用 ModelScope 或智谱 BigModel 的地址）\n"
                    f"2. 如果确实需要本地服务，请确保服务正在运行"
                )
            else:
                return (
                    f"连接错误: 无法连接到模型服务\n"
                    f"详细信息: {error_str}\n\n"
                    f"请检查:\n"
                    f"1. Base URL 是否正确\n"
                    f"2. 网络连接是否正常\n"
                    f"3. 模型服务是否正在运行"
                )

        # For authentication errors
        if "401" in error_str or "unauthorized" in error_str.lower() or "authentication" in error_str.lower():
            return (
                f"认证错误: API Key 无效或已过期\n"
                f"详细信息: {error_str}\n\n"
                f"请检查:\n"
                f"1. API Key 是否正确\n"
                f"2. API Key 是否已过期\n"
                f"3. 请参考 使用必读.txt 重新获取 API Key"
            )

        # Default error format
        return f"{error_type}: {error_str}"

    def _clean_thinking(self, text: str) -> str:
        """
        Clean thinking text by removing code-like patterns.
        
        Args:
            text: Raw thinking text that may contain code fragments
            
        Returns:
            Cleaned thinking text without code patterns
        """
        if not text:
            return text
        
        # Remove action markers and any content after them
        cleaned = text
        
        # Remove action markers if they appear (case-insensitive)
        # Check for "do(action" pattern (with or without "=")
        if "do(action" in cleaned.lower():
            # Find the position (case-insensitive)
            pos = cleaned.lower().find("do(action")
            cleaned = cleaned[:pos].rstrip()
        
        # Check for "finish(message" pattern (with or without "=")
        if "finish(message" in cleaned.lower():
            # Find the position (case-insensitive)
            pos = cleaned.lower().find("finish(message")
            cleaned = cleaned[:pos].rstrip()
        
        # Remove any lines that contain code patterns
        lines = cleaned.split('\n')
        cleaned_lines = []
        for line in lines:
            # Skip lines that contain code markers
            line_lower = line.lower()
            if "do(action" in line_lower or "finish(message" in line_lower:
                # If line contains marker, only keep part before it
                if "do(action" in line_lower:
                    pos = line_lower.find("do(action")
                    line = line[:pos].rstrip()
                if "finish(message" in line_lower:
                    pos = line_lower.find("finish(message")
                    line = line[:pos].rstrip()
                # Only add if there's meaningful content
                if line.strip() and not line.strip().startswith(('{', '}', '[', ']')):
                    cleaned_lines.append(line)
            else:
                # Check if line looks like code (starts with code-like characters)
                stripped = line.strip()
                if stripped and not stripped.startswith(('{', '}', '[', ']', 'do', 'finish')):
                    cleaned_lines.append(line)
        
        cleaned = '\n'.join(cleaned_lines).rstrip()
        
        # Remove any trailing incomplete code patterns
        # Remove trailing code-like characters
        while cleaned and cleaned[-1] in ['{', '}', '[', ']', '=', '(', ')', ',', ';']:
            cleaned = cleaned[:-1].rstrip()
        
        # Remove trailing code keywords
        code_keywords = ["do(action", "finish(message", "do", "finish", "action", "message"]
        for keyword in code_keywords:
            if cleaned.lower().endswith(keyword.lower()):
                cleaned = cleaned[:-len(keyword)].rstrip()
                break
        
        # Remove any remaining code-like patterns at the end
        # Look for patterns like "do(action", "finish(message" anywhere in the text
        if "do(action" in cleaned.lower():
            pos = cleaned.lower().rfind("do(action")
            cleaned = cleaned[:pos].rstrip()
        if "finish(message" in cleaned.lower():
            pos = cleaned.lower().rfind("finish(message")
            cleaned = cleaned[:pos].rstrip()
        
        return cleaned

    def _parse_response(self, content: str) -> tuple[str, str]:
        """
        Parse the model response into thinking and action parts.

        Parsing rules:
        1. If content contains 'finish(message=', everything before is thinking,
           everything from 'finish(message=' onwards is action.
        2. If rule 1 doesn't apply but content contains 'do(action=',
           everything before is thinking, everything from 'do(action=' onwards is action.
        3. Fallback: If content contains '<answer>', use legacy parsing with XML tags.
        4. Otherwise, return empty thinking and full content as action.

        Args:
            content: Raw response content.

        Returns:
            Tuple of (thinking, action).
        """
        # Rule 1: Check for finish(message=
        if "finish(message=" in content:
            parts = content.split("finish(message=", 1)
            thinking = parts[0].strip()
            action = "finish(message=" + parts[1]
            return thinking, action

        # Rule 2: Check for do(action=
        if "do(action=" in content:
            parts = content.split("do(action=", 1)
            thinking = parts[0].strip()
            action = "do(action=" + parts[1]
            return thinking, action

        # Rule 3: Fallback to legacy XML tag parsing
        if "<answer>" in content:
            parts = content.split("<answer>", 1)
            thinking = parts[0].replace("<think>", "").replace("</think>", "").strip()
            action = parts[1].replace("</answer>", "").strip()
            return thinking, action

        # Rule 4: No markers found, return content as action
        return "", content


class MessageBuilder:
    """Helper class for building conversation messages."""

    @staticmethod
    def create_system_message(content: str) -> dict[str, Any]:
        """Create a system message."""
        return {"role": "system", "content": content}

    @staticmethod
    def create_user_message(
        text: str, image_base64: str | None = None
    ) -> dict[str, Any]:
        """
        Create a user message with optional image.

        Args:
            text: Text content.
            image_base64: Optional base64-encoded image.

        Returns:
            Message dictionary.
        """
        content = []

        if image_base64:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                }
            )

        content.append({"type": "text", "text": text})

        return {"role": "user", "content": content}

    @staticmethod
    def create_assistant_message(content: str) -> dict[str, Any]:
        """Create an assistant message."""
        return {"role": "assistant", "content": content}

    @staticmethod
    def remove_images_from_message(message: dict[str, Any]) -> dict[str, Any]:
        """
        Remove image content from a message to save context space.

        Args:
            message: Message dictionary.

        Returns:
            Message with images removed.
        """
        if isinstance(message.get("content"), list):
            message["content"] = [
                item for item in message["content"] if item.get("type") == "text"
            ]
        return message

    @staticmethod
    def build_screen_info(current_app: str, **extra_info) -> str:
        """
        Build screen info string for the model.

        Args:
            current_app: Current app name.
            **extra_info: Additional info to include.

        Returns:
            JSON string with screen info.
        """
        info = {"current_app": current_app, **extra_info}
        return json.dumps(info, ensure_ascii=False)
