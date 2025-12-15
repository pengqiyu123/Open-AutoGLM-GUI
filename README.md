# Open-AutoGLM-GUI 备份版

本文档为当前仓库定制说明，原始 README 已移除，请按此文档使用。

## 项目简介
- 基于 Open-AutoGLM 的备份与二次开发基线，便于本地验证、演示和后续移植。
- 包含 Python 版 Phone Agent（多模态屏幕理解 + ADB 控制）及简易 PyQt5 GUI 启动入口。
- 适合作为 Android 端移植或功能扩展的参考实现。

## 主要组成
- `phone_agent/`：核心代理、动作处理、ADB/截图/输入封装、配置与模型客户端。
- `gui/`：简易 PyQt5 窗口与工具；`gui_app.py` 为入口。
- `scripts/`：部署/检查脚本与示例消息。
- `resources/`：示例截图与隐私/说明文档。
- `build_gui.*`：GUI 打包相关脚本和 spec。

## 快速开始
```bash
# 安装依赖
pip install -r requirements.txt

# 运行示例 GUI
python gui_app.py

# 直接运行核心 agent（示例）
python main.py
```

## 注意事项
- 默认使用 ADB 控制真实或模拟 Android 设备，请确保已开启开发者模式与 USB 调试。
- 请遵守相关法律法规，仅用于学习与研究场景。

## 致谢与引用
本项目的设计思路与部分实现借鉴自原项目 **Open-AutoGLM**：
- https://github.com/zai-org/Open-AutoGLM

保留 MIT 许可证（见 `LICENSE`）。
