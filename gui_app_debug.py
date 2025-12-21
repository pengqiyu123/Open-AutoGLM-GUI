"""
GUI应用启动脚本 - 带详细日志输出
用于调试和监控应用运行状态
"""

import sys
import logging
from pathlib import Path

# 配置详细的日志输出到终端
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s.%(funcName)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 设置各个模块的日志级别
logging.getLogger('gui.utils.task_logger').setLevel(logging.DEBUG)
logging.getLogger('gui.widgets.task_review').setLevel(logging.DEBUG)
logging.getLogger('gui.widgets.data_storage').setLevel(logging.DEBUG)
logging.getLogger('gui.main_window').setLevel(logging.DEBUG)
logging.getLogger('gui.utils.agent_runner').setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from PyQt5.QtWidgets import QApplication
from gui.main_window import MainWindow

def main():
    """启动GUI应用"""
    logger.info("=" * 80)
    logger.info("启动 Open-AutoGLM GUI (调试模式)")
    logger.info("=" * 80)
    
    logger.info("创建 QApplication...")
    app = QApplication(sys.argv)
    
    logger.info("创建主窗口...")
    window = MainWindow()
    
    logger.info("显示主窗口...")
    window.show()
    
    logger.info("=" * 80)
    logger.info("GUI 已启动，等待用户操作...")
    logger.info("所有操作都会输出详细日志到终端")
    logger.info("=" * 80)
    
    # 启动事件循环
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
