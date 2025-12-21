# Requirements Document - 任务回顾与学习系统

## Introduction

本文档定义 Open-AutoGLM GUI 电脑版的任务回顾与学习系统。该系统允许用户在任务执行后回顾每个步骤，标注正确/错误，并从中自动生成"黄金路径"和"错误模式"，使 AI 能够从失败中学习，在后续执行相同任务时自动应用学到的知识。

## Glossary

- **System**: Open-AutoGLM GUI 应用程序
- **Task**: 用户输入的完整任务描述，如"打开微信并发送消息"
- **Session**: 一次完整的任务执行过程，包含多个步骤
- **Step**: 任务执行过程中的单个操作，包含 thinking、action、screenshot
- **Golden Path**: 经过用户确认的正确步骤序列，可作为后续任务的参考
- **Error Pattern**: 用户标记的错误步骤及纠正说明，用于避免重复错误
- **Steering File**: 存储黄金路径和错误模式的文档，AI 可自动读取学习
- **User Label**: 用户对步骤的标注（correct/wrong/skip）
- **Task Pattern**: 任务的抽象模式，用于匹配相似任务

## Requirements

### Requirement 1: 数据库扩展

**User Story:** 作为系统开发者，我希望扩展现有数据库结构，以便存储用户对步骤的标注和纠正说明。

#### Acceptance Criteria

1. WHEN 系统初始化数据库 THEN System SHALL 在 steps 表中添加 user_label 字段用于存储标注类型
2. WHEN 系统初始化数据库 THEN System SHALL 在 steps 表中添加 user_correction 字段用于存储纠正说明
3. WHEN 系统初始化数据库 THEN System SHALL 创建 golden_paths 表用于存储黄金路径
4. WHEN 系统初始化数据库 THEN System SHALL 创建 error_patterns 表用于存储错误模式
5. WHEN 数据库已存在 THEN System SHALL 安全地执行迁移而不丢失现有数据

### Requirement 2: 任务回顾界面

**User Story:** 作为用户，我希望在任务完成后能够回顾所有步骤，以便标注哪些步骤是正确的，哪些是错误的。

#### Acceptance Criteria

1. WHEN 用户打开数据存储面板 THEN System SHALL 显示"任务回顾"标签页
2. WHEN 用户查看任务列表 THEN System SHALL 按失败次数和步骤数排序显示所有历史任务
3. WHEN 用户选择一个任务 THEN System SHALL 在步骤播放器中显示该任务的所有步骤
4. WHEN 用户查看某个步骤 THEN System SHALL 显示该步骤的截图、thinking 和 action
5. WHEN 用户查看某个步骤 THEN System SHALL 提供"✓ 正确"、"✗ 错误"、"→ 跳过"三个标注按钮
6. WHEN 用户标记步骤为错误 THEN System SHALL 显示文本输入框供用户输入纠正说明
7. WHEN 用户输入纠正说明 THEN System SHALL 保存标注和说明到数据库

### Requirement 3: 步骤标注功能

**User Story:** 作为用户，我希望能够快速标注多个步骤，以便高效地完成任务回顾。

#### Acceptance Criteria

1. WHEN 用户点击"✓ 正确"按钮 THEN System SHALL 将该步骤标记为 correct 并自动跳转到下一步
2. WHEN 用户点击"✗ 错误"按钮 THEN System SHALL 将该步骤标记为 wrong 并显示纠正输入框
3. WHEN 用户点击"→ 跳过"按钮 THEN System SHALL 不标记该步骤并跳转到下一步
4. WHEN 用户完成标注 THEN System SHALL 立即保存到数据库
5. WHEN 用户重新打开已标注的任务 THEN System SHALL 显示之前的标注状态

### Requirement 4: 黄金路径提取

**User Story:** 作为用户，我希望系统能够从标注的步骤中自动提取黄金路径，以便后续任务可以参考。

#### Acceptance Criteria

1. WHEN 用户完成任务标注 THEN System SHALL 提供"生成黄金路径"按钮
2. WHEN 用户点击生成黄金路径 THEN System SHALL 从连续标记为 correct 的步骤中提取路径
3. WHEN 系统提取黄金路径 THEN System SHALL 去除冗余步骤（如多余的返回、等待）
4. WHEN 系统生成黄金路径 THEN System SHALL 保存到 golden_paths 表
5. WHEN 系统生成黄金路径 THEN System SHALL 同时生成对应的 steering 文件
6. WHEN 生成 steering 文件 THEN System SHALL 使用 YAML 格式以便人类阅读和编辑

### Requirement 5: 错误模式识别

**User Story:** 作为用户，我希望系统能够识别常见的错误模式，以便在后续任务中自动避免。

#### Acceptance Criteria

