---
inclusion: always
---

# Open-AutoGLM GUI 电脑版项目知识

本文档记录 Open-AutoGLM GUI 电脑版项目的特定配置、约定和常见问题解决方案。

## 项目概述

Open-AutoGLM 是一个基于 GLM 大模型的手机自动化控制系统，GUI 电脑版提供图形界面来控制 Android 设备。

## 项目结构

```
Open-AutoGLM-main/
├── gui/                          # GUI 相关代码
├── phone_agent/                  # 手机代理核心逻辑
├── resources/                    # 资源文件
├── scripts/                      # 脚本工具
├── examples/                     # 示例代码
├── logs/                         # 日志文件
├── dist/                         # 构建输出目录
├── build/                        # 构建临时文件
├── gui_app.py                    # GUI 主程序
├── main.py                       # 命令行主程序
├── requirements.txt              # Python 依赖
├── build_gui.spec                # PyInstaller 配置
├── build_gui_with_progress.bat   # 构建脚本（带进度）
├── build_gui.bat                 # 构建脚本
└── GUI.exe                       # 构建后的可执行文件
```

## 关键文件说明

### gui_app.py
- GUI 应用的主入口
- 使用 tkinter 或其他 GUI 框架
- 包含界面布局和事件处理

### main.py
- 命令行版本的主入口
- 提供非 GUI 模式的功能

### requirements.txt
主要依赖包：
```
# 核心依赖
zhipuai          # GLM API 客户端
adbutils         # ADB 工具库
Pillow           # 图像处理
requests         # HTTP 请求

# GUI 依赖
tkinter          # GUI 框架（通常内置）
# 或其他 GUI 框架

# 构建依赖
pyinstaller      # 打包工具
```

### build_gui.spec
PyInstaller 配置文件，包含：
- 入口文件
- 隐藏导入（hiddenimports）
- 资源文件（datas）
- 排除模块（excludes）
- 图标和版本信息

## 构建系统

### Windows 构建命令

```cmd
REM 方式1：使用带进度的构建脚本（推荐）
build_gui_with_progress.bat

REM 方式2：使用标准构建脚本
build_gui.bat

REM 方式3：直接使用 PyInstaller
pyinstaller build_gui.spec
```

### 构建输出

