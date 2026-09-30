"""
待处理题目接口 - /api/pending
"""

import asyncio
import logging
from fastapi import APIRouter, Request, HTTPException

from ..schemas import QuestionCreate

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/pending")
async def get_pending_list(
    req: Request,
    limit: int = 100,
    offset: int = 0,
    search: str = "",
    sort: str = "count"
):
    db = req.app.state.db
    questions, total = await asyncio.gather(
        db.get_pending_questions(limit, offset, search, sort),
        db.get_pending_count(search)
    )
    return {"code": 1, "data": questions, "total": total}


@router.delete("/api/pending/{pending_id}")
async def delete_pending(pending_id: int, req: Request):
    db = req.app.state.db
    success = await db.delete_pending_question(pending_id)
    if not success:
        raise HTTPException(status_code=404, detail="待处理题目不存在")
    return {"code": 1, "msg": "删除成功"}


@router.post("/api/pending/{pending_id}/to-question")
async def pending_to_question(pending_id: int, question: QuestionCreate, req: Request):
    db = req.app.state.db
    success = await db.delete_pending_question(pending_id)
    if not success:
        raise HTTPException(status_code=404, detail="待处理题目不存在")
    question_id = await db.create_question(question)
    return {"code": 1, "msg": "已添加到题库", "data": {"id": question_id}}
