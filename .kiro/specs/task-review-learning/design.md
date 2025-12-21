# Design Document - 任务回顾与学习系统

## Overview

任务回顾与学习系统是 Open-AutoGLM GUI 的核心增强功能，通过记录、标注和学习历史任务执行过程，使 AI 能够从失败中学习并持续改进。系统采用"日志 → 标注 → 提取 → 应用"的闭环设计，确保知识能够有效积累和复用。

## Architecture

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        GUI Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Task Review  │  │ Step Player  │  │ Statistics   │      │
│  │ Panel        │  │ Widget       │  │ Dashboard    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Business Logic                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Annotation   │  │ Golden Path  │  │ Task Matcher │      │
│  │ Manager      │  │ Extractor    │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ TaskLogger   │  │ Golden Path  │  │ Steering     │      │
│  │ (SQLite)     │  │ Repository   │  │ File Manager │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 数据流

```
执行任务 → 记录日志 → 用户标注 → 提取路径 → 生成 Steering → 应用学习
   │          │          │          │           │            │
   ▼          ▼          ▼          ▼           ▼            ▼
 Agent    TaskLogger  Annotation  Extractor  FileManager  Prompt
Runner               Manager                              Builder
```

## Components and Interfaces

### 1. TaskLogger 扩展

**职责**: 扩展现有的 TaskLogger 以支持用户标注

**新增方法**:
```python
class TaskLogger:
    def add_user_feedback(
        self,
        session_id: str,
        step_num: int,
        user_label: str,  # 'correct' | 'wrong' | None
        user_correction: str = ""
    ) -> None:
        """添加用户对步骤的标注"""
        
    def get_session_steps(
        self,
        session_id: str,
        include_feedback: bool = True
    ) -> List[Dict]:
        """获取会话的所有步骤"""
        
    def get_annotated_sessions(self) -> List[Dict]:
        """获取所有已标注的会话"""
```

### 2. TaskReviewWidget

**职责**: 提供任务回顾和标注的用户界面

**主要组件**:
```python
class TaskReviewWidget(QWidget):
    def __init__(self, task_logger: TaskLogger):
        self.task_list = QListWidget()  # 任务列表
        self.step_player = StepPlayerWidget()  # 步骤播放器
        self.annotation_panel = AnnotationPanel()  # 标注面板
        
    def load_tasks(self) -> None:
        """加载历史任务列表"""
        
    def on_task_selected(self, session_id: str) -> None:
        """用户选择任务时的处理"""
        
    def on_step_annotated(
        self,
        step_num: int,
        label: str,
        correction: str
    ) -> None:
        """用户标注步骤时的处理"""
```

### 3. StepPlayerWidget

**职责**: 显示单个步骤的详细信息并提供标注功能

**界面元素**:
```python
class StepPlayerWidget(QWidget):
    def __init__(self):
        self.screenshot_label = QLabel()  # 截图显示
        self.thinking_text = QTextEdit()  # Thinking 显示
        self.action_text = QTextEdit()  # Action 显示
        self.correct_btn = QPushButton("✓ 正确")
        self.wrong_btn = QPushButton("✗ 错误")
        self.skip_btn = QPushButton("→ 跳过")
        self.correction_input = QTextEdit()  # 纠正说明输入
        
    def load_step(self, step_data: Dict) -> None:
        """加载步骤数据"""
        
    def show_correction_input(self) -> None:
        """显示纠正说明输入框"""
```

### 4. GoldenPathExtractor

**职责**: 从标注数据中提取黄金路径

**核心算法**:
```python
class GoldenPathExtractor:
    def extract_from_session(
        self,
        session_id: str
    ) -> Optional[GoldenPath]:
        """从单个会话提取黄金路径"""
        # 1. 获取所有标记为 correct 的步骤
        # 2. 去除冗余步骤（连续的返回、等待）
        # 3. 提取关键动作序列
        # 4. 生成自然语言描述
        
    def merge_similar_paths(
        self,
        paths: List[GoldenPath]
    ) -> GoldenPath:
        """合并相似的黄金路径"""
        # 1. 找出共同步骤
        # 2. 保留最短路径
        # 3. 合并错误提示
```

### 5. ErrorPatternAnalyzer

**职责**: 识别和分析错误模式

