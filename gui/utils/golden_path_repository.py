"""
Golden Path Repository - 黄金路径数据库操作

负责黄金路径的数据库存储、查询和更新操作。
"""

import sqlite3
import json
from typing import List, Optional, Dict
from datetime import datetime
from threading import Lock


class GoldenPathRepository:
    """黄金路径数据库仓库"""

    def __init__(self, db_path: str):
        """
        初始化仓库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._db_lock = Lock()
        self._ensure_tables()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self) -> None:
        """确保数据库表存在"""
        with self._db_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            
            # 创建黄金路径表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS golden_paths (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_pattern TEXT NOT NULL,
                    apps TEXT,
                    difficulty TEXT,
                    can_replay INTEGER DEFAULT 0,
                    natural_sop TEXT,
                    action_sop TEXT,
                    common_errors TEXT,
                    correct_path TEXT,
                    forbidden TEXT,
                    hints TEXT,
                    success_rate REAL DEFAULT 0.0,
                    usage_count INTEGER DEFAULT 0,
                    source_sessions TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            
            # 检查并添加新字段（兼容旧数据库）
            try:
                cur.execute("SELECT correct_path FROM golden_paths LIMIT 1")
            except:
                cur.execute("ALTER TABLE golden_paths ADD COLUMN correct_path TEXT")
            
            try:
                cur.execute("SELECT forbidden FROM golden_paths LIMIT 1")
            except:
                cur.execute("ALTER TABLE golden_paths ADD COLUMN forbidden TEXT")
            
            try:
                cur.execute("SELECT hints FROM golden_paths LIMIT 1")
            except:
                cur.execute("ALTER TABLE golden_paths ADD COLUMN hints TEXT")
            
            # 创建索引
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_golden_paths_pattern
                ON golden_paths(task_pattern)
            """)
            
            conn.commit()
            conn.close()

    def save(self, golden_path) -> int:
        """
        保存黄金路径到数据库
        
        如果已存在相同 task_pattern 的路径，则更新而不是插入新记录。
        
        Args:
            golden_path: GoldenPath 对象
            
        Returns:
            记录 ID（新插入或已存在的）
        """
        with self._db_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            
            # 检查是否已存在相同的 task_pattern
            cur.execute(
                "SELECT id FROM golden_paths WHERE task_pattern = ?",
                (golden_path.task_pattern,)
            )
            existing = cur.fetchone()
            
            if existing:
                # 更新现有记录
                path_id = existing['id']
                cur.execute("""
                    UPDATE golden_paths
                    SET apps = ?,
                        difficulty = ?,
                        can_replay = ?,
                        natural_sop = ?,
                        action_sop = ?,
                        common_errors = ?,
                        correct_path = ?,
                        forbidden = ?,
                        hints = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    json.dumps(golden_path.apps, ensure_ascii=False),
                    golden_path.difficulty,
                    1 if golden_path.can_replay else 0,
                    golden_path.natural_sop,
                    json.dumps(golden_path.action_sop, ensure_ascii=False),
                    json.dumps(golden_path.common_errors, ensure_ascii=False),
                    json.dumps(getattr(golden_path, 'correct_path', []), ensure_ascii=False),
                    json.dumps(getattr(golden_path, 'forbidden', []), ensure_ascii=False),
                    json.dumps(getattr(golden_path, 'hints', []), ensure_ascii=False),
                    golden_path.updated_at,
                    path_id
                ))
                print(f"更新已存在的黄金路径 ID={path_id}")
            else:
                # 插入新记录
                cur.execute("""
                    INSERT INTO golden_paths (
                        task_pattern, apps, difficulty, can_replay,
                        natural_sop, action_sop, common_errors,
                        correct_path, forbidden, hints,
                        success_rate, usage_count, source_sessions,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    golden_path.task_pattern,
                    json.dumps(golden_path.apps, ensure_ascii=False),
                    golden_path.difficulty,
                    1 if golden_path.can_replay else 0,
                    golden_path.natural_sop,
                    json.dumps(golden_path.action_sop, ensure_ascii=False),
                    json.dumps(golden_path.common_errors, ensure_ascii=False),
                    json.dumps(getattr(golden_path, 'correct_path', []), ensure_ascii=False),
                    json.dumps(getattr(golden_path, 'forbidden', []), ensure_ascii=False),
                    json.dumps(getattr(golden_path, 'hints', []), ensure_ascii=False),
                    golden_path.success_rate,
                    golden_path.usage_count,
                    json.dumps(golden_path.source_sessions, ensure_ascii=False),
                    golden_path.created_at,
                    golden_path.updated_at
                ))
                path_id = cur.lastrowid
                print(f"创建新黄金路径 ID={path_id}")
            
            conn.commit()
            conn.close()
            
            return path_id

    def update(self, path_id: int, golden_path) -> bool:
        """
        更新黄金路径
        
        Args:
            path_id: 路径 ID
            golden_path: GoldenPath 对象
            
        Returns:
            是否更新成功
        """
        with self._db_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            
            cur.execute("""
                UPDATE golden_paths
                SET task_pattern = ?,
                    apps = ?,
                    difficulty = ?,
                    can_replay = ?,
                    natural_sop = ?,
                    action_sop = ?,
                    common_errors = ?,
                    success_rate = ?,
                    usage_count = ?,
                    source_sessions = ?,
                    updated_at = ?
                WHERE id = ?
            """, (
                golden_path.task_pattern,
                json.dumps(golden_path.apps, ensure_ascii=False),
                golden_path.difficulty,
                1 if golden_path.can_replay else 0,
                golden_path.natural_sop,
                json.dumps(golden_path.action_sop, ensure_ascii=False),
                json.dumps(golden_path.common_errors, ensure_ascii=False),
                golden_path.success_rate,
                golden_path.usage_count,
                json.dumps(golden_path.source_sessions, ensure_ascii=False),
                datetime.now().isoformat(),
                path_id
            ))
            
            success = cur.rowcount > 0
            conn.commit()
            conn.close()
            
            return success

    def find_by_id(self, path_id: int) -> Optional[Dict]:
        """
        根据 ID 查找黄金路径
        
        Args:
            path_id: 路径 ID
            
        Returns:
            黄金路径字典，如果不存在则返回 None
        """
        with self._db_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT * FROM golden_paths WHERE id = ?
            """, (path_id,))
            
            row = cur.fetchone()
            conn.close()
            
            if row:
                return self._row_to_dict(row)
            return None

    def find_by_pattern(self, task_pattern: str) -> List[Dict]:
        """
        根据任务模式查找黄金路径
        
        Args:
            task_pattern: 任务模式（支持模糊匹配）
            
        Returns:
            黄金路径字典列表
        """
        with self._db_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT * FROM golden_paths
                WHERE task_pattern LIKE ?
                ORDER BY success_rate DESC, usage_count DESC
            """, (f'%{task_pattern}%',))
            
            rows = cur.fetchall()
            conn.close()
            
            return [self._row_to_dict(row) for row in rows]

    def find_all(self) -> List[Dict]:
        """
        获取所有黄金路径
        
        Returns:
            黄金路径字典列表
        """
        with self._db_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT * FROM golden_paths
                ORDER BY created_at DESC
            """)
            
            rows = cur.fetchall()
            conn.close()
            
            return [self._row_to_dict(row) for row in rows]

    def delete(self, path_id: int) -> bool:
        """
        删除黄金路径
        
        Args:
            path_id: 路径 ID
            
        Returns:
            是否删除成功
        """
        with self._db_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            
            cur.execute("""
                DELETE FROM golden_paths WHERE id = ?
            """, (path_id,))
            
            success = cur.rowcount > 0
            conn.commit()
            conn.close()
            
            return success

    def increment_usage(self, path_id: int) -> bool:
        """
        增加使用次数
        
        Args:
            path_id: 路径 ID
            
        Returns:
            是否更新成功
        """
        with self._db_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            
            cur.execute("""
                UPDATE golden_paths
                SET usage_count = usage_count + 1,
                    updated_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), path_id))
            
            success = cur.rowcount > 0
            conn.commit()
            conn.close()
            
            return success

    def update_success_rate(self, path_id: int, new_rate: float) -> bool:
        """
        更新成功率
        
        Args:
            path_id: 路径 ID
            new_rate: 新的成功率 (0.0 - 1.0)
            
        Returns:
            是否更新成功
        """
        with self._db_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            
            cur.execute("""
                UPDATE golden_paths
                SET success_rate = ?,
                    updated_at = ?
                WHERE id = ?
            """, (new_rate, datetime.now().isoformat(), path_id))
            
            success = cur.rowcount > 0
            conn.commit()
            conn.close()
            
            return success

    def get_statistics(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        with self._db_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            
            # 总数
            cur.execute("SELECT COUNT(*) FROM golden_paths")
            total_count = cur.fetchone()[0]
            
            # 平均成功率
            cur.execute("SELECT AVG(success_rate) FROM golden_paths")
            avg_success_rate = cur.fetchone()[0] or 0.0
            
            # 总使用次数
            cur.execute("SELECT SUM(usage_count) FROM golden_paths")
            total_usage = cur.fetchone()[0] or 0
            
            # 按难度分组统计
            cur.execute("""
                SELECT difficulty, COUNT(*) as count
                FROM golden_paths
                GROUP BY difficulty
            """)
            difficulty_stats = {row[0]: row[1] for row in cur.fetchall()}
            
            conn.close()
            
            return {
                'total_count': total_count,
                'avg_success_rate': avg_success_rate,
                'total_usage': total_usage,
                'difficulty_stats': difficulty_stats
            }

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """将数据库行转换为字典"""
        result = {
            'id': row['id'],
            'task_pattern': row['task_pattern'],
            'apps': json.loads(row['apps']) if row['apps'] else [],
            'difficulty': row['difficulty'],
            'can_replay': bool(row['can_replay']),
            'natural_sop': row['natural_sop'],
            'action_sop': json.loads(row['action_sop']) if row['action_sop'] else [],
            'common_errors': json.loads(row['common_errors']) if row['common_errors'] else [],
            'success_rate': row['success_rate'],
            'usage_count': row['usage_count'],
            'source_sessions': json.loads(row['source_sessions']) if row['source_sessions'] else [],
            'created_at': row['created_at'],
            'updated_at': row['updated_at']
        }
        
        # 新字段（兼容旧数据）
        try:
            result['correct_path'] = json.loads(row['correct_path']) if row['correct_path'] else []
        except (KeyError, TypeError):
            result['correct_path'] = []
        
        try:
            result['forbidden'] = json.loads(row['forbidden']) if row['forbidden'] else []
        except (KeyError, TypeError):
            result['forbidden'] = []
        
        try:
            result['hints'] = json.loads(row['hints']) if row['hints'] else []
        except (KeyError, TypeError):
            result['hints'] = []
        
        return result
