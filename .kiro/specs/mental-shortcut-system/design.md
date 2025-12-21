# Design Document: Mental Shortcut System

## Overview

思维捷径系统是 Open-AutoGLM 的核心增强功能，通过从成功执行中自动提取元素位置信息，让模型形成"位置记忆"，从而提高执行成功率。

### 核心价值
- **自动学习**：从成功执行中自动提取经验，无需人工标注
- **位置记忆**：记住常用元素的位置，减少重复分析
- **质量控制**：严格验证确保只注入可靠的捷径
- **渐进式**：学习期机制避免早期噪音

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AgentRunner                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Task      │  │  Enhanced   │  │   Step      │         │
│  │  Execution  │→ │   Prompt    │→ │  Callback   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│         │                │                │                 │
└─────────┼────────────────┼────────────────┼─────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ ShortcutInjector│ │ QualityController│ │ThinkingExtractor│
│                 │ │                 │ │                 │
│ - build_prompt  │ │ - validate      │ │ - extract       │
│ - format        │ │ - should_inject │ │ - parse_coords  │
│ - add_disclaimer│ │ - learning_check│ │ - parse_hints   │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
                 ┌─────────────────────┐
                 │MentalShortcutRepo   │
                 │                     │
                 │ - save              │
                 │ - find_by_app       │
                 │ - update_usage      │
                 │ - find_or_create    │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │   SQLite Database   │
                 │  mental_shortcuts   │
                 └─────────────────────┘
```

## Components and Interfaces

### 1. MentalShortcut (Data Model)

```python
@dataclass
class MentalShortcut:
    id: Optional[int] = None
    app: str = ""                      # 应用名
    scene: str = "未知页面"             # 场景
    element: str = ""                  # UI元素名
    location_hint: str = ""            # 位置描述
    typical_coords: List[int] = None   # 归一化坐标 [x, y]
    coord_variance: List[float] = None # 坐标方差 [var_x, var_y]
    action: str = ""                   # 动作类型
    data_source: str = "action"        # 数据来源
    confidence: float = 1.0            # 置信度
    usage_count: int = 1               # 使用次数
    success_count: int = 1             # 成功次数
    created_at: str = ""               # 创建时间
    updated_at: str = ""               # 更新时间
    last_used_at: str = ""             # 最后使用时间
```

### 2. ThinkingExtractor

```python
class ThinkingExtractor:
    """从步骤数据中提取思维捷径"""
    
    # 数据源权重
    SOURCE_WEIGHTS = {
        'action': 1.0,
        'screenshot': 0.9,
        'thinking_coords': 0.7,
        'thinking_location': 0.5
    }
    
    def extract_from_step(self, step_data: Dict) -> Optional[MentalShortcut]:
        """从步骤数据提取捷径"""
        
    def _extract_coords_from_action(self, action: Dict) -> Tuple[List[int], str]:
        """从action提取坐标，返回(coords, source)"""
        
    def _extract_coords_from_thinking(self, thinking: str) -> Optional[List[int]]:
        """从thinking文本提取坐标"""
        
    def _extract_location_hint(self, thinking: str) -> str:
        """提取位置描述"""
        
    def _extract_element_name(self, thinking: str) -> str:
        """提取元素名称"""
        
    def _calculate_confidence(self, data_source: str) -> float:
        """计算置信度（含衰减）"""
```

### 3. MentalShortcutRepository

```python
class MentalShortcutRepository:
    """思维捷径数据库操作"""
    
    def __init__(self, db_path: str):
        """初始化，创建表"""
        
    def save(self, shortcut: MentalShortcut) -> int:
        """保存捷径，返回ID"""
        
    def find_by_app(self, app: str) -> List[MentalShortcut]:
        """按应用查询"""
        
    def find_by_app_scene(self, app: str, scene: str) -> List[MentalShortcut]:
        """按应用和场景查询"""
        
    def find_or_create(self, shortcut: MentalShortcut) -> MentalShortcut:
        """查找或创建，处理去重"""
        
    def update_usage(self, shortcut_id: int, success: bool):
        """更新使用统计"""
        
    def update_coords_variance(self, shortcut_id: int, new_coords: List[int]):
        """更新坐标方差"""
