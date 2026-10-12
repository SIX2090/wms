# -*- coding: utf-8 -*-
"""P4-2026-10-12 查询记忆机制（Vanna Tool Memory 简化版）。

只记忆「问题 → LLM 选的工具 + 参数」映射，不记忆答案本身——
库存数据随时变化，复用旧答案会过期；复用成功的选择（tool/params）
则永远有效。相似问题命中时作为 few-shot 示例注入 P2 调度层 prompt，
让 LLM 越用越准（参考 Vanna AI Tool Memory / Odoo RAG 助手经验库）。

存储：instance/query_memory.json，上限 500 条 LRU。
相似度：字符 bigram Jaccard，阈值 0.35，取 top_k=2。
"""

import json
import os
import re
import threading
import time

MEMORY_LIMIT = 500
SIMILARITY_THRESHOLD = 0.35
TOP_K = 2

_LOCK = threading.Lock()


def _normalize(text):
    if not text:
        return ''
    text = str(text).strip().lower()
    # 保留数字（规格如 6*10 是匹配关键），只剔空白与标点
    return re.sub(r'[\s，。？！、,.?!\-—]+', '', text)


def _bigrams(text):
    text = _normalize(text)
    if len(text) < 2:
        return {text} if text else set()
    return {text[i:i + 2] for i in range(len(text) - 1)}


def _similarity(a, b):
    bg_a, bg_b = _bigrams(a), _bigrams(b)
    if not bg_a or not bg_b:
        return 0.0
    return len(bg_a & bg_b) / len(bg_a | bg_b)


def _memory_path():
    try:
        from flask import current_app
        instance_path = current_app.instance_path
    except Exception:
        instance_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance')
    os.makedirs(instance_path, exist_ok=True)
    return os.path.join(instance_path, 'query_memory.json')


def _load(path):
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(path, entries):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(entries[-MEMORY_LIMIT:], fh, ensure_ascii=False)
    os.replace(tmp, path)


def record_query_memory(question, tool, params):
    """记录一次成功的选择（问题 → tool + params）。异常静默，不影响主链路。"""
    question = (question or '').strip()
    if not question or not tool or len(question) < 4:
        return False
    try:
        with _LOCK:
            path = _memory_path()
            entries = _load(path)
            key = _normalize(question)
            entries = [e for e in entries if _normalize(e.get('q', '')) != key]
            entries.append({
                'q': question[:200],
                'tool': str(tool)[:64],
                'params': params if isinstance(params, dict) else {},
                'ts': int(time.time()),
            })
            _save(path, entries)
        return True
    except Exception:
        return False


def find_similar(question, top_k=TOP_K, threshold=SIMILARITY_THRESHOLD):
    """返回与 question 相似的历史记录，按相似度降序。"""
    try:
        path = _memory_path()
        entries = _load(path)
    except Exception:
        return []
    scored = []
    for entry in entries:
        score = _similarity(question, entry.get('q', ''))
        if score >= threshold:
            scored.append((score, entry))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [entry for _score, entry in scored[:top_k]]


def memory_examples_text(question, top_k=TOP_K):
    """构造 few-shot 示例文本；无相似记录时返回空串。"""
    examples = find_similar(question, top_k=top_k)
    if not examples:
        return ''
    lines = ['【历史成功案例】以下是用户过去问过的类似问题及正确的工具调用，可参考其理解方式：']
    for entry in examples:
        try:
            params_json = json.dumps(entry.get('params', {}), ensure_ascii=False)
        except (TypeError, ValueError):
            params_json = '{}'
        lines.append('- 问题："{}" → {{"tool": "{}", "params": {}}}'.format(
            entry.get('q', ''), entry.get('tool', ''), params_json))
    return '\n'.join(lines)
