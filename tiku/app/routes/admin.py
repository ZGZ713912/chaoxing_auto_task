"""
管理接口 - 导入导出、统计
"""

import os
import json
import tempfile
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse

from ..config import JSON_FILE

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/stats")
async def get_stats(req: Request):
    db = req.app.state.db
    total, pending = await asyncio.gather(db.get_count(), db.get_pending_count())
    return {"code": 1, "data": {"total": total, "pending": pending}}


@router.post("/api/import-json")
async def import_json(req: Request, file: UploadFile = File(None)):
    db = req.app.state.db
    try:
        if file is None:
            if not os.path.exists(JSON_FILE):
                raise HTTPException(status_code=404, detail="找不到默认JSON文件")
            success = await db.import_from_json(JSON_FILE)
        else:
            try:
                content = await file.read()
                content_str = content.decode('utf-8')
                questions = json.loads(content_str)

                if not isinstance(questions, list):
                    raise HTTPException(status_code=400, detail="JSON格式错误：根元素必须是数组")

                for i, q in enumerate(questions):
                    if not isinstance(q, dict):
                        raise HTTPException(status_code=400, detail=f"第{i+1}个题目格式错误：必须是对象")
                    if 'question' not in q:
                        raise HTTPException(status_code=400, detail=f"第{i+1}个题目缺少'question'字段")
                    if 'type' not in q:
                        raise HTTPException(status_code=400, detail=f"第{i+1}个题目缺少'type'字段")
                    if 'answer' not in q:
                        raise HTTPException(status_code=400, detail=f"第{i+1}个题目缺少'answer'字段")

                temp_dir = tempfile.gettempdir()
                temp_file = os.path.join(temp_dir, f"tiku_import_{os.getpid()}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")

                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(content_str)

                try:
                    success = await db.import_from_json(temp_file)
                finally:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
            except UnicodeDecodeError:
                raise HTTPException(status_code=400, detail="文件编码错误，请使用UTF-8编码的JSON文件")
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"JSON解析错误: {str(e)}")

        if success:
            total = await db.get_count()
            return {"code": 1, "msg": "导入成功", "total": total}
        else:
            raise HTTPException(status_code=500, detail="导入失败，请检查JSON文件格式")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导入JSON失败: {e}")
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.get("/api/export-json")
async def export_json(req: Request):
    db = req.app.state.db
    try:
        questions = await db.get_all_questions_for_export()
        now = datetime.now()
        filename = now.strftime("%Y%m%d%H%M.json")

        temp_dir = tempfile.gettempdir()
        export_file = os.path.join(temp_dir, f"tiku_export_{os.getpid()}_{now.strftime('%Y%m%d%H%M%S')}.json")

        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)

        def cleanup_temp_file(path: str):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.error(f"清理临时文件失败: {e}")

        background_tasks = BackgroundTasks()
        background_tasks.add_task(cleanup_temp_file, export_file)

        return FileResponse(
            export_file,
            media_type="application/json",
            filename=filename,
            background=background_tasks
        )
    except Exception as e:
        logger.error(f"导出JSON失败: {e}")
        raise HTTPException(status_code=500, detail="导出失败")