1. WHEN 用户标记步骤为错误并提供纠正说明 THEN System SHALL 保存到 error_patterns 表
2. WHEN 多个任务出现相似错误 THEN System SHALL 识别为常见错误模式
3. WHEN 系统识别错误模式 THEN System SHALL 在 steering 文件中记录错误描述和纠正方法
4. WHEN 系统生成错误模式 THEN System SHALL 包含错误出现频率统计
5. WHEN 用户查看错误模式 THEN System SHALL 显示所有相关的历史案例

### Requirement 6: 任务相似度匹配

**User Story:** 作为系统，我需要判断两个任务是否相似，以便应用正确的黄金路径。

#### Acceptance Criteria

1. WHEN 用户输入新任务 THEN System SHALL 提取任务描述中的关键词
2. WHEN 系统提取关键词 THEN System SHALL 在黄金路径库中搜索匹配的任务模式
3. WHEN 找到候选黄金路径 THEN System SHALL 计算任务描述的语义相似度
4. WHEN 相似度超过阈值（0.8）THEN System SHALL 选择该黄金路径作为参考
5. WHEN 未找到匹配的黄金路径 THEN System SHALL 按正常流程执行任务并记录日志

### Requirement 7: 黄金路径应用

**User Story:** 作为用户，我希望系统在执行任务时能够自动应用已学习的黄金路径，以便提高成功率。

#### Acceptance Criteria

1. WHEN 系统找到匹配的黄金路径 THEN System SHALL 将其作为 prompt 提示加入 AI 规划
2. WHEN 系统应用黄金路径 THEN System SHALL 在 prompt 中包含自然语言步骤描述
3. WHEN 系统应用黄金路径 THEN System SHALL 在 prompt 中包含常见错误提示
4. WHEN 黄金路径标记为可重放 THEN System SHALL 提供直接重放选项
5. WHEN 直接重放失败 THEN System SHALL 自动降级到 AI 规划模式

### Requirement 8: Steering 文件管理

**User Story:** 作为用户，我希望能够查看和编辑 steering 文件，以便手动优化黄金路径。

#### Acceptance Criteria

1. WHEN 系统生成 steering 文件 THEN System SHALL 保存到 .kiro/steering/golden-paths/ 目录
2. WHEN 生成 steering 文件 THEN System SHALL 使用任务模式作为文件名
3. WHEN 用户打开 steering 文件 THEN System SHALL 显示人类可读的 YAML 格式
4. WHEN 用户编辑 steering 文件 THEN System SHALL 在下次任务执行时自动读取更新
5. WHEN steering 文件包含语法错误 THEN System SHALL 记录警告但不中断任务执行

### Requirement 9: 统计和分析

**User Story:** 作为用户，我希望看到任务执行的统计信息，以便了解学习系统的效果。

#### Acceptance Criteria

1. WHEN 用户查看任务回顾面板 THEN System SHALL 显示总任务数、成功率、平均步骤数
2. WHEN 用户查看黄金路径列表 THEN System SHALL 显示每个路径的成功率和使用次数
3. WHEN 用户查看错误模式列表 THEN System SHALL 显示每个错误的出现频率
4. WHEN 系统应用黄金路径 THEN System SHALL 记录应用结果（成功/失败）
5. WHEN 用户查看统计图表 THEN System SHALL 显示学习效果的趋势变化

### Requirement 10: 手动演示模式（未来扩展）

**User Story:** 作为用户，我希望能够通过对话方式手动演示任务步骤，以便创建高质量的黄金路径。

#### Acceptance Criteria

1. WHEN 用户启用演示模式 THEN System SHALL 切换到手动控制界面
2. WHEN 系统截取屏幕 THEN System SHALL 使用 AI 分析并描述当前界面
3. WHEN 用户输入自然语言指令 THEN System SHALL 将其转换为具体动作并执行
4. WHEN 系统执行动作 THEN System SHALL 自动标记该步骤为 correct
5. WHEN 用户完成演示 THEN System SHALL 自动生成黄金路径和 steering 文件

## Technical Constraints

- 系统必须向后兼容现有的 tasks.db 数据库
- 数据库操作必须是线程安全的
- steering 文件必须使用 UTF-8 编码
- UI 更新必须在主线程执行
- 黄金路径匹配算法的响应时间应小于 100ms

## Non-Functional Requirements

- 任务回顾界面应在 1 秒内加载完成
- 步骤标注操作应立即响应（< 100ms）
- 数据库查询应使用索引优化性能
- steering 文件大小应控制在 50KB 以内
- 系统应支持至少 1000 个历史任务的存储和查询

## Future Enhancements

- 支持多用户协作标注
- 使用机器学习自动识别错误模式
- 支持黄金路径的版本管理
- 提供黄金路径的可视化编辑器
- 支持导入/导出黄金路径库
