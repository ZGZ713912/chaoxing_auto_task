"""
题目管理接口 - /api/questions
"""

import logging
from fastapi import APIRouter, Request, HTTPException, Query

from ..schemas import QuestionCreate, QuestionUpdate
from ..config import MAX_LIMIT, MAX_OFFSET, MAX_SEARCH_LENGTH

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/questions")
async def get_questions(
    req: Request,
    limit: int = Query(100, ge=1, le=MAX_LIMIT, description="每页数量"),
    offset: int = Query(0, ge=0, le=MAX_OFFSET, description="偏移量"),
    search: str = Query("", max_length=MAX_SEARCH_LENGTH, description="搜索关键词")
):
    db = req.app.state.db
    try:
        if search and search.strip():
            questions = await db.search_questions(search.strip(), limit)
        else:
            questions = await db.get_all_questions(limit, offset)
        total = await db.get_count()
        return {"code": 1, "data": questions, "total": total}
    except Exception as e:
        logger.error(f"获取题目列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取数据失败")


@router.get("/api/questions/{question_id}")
async def get_question(question_id: int, req: Request):
    db = req.app.state.db
    question = await db.get_question_by_id(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    return {"code": 1, "data": question}


@router.post("/api/questions")
async def create_question_api(question: QuestionCreate, req: Request):
    db = req.app.state.db
    question_id = await db.create_question(question)
    return {"code": 1, "msg": "创建成功", "data": {"id": question_id}}


@router.put("/api/questions/{question_id}")
async def update_question_api(question_id: int, question: QuestionUpdate, req: Request):
    db = req.app.state.db
    success = await db.update_question(question_id, question)
    if not success:
        raise HTTPException(status_code=404, detail="题目不存在")
    return {"code": 1, "msg": "更新成功"}


@router.delete("/api/questions/{question_id}")
async def delete_question_api(question_id: int, req: Request):
    db = req.app.state.db
    success = await db.delete_question(question_id)
    if not success:
        raise HTTPException(status_code=404, detail="题目不存在")
    return {"code": 1, "msg": "删除成功"}
