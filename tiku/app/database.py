"""
异步数据库操作 - 支持高并发连接池和 WAL 模式
"""

import json
import os
import asyncio
import logging
from typing import List, Optional

import aiosqlite

from .config import (
    DATABASE_FILE, MAX_QUESTION_LENGTH, MAX_OPTIONS_COUNT,
    MAX_SEARCH_LENGTH, MAX_LIMIT, MAX_OFFSET
)
from .schemas import QuestionCreate, QuestionUpdate
from .matching import normalize_question, text_similarity, options_match_score, combined_score

logger = logging.getLogger(__name__)


class AsyncDatabase:
    """异步数据库类 - 支持高并发，使用连接池和WAL模式"""

    def __init__(self, db_file: str):
        self.db_file = db_file
        self._lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._question_count: Optional[int] = None
        self._count_cache_time: float = 0
        self._cache_ttl: int = 60
        self._connection_pool: List[aiosqlite.Connection] = []
        self._pool_lock = asyncio.Lock()
        self._pool_size = 10
        self._initialized = False

    async def _get_connection(self) -> aiosqlite.Connection:
        async with self._pool_lock:
            if self._connection_pool:
                return self._connection_pool.pop()
            conn = await aiosqlite.connect(self.db_file, timeout=30.0)
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA cache_size=10000")
            await conn.execute("PRAGMA temp_store=MEMORY")
            await conn.execute("PRAGMA busy_timeout=30000")
            return conn

    async def _release_connection(self, conn: aiosqlite.Connection):
        async with self._pool_lock:
            if len(self._connection_pool) < self._pool_size:
                self._connection_pool.append(conn)
            else:
                await conn.close()

    async def init_db(self):
        async with self._lock:
            if self._initialized:
                return

            conn = await self._get_connection()
            try:
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS questions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question TEXT NOT NULL,
                        type TEXT NOT NULL,
                        options TEXT DEFAULT '[]',
                        answer TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS pending_questions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question TEXT NOT NULL,
                        type TEXT NOT NULL,
                        options TEXT DEFAULT '[]',
                        search_count INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_question ON questions(question)')
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_pending_question ON pending_questions(question)')
                await conn.execute('CREATE INDEX IF NOT EXISTS idx_type ON questions(type)')

                # 迁移：检查 pending_questions 是否有 options 列
                cursor = await conn.execute("PRAGMA table_info(pending_questions)")
                columns = await cursor.fetchall()
                column_names = [col['name'] for col in columns]
                if 'options' not in column_names:
                    await conn.execute("ALTER TABLE pending_questions ADD COLUMN options TEXT DEFAULT '[]'")
                    logger.info("Migration: added options column to pending_questions")

                await conn.commit()
                self._initialized = True
            finally:
                await self._release_connection(conn)

    async def import_from_json(self, json_file: str) -> bool:
        if not os.path.exists(json_file):
            logger.warning(f"找不到文件 {json_file}")
            return False

        try:
            async with self._lock:
                with open(json_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not content.strip():
                        logger.warning(f"JSON文件为空: {json_file}")
                        return False
                    questions = json.loads(content)

                if not isinstance(questions, list):
                    logger.error(f"JSON格式错误: 期望数组，得到 {type(questions)}")
                    return False

                conn = await self._get_connection()
                try:
                    await conn.execute('DELETE FROM questions')
                    batch = []
                    for q in questions:
                        if not isinstance(q, dict):
                            continue
                        question_text = str(q.get('question', '')).strip()
                        question_type = str(q.get('type', '0')).strip()
                        options = q.get('options', [])
                        answer = str(q.get('answer', '')).strip()

                        if not question_text or not answer:
                            continue

                        if isinstance(options, list):
                            options_str = json.dumps(options, ensure_ascii=False)
                        else:
                            options_str = '[]'

                        batch.append((question_text, question_type, options_str, answer))

                        if len(batch) >= 1000:
                            await conn.executemany(
                                'INSERT INTO questions (question, type, options, answer) VALUES (?, ?, ?, ?)',
                                batch
                            )
                            batch = []

                    if batch:
                        await conn.executemany(
                            'INSERT INTO questions (question, type, options, answer) VALUES (?, ?, ?, ?)',
                            batch
                        )

                    await conn.commit()
                    self._question_count = None
                    logger.info(f"成功导入 {len(questions)} 道题目")
                    return True
                finally:
                    await self._release_connection(conn)
        except Exception as e:
            logger.error(f"导入JSON失败: {e}")
            return False

    async def get_all_questions(self, limit: int = 100, offset: int = 0) -> List[dict]:
        limit = max(1, min(limit, MAX_LIMIT))
        offset = max(0, min(offset, MAX_OFFSET))
        try:
            conn = await self._get_connection()
            try:
                cursor = await conn.execute(
                    'SELECT * FROM questions ORDER BY id DESC LIMIT ? OFFSET ?',
                    (limit, offset)
                )
                rows = await cursor.fetchall()
                return [self._row_to_dict(row) for row in rows]
            finally:
                await self._release_connection(conn)
        except Exception as e:
            logger.error(f"获取题目列表失败: {e}")
            return []

    async def get_question_by_id(self, question_id: int) -> Optional[dict]:
        try:
            conn = await self._get_connection()
            try:
                cursor = await conn.execute(
                    'SELECT * FROM questions WHERE id = ?', (question_id,)
                )
                row = await cursor.fetchone()
                return self._row_to_dict(row) if row else None
            finally:
                await self._release_connection(conn)
        except Exception as e:
            logger.error(f"获取题目失败 (id={question_id}): {e}")
            return None

    async def search_questions(self, keyword: str, limit: int = 50) -> List[dict]:
        if not keyword or len(keyword) > MAX_SEARCH_LENGTH:
            return []
        keyword = keyword.replace('%', '').replace('_', '').replace('[', '').replace(']', '')
        if not keyword:
            return []
        limit = max(1, min(limit, MAX_LIMIT))
        try:
            conn = await self._get_connection()
            try:
                cursor = await conn.execute(
                    'SELECT * FROM questions WHERE question LIKE ? ORDER BY id DESC LIMIT ?',
                    (f'%{keyword}%', limit)
                )
                rows = await cursor.fetchall()
                return [self._row_to_dict(row) for row in rows]
            finally:
                await self._release_connection(conn)
        except Exception as e:
            logger.error(f"搜索题目失败: {e}")
            return []

    async def find_by_question(
        self,
        question_text: str,
        question_type: str = None,
        options: List[str] = None
    ) -> Optional[dict]:
        """根据题目内容和选项查找"""
        if not question_text or len(question_text) > MAX_QUESTION_LENGTH:
            return None

        clean_input = question_text.replace("'", "").replace('"', "")
        has_options = bool(options)

        try:
            conn = await self._get_connection()
            try:
                candidates = []

                # 阶段1：带类型的精确匹配
                if question_type:
                    cursor = await conn.execute(
                        'SELECT * FROM questions WHERE question = ? AND type = ?',
                        (clean_input, question_type)
                    )
                    row = await cursor.fetchone()
                    if row:
                        candidates.append((1.0, self._row_to_dict(row)))

                    if not candidates:
                        search_text = clean_input[:100]
                        cursor = await conn.execute(
                            'SELECT * FROM questions WHERE question LIKE ? AND type = ? LIMIT 10',
                            (f'%{search_text}%', question_type)
                        )
                        rows = await cursor.fetchall()
                        for r in rows:
                            candidates.append((0.9, self._row_to_dict(r)))

                # 阶段2：无类型的精确匹配
                if not candidates:
                    cursor = await conn.execute(
                        'SELECT * FROM questions WHERE question = ?', (clean_input,)
                    )
                    row = await cursor.fetchone()
                    if row:
                        candidates.append((1.0, self._row_to_dict(row)))

                # 阶段3：模糊匹配
                if not candidates:
                    search_text = clean_input[:100]
                    cursor = await conn.execute(
                        'SELECT * FROM questions WHERE question LIKE ? LIMIT 10',
                        (f'%{search_text}%',)
                    )
                    rows = await cursor.fetchall()
                    for r in rows:
                        candidates.append((0.85, self._row_to_dict(r)))

                # 阶段4：反向模糊匹配
                if not candidates:
                    search_keyword = clean_input[:50]
                    cursor = await conn.execute(
                        "SELECT * FROM questions WHERE ? LIKE '%' || question || '%' LIMIT 10",
                        (search_keyword,)
                    )
                    rows = await cursor.fetchall()
                    for r in rows:
                        candidates.append((0.8, self._row_to_dict(r)))

                # 阶段5：清理后匹配
                if not candidates:
                    clean_text = clean_input.strip().rstrip(')').rstrip(' ').rstrip('(').rstrip(' ')
                    if clean_text and clean_text != clean_input and len(clean_text) > 5:
                        cursor = await conn.execute(
                            'SELECT * FROM questions WHERE question LIKE ? LIMIT 10',
                            (f'%{clean_text[:100]}%',)
                        )
                        rows = await cursor.fetchall()
                        for r in rows:
                            candidates.append((0.75, self._row_to_dict(r)))

                # 阶段6：去除下划线匹配
                if not candidates:
                    no_underscore = clean_input.replace('_', '').strip()
                    if no_underscore and no_underscore != clean_input and len(no_underscore) > 5:
                        cursor = await conn.execute(
                            'SELECT * FROM questions WHERE question LIKE ? OR ? LIKE \'%\' || question || \'%\' LIMIT 10',
                            (f'%{no_underscore[:100]}%', no_underscore[:100])
                        )
                        rows = await cursor.fetchall()
                        for r in rows:
                            candidates.append((0.7, self._row_to_dict(r)))

                # 阶段7：标准化模糊匹配
                if not candidates:
                    normalized_input = normalize_question(clean_input)
                    if normalized_input and len(normalized_input) > 5:
                        input_len = len(normalized_input)
                        min_len = max(1, input_len - 20)
                        max_len = input_len + 20
                        cursor = await conn.execute(
                            'SELECT * FROM questions WHERE length(question) >= ? AND length(question) <= ? LIMIT 500',
                            (min_len, max_len)
                        )
                        candidate_rows = await cursor.fetchall()
                        for r in candidate_rows:
                            r_dict = self._row_to_dict(r)
                            db_normalized = normalize_question(r_dict['question'])
                            sim = text_similarity(normalized_input, db_normalized)
                            if sim >= 0.85:
                                candidates.append((sim, r_dict))

                # 如果没有候选，返回 None
                if not candidates:
                    return None

                # 如果没有选项，返回第一个候选
                if not has_options:
                    return candidates[0][1]

                # 有选项时，计算综合得分排序
                scored = []
                for text_score, candidate in candidates:
                    db_options = candidate.get('options', [])
                    opt_score = options_match_score(options, db_options) if db_options else 0.0
                    score = combined_score(text_score, opt_score, has_options=True)
                    scored.append((score, candidate))

                scored.sort(key=lambda x: x[0], reverse=True)

                # 返回最高分（阈值 > 0.3）
                if scored and scored[0][0] > 0.3:
                    return scored[0][1]

                return candidates[0][1]

            finally:
                await self._release_connection(conn)
        except Exception as e:
            logger.error(f"查找题目失败: {e}")
            return None

    async def create_question(self, question: QuestionCreate) -> int:
        async with self._write_lock:
            try:
                conn = await self._get_connection()
                try:
                    cursor = await conn.execute(
                        'INSERT INTO questions (question, type, options, answer) VALUES (?, ?, ?, ?)',
                        (question.question, question.type,
                         json.dumps(question.options, ensure_ascii=False), question.answer)
                    )
                    await conn.commit()
                    self._question_count = None
                    return cursor.lastrowid
                finally:
                    await self._release_connection(conn)
            except Exception as e:
                logger.error(f"创建题目失败: {e}")
                raise

    async def update_question(self, question_id: int, question: QuestionUpdate) -> bool:
        if question_id <= 0 or question_id > 2147483647:
            return False
        async with self._write_lock:
            try:
                conn = await self._get_connection()
                try:
                    cursor = await conn.execute(
                        'SELECT * FROM questions WHERE id = ?', (question_id,)
                    )
                    row = await cursor.fetchone()
                    if not row:
                        return False
                    existing = self._row_to_dict(row)

                    new_question = question.question if question.question is not None else existing['question']
                    new_type = question.type if question.type is not None else existing['type']
                    new_options = question.options if question.options is not None else existing['options']
                    new_answer = question.answer if question.answer is not None else existing['answer']

                    await conn.execute(
                        'UPDATE questions SET question = ?, type = ?, options = ?, answer = ? WHERE id = ?',
                        (new_question, new_type, json.dumps(new_options, ensure_ascii=False),
                         new_answer, question_id)
                    )
                    await conn.commit()
                    return True
                finally:
                    await self._release_connection(conn)
            except Exception as e:
                logger.error(f"更新题目失败 (id={question_id}): {e}")
                return False

    async def delete_question(self, question_id: int) -> bool:
        if question_id <= 0 or question_id > 2147483647:
            return False
        async with self._write_lock:
            try:
                conn = await self._get_connection()
                try:
                    cursor = await conn.execute(
                        'DELETE FROM questions WHERE id = ?', (question_id,)
                    )
                    await conn.commit()
                    if cursor.rowcount > 0:
                        self._question_count = None
                        return True
                    return False
                finally:
                    await self._release_connection(conn)
            except Exception as e:
                logger.error(f"删除题目失败 (id={question_id}): {e}")
                return False

    async def get_count(self) -> int:
        current_time = asyncio.get_event_loop().time()
        if self._question_count is not None and (current_time - self._count_cache_time) < self._cache_ttl:
            return self._question_count
        try:
            conn = await self._get_connection()
            try:
                cursor = await conn.execute('SELECT COUNT(*) FROM questions')
                row = await cursor.fetchone()
                self._question_count = row[0] if row else 0
                self._count_cache_time = current_time
                return self._question_count
            finally:
                await self._release_connection(conn)
        except Exception as e:
            logger.error(f"获取题目总数失败: {e}")
            return self._question_count or 0

    async def get_all_questions_for_export(self) -> List[dict]:
        try:
            conn = await self._get_connection()
            try:
                cursor = await conn.execute(
                    'SELECT id, question, type, options, answer FROM questions ORDER BY id'
                )
                rows = await cursor.fetchall()
                result = []
                for row in rows:
                    try:
                        options = json.loads(row['options']) if row['options'] else []
                    except json.JSONDecodeError:
                        options = []
                    result.append({
                        'question': row['question'],
                        'type': row['type'],
                        'options': options,
                        'answer': row['answer']
                    })
                return result
            finally:
                await self._release_connection(conn)
        except Exception as e:
            logger.error(f"导出题目失败: {e}")
            return []

    # ============ 待处理题目 ============

    async def add_pending_question(self, question_text: str, question_type: str, options: List[str] = None):
        question_text = str(question_text)[:MAX_QUESTION_LENGTH] if question_text else ""
        question_type = str(question_type)[:50] if question_type else "0"
        if not question_text:
            return

        options_json = json.dumps(options or [], ensure_ascii=False)

        async with self._write_lock:
            try:
                conn = await self._get_connection()
                try:
                    cursor = await conn.execute(
                        'SELECT id, search_count FROM pending_questions WHERE question = ?',
                        (question_text,)
                    )
                    row = await cursor.fetchone()

                    if row:
                        new_count = min(row['search_count'] + 1, 999999)
                        if options:
                            await conn.execute(
                                'UPDATE pending_questions SET search_count = ?, options = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                                (new_count, options_json, row['id'])
                            )
                        else:
                            await conn.execute(
                                'UPDATE pending_questions SET search_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                                (new_count, row['id'])
                            )
                    else:
                        await conn.execute(
                            'INSERT INTO pending_questions (question, type, options) VALUES (?, ?, ?)',
                            (question_text, question_type, options_json)
                        )

                    await conn.commit()
                finally:
                    await self._release_connection(conn)
            except Exception as e:
                logger.error(f"添加待处理题目失败: {e}")

    async def get_pending_questions(self, limit: int = 100, offset: int = 0, search: str = "", sort: str = "count") -> List[dict]:
        limit = max(1, min(limit, MAX_LIMIT))
        offset = max(0, min(offset, MAX_OFFSET))

        order_map = {
            "count": "search_count DESC, updated_at DESC",
            "time": "updated_at DESC",
            "time_asc": "updated_at ASC"
        }
        order = order_map.get(sort, order_map["count"])

        try:
            conn = await self._get_connection()
            try:
                if search and search.strip():
                    keyword = search.strip().replace('%', '').replace('_', '')
                    cursor = await conn.execute(
                        f'SELECT * FROM pending_questions WHERE question LIKE ? ORDER BY {order} LIMIT ? OFFSET ?',
                        (f'%{keyword}%', limit, offset)
                    )
                else:
                    cursor = await conn.execute(
                        f'SELECT * FROM pending_questions ORDER BY {order} LIMIT ? OFFSET ?',
                        (limit, offset)
                    )
                rows = await cursor.fetchall()
                return [{
                    'id': row['id'],
                    'question': row['question'],
                    'type': row['type'],
                    'options': json.loads(row['options']) if row['options'] else [],
                    'search_count': row['search_count'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                } for row in rows]
            finally:
                await self._release_connection(conn)
        except Exception as e:
            logger.error(f"获取待处理题目失败: {e}")
            return []

    async def get_pending_count(self, search: str = "") -> int:
        try:
            conn = await self._get_connection()
            try:
                if search and search.strip():
                    keyword = search.strip().replace('%', '').replace('_', '')
                    cursor = await conn.execute(
                        'SELECT COUNT(*) FROM pending_questions WHERE question LIKE ?',
                        (f'%{keyword}%',)
                    )
                else:
                    cursor = await conn.execute('SELECT COUNT(*) FROM pending_questions')
                row = await cursor.fetchone()
                return row[0] if row else 0
            finally:
                await self._release_connection(conn)
        except Exception as e:
            logger.error(f"获取待处理数量失败: {e}")
            return 0

    async def delete_pending_question(self, pending_id: int) -> bool:
        if pending_id <= 0 or pending_id > 2147483647:
            return False
        async with self._write_lock:
            try:
                conn = await self._get_connection()
                try:
                    cursor = await conn.execute(
                        'DELETE FROM pending_questions WHERE id = ?', (pending_id,)
                    )
                    await conn.commit()
                    return cursor.rowcount > 0
                finally:
                    await self._release_connection(conn)
            except Exception as e:
                logger.error(f"删除待处理题目失败 (id={pending_id}): {e}")
                return False

    def _row_to_dict(self, row) -> dict:
        if row is None:
            return {}
        try:
            options = json.loads(row['options']) if row['options'] else []
        except (json.JSONDecodeError, TypeError):
            options = []
        return {
            'id': row['id'],
            'question': row['question'],
            'type': row['type'],
            'options': options,
            'answer': row['answer'],
            'created_at': row['created_at'] if 'created_at' in row.keys() else None
        }
