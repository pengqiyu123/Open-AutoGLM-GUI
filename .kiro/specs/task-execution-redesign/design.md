# 任务执行与数据持久化重构设计文档

## 概述

本文档描述了任务执行和数据持久化系统的完全重构设计。新架构采用状态机模式、同步持久化和独立的数据访问层，从根本上解决当前实现中的数据丢失和状态不一致问题。

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                         GUI Layer                            │
│  (MainWindow, TaskInputWidget, DataStorageWidget)           │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    Task Executor Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ TaskExecutor │  │  StateMachine│  │  StepBuffer  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│              Data Persistence Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ TaskRepository│  │StepRepository│  │BackupManager │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                      Database Layer                          │
│              (SQLite with WAL mode)                          │
└─────────────────────────────────────────────────────────────┘
```

## 组件设计

### 1. TaskStateMachine (任务状态机)

**职责**: 管理任务状态转换，确保状态转换的合法性和原子性。

**状态定义**:
```python
class TaskState(Enum):
    CREATED = "CREATED"       # 任务已创建
    RUNNING = "RUNNING"       # 任务执行中
    STOPPING = "STOPPING"     # 任务停止中
    STOPPED = "STOPPED"       # 任务已停止
    SUCCESS = "SUCCESS"       # 任务成功完成
    FAILED = "FAILED"         # 任务执行失败
    CRASHED = "CRASHED"       # 系统崩溃
```

**状态转换规则**:
```
CREATED → RUNNING
RUNNING → STOPPING → STOPPED
RUNNING → SUCCESS
RUNNING → FAILED
任何状态 → CRASHED (系统崩溃时)
```

**接口设计**:
```python
class TaskStateMachine:
    def __init__(self, session_id: str, persistence_layer):
        self.session_id = session_id
        self.current_state = TaskState.CREATED
        self.persistence = persistence_layer
        self.lock = threading.Lock()
    
    def transition_to(self, new_state: TaskState) -> bool:
        """
        尝试转换到新状态
        Returns: True if transition successful, False otherwise
        """
        with self.lock:
            if self._is_valid_transition(new_state):
                old_state = self.current_state
                self.current_state = new_state
                # 立即持久化状态变更
                self.persistence.update_task_state(
                    self.session_id, new_state
                )
                self._emit_state_changed(old_state, new_state)
                return True
            return False
    
    def _is_valid_transition(self, new_state: TaskState) -> bool:
        """验证状态转换是否合法"""
        valid_transitions = {
            TaskState.CREATED: [TaskState.RUNNING],
            TaskState.RUNNING: [TaskState.STOPPING, TaskState.SUCCESS, TaskState.FAILED],
            TaskState.STOPPING: [TaskState.STOPPED],
        }
        return new_state in valid_transitions.get(self.current_state, [])
```

### 2. StepBuffer (步骤缓冲区)

**职责**: 临时存储步骤数据，确保数据不丢失，支持批量写入。

**设计**:
```python
class StepBuffer:
    def __init__(self, session_id: str, persistence_layer, max_size: int = 10):
        self.session_id = session_id
        self.persistence = persistence_layer
        self.max_size = max_size
        self.buffer: List[StepData] = []
        self.lock = threading.Lock()
    
    def add_step(self, step_data: StepData):
        """添加步骤到缓冲区"""
        with self.lock:
            self.buffer.append(step_data)
            # 立即写入数据库（同步）
            self._write_step_immediately(step_data)
            
            # 如果缓冲区满，触发批量优化
            if len(self.buffer) >= self.max_size:
                self._optimize_buffer()
    
    def _write_step_immediately(self, step_data: StepData):
        """立即写入单个步骤（同步）"""
        try:
            self.persistence.insert_step(step_data)
        except Exception as e:
            # 写入失败，保存到备份文件
            self._save_to_backup(step_data)
            raise
    
    def flush(self):
        """刷新缓冲区，确保所有数据已写入"""
        with self.lock:
            # 验证所有步骤都已写入数据库
            for step in self.buffer:
                if not self.persistence.step_exists(step.step_num):
                    self._write_step_immediately(step)
            self.buffer.clear()
    
    def _save_to_backup(self, step_data: StepData):
        """保存到备份文件"""
        backup_file = f"logs/backup/{self.session_id}.json"
        # 实现备份逻辑
