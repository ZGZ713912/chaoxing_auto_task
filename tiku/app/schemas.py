"""
Pydantic 数据模型
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

from .config import MAX_QUESTION_LENGTH, MAX_OPTIONS_COUNT, MAX_SEARCH_LENGTH


class Question(BaseModel):
    id: Optional[int] = None
    question: str
    type: str
    options: List[str] = []
    answer: str


class QuestionCreate(BaseModel):
    question: str = Field(..., max_length=MAX_QUESTION_LENGTH)
    type: str = Field(..., max_length=50)
    options: List[str] = Field(default=[], max_length=MAX_OPTIONS_COUNT)
    answer: str = Field(..., max_length=1000)

    @field_validator('question')
    @classmethod
    def validate_question(cls, v):
        if not v or not v.strip():
            raise ValueError('题目内容不能为空')
        return v.strip()

    @field_validator('answer')
    @classmethod
    def validate_answer(cls, v):
        if not v or not v.strip():
            raise ValueError('答案不能为空')
        return v.strip()

    @field_validator('options')
    @classmethod
    def validate_options(cls, v):
        if v is None:
            return []
        return [opt[:500] for opt in v]


class QuestionUpdate(BaseModel):
    question: Optional[str] = Field(None, max_length=MAX_QUESTION_LENGTH)
    type: Optional[str] = Field(None, max_length=50)
    options: Optional[List[str]] = Field(None, max_length=MAX_OPTIONS_COUNT)
    answer: Optional[str] = Field(None, max_length=1000)

    @field_validator('question')
    @classmethod
    def validate_question(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError('题目内容不能为空')
        return v

    @field_validator('answer')
    @classmethod
    def validate_answer(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError('答案不能为空')
        return v

    @field_validator('options')
    @classmethod
    def validate_options(cls, v):
        if v is not None:
            return [opt[:500] for opt in v]
        return v


class SearchRequest(BaseModel):
    question: str = Field(..., max_length=MAX_SEARCH_LENGTH)
    type: str = Field(..., max_length=50)
    key: Optional[str] = Field(None, max_length=100)
    options: Optional[List[str]] = Field(default=None, max_length=MAX_OPTIONS_COUNT)

    @field_validator('question')
    @classmethod
    def validate_question(cls, v):
        if not v or not v.strip():
            raise ValueError('搜索内容不能为空')
        return v.strip()


class SearchResponse(BaseModel):
    code: int
    msg: Optional[str] = None
    data: Optional[dict] = None
    answer: Optional[str] = None
