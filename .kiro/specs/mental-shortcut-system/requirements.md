# Requirements Document

## Introduction

思维捷径系统（Mental Shortcut System）是 Open-AutoGLM 的核心增强功能，旨在从模型成功执行的 thinking 日志中自动提取"思维捷径"，让模型形成类似人类的"肌肉记忆"，从而提高执行成功率和效率。

该系统将与现有的黄金路径系统协同工作，形成统一的经验学习体系：
- **黄金路径**：提供任务级指导（做什么）
- **思维捷径**：提供元素级指导（在哪里）

## Glossary

- **Mental Shortcut（思维捷径）**: 从成功执行中提取的元素位置记忆，包含应用、场景、元素、坐标等信息
- **ThinkingExtractor（思维提取器）**: 从步骤数据中提取思维捷径的组件
- **ShortcutRepository（捷径存储库）**: 存储和查询思维捷径的数据库操作组件
- **QualityController（质量控制器）**: 验证捷径质量和控制注入条件的组件
- **ShortcutInjector（捷径注入器）**: 将思维捷径注入到模型提示词的组件
- **Learning Period（学习期）**: 捷径被记录但不注入的初始阶段，用于积累数据
- **Confidence（置信度）**: 捷径可靠性的数值指标，范围0-1
- **Normalized Coordinates（归一化坐标）**: 0-999范围的设备无关坐标系统

## Requirements

### Requirement 1

**User Story:** As a system, I want to extract mental shortcuts from successful task executions, so that the model can learn element positions automatically.

#### Acceptance Criteria

1. WHEN a task step executes successfully THEN the ThinkingExtractor SHALL extract coordinates from the action data with 100% confidence
2. WHEN extracting from action data THEN the ThinkingExtractor SHALL prioritize action['element'] coordinates over thinking text
3. WHEN action coordinates are unavailable THEN the ThinkingExtractor SHALL attempt to extract coordinates from thinking text with reduced confidence (0.7)
4. WHEN extracting location hints THEN the ThinkingExtractor SHALL parse thinking text for relative position descriptions like "顶部中央" or "底部导航栏"
5. WHEN extracting element names THEN the ThinkingExtractor SHALL identify UI elements like "搜索框", "发送按钮", "输入框" from thinking text

### Requirement 2

**User Story:** As a system, I want to store mental shortcuts persistently, so that they can be reused across sessions.

#### Acceptance Criteria

1. WHEN a new shortcut is extracted THEN the MentalShortcutRepository SHALL check for existing shortcuts with the same app, scene, and element
2. WHEN a matching shortcut exists THEN the MentalShortcutRepository SHALL update usage_count and recalculate coord_variance
3. WHEN no matching shortcut exists THEN the MentalShortcutRepository SHALL create a new record in the mental_shortcuts table
4. WHEN querying shortcuts THEN the MentalShortcutRepository SHALL support filtering by app and scene
5. WHEN updating statistics THEN the MentalShortcutRepository SHALL increment usage_count and conditionally increment success_count

### Requirement 3

**User Story:** As a system, I want to validate shortcut quality before injection, so that only reliable shortcuts are used.

#### Acceptance Criteria

1. WHEN a shortcut has usage_count less than the learning period (10) THEN the QualityController SHALL mark it as in learning period and prevent injection
2. WHEN validating a shortcut THEN the QualityController SHALL require usage_count >= 5 for injection eligibility
3. WHEN validating a shortcut THEN the QualityController SHALL require success_rate >= 95% for injection eligibility
4. WHEN validating a shortcut THEN the QualityController SHALL require coord_variance < 30 for injection eligibility
5. WHEN validating a shortcut THEN the QualityController SHALL require confidence >= 0.9 for injection eligibility
6. IF a shortcut fails validation THEN the QualityController SHALL return the specific failure reason

### Requirement 4

**User Story:** As a system, I want to inject mental shortcuts into model prompts, so that the model receives position guidance.

#### Acceptance Criteria

1. WHEN building shortcut prompts THEN the ShortcutInjector SHALL query shortcuts by current app and scene
2. WHEN step_num is 1 THEN the ShortcutInjector SHALL display task overview from golden path
3. WHEN step_num is 2 or 3 THEN the ShortcutInjector SHALL display current step guidance
4. WHEN step_num is 4 or greater THEN the ShortcutInjector SHALL display element position hints
5. WHEN displaying shortcuts THEN the ShortcutInjector SHALL limit to 3 most relevant shortcuts to avoid information overload
6. WHEN injecting shortcuts THEN the ShortcutInjector SHALL append a disclaimer: "以上位置仅供参考，如果界面有变化，请重新分析"

### Requirement 5

**User Story:** As a system, I want to integrate the mental shortcut system with AgentRunner, so that shortcuts are automatically extracted and injected during task execution.

#### Acceptance Criteria

1. WHEN AgentRunner initializes THEN the system SHALL create instances of ThinkingExtractor, MentalShortcutRepository, QualityController, and ShortcutInjector
2. WHEN a task step succeeds THEN AgentRunner SHALL call ThinkingExtractor to extract shortcuts
3. WHEN building enhanced prompts THEN AgentRunner SHALL call ShortcutInjector to get shortcut prompts
4. WHEN a step completes THEN AgentRunner SHALL update shortcut statistics based on success/failure
5. IF shortcut extraction fails THEN AgentRunner SHALL continue task execution without interruption
6. IF shortcut injection fails THEN AgentRunner SHALL fall back to original prompt without shortcuts

### Requirement 6

**User Story:** As a system, I want to apply confidence decay based on data source, so that less reliable data sources have lower confidence.

#### Acceptance Criteria

1. WHEN extracting from action['element'] THEN the system SHALL assign confidence weight of 1.0
2. WHEN extracting from screenshot_analysis THEN the system SHALL assign confidence weight of 0.9
3. WHEN extracting coordinates from thinking text THEN the system SHALL assign confidence weight of 0.7
4. WHEN extracting location hints from thinking text THEN the system SHALL assign confidence weight of 0.5
5. WHEN calculating final confidence THEN the system SHALL multiply raw confidence by source weight

### Requirement 7

**User Story:** As a system, I want to track coordinate variance across multiple uses, so that unstable shortcuts can be identified and filtered.

#### Acceptance Criteria

1. WHEN a shortcut is used with new coordinates THEN the system SHALL update the coord_variance calculation
2. WHEN coord_variance exceeds 30 THEN the QualityController SHALL reject the shortcut for injection
3. WHEN storing coord_variance THEN the system SHALL store as JSON array [var_x, var_y]
4. WHEN multiple coordinates are recorded THEN the system SHALL calculate variance using standard deviation formula

### Requirement 8

**User Story:** As a developer, I want the mental shortcut system to have proper error handling, so that failures don't crash the main application.

#### Acceptance Criteria

1. IF database operations fail THEN the system SHALL log the error and continue without shortcuts
2. IF extraction fails THEN the system SHALL return None and allow task to continue
3. IF injection fails THEN the system SHALL return empty string and use original prompt
4. WHEN errors occur THEN the system SHALL log detailed error messages for debugging