```

### 3. DataPersistenceLayer (数据持久化层)

**职责**: 统一管理所有数据库操作，提供事务支持和错误处理。

**组件结构**:

#### 3.1 TaskRepository
```python
class TaskRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection_pool = self._create_connection_pool()
    
    def create_task(self, task_data: TaskData) -> str:
        """创建任务记录（同步）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (
                    session_id, user_id, timestamp, task_description,
                    final_status, total_steps, total_time, error_message,
                    device_id, base_url, model_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_data.session_id,
                task_data.user_id,
                task_data.timestamp,
                task_data.description,
                TaskState.CREATED.value,
                0, None, None,
                task_data.device_id,
                task_data.base_url,
                task_data.model_name
            ))
            conn.commit()
            return task_data.session_id
    
    def update_task_state(self, session_id: str, state: TaskState):
        """更新任务状态（同步，带重试）"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE tasks 
                        SET final_status = ?, 
                            updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = ?
                    """, (state.value, session_id))
                    
                    if cursor.rowcount == 0:
                        raise ValueError(f"Task {session_id} not found")
                    
                    conn.commit()
                    return
            except sqlite3.OperationalError as e:
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))  # 指数退避
                else:
                    raise
    
    def finalize_task(self, session_id: str, final_state: TaskState, 
                     total_steps: int, total_time: float, error_msg: str = None):
        """最终化任务（同步）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tasks 
                SET final_status = ?,
                    total_steps = ?,
                    total_time = ?,
                    error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, (final_state.value, total_steps, total_time, error_msg, session_id))
            conn.commit()
```

#### 3.2 StepRepository
```python
class StepRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection_pool = self._create_connection_pool()
    
    def insert_step(self, step_data: StepData):
        """插入步骤记录（同步）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO steps (
                    session_id, step_num, screenshot_path, screenshot_analysis,
                    action, action_params, execution_time, success, message, thinking
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                step_data.session_id,
                step_data.step_num,
                step_data.screenshot_path,
                step_data.screenshot_analysis,
                json.dumps(step_data.action) if step_data.action else None,
                json.dumps(step_data.action_params) if step_data.action_params else None,
                step_data.execution_time,
                1 if step_data.success else 0,
                step_data.message,
                step_data.thinking
            ))
            conn.commit()
    
    def batch_insert_steps(self, steps: List[StepData]):
        """批量插入步骤（事务）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            conn.execute("BEGIN TRANSACTION")
            try:
                for step in steps:
                    cursor.execute("""
                        INSERT INTO steps (...)
                        VALUES (?, ?, ?, ...)
                    """, (...))
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise
    
    def step_exists(self, session_id: str, step_num: int) -> bool:
        """检查步骤是否存在"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM steps 
                WHERE session_id = ? AND step_num = ?
            """, (session_id, step_num))
            return cursor.fetchone() is not None