**分析方法**:
```python
class ErrorPatternAnalyzer:
    def analyze_errors(
        self,
        task_pattern: str
    ) -> List[ErrorPattern]:
        """分析特定任务的错误模式"""
        # 1. 收集所有标记为 wrong 的步骤
        # 2. 按 action 类型分组
        # 3. 统计频率
        # 4. 提取共同特征
        
    def generate_correction_hints(
        self,
        error_pattern: ErrorPattern
    ) -> str:
        """生成纠正提示"""
```

### 6. TaskMatcher

**职责**: 匹配相似任务以应用黄金路径

**匹配策略**:
```python
class TaskMatcher:
    def find_matching_path(
        self,
        task_description: str
    ) -> Optional[GoldenPath]:
        """查找匹配的黄金路径"""
        # 1. 关键词提取
        keywords = self.extract_keywords(task_description)
        
        # 2. 候选筛选
        candidates = self.query_by_keywords(keywords)
        
        # 3. 语义相似度计算
        best_match = max(
            candidates,
            key=lambda p: self.semantic_similarity(
                task_description,
                p.task_pattern
            )
        )
        
        # 4. 阈值判断
        if similarity > 0.8:
            return best_match
        return None
```

### 7. SteeringFileManager

**职责**: 管理 steering 文件的生成和读取

**文件格式**:
```yaml
# .kiro/steering/golden-paths/open-wechat-send-message.yaml
---
task_pattern: "打开微信并给文件传输助手发消息"
apps: ["微信"]
difficulty: "simple"
can_replay: true

natural_sop: |
  1. 在桌面找到微信图标（通常在右下角）
  2. 点击打开微信
  3. 在聊天列表中找到"文件传输助手"
  4. 点击进入聊天界面
  5. 点击底部输入框
  6. 输入消息内容
  7. 点击发送按钮

action_sop:
  - action: tap
    target: "微信"
    method: "text_match"
  - action: tap
    target: "文件传输助手"
    method: "text_match"
  - action: tap
    target: "输入框"
    method: "ocr_region"
  - action: type
    text: "{message_content}"
  - action: tap
    target: "发送"
    method: "text_match"

common_errors:
  - error: "点击了 QQ 而不是微信"
    correction: "优先匹配文字为'微信'的图标"
  - error: "点击了其他聊天而不是文件传输助手"
    correction: "精确匹配'文件传输助手'这几个字"

success_rate: 0.95
last_updated: "2024-12-18"
source_sessions: ["session_123", "session_456"]
```

## Data Models

### Database Schema

```sql
-- 扩展 steps 表
ALTER TABLE steps ADD COLUMN user_label TEXT;      -- 'correct'/'wrong'/NULL
ALTER TABLE steps ADD COLUMN user_correction TEXT; -- 纠正说明

-- 黄金路径表
CREATE TABLE golden_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_pattern TEXT NOT NULL,
    apps TEXT,  -- JSON array
    difficulty TEXT,  -- 'simple'/'medium'/'complex'
    can_replay INTEGER DEFAULT 0,
    natural_sop TEXT,
    action_sop TEXT,  -- JSON
    common_errors TEXT,  -- JSON
    success_rate REAL DEFAULT 0.0,
    usage_count INTEGER DEFAULT 0,
    source_sessions TEXT,  -- JSON array
    created_at TEXT,
    updated_at TEXT
);

-- 错误模式表
CREATE TABLE error_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_pattern TEXT NOT NULL,
    error_description TEXT NOT NULL,
    correction TEXT NOT NULL,
    frequency INTEGER DEFAULT 1,
    last_seen TEXT,
    created_at TEXT
);

-- 索引
CREATE INDEX idx_golden_paths_pattern ON golden_paths(task_pattern);
CREATE INDEX idx_error_patterns_pattern ON error_patterns(task_pattern);
CREATE INDEX idx_steps_session_label ON steps(session_id, user_label);
```

### Python Data Classes