- **dist/GUI.exe** - 最终的可执行文件
- **build/** - 临时构建文件（可删除）
- **GUI.exe** - 复制到根目录的可执行文件

### 常见构建问题

#### 问题 1: ModuleNotFoundError
**原因:** 某些模块未被 PyInstaller 自动检测

**解决方案:**
在 build_gui.spec 中添加到 hiddenimports：
```python
hiddenimports=[
    'zhipuai',
    'adbutils',
    'PIL._tkinter_finder',
    # 添加其他缺失的模块
]
```

#### 问题 2: 资源文件未打包
**原因:** 资源文件路径未配置

**解决方案:**
在 build_gui.spec 中添加到 datas：
```python
datas=[
    ('resources', 'resources'),
    ('gui', 'gui'),
]
```

#### 问题 3: exe 文件过大
**原因:** 打包了不必要的依赖

**解决方案:**
在 build_gui.spec 中添加到 excludes：
```python
excludes=[
    'matplotlib',
    'numpy',
    'pandas',
    # 其他不需要的大型库
]
```

## ADB 配置

### ADB 工具位置
- 项目根目录的 `platform-tools` 文件夹
- 或系统环境变量中的 ADB

### ADB 常用命令

```cmd
REM 查看设备
adb devices

REM 安装应用
adb install app.apk

REM 卸载应用
adb uninstall com.package.name

REM 截图
adb shell screencap -p /sdcard/screen.png
adb pull /sdcard/screen.png

REM 输入文本
adb shell input text "hello"

REM 点击坐标
adb shell input tap 100 200

REM 滑动
adb shell input swipe 100 200 300 400

REM 查看日志
adb logcat
```

## API 配置

### GLM API
- 需要在智谱 AI 平台申请 API key
- 配置方式：环境变量或配置文件
- API 文档：https://open.bigmodel.cn/

### API 调用示例
```python
from zhipuai import ZhipuAI

client = ZhipuAI(api_key="your_api_key")
response = client.chat.completions.create(
    model="glm-4",
    messages=[
        {"role": "user", "content": "你好"}
    ]
)
```

## 日志系统

### 日志位置
- `logs/` 目录
- 按日期或会话分类

### 日志级别
- DEBUG: 详细调试信息
- INFO: 一般信息
- WARNING: 警告信息
- ERROR: 错误信息
- CRITICAL: 严重错误

## 已知问题与解决方案

### 问题 1: GUI 启动慢
**现象:** GUI.exe 启动需要很长时间

**解决方案:**
1. 使用 --onefile 模式会慢，考虑使用 --onedir
2. 优化导入，延迟加载大型库
3. 添加启动画面提示用户等待

### 问题 2: 中文显示乱码
**现象:** GUI 中中文显示为方块或乱码

**解决方案:**
1. 确保源代码使用 UTF-8 编码
2. 在代码中指定字体
3. 打包时包含中文字体文件

### 问题 3: ADB 连接不稳定
**现象:** 设备频繁断开连接

**解决方案:**
1. 使用质量好的 USB 线
2. 禁用 USB 选择性暂停
3. 添加自动重连机制
4. 使用 WiFi ADB（需要设备支持）

### 问题 4: API 调用超时
**现象:** API 请求经常超时

**解决方案:**
1. 增加超时时间
2. 添加重试机制
3. 检查网络连接
4. 使用异步调用避免阻塞 GUI

## 开发环境设置

### Python 环境
- 推荐版本: Python 3.8 - 3.11
- 使用虚拟环境隔离依赖

### 安装依赖
```cmd
REM 创建虚拟环境
python -m venv venv

REM 激活虚拟环境
venv\Scripts\activate

REM 安装依赖
pip install -r requirements.txt
```

### 开发工具
- IDE: PyCharm, VS Code
- 调试: Python Debugger
- 版本控制: Git

## 测试流程

### 功能测试
1. 测试 GUI 界面显示
2. 测试设备连接
3. 测试 API 调用
4. 测试自动化任务执行

### 构建测试
1. 清理旧的构建文件
2. 执行构建脚本
3. 测试 exe 文件运行
4. 测试所有功能正常

## 发布检查清单

- [ ] 更新版本号
- [ ] 测试所有主要功能
- [ ] 检查日志输出正常
- [ ] 验证 API 连接
- [ ] 测试 ADB 连接
- [ ] 检查资源文件完整
- [ ] 更新 README 和文档
- [ ] 清理临时文件
- [ ] 构建最终版本
- [ ] 测试最终 exe 文件

## 文档索引

项目包含以下重要文档：
- `README.md` - 项目概述和使用说明
- `README_en.md` - 英文版说明
- `README_coding_agent.md` - 编程代理说明
- `使用必读.txt` - 使用注意事项
- `打开dist使用.txt` - dist 目录使用说明
- `项目后续优化思路.md` - 优化计划

## 代码风格

- 使用 Python PEP 8 风格
- 函数和变量使用小写加下划线
- 类名使用大驼峰命名
- 添加适当的注释和文档字符串
- 使用类型提示（Type Hints）

## 性能优化建议

1. **启动优化**
   - 延迟加载非必需模块
   - 使用多线程加载资源
   - 添加启动缓存

2. **运行优化**
   - 使用异步 I/O
   - 缓存频繁访问的数据
   - 优化图像处理

3. **内存优化**
   - 及时释放大对象
   - 使用生成器代替列表
   - 限制日志文件大小

## 安全注意事项

- 不要在代码中硬编码 API key
- 使用环境变量或加密配置文件
- 验证用户输入
- 限制 ADB 命令执行权限
- 定期更新依赖包修复安全漏洞
