"""
搜索接口 - POST /api/search
"""

from fastapi import APIRouter, Request

from ..schemas import SearchRequest, SearchResponse
from ..config import API_KEY

router = APIRouter()


@router.post("/api/search", response_model=SearchResponse)
async def search_answer(request: SearchRequest, req: Request):
    """题目查询接口"""
    db = req.app.state.db

    if API_KEY and request.key and request.key != API_KEY:
        return SearchResponse(code=0, msg="密钥无效", data={})

    result = await db.find_by_question(request.question, request.type, request.options)

    if result:
        count = await db.get_count()
        return SearchResponse(
            code=-1,
            msg="查询成功",
            data={"answer": result['answer'], "num": str(count), "usenum": "1"}
        )
    else:
        await db.add_pending_question(request.question, request.type, request.options)
        return SearchResponse(code=0, msg="未找到答案", data={})
