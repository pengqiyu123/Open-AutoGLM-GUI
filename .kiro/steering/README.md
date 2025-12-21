---
inclusion: manual
---

# Steering 系统使用指南 - GUI 电脑版

## 什么是 Steering？

Steering 是 Kiro AI 的学习和记忆系统，让 AI 助手能够：
- 从历史错误中学习
- 避免重复相同的错误
- 遵循项目特定的最佳实践
- 提供一致的任务执行质量

## 文件说明

### 1. error-recovery-log.md
记录实际发生的错误和成功的解决方案

### 2. task-execution-patterns.md
记录常见任务的正确执行步骤

### 3. project-specific-knowledge.md
记录项目特定的配置、约定和知识

## 工作流程

### 第一次任务失败时

1. **记录错误** - 在 error-recovery-log.md 中添加错误条目
2. **提取模式** - 在 task-execution-patterns.md 中添加正确步骤
3. **下次执行** - AI 会自动参考历史记录避免错误

### 定义新任务时

1. **分析任务** - 确定关键步骤和错误点
2. **创建模式** - 在 task-execution-patterns.md 中添加
3. **测试验证** - 让 AI 按照新模式执行

## 示例：完整的错误学习流程

**第一次：构建失败**
```
用户: "构建 GUI.exe"
AI: 执行 pyinstaller build_gui.spec
结果: 失败 - ModuleNotFoundError
```

**记录错误和解决方案**

**第二次：构建成功**
```
用户: "构建 GUI.exe"
AI: 
  1. 检查 requirements.txt ✓
  2. 验证依赖已安装 ✓
  3. 测试 python gui_app.py ✓
  4. 检查 build_gui.spec ✓
  5. 执行构建 ✓
  6. 验证 exe 文件 ✓
结果: 成功！
```

## 最佳实践

### 记录错误时
- ✅ 包含完整的错误信息
- ✅ 分析根本原因
- ✅ 记录可重现的解决步骤
- ✅ 添加预防措施

### 定义任务模式时
- ✅ 步骤要具体、可执行
- ✅ 包含验证方法
- ✅ 标注常见错误
- ✅ 提供纠正方案

## 维护建议

- **每周**: 审查新增的错误记录
- **每月**: 整理和优化任务模式
- **每季度**: 清理过时信息

## 总结

通过 Steering 系统，你可以让 AI 从错误中学习，建立项目知识库，提高任务执行成功率。

**记住：好的记录 = 更聪明的 AI**
