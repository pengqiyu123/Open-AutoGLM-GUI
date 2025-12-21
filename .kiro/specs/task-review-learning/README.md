# 任务回顾与学习系统 - Spec 总览

## 项目概述

本 spec 定义了 Open-AutoGLM GUI 电脑版的任务回顾与学习系统，使 AI 能够从失败中学习并持续改进。

## 核心目标

1. **记录完整执行过程** - 保存每个步骤的 thinking、action、screenshot
2. **用户标注反馈** - 允许用户标记步骤为正确/错误/跳过
3. **自动提取黄金路径** - 从标注数据中生成最佳执行路径
4. **智能应用学习** - 在后续任务中自动应用学到的知识

## 文档结构

- **requirements.md** - 10个核心需求，50+验收标准
- **design.md** - 系统架构、组件设计、23个正确性属性
- **tasks.md** - 17个主要任务，80+子任务，详细实施计划

## 快速开始

### 查看需求
```bash
# 打开需求文档
Open-AutoGLM-main/.kiro/specs/task-review-learning/requirements.md
```

### 查看设计
```bash
# 打开设计文档
Open-AutoGLM-main/.kiro/specs/task-review-learning/design.md
```

### 开始实施
```bash
# 打开任务列表
Open-AutoGLM-main/.kiro/specs/task-review-learning/tasks.md
```

在 Kiro 中打开 tasks.md 文件，点击任务旁边的 "Start task" 按钮开始实施。

## 实施策略

### MVP 优先（推荐）

用户已选择 **保持可选测试**，这意味着：

✅ **先实现核心功能**
- 数据库扩展
- 任务回顾UI
- 黄金路径提取
- 基本的应用逻辑

⏸️ **测试任务标记为可选（*）**
- 可以在核心功能完成后再补充
- 或者在发现问题时针对性地添加

### 实施顺序

**第1周：基础设施**
1. 数据库扩展和迁移
2. TaskLogger 功能扩展
3. 基础 UI 框架

**第2周：核心逻辑**
4. 步骤播放器和标注功能
5. 黄金路径提取器
6. 错误模式分析器

**第3周：集成应用**
7. 任务匹配器
8. Steering 文件管理
9. 集成到 AgentRunner

**第4周：优化完善**
10. 统计和分析
11. UI 优化
12. 性能优化
13. 文档和测试

## 关键组件

### 数据层
- **TaskLogger** - 扩展以支持用户标注
- **GoldenPathRepository** - 黄金路径存储
- **SteeringFileManager** - YAML 文件管理

### 业务逻辑层
- **GoldenPathExtractor** - 提取黄金路径
- **ErrorPatternAnalyzer** - 分析错误模式
- **TaskMatcher** - 匹配相似任务

### UI 层
- **TaskReviewWidget** - 任务回顾主界面
- **StepPlayerWidget** - 步骤播放器
- **StatisticsWidget** - 统计分析面板

## 数据流

```
执行任务 → 记录日志 → 用户标注 → 提取路径 → 生成 Steering → 应用学习
   ↓          ↓          ↓          ↓           ↓            ↓
 Agent    TaskLogger  Annotation  Extractor  FileManager  Prompt
Runner               Manager                              Builder
```

## 技术栈

- **语言**: Python 3.8+
- **UI 框架**: PyQt5
- **数据库**: SQLite
- **配置格式**: YAML
- **测试框架**: pytest + Hypothesis（属性测试）

## 预期效果

实施完成后，系统将能够：

1. ✅ **记住成功路径** - 第一次可能失败，但会记录完整过程
2. ✅ **避免重复错误** - 用户标注的错误不会再犯
3. ✅ **持续改进** - 随着使用次数增加，成功率不断提升
4. ✅ **知识复用** - 相似任务自动应用已学习的知识

## 性能指标

- 任务回顾界面加载时间 < 1秒
- 步骤标注响应时间 < 100ms
- 黄金路径匹配时间 < 100ms
- 支持 1000+ 历史任务存储

## 后续扩展

- 手动演示模式（对话式步骤编辑器）
- 机器学习自动识别错误模式
- 多用户协作标注
- 黄金路径可视化编辑器
- 导入/导出黄金路径库

## 相关文档

- [项目主 README](../../../README.md)
- [Steering 系统说明](../../steering/README.md)
- [项目优化思路](../../../项目后续优化思路.md)

## 联系方式

如有问题或建议，请在项目中提出 issue。