```python
@dataclass
class GoldenPath:
    task_pattern: str
    apps: List[str]
    difficulty: str
    can_replay: bool
    natural_sop: str
    action_sop: List[Dict]
    common_errors: List[Dict]
    success_rate: float
    usage_count: int
    source_sessions: List[str]
    created_at: str
    updated_at: str

@dataclass
class ErrorPattern:
    task_pattern: str
    error_description: str
    correction: str
    frequency: int
    last_seen: str
    created_at: str

@dataclass
class StepAnnotation:
    session_id: str
    step_num: int
    user_label: str  # 'correct' | 'wrong' | None
    user_correction: str
    annotated_at: str
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Database Migration Preserves Data

*For any* existing database with task and step records, when the system performs schema migration, all existing data should remain intact and accessible.

**Validates: Requirements 1.5**

### Property 2: Task Sorting Consistency

*For any* set of historical tasks, when displayed in the task list, tasks should be consistently sorted by failure count (descending) then by step count (descending).

**Validates: Requirements 2.2**

### Property 3: Annotation Persistence

*For any* step annotation (correct/wrong/skip with optional correction text), when saved to the database and later retrieved, the annotation data should match exactly what was saved.

**Validates: Requirements 2.7, 3.4, 3.5**

### Property 4: Correct Label Navigation

*For any* step marked as "correct", the system should automatically advance to the next step and save the label to the database.

**Validates: Requirements 3.1**

### Property 5: Wrong Label Shows Input

*For any* step marked as "wrong", the system should display the correction input field and save the label to the database.

**Validates: Requirements 3.2**

### Property 6: Skip Label No Persistence

*For any* step marked as "skip", the system should advance to the next step without saving any label (user_label remains NULL).

**Validates: Requirements 3.3**

### Property 7: Golden Path Extraction from Correct Steps

*For any* session with consecutive steps marked as "correct", the golden path extractor should include only those correct steps in the extracted path.

**Validates: Requirements 4.2**

### Property 8: Redundant Step Removal

*For any* sequence of steps containing redundant actions (consecutive returns, waits), the golden path extractor should remove these redundant steps while preserving the essential action sequence.

**Validates: Requirements 4.3**

### Property 9: Golden Path Database Persistence

*For any* generated golden path, when saved to the database and later queried, all path data (task_pattern, steps, errors) should be retrievable and match the original.

**Validates: Requirements 4.4**

### Property 10: Steering File Generation

*For any* golden path saved to the database, a corresponding YAML steering file should be created in the correct directory with valid YAML syntax.

**Validates: Requirements 4.5, 4.6**

### Property 11: Error Pattern Accumulation

*For any* step marked as "wrong" with correction text, the error pattern should be saved to the database with frequency count incremented if a similar error already exists.

**Validates: Requirements 5.1, 5.2**

### Property 12: Error Pattern in Steering

*For any* identified error pattern, the corresponding steering file should include the error description and correction in the common_errors section.

**Validates: Requirements 5.3**

### Property 13: Keyword Extraction Consistency

*For any* task description, the keyword extraction should produce a consistent set of keywords when run multiple times on the same input.

**Validates: Requirements 6.1**

### Property 14: Similarity Threshold Matching

*For any* task description and golden path, if the semantic similarity score exceeds 0.8, the system should select that golden path; if below 0.8, no path should be selected.

**Validates: Requirements 6.4**

### Property 15: Fallback to Normal Execution

*For any* task without a matching golden path (similarity < 0.8), the system should execute the task normally and log all steps for future annotation.

**Validates: Requirements 6.5**

### Property 16: Prompt Includes Golden Path

*For any* matched golden path, the generated prompt should contain the natural_sop text from the golden path.

**Validates: Requirements 7.1, 7.2**

### Property 17: Prompt Includes Error Warnings

*For any* matched golden path with common_errors, the generated prompt should include all error descriptions and corrections.

**Validates: Requirements 7.3**

### Property 18: Replay Fallback on Failure

*For any* golden path marked as can_replay=true, if direct replay fails, the system should automatically switch to AI planning mode without user intervention.

**Validates: Requirements 7.5**

### Property 19: Steering File Path Convention

*For any* generated steering file, the file path should follow the pattern `.kiro/steering/golden-paths/{sanitized_task_pattern}.yaml`.

**Validates: Requirements 8.1, 8.2**

### Property 20: Steering File Round-Trip

*For any* steering file written to disk, when read back and parsed, the data structure should match the original golden path object.

**Validates: Requirements 8.4**

### Property 21: Graceful Error Handling

*For any* steering file with YAML syntax errors, the system should log a warning and continue task execution without crashing.

**Validates: Requirements 8.5**

### Property 22: Statistics Accuracy

*For any* set of tasks in the database, the displayed statistics (total count, success rate, average steps) should accurately reflect the actual data.

**Validates: Requirements 9.1, 9.2, 9.3**

### Property 23: Application Result Logging

*For any* golden path applied to a task, the system should record whether the application resulted in success or failure.

**Validates: Requirements 9.4**

## Error Handling

### Database Errors

- **Connection Failures**: Retry with exponential backoff, max 3 attempts
- **Schema Migration Errors**: Rollback transaction, log error, notify user
- **Constraint Violations**: Log warning, skip problematic record, continue processing

### File System Errors

- **Steering File Write Failures**: Log error, save to database only, retry on next generation
- **YAML Parse Errors**: Log warning with line number, skip file, use database data
- **Permission Errors**: Notify user with clear instructions

### UI Errors

- **Widget Load Failures**: Show error message, disable affected feature, allow other features to work
- **Screenshot Display Errors**: Show placeholder image, log error
- **Annotation Save Failures**: Show retry dialog, cache annotation locally

### Algorithm Errors

- **Similarity Calculation Failures**: Default to 0.0 similarity, log error
- **Keyword Extraction Failures**: Use full task description, log warning
- **Path Extraction Failures**: Notify user, allow manual export

## Testing Strategy

### Unit Tests

- Database schema migration logic
- Keyword extraction algorithm
- Similarity calculation
- YAML file generation and parsing
- Error pattern frequency counting
- Redundant step detection

### Property-Based Tests

Each correctness property listed above should be implemented as a property-based test using an appropriate testing framework (e.g., Hypothesis for Python).

**Configuration**:
- Minimum 100 iterations per property test
- Use random data generators for tasks, steps, annotations
- Test edge cases: empty inputs, very long inputs, special characters

**Test Tagging**:
Each property test must include a comment with the format:
```python
# Feature: task-review-learning, Property X: [property description]
# Validates: Requirements X.Y
```

### Integration Tests

- End-to-end annotation workflow
- Golden path extraction and application
- Steering file generation and loading
- UI interaction flows

### Manual Testing

- UI responsiveness and usability
- Visual appearance of widgets
- Error message clarity
- Performance with large datasets (1000+ tasks)

## Performance Considerations

### Database Optimization

- Create indexes on frequently queried columns (session_id, user_label, task_pattern)
- Use connection pooling for concurrent access
- Implement query result caching for read-heavy operations
- Batch insert operations for bulk annotations

### UI Responsiveness

- Load task list asynchronously in background thread
- Implement pagination for large task lists (50 items per page)
- Cache screenshot images in memory
- Use lazy loading for step details

### File I/O Optimization

- Write steering files asynchronously
- Batch file operations when possible
- Use file system watchers instead of polling
- Compress old steering files to save space

### Memory Management

- Limit screenshot cache size (max 100 images)
- Release resources when widgets are closed
- Use weak references for large objects
- Implement periodic garbage collection

## Security Considerations

- Sanitize task descriptions before using as file names
- Validate YAML content before parsing
- Limit steering file size (max 50KB)
- Escape special characters in SQL queries (use parameterized queries)
- Validate user input in correction text fields

## Deployment Strategy

### Phase 1: Database Migration (Week 1)

1. Add new columns to steps table
2. Create golden_paths and error_patterns tables
3. Test migration on sample database
4. Deploy with automatic backup

### Phase 2: Basic UI (Week 1-2)

1. Implement TaskReviewWidget skeleton
2. Add task list display
3. Implement StepPlayerWidget
4. Add annotation buttons

### Phase 3: Core Logic (Week 2)

1. Implement annotation persistence
2. Add golden path extraction
3. Implement error pattern analysis
4. Add steering file generation

### Phase 4: Integration (Week 2-3)

1. Integrate with existing AgentRunner
2. Implement task matching
3. Add prompt building with golden paths
4. Test end-to-end workflow

### Phase 5: Polish (Week 3)

1. Add statistics dashboard
2. Optimize performance
3. Improve error handling
4. User testing and feedback

## Future Enhancements

- **Machine Learning Integration**: Use ML models to automatically identify error patterns
- **Collaborative Annotation**: Allow multiple users to annotate the same tasks
- **Version Control**: Track changes to golden paths over time
- **Visual Path Editor**: Drag-and-drop interface for editing golden paths
- **Export/Import**: Share golden path libraries between users
- **A/B Testing**: Compare effectiveness of different golden paths
- **Real-time Suggestions**: Show golden path suggestions during task execution
