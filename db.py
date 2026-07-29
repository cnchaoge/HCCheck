"""运管站货车审验 - SQLite 处理结果数据库

数据层:所有车处理结果写入 ~/Library/Application Support/HCCheck/hccheck.db
- 一次运行一个 run_id (UUID),便于按"这次跑"查询
- 字段与原 xlsx 保持兼容
- 启动时自动 init_db(),无需手动建表

替代旧的 export_results_excel() (每次跑生成新 xlsx 累积问题)
"""
import sqlite3
import time as _time
import uuid

import config


# ========= Schema =========
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    plate TEXT NOT NULL,
    flow_type TEXT NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL,
    duration REAL,
    status TEXT NOT NULL,
    error TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_plate ON runs(plate);
CREATE INDEX IF NOT EXISTS idx_run_id ON runs(run_id);
CREATE INDEX IF NOT EXISTS idx_created ON runs(created_at);
"""


# ========= 一次运行一个 run_id (程序内一致) =========
_RUN_ID = f"{_time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"


def get_run_id() -> str:
    """返回当前运行的唯一 ID (整个程序运行期间保持一致)"""
    return _RUN_ID


# ========= 初始化 =========
def init_db() -> bool:
    """启动时初始化数据库(创建表 + 索引,幂等)

    返回:True=成功, False=失败(降级处理,不阻断主流程)
    """
    try:
        with sqlite3.connect(config.DB_FILE, timeout=5) as conn:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
        return True
    except Exception as e:
        if config.DEBUG:
            print(f"  调试 - 初始化数据库失败: {e}")
        return False


# ========= 写入 =========
def record_run(plate: str, flow_type: str, start_time: float, end_time: float,
               status: str, error: str = "", run_id: str = None) -> bool:
    """记录一次处理结果到数据库

    Args:
        plate: 车牌号 (如 "冀J0E139")
        flow_type: '带挂' / '不带挂'
        start_time, end_time: epoch 时间戳 (time.time())
        status: '成功' / '失败'
        error: 错误信息(成功时为空)
        run_id: 一次运行的 UUID,None 则用全局 _RUN_ID

    Returns:True=成功写入,False=失败
    """
    if run_id is None:
        run_id = _RUN_ID
    duration = end_time - start_time
    try:
        with sqlite3.connect(config.DB_FILE, timeout=5) as conn:
            conn.execute("""
                INSERT INTO runs (run_id, plate, flow_type, start_time, end_time,
                                  duration, status, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (run_id, plate, flow_type, start_time, end_time,
                  duration, status, error))
            conn.commit()
        return True
    except Exception as e:
        if config.DEBUG:
            print(f"  调试 - 记录数据库失败: {e}")
        return False
