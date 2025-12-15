#!/usr/bin/env python3
"""
简单的 API 测试工具 - GUI 版本
"""

import sys
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
)


class TestWorker(QThread):
    """后台测试线程"""
    finished = pyqtSignal(bool, str)  # 成功标志, 消息

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    def run(self):
        """执行测试"""
        try:
            from openai import OpenAI
            import requests

            # 创建客户端
            client = OpenAI(
                base_url='https://api-inference.modelscope.cn/v1',
                api_key=self.api_key,
            )

            # 获取测试消息
            json_url = "https://modelscope.oss-cn-beijing.aliyuncs.com/phone_agent_test.json"
            response_json = requests.get(json_url, timeout=10)
            messages = response_json.json()

            # 调用 API
            response = client.chat.completions.create(
                model='ZhipuAI/AutoGLM-Phone-9B',
                messages=messages,
                temperature=0.0,
                max_tokens=1024,
                stream=False,
            )

            content = response.choices[0].message.content
            self.finished.emit(True, content)

        except Exception as e:
            error_msg = str(e)
            self.finished.emit(False, error_msg)


class TestWindow(QWidget):
    """测试窗口"""

    def __init__(self):
        super().__init__()
        self.test_thread = None
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("API 测试工具")
        self.setMinimumSize(600, 500)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # API Key 输入
        key_label = QLabel("API Key:")
        key_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(key_label)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("请输入 ModelScope API Key")
        self.key_input.setMinimumHeight(35)
        layout.addWidget(self.key_input)

        # 测试按钮
        self.test_btn = QPushButton("开始测试")
        self.test_btn.setMinimumHeight(40)
        self.test_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14pt;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """
        )
        self.test_btn.clicked.connect(self.start_test)
        layout.addWidget(self.test_btn)

        # 结果显示
        result_label = QLabel("测试结果:")
        result_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(result_label)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("测试结果将显示在这里...")
        self.result_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10pt;
            }
        """
        )
        layout.addWidget(self.result_text)

        self.setLayout(layout)

    def start_test(self):
        """开始测试"""
        api_key = self.key_input.text().strip()

        if not api_key:
            self.result_text.setText("❌ 错误: 请输入 API Key")
            self.result_text.setStyleSheet(
                """
                QTextEdit {
                    background-color: #ffebee;
                    border: 1px solid #f44336;
                    border-radius: 5px;
                    padding: 10px;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 10pt;
                }
            """
            )
            return

        # 禁用按钮
        self.test_btn.setEnabled(False)
        self.test_btn.setText("测试中...")
        self.result_text.setText("⏳ 正在测试，请稍候...")
        self.result_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #fff3e0;
                border: 1px solid #ff9800;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10pt;
            }
        """
        )

        # 启动测试线程
        self.test_thread = TestWorker(api_key)
        self.test_thread.finished.connect(self.on_test_finished)
        self.test_thread.start()

    def on_test_finished(self, success: bool, message: str):
        """测试完成回调"""
        # 恢复按钮
        self.test_btn.setEnabled(True)
        self.test_btn.setText("开始测试")

        # 显示结果
        if success:
            self.result_text.setText(f"✅ 测试成功！\n\n模型响应:\n{'-'*50}\n{message}")
            self.result_text.setStyleSheet(
                """
                QTextEdit {
                    background-color: #e8f5e9;
                    border: 1px solid #4CAF50;
                    border-radius: 5px;
                    padding: 10px;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 10pt;
                }
            """
            )
        else:
            self.result_text.setText(f"❌ 测试失败！\n\n错误信息:\n{'-'*50}\n{message}")
            self.result_text.setStyleSheet(
                """
                QTextEdit {
                    background-color: #ffebee;
                    border: 1px solid #f44336;
                    border-radius: 5px;
                    padding: 10px;
                    font-family: 'Consolas', 'Monaco', monospace;
                    font-size: 10pt;
                }
            """
            )

        # 清理线程
        if self.test_thread:
            self.test_thread.quit()
            self.test_thread.wait()
            self.test_thread = None


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用 Fusion 样式

    window = TestWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

