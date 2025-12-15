"""System checker utilities for GUI application."""

import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from openai import OpenAI

from phone_agent.adb import list_devices


@dataclass
class CheckResult:
    """Result of a system check."""

    success: bool
    message: str
    details: Optional[str] = None
    solution: Optional[str] = None


def check_adb_installation() -> CheckResult:
    """
    Check if ADB is installed and accessible.

    Returns:
        CheckResult with status and message.
    """
    if shutil.which("adb") is None:
        return CheckResult(
            success=False,
            message="ADB 未安装或不在 PATH 中",
            details="ADB is not installed or not in PATH.",
            solution="安装 Android SDK Platform Tools:\n"
            "- macOS: brew install android-platform-tools\n"
            "- Linux: sudo apt install android-tools-adb\n"
            "- Windows: 从 https://developer.android.com/studio/releases/platform-tools 下载",
        )

    try:
        result = subprocess.run(
            ["adb", "version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            version_line = result.stdout.strip().split("\n")[0]
            return CheckResult(
                success=True, message=f"ADB 已安装 ({version_line})", details=version_line
            )
        else:
            return CheckResult(
                success=False,
                message="ADB 命令执行失败",
                details="ADB command failed to run.",
            )
    except FileNotFoundError:
        return CheckResult(
            success=False, message="ADB 命令未找到", details="ADB command not found."
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            success=False, message="ADB 命令超时", details="ADB command timed out."
        )
    except Exception as e:
        return CheckResult(
            success=False, message=f"ADB 检查出错: {e}", details=str(e)
        )


def check_devices() -> CheckResult:
    """
    Check if any devices are connected.

    Returns:
        CheckResult with status and device list.
    """
    try:
        devices = list_devices()
        connected_devices = [d for d in devices if d.status == "device"]

        if not connected_devices:
            return CheckResult(
                success=False,
                message="未检测到设备",
                details="No devices connected.",
                solution="1. 在 Android 设备上启用 USB 调试\n"
                "2. 通过 USB 连接并授权连接\n"
                "3. 或远程连接: python main.py --connect <ip>:<port>",
            )

        device_ids = [d.device_id for d in connected_devices]
        device_info = "\n".join(
            [
                f"  - {d.device_id} ({d.connection_type.value})"
                for d in connected_devices
            ]
        )
        return CheckResult(
            success=True,
            message=f"检测到 {len(connected_devices)} 个设备",
            details=f"Connected devices:\n{device_info}",
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            success=False, message="设备检查超时", details="ADB command timed out."
        )
    except Exception as e:
        return CheckResult(
            success=False, message=f"设备检查出错: {e}", details=str(e)
        )


def check_adb_keyboard(device_id: Optional[str] = None) -> CheckResult:
    """
    Check if ADB Keyboard is installed on the device.

    Args:
        device_id: Optional device ID for multi-device setups.
                  For WiFi/remote connections, device_id should be provided.

    Returns:
        CheckResult with status and message.
    """
    # Check if device is selected (especially important for WiFi/remote connections)
    if not device_id:
        # Try to get first connected device
        try:
            devices = list_devices()
            connected_devices = [d for d in devices if d.status == "device"]
            if not connected_devices:
                return CheckResult(
                    success=False,
                    message="未选择设备",
                    details="No device selected or connected.",
                    solution="1. 请先在设备列表中选择一个设备\n"
                    "2. 如果是无线连接，请确保设备已连接\n"
                    "3. 无线连接时建议先选择设备再检查",
                )
            # Use first connected device if no device_id provided
            device_id = connected_devices[0].device_id
        except Exception:
            return CheckResult(
                success=False,
                message="无法获取设备列表",
                details="Cannot get device list.",
                solution="1. 检查 ADB 连接\n"
                "2. 确保至少有一个设备已连接\n"
                "3. 如果是无线连接，请先连接设备",
            )

    adb_prefix = ["adb"]
    if device_id:
        adb_prefix.extend(["-s", device_id])

    try:
        # Increased timeout for WiFi/remote connections (20 seconds)
        result = subprocess.run(
            adb_prefix + ["shell", "ime", "list", "-s"],
            capture_output=True,
            text=True,
            timeout=20,  # Increased from 10 to 20 seconds for WiFi connections
        )
        
        # Check return code
        if result.returncode != 0:
            error_output = result.stderr.strip() or result.stdout.strip()
            if "device not found" in error_output.lower() or "offline" in error_output.lower():
                return CheckResult(
                    success=False,
                    message="设备未连接或已离线",
                    details=f"Device not found or offline: {error_output}",
                    solution="1. 检查设备连接状态\n"
                    "2. 如果是无线连接，请重新连接设备\n"
                    "3. 尝试: adb devices 查看设备状态",
                )
            else:
                return CheckResult(
                    success=False,
                    message="ADB 命令执行失败",
                    details=f"ADB command failed: {error_output}",
                    solution="1. 检查设备连接\n"
                    "2. 确认设备已授权 ADB 调试\n"
                    "3. 如果是无线连接，检查网络连接",
                )
        
        ime_list = result.stdout.strip()
        
        if not ime_list:
            return CheckResult(
                success=False,
                message="无法获取输入法列表",
                details="Cannot get IME list from device.",
                solution="1. 检查设备连接是否正常\n"
                "2. 如果是无线连接，可能需要更长时间\n"
                "3. 尝试重新连接设备",
            )

        if "com.android.adbkeyboard/.AdbIME" in ime_list:
            return CheckResult(
                success=True,
                message="ADB Keyboard 已安装",
                details=f"ADB Keyboard is installed on device: {device_id}",
            )
        else:
            # Try alternative detection method: check if package is installed
            try:
                alt_result = subprocess.run(
                    adb_prefix + ["shell", "pm", "list", "packages", "|", "grep", "adbkeyboard"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if "adbkeyboard" in alt_result.stdout.lower():
                    return CheckResult(
                        success=True,
                        message="ADB Keyboard 已安装（但可能未启用）",
                        details="ADB Keyboard package found but may not be enabled.",
                        solution="1. 在设置中启用 ADB Keyboard:\n"
                        "   设置 > 系统 > 语言和输入法 > 虚拟键盘\n"
                        "2. 确保 ADB Keyboard 已启用",
                    )
            except Exception:
                pass  # Fall through to "not installed" message
            
            return CheckResult(
                success=False,
                message="ADB Keyboard 未安装",
                details=f"ADB Keyboard is not installed on device: {device_id}",
                solution="1. 下载 ADB Keyboard APK:\n"
                "   https://github.com/senzhk/ADBKeyBoard/blob/master/ADBKeyboard.apk\n"
                "2. 安装到设备:\n"
                f"   adb -s {device_id} install ADBKeyboard.apk\n"
                "3. 在设置中启用: 设置 > 系统 > 语言和输入法 > 虚拟键盘",
            )
    except subprocess.TimeoutExpired:
        return CheckResult(
            success=False,
            message="ADB Keyboard 检查超时",
            details=f"ADB command timed out after 20 seconds (device: {device_id})",
            solution="1. 如果是无线连接，网络可能较慢\n"
            "2. 检查网络连接质量\n"
            "3. 尝试重新连接设备\n"
            "4. 如果问题持续，可以手动确认 ADB Keyboard 是否已安装",
        )
    except FileNotFoundError:
        return CheckResult(
            success=False,
            message="ADB 命令未找到",
            details="ADB command not found.",
            solution="1. 检查 ADB 是否已安装\n"
            "2. 确认 ADB 在系统 PATH 中",
        )
    except Exception as e:
        error_msg = str(e)
        # Check for specific connection errors
        if "device not found" in error_msg.lower() or "offline" in error_msg.lower():
            return CheckResult(
                success=False,
                message="设备未连接或已离线",
                details=f"Device connection error: {error_msg}",
                solution="1. 检查设备连接状态\n"
                "2. 如果是无线连接，请重新连接\n"
                "3. 尝试: adb devices 查看设备状态",
            )
        elif "connection" in error_msg.lower() or "connect" in error_msg.lower():
            return CheckResult(
                success=False,
                message="无法连接到设备",
                details=f"Connection error: {error_msg}",
                solution="1. 检查设备连接\n"
                "2. 如果是无线连接，检查网络连接\n"
                "3. 确认设备 IP 和端口正确",
            )
        else:
            return CheckResult(
                success=False,
                message=f"ADB Keyboard 检查出错: {error_msg}",
                details=f"Error: {error_msg}",
                solution="1. 检查设备连接\n"
                "2. 确认设备已授权 ADB 调试\n"
                "3. 如果是无线连接，可能需要更长时间",
            )


def check_model_api(base_url: str, model_name: str, api_key: str = "EMPTY") -> CheckResult:
    """
    Check if the model API is accessible using simple test like test_api.py.

    Args:
        base_url: The API base URL
        model_name: The model name to check
        api_key: The API key for authentication

    Returns:
        CheckResult with status and message.
    """
    if not base_url or not base_url.strip():
        return CheckResult(
            success=False,
            message="Base URL 未设置",
            details="Base URL is not set.",
        )

    try:
        parsed = urlparse(base_url)
        if not parsed.scheme or not parsed.netloc:
            return CheckResult(
                success=False,
                message="Base URL 格式无效",
                details=f"Invalid URL format: {base_url}",
            )

        # Use simple test like test_api.py (exact same implementation)
        import requests
        
        # Create client with reasonable timeout (30 seconds for GUI responsiveness)
        # test_api.py doesn't set timeout, but for GUI we need reasonable timeout
        client = OpenAI(base_url=base_url, api_key=api_key, timeout=30.0)
        
        # Try to get test messages from ModelScope (exact same as test_api.py)
        try:
            json_url = "https://modelscope.oss-cn-beijing.aliyuncs.com/phone_agent_test.json"
            response_json = requests.get(json_url, timeout=10)  # Same as test_api.py
            messages = response_json.json()
        except Exception:
            # If can't load test messages, use simple default (same as test_api.py fallback)
            messages = [
                {
                    "role": "system",
                    "content": "你是一个智能助手。",
                },
                {
                    "role": "user",
                    "content": "请简单介绍一下你自己。",
                },
            ]

        # Test API with simple chat completion (exact same as test_api.py)
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.0,
            max_tokens=1024,
            stream=False,
        )

        content = response.choices[0].message.content
        
        # Test streaming response
        streaming_supported = False
        streaming_test_details = ""
        try:
            stream = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.0,
                max_tokens=100,  # Use smaller token limit for test
                stream=True,
            )
            
            chunk_count = 0
            first_chunk_time = None
            import time
            start_time = time.time()
            
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        chunk_count += 1
                        if first_chunk_time is None:
                            first_chunk_time = time.time() - start_time
                        # Only check first few chunks to avoid long test
                        if chunk_count >= 5:
                            break
            
            if chunk_count > 0:
                streaming_supported = True
                streaming_test_details = f"\n流式响应: ✅ 支持 (收到 {chunk_count} 个chunk, 首个chunk延迟: {first_chunk_time:.2f}秒)"
            else:
                streaming_test_details = "\n流式响应: ⚠️ 未收到chunk"
        except Exception as stream_error:
            streaming_test_details = f"\n流式响应: ❌ 不支持 ({str(stream_error)[:50]})"
        
        details = f"Connected to {base_url}\nModel: {model_name}\n测试响应: {content[:100]}..." if len(content) > 100 else f"Connected to {base_url}\nModel: {model_name}\n测试响应: {content}"
        details += streaming_test_details
        
        message = "模型 API 连接成功"
        if not streaming_supported:
            message += " (流式响应可能不支持)"
        
        return CheckResult(
            success=True,
            message=message,
            details=details,
        )
    except Exception as e:
        error_msg = str(e)
        
        # Check for authentication errors (401)
        if "401" in error_msg or "unauthorized" in error_msg.lower() or "令牌已过期" in error_msg or "验证不正确" in error_msg:
            return CheckResult(
                success=False,
                message="API Key 已过期或无效",
                details=f"Authentication failed: {error_msg}",
                solution="1. 检查 API Key 是否正确\n"
                "2. 确认 API Key 是否已过期\n"
                "3. 在对应平台重新申请 API Key\n"
                "   - ModelScope: https://modelscope.cn\n"
                "   - 智谱 BigModel: https://open.bigmodel.cn",
            )
        
        # Check for connection errors
        if "Connection refused" in error_msg or "Connection error" in error_msg or "cannot connect" in error_msg.lower() or "connect call failed" in error_msg.lower():
            # Check if it's localhost/127.0.0.1
            if "127.0.0.1" in error_msg or "localhost" in error_msg.lower():
                return CheckResult(
                    success=False,
                    message="无法连接到本地服务",
                    details=f"Cannot connect to local service: {error_msg}",
                    solution="1. 检查模型配置中的 Base URL\n"
                    "2. 确保使用正确的服务地址：\n"
                    "   - ModelScope: https://api-inference.modelscope.cn/v1\n"
                    "   - 智谱 BigModel: https://open.bigmodel.cn/api/paas/v4\n"
                    "3. 如果确实需要本地服务，请确保服务正在运行",
                )
            else:
                return CheckResult(
                    success=False,
                    message=f"无法连接到 {base_url}",
                    details=f"Cannot connect to {base_url}: {error_msg}",
                    solution="1. 检查模型服务器是否运行\n"
                    "2. 验证 Base URL 是否正确\n"
                    "3. 检查网络连接",
                )
        elif "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
            return CheckResult(
                success=False,
                message=f"连接到 {base_url} 超时",
                details=f"Connection to {base_url} timed out",
                solution="1. 检查网络连接\n" "2. 验证服务器是否响应",
            )
        elif (
            "Name or service not known" in error_msg
            or "nodename nor servname" in error_msg
        ):
            return CheckResult(
                success=False,
                message="无法解析主机名",
                details="Cannot resolve hostname",
                solution="1. 检查 URL 是否正确\n" "2. 验证 DNS 设置",
            )
        elif "404" in error_msg or "not found" in error_msg.lower():
            return CheckResult(
                success=False,
                message=f"模型 '{model_name}' 未找到",
                details=f"Model not found: {error_msg}",
                solution=f"1. 检查模型名称 '{model_name}' 是否正确\n"
                "2. 确认该模型是否在可用模型列表中",
            )
        elif "500" in error_msg or "internal error" in error_msg.lower():
            # Check if it's trying to connect to localhost
            if "127.0.0.1" in error_msg or "localhost" in error_msg.lower():
                return CheckResult(
                    success=False,
                    message="本地服务连接失败",
                    details=f"Local service connection failed: {error_msg}",
                    solution="1. 检查模型配置中的 Base URL\n"
                    "2. 确保使用正确的服务地址：\n"
                    "   - ModelScope: https://api-inference.modelscope.cn/v1\n"
                    "   - 智谱 BigModel: https://open.bigmodel.cn/api/paas/v4\n"
                    "3. 如果确实需要本地服务，请确保服务正在运行",
                )
            else:
                return CheckResult(
                    success=False,
                    message="模型服务内部错误",
                    details=f"Model service error: {error_msg}",
                    solution="1. 检查 Base URL 和 Model 名称是否正确\n"
                    "2. API Key 是否有效\n"
                    "3. 模型服务是否正常运行",
                )
        else:
            return CheckResult(
                success=False, message=f"API 检查出错: {error_msg}", details=error_msg
            )


def run_all_checks(
    base_url: str = "",
    model_name: str = "",
    api_key: str = "EMPTY",
    device_id: Optional[str] = None,
) -> dict[str, CheckResult]:
    """
    Run all system checks and return results.

    Args:
        base_url: Model API base URL
        model_name: Model name
        api_key: API key
        device_id: Optional device ID

    Returns:
        Dictionary mapping check names to CheckResult objects.
    """
    results = {}

    # Check ADB installation
    results["adb"] = check_adb_installation()

    # Check devices (only if ADB is installed)
    if results["adb"].success:
        results["devices"] = check_devices()

        # Check ADB Keyboard (only if devices are connected)
        if results["devices"].success:
            results["keyboard"] = check_adb_keyboard(device_id)
    else:
        results["devices"] = CheckResult(
            success=False, message="跳过设备检查（ADB 未安装）", details="Skipped"
        )
        results["keyboard"] = CheckResult(
            success=False, message="跳过键盘检查（ADB 未安装）", details="Skipped"
        )

    # Check model API
    if base_url and model_name:
        results["model_api"] = check_model_api(base_url, model_name, api_key)
    else:
        results["model_api"] = CheckResult(
            success=False,
            message="跳过模型 API 检查（未配置）",
            details="Skipped - Base URL or Model not set",
        )

    return results