```

### 4. ShortcutQualityController

```python
class ShortcutQualityController:
    """质量控制器"""
    
    # 第一阶段阈值
    LEARNING_PERIOD = 10
    MIN_USAGE_COUNT = 5
    MIN_SUCCESS_RATE = 0.95
    MAX_COORD_VARIANCE = 30
    MIN_CONFIDENCE = 0.9
    
    def __init__(self, learning_period: int = 10):
        """初始化"""
        
    def validate_shortcut(self, shortcut: MentalShortcut) -> Tuple[bool, str]:
        """验证捷径质量，返回(是否通过, 原因)"""
        
    def should_inject(self, shortcut: MentalShortcut, context: Dict) -> bool:
        """判断是否应该注入"""
        
    def is_in_learning_period(self, shortcut: MentalShortcut) -> bool:
        """是否在学习期"""
```

### 5. ShortcutInjector

```python
class ShortcutInjector:
    """捷径注入器"""
    
    def __init__(self, repository: MentalShortcutRepository, 
                 quality_controller: ShortcutQualityController):
        """初始化"""
        
    def build_shortcut_prompt(self, app: str, scene: str, 
                              step_num: int, golden_path: Dict = None) -> str:
        """构建捷径提示词"""
        
    def _build_step1_prompt(self, golden_path: Dict) -> str:
        """步骤1：任务概览"""
        
    def _build_step2_3_prompt(self, golden_path: Dict, step_num: int) -> str:
        """步骤2-3：当前步骤指导"""
        
    def _build_step4_plus_prompt(self, shortcuts: List[MentalShortcut]) -> str:
        """步骤4+：元素位置提示"""
        
    def _format_shortcuts(self, shortcuts: List[MentalShortcut]) -> str:
        """格式化捷径列表"""
        
    def _add_disclaimer(self, prompt: str) -> str:
        """添加免责声明"""
```

## Data Models

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS mental_shortcuts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app TEXT NOT NULL,
    scene TEXT DEFAULT '未知页面',
    element TEXT NOT NULL,
    location_hint TEXT,
    typical_coords TEXT,          -- JSON: [x, y]
    coord_variance TEXT,          -- JSON: [var_x, var_y]
    action TEXT,
    data_source TEXT DEFAULT 'action',
    confidence REAL DEFAULT 1.0,
    usage_count INTEGER DEFAULT 1,
    success_count INTEGER DEFAULT 1,
    source_sessions TEXT,         -- JSON: [session_id, ...]
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_used_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_shortcuts_app ON mental_shortcuts(app);
CREATE INDEX IF NOT EXISTS idx_shortcuts_app_scene ON mental_shortcuts(app, scene);
CREATE INDEX IF NOT EXISTS idx_shortcuts_confidence ON mental_shortcuts(confidence);
```

### Data Flow