```

#### 3.3 BackupManager
```python
class BackupManager:
    def __init__(self, backup_dir: str = "logs/backup"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def save_task_backup(self, session_id: str, task_data: dict):
        """保存任务备份"""
        backup_file = self.backup_dir / f"{session_id}_task.json"
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(task_data, f, ensure_ascii=False, indent=2)
    
    def save_step_backup(self, session_id: str, step_data: dict):
        """保存步骤备份（追加模式）"""
        backup_file = self.backup_dir / f"{session_id}_steps.jsonl"
        with open(backup_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(step_data, ensure_ascii=False) + '\n')
    
    def recover_from_backup(self, session_id: str) -> Tuple[dict, List[dict]]:
        """从备份恢复数据"""
        task_file = self.backup_dir / f"{session_id}_task.json"
        steps_file = self.backup_dir / f"{session_id}_steps.jsonl"
        
        task_data = None
        if task_file.exists():
            with open(task_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
        
        steps_data = []
        if steps_file.exists():
            with open(steps_file, 'r', encoding='utf-8') as f:
                for line in f:
                    steps_data.append(json.loads(line))
        
        return task_data, steps_data
    
    def cleanup_backup(self, session_id: str):
        """清理备份文件"""
        task_file = self.backup_dir / f"{session_id}_task.json"
        steps_file = self.backup_dir / f"{session_id}_steps.jsonl"
        
        if task_file.exists():
            task_file.unlink()
        if steps_file.exists():
            steps_file.unlink()
```

### 4. TaskExecutor (任务执行器)

**职责**: 管理任务的完整生命周期，协调各个组件。

**设计**:
```python
class TaskExecutor:
    def __init__(self, task_data: TaskData, persistence_layer):
        self.session_id = task_data.session_id
        self.task_data = task_data
        self.persistence = persistence_layer
        
        # 核心组件
        self.state_machine = TaskStateMachine(self.session_id, persistence_layer)
        self.step_buffer = StepBuffer(self.session_id, persistence_layer)
        self.backup_manager = BackupManager()
        
        # 控制标志
        self.stop_requested = threading.Event()
        self.worker_thread: Optional[QThread] = None
        self.agent_runner: Optional[AgentRunner] = None
        
        # 统计信息
        self.start_time: Optional[float] = None
        self.step_count: int = 0
    
    def start(self):
        """启动任务执行"""
        try:
            # 1. 创建任务记录
            self.persistence.task_repo.create_task(self.task_data)
            
            # 2. 转换状态到 RUNNING
            if not self.state_machine.transition_to(TaskState.RUNNING):
                raise RuntimeError("Failed to transition to RUNNING state")
            
            # 3. 记录开始时间
            self.start_time = time.time()
            
            # 4. 启动工作线程
            self._start_worker_thread()
            
        except Exception as e:
            # 启动失败，转换到 FAILED 状态
            self.state_machine.transition_to(TaskState.FAILED)
            self.persistence.task_repo.finalize_task(
                self.session_id, TaskState.FAILED, 0, 0, str(e)
            )
            raise
    
    def stop(self):
        """停止任务执行"""
        # 1. 设置停止标志
        self.stop_requested.set()
        
        # 2. 转换状态到 STOPPING
        if not self.state_machine.transition_to(TaskState.STOPPING):
            return  # 已经在停止或已完成
        
        # 3. 停止 agent runner
        if self.agent_runner:
            self.agent_runner.stop()
        
        # 4. 等待工作线程完成当前步骤（非阻塞）
        QTimer.singleShot(100, self._finalize_stop)
    
    def _finalize_stop(self):
        """最终化停止流程"""
        # 1. 刷新步骤缓冲区
        self.step_buffer.flush()
        
        # 2. 计算总耗时
        total_time = time.time() - self.start_time if self.start_time else 0
        
        # 3. 转换状态到 STOPPED
        self.state_machine.transition_to(TaskState.STOPPED)
        
        # 4. 更新任务最终状态
        self.persistence.task_repo.finalize_task(
            self.session_id,
            TaskState.STOPPED,
            self.step_count,
            total_time,
            "Stopped by user"
        )
        
        # 5. 清理备份文件
        self.backup_manager.cleanup_backup(self.session_id)
        
        # 6. 清理资源
        self._cleanup()
    
    def on_step_completed(self, step_num: int, step_data: StepData):
        """处理步骤完成事件"""
        # 检查是否已请求停止
        if self.stop_requested.is_set():
            return  # 忽略停止后的步骤
        
        # 更新步骤计数
        self.step_count = max(self.step_count, step_num)
        
        # 添加到缓冲区（会立即写入数据库）
        try:
            self.step_buffer.add_step(step_data)
        except Exception as e:
            # 写入失败，保存到备份
            self.backup_manager.save_step_backup(self.session_id, step_data.__dict__)
    
    def on_task_completed(self, success: bool, error_msg: str = None):
        """处理任务完成事件"""
        # 1. 刷新缓冲区
        self.step_buffer.flush()
        
        # 2. 计算总耗时
        total_time = time.time() - self.start_time if self.start_time else 0
        
        # 3. 确定最终状态
        final_state = TaskState.SUCCESS if success else TaskState.FAILED
        
        # 4. 转换状态
        self.state_machine.transition_to(final_state)
        
        # 5. 更新任务最终状态
        self.persistence.task_repo.finalize_task(
            self.session_id,
            final_state,
            self.step_count,
            total_time,
            error_msg
        )
        
        # 6. 清理备份文件
        self.backup_manager.cleanup_backup(self.session_id)
        
        # 7. 清理资源
        self._cleanup()
    
    def _cleanup(self):
        """清理资源"""
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait(1000)  # 等待最多1秒
            self.worker_thread = None
        
        if self.agent_runner:
            self.agent_runner = None
```

## 数据模型

### TaskData
```python
@dataclass
class TaskData:
    session_id: str
    user_id: str
    timestamp: str
    description: str
    device_id: Optional[str]
    base_url: Optional[str]
    model_name: Optional[str]
```

### StepData
```python
@dataclass
class StepData:
    session_id: str
    step_num: int
    screenshot_path: Optional[str]
    screenshot_analysis: Optional[str]
    action: Optional[dict]
    action_params: Optional[dict]
    execution_time: Optional[float]
    success: bool
    message: str
    thinking: Optional[str]
```

## 错误处理策略

### 1. 数据库操作失败
```python
def _handle_db_error(self, operation: str, error: Exception):
    """处理数据库错误"""
    # 1. 记录错误日志
    logger.error(f"Database operation failed: {operation}", exc_info=error)
    
    # 2. 尝试重连
    if isinstance(error, sqlite3.OperationalError):
        self._reconnect_database()
    
    # 3. 保存到备份
    self.backup_manager.save_task_backup(self.session_id, self._get_current_state())
    
    # 4. 通知用户
    self._emit_error_signal(f"数据保存失败: {str(error)}")
```

### 2. 系统崩溃恢复
```python
def recover_crashed_tasks(persistence_layer):
    """恢复崩溃的任务"""
    # 1. 查找所有 RUNNING 或 STOPPING 状态的任务
    crashed_tasks = persistence_layer.task_repo.find_tasks_by_states([
        TaskState.RUNNING, TaskState.STOPPING
    ])
    
    # 2. 将它们标记为 CRASHED
    for task in crashed_tasks:
        persistence_layer.task_repo.update_task_state(
            task.session_id, TaskState.CRASHED
        )
    
    # 3. 尝试从备份恢复数据
    backup_manager = BackupManager()
    for task in crashed_tasks:
        task_data, steps_data = backup_manager.recover_from_backup(task.session_id)
        if steps_data:
            # 恢复缺失的步骤
            for step in steps_data:
                if not persistence_layer.step_repo.step_exists(
                    task.session_id, step['step_num']
                ):
                    persistence_layer.step_repo.insert_step(StepData(**step))
```

## 性能优化

### 1. 连接池
```python
class ConnectionPool:
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self.connections: Queue = Queue(maxsize=pool_size)
        self._initialize_pool()
    
    def _initialize_pool(self):
        for _ in range(self.pool_size):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            self.connections.put(conn)
    
    @contextmanager
    def get_connection(self):
        conn = self.connections.get()
        try:
            yield conn
        finally:
            self.connections.put(conn)
```

### 2. 批量写入优化
```python
def optimize_batch_insert(steps: List[StepData]):
    """优化批量插入"""
    # 使用 executemany 而不是多次 execute
    with conn.cursor() as cursor:
        cursor.executemany("""
            INSERT INTO steps (...) VALUES (?, ?, ...)
        """, [step.to_tuple() for step in steps])
```

## 测试策略

### 单元测试
- TaskStateMachine: 测试所有状态转换
- StepBuffer: 测试缓冲区操作
- TaskRepository/StepRepository: 测试数据库操作
- BackupManager: 测试备份和恢复

### 集成测试
- 完整任务执行流程
- 停止任务流程
- 错误恢复流程
- 并发场景

### 性能测试
- 1000 个步骤的任务执行
- 并发执行多个任务
- 数据库操作延迟测试

## 迁移策略

### 数据库迁移
```python
def migrate_database():
    """迁移数据库到新架构"""
    # 1. 备份现有数据库
    shutil.copy("logs/tasks.db", "logs/tasks.db.backup")
    
    # 2. 添加新字段
    conn = sqlite3.connect("logs/tasks.db")
    conn.execute("ALTER TABLE tasks ADD COLUMN updated_at TEXT")
    
    # 3. 修复 UNKNOWN 状态
    conn.execute("""
        UPDATE tasks 
        SET final_status = 'CRASHED' 
        WHERE final_status = 'UNKNOWN'
    """)
    
    conn.commit()
    conn.close()
```

## 部署计划

### 阶段 1: 核心组件（1-2 周）
- 实现 TaskStateMachine
- 实现 DataPersistenceLayer
- 单元测试

### 阶段 2: 执行器（1-2 周）
- 实现 TaskExecutor
- 实现 StepBuffer
- 集成测试

### 阶段 3: 错误处理（1 周）
- 实现 BackupManager
- 实现错误恢复
- 压力测试

### 阶段 4: 集成和测试（1 周）
- 集成到 MainWindow
- 端到端测试
- 性能优化

总计: 4-6 周
