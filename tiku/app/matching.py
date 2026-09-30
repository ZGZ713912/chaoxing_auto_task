"""
题目匹配逻辑 - 支持文本匹配和选项匹配
"""

import re
from typing import List, Optional


def normalize_question(text: str) -> str:
    """标准化题目文本，去除括号和空白字符用于比对"""
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'（[^）]*）', '', text)
    text = re.sub(r'\[[^\]]*\]', '', text)
    text = re.sub(r'【[^】]*】', '', text)
    text = text.replace('_', '')
    text = ' '.join(text.split())
    return text.strip()


def text_similarity(s1: str, s2: str) -> float:
    """计算两个字符串的相似度（使用优化的Levenshtein距离）"""
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    if abs(len1 - len2) > max(len1, len2) * 0.3:
        return 0.0

    prev_row = list(range(len2 + 1))
    curr_row = [0] * (len2 + 1)

    for i in range(1, len1 + 1):
        curr_row[0] = i
        for j in range(1, len2 + 1):
            if s1[i-1] == s2[j-1]:
                curr_row[j] = prev_row[j-1]
            else:
                curr_row[j] = min(prev_row[j], curr_row[j-1], prev_row[j-1]) + 1
        prev_row, curr_row = curr_row, prev_row

    max_len = max(len1, len2)
    if max_len == 0:
        return 1.0

    distance = prev_row[len2]
    return 1.0 - (distance / max_len)


def options_match_score(request_options: List[str], db_options: List[str]) -> float:
    """计算两个选项集的相似度，返回 0.0-1.0"""
    if not request_options or not db_options:
        return 0.0

    def normalize(opt):
        return opt.strip().lower().replace(' ', '')

    request_norm = [normalize(o) for o in request_options]
    db_norm = [normalize(o) for o in db_options]

    if set(request_norm) == set(db_norm):
        return 1.0

    matches = sum(1 for ro in request_norm if ro in db_norm)
    return matches / max(len(request_norm), len(db_norm))


def combined_score(text_score: float, options_score: float, has_options: bool) -> float:
    """综合评分：文本 70% + 选项 30%，无选项时纯文本得分"""
    if not has_options:
        return text_score
    return text_score * 0.7 + options_score * 0.3