```
Step Success
    │
    ▼
┌─────────────────────────────────────────┐
│ step_data = {                           │
│   'thinking': "我看到搜索框在顶部...",   │
│   'action': {'action': 'Tap',           │
│              'element': [500, 80]},     │
│   'app': '微信',                         │
│   'success': True                       │
│ }                                       │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ ThinkingExtractor.extract_from_step()   │
│   - coords: [500, 80] (from action)     │
│   - element: "搜索框" (from thinking)   │
│   - location_hint: "顶部" (from thinking)│
│   - confidence: 1.0 (action source)     │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ MentalShortcut {                        │
│   app: "微信",                           │
│   scene: "未知页面",                     │
│   element: "搜索框",                     │
│   location_hint: "顶部",                 │
│   typical_coords: [500, 80],            │
│   confidence: 1.0                       │
│ }                                       │
└─────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────┐
│ MentalShortcutRepository.find_or_create()│
│   - Check existing: app + scene + element│
│   - If exists: update usage_count       │
│   - If new: insert record               │
└─────────────────────────────────────────┘
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Action coordinates have highest priority
*For any* step data containing both action coordinates and thinking coordinates, the ThinkingExtractor SHALL always use action coordinates with confidence 1.0
**Validates: Requirements 1.1, 1.2**

### Property 2: Confidence decay by source
*For any* extraction, the final confidence SHALL equal raw_confidence multiplied by source_weight where action=1.0, screenshot=0.9, thinking_coords=0.7, thinking_location=0.5
**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

### Property 3: Learning period prevents injection
*For any* shortcut with usage_count < learning_period (10), the QualityController.should_inject() SHALL return False
**Validates: Requirements 3.1**

### Property 4: Validation thresholds are enforced
*For any* shortcut, validation SHALL fail if usage_count < 5 OR success_rate < 0.95 OR coord_variance >= 30 OR confidence < 0.9
**Validates: Requirements 3.2, 3.3, 3.4, 3.5**

### Property 5: Shortcut deduplication
*For any* two shortcuts with same (app, scene, element), the repository SHALL maintain only one record with updated usage_count
**Validates: Requirements 2.1, 2.2, 2.3**

### Property 6: Query filtering correctness
*For any* query by app and scene, the repository SHALL return only shortcuts matching both criteria
**Validates: Requirements 2.4**

### Property 7: Step-based prompt content
*For any* step_num >= 4, the ShortcutInjector SHALL include element position hints in the prompt
**Validates: Requirements 4.4**

### Property 8: Shortcut limit enforcement
*For any* injection with more than 3 available shortcuts, the ShortcutInjector SHALL display at most 3 shortcuts
**Validates: Requirements 4.5**

### Property 9: Disclaimer always present
*For any* non-empty shortcut prompt, the ShortcutInjector SHALL append the disclaimer text
**Validates: Requirements 4.6**

### Property 10: Variance calculation correctness
*For any* set of coordinates, the calculated variance SHALL match the standard deviation formula
**Validates: Requirements 7.1, 7.4**

### Property 11: Error handling - extraction failure
*For any* extraction failure, the system SHALL return None without raising exceptions
**Validates: Requirements 8.2**

### Property 12: Error handling - injection failure
*For any* injection failure, the system SHALL return empty string without raising exceptions
**Validates: Requirements 8.3**

## Error Handling

### Extraction Errors
```python
def extract_from_step(self, step_data: Dict) -> Optional[MentalShortcut]:
    try:
        # extraction logic
        return shortcut
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return None  # 不影响任务执行
```

### Database Errors
```python
def save(self, shortcut: MentalShortcut) -> int:
    try:
        # database operation
        return shortcut_id
    except Exception as e:
        logger.error(f"Database save failed: {e}")
        return -1  # 返回无效ID
```

### Injection Errors
```python
def build_shortcut_prompt(self, ...) -> str:
    try:
        # build prompt
        return prompt
    except Exception as e:
        logger.error(f"Injection failed: {e}")
        return ""  # 返回空字符串，使用原始提示词
```

## Testing Strategy

### Unit Testing
- 使用 pytest 框架
- 每个组件独立测试
- Mock 外部依赖（数据库、文件系统）

### Property-Based Testing
- 使用 hypothesis 库进行属性测试
- 每个 Correctness Property 对应一个属性测试
- 最少运行 100 次迭代

**Property-Based Testing Library**: hypothesis

**Test Annotation Format**: 
```python
# **Feature: mental-shortcut-system, Property {number}: {property_text}**
```

### Test Files Structure
```
tests/
├── test_thinking_extractor.py
├── test_mental_shortcut_repository.py
├── test_shortcut_quality_controller.py
├── test_shortcut_injector.py
└── test_integration.py
```

### Key Test Cases

1. **ThinkingExtractor**
   - 从 action 提取坐标
   - 从 thinking 提取坐标（fallback）
   - 位置描述提取
   - 元素名称提取
   - 置信度计算

2. **MentalShortcutRepository**
   - CRUD 操作
   - 去重逻辑
   - 查询过滤
   - 统计更新

3. **ShortcutQualityController**
   - 学习期检查
   - 阈值验证
   - 失败原因返回

4. **ShortcutInjector**
   - 分步骤提示词
   - 数量限制
   - 免责声明

5. **Integration**
   - 完整流程测试
   - 错误处理测试

