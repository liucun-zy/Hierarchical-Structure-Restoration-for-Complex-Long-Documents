from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter, deque
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from rapidfuzz import fuzz

from .llm_client import LLMClient, extract_json_payload

try:
    import zhconv
    ZHCONV_AVAILABLE = True
except Exception:
    ZHCONV_AVAILABLE = False

try:
    from opencc import OpenCC
    OPENCC_AVAILABLE = True
    OPENCC_T2S = OpenCC("t2s")
    OPENCC_S2T = OpenCC("s2t")
except Exception:
    OPENCC_AVAILABLE = False
    OPENCC_T2S = None
    OPENCC_S2T = None


_HEADING_RE = re.compile(r"^(#+)\s*(.+?)\s*$")
_SECTION_PREFIX_RE = re.compile(
    r"^\s*(?:[（(]?\s*(?:\d+(?:\.\d+)*|[一二三四五六七八九十百千]+|[IVXLC]+)\s*[)）．\.\-、:]?\s*)+",
    re.IGNORECASE,
)
_CHAPTER_PREFIX_RE = re.compile(r"^\s*第\s*[一二三四五六七八九十百千0-9]+\s*[章节篇部]\s*")
_FALLBACK_S2T = {
    "业": "業", "产": "產", "于": "於", "会": "會", "价": "價", "关": "關", "别": "別", "办": "辦",
    "创": "創", "务": "務", "员": "員", "参": "參", "与": "與", "议": "議", "题": "題", "识": "識",
    "结": "結", "构": "構", "机": "機", "愿": "願", "观": "觀", "职": "職", "责": "責", "标": "標",
    "现": "現", "览": "覽", "质": "質", "户": "戶", "环": "環", "资": "資", "装": "裝", "响": "響",
    "应": "應", "对": "對", "气": "氣", "变": "變", "爱": "愛", "训": "訓", "卫": "衛", "区": "區",
    "规": "規", "经": "經", "营": "營", "败": "敗", "范": "範", "围": "圍", "准": "準", "则": "則",
    "报": "報", "辞": "辭", "绍": "紹", "绩": "績", "记": "記", "荣": "榮", "誉": "譽", "简": "簡", "过": "過",
}
_FALLBACK_T2S = {trad: simp for simp, trad in _FALLBACK_S2T.items()}


@dataclass
class Heading:
    title: str
    line_num: int
    level: int


@dataclass
class AlignmentResult:
    aligned_markdown: str
    unmatched_titles: List[Tuple[str, int, int, Optional[str]]] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)


@dataclass
class TocTitle:
    title: str
    level: int
    index: int
    parent: Optional[str]


@dataclass
class AnchorWindow:
    start_line: int
    end_line: int
    prev_title: Optional[str]
    next_title: Optional[str]


@lru_cache(maxsize=8192)
def _convert_with_map(text: str, mapping: Dict[str, str]) -> str:
    return "".join(mapping.get(char, char) for char in text)


@lru_cache(maxsize=8192)
def to_simplified(text: str) -> str:
    if ZHCONV_AVAILABLE:
        return zhconv.convert(text, "zh-cn")
    if OPENCC_AVAILABLE and OPENCC_T2S:
        return OPENCC_T2S.convert(text)
    return _convert_with_map(text, _FALLBACK_T2S)


@lru_cache(maxsize=8192)
def to_traditional(text: str) -> str:
    if ZHCONV_AVAILABLE:
        return zhconv.convert(text, "zh-hk")
    if OPENCC_AVAILABLE and OPENCC_S2T:
        return OPENCC_S2T.convert(text)
    return _convert_with_map(text, _FALLBACK_S2T)


def extract_chinese(text: str) -> str:
    return "".join(char for char in text if "\u4e00" <= char <= "\u9fff")


@lru_cache(maxsize=8192)
def strip_section_prefix(text: str) -> str:
    text = _CHAPTER_PREFIX_RE.sub("", text)
    text = _SECTION_PREFIX_RE.sub("", text)
    return text.strip()


@lru_cache(maxsize=8192)
def normalize_for_match(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = strip_section_prefix(text)
    text = text.upper()
    text = "".join(char for char in text if not unicodedata.category(char).startswith(("P", "S")))
    text = re.sub(r"\s+", "", text)
    return text


@lru_cache(maxsize=8192)
def normalize_for_tokens(text: str) -> Tuple[str, ...]:
    text = unicodedata.normalize("NFKC", text)
    text = strip_section_prefix(text)
    text = text.upper()
    return tuple(re.findall(r"[A-Z0-9]+", text))


def is_traditional_text(text: str) -> bool:
    chinese_chars = [char for char in text if "\u4e00" <= char <= "\u9fff"]
    if len(chinese_chars) < 20:
        return False
    simplified = to_simplified("".join(chinese_chars))
    changed = sum(1 for original, simp in zip(chinese_chars, simplified) if original != simp)
    if len(chinese_chars) == 0:
        return False
    return (changed / len(chinese_chars)) >= 0.02


def maybe_to_traditional(text: Optional[str], doc_is_traditional: bool) -> Optional[str]:
    if text is None:
        return None
    return to_traditional(text) if doc_is_traditional else text


def get_title_level(
    entry: Any,
    is_top_level: bool = False,
    parent_level: int = 0,
    is_in_third_level: bool = False,
    string_subtitles_have_subtitles: Optional[bool] = None,
) -> int:
    if not isinstance(entry, dict):
        if is_top_level:
            return 1
        if string_subtitles_have_subtitles is not None:
            return 3 if string_subtitles_have_subtitles else 2
        if parent_level >= 2:
            return 3
        return 2

    if is_in_third_level:
        return 3
    if is_top_level:
        return 1

    subtitles = entry.get("subtitles") or []
    if subtitles:
        first_subtitle = subtitles[0]
        if isinstance(first_subtitle, str):
            return 2
        if isinstance(first_subtitle, dict) and first_subtitle.get("subtitles"):
            return 2

    if parent_level == 1:
        return 2
    if parent_level == 2:
        return 3
    if parent_level == 3:
        return 4
    return 4


def flatten_toc(titles_json: Sequence[Any]) -> List[TocTitle]:
    result: List[TocTitle] = []

    def walk(entry: Any, index: int, parent: Optional[str], parent_level: int, is_top_level: bool, is_in_third_level: bool) -> None:
        if isinstance(entry, str):
            level = get_title_level(entry, is_top_level, parent_level, is_in_third_level)
            result.append(TocTitle(entry, level, index, parent))
            return
        if not isinstance(entry, dict):
            return
        title = entry.get("title", "")
        if not title:
            return
        level = get_title_level(entry, is_top_level, parent_level, is_in_third_level)
        result.append(TocTitle(title, level, index, parent))
        subtitles = entry.get("subtitles") or []
        subtitles_have_subtitles = any(isinstance(sub, dict) and sub.get("subtitles") for sub in subtitles)
        for sub in subtitles:
            if isinstance(sub, str):
                sub_level = get_title_level(sub, False, level, level == 2, subtitles_have_subtitles)
                result.append(TocTitle(sub, sub_level, index, title))
            else:
                walk(sub, index, title, level, False, level == 2)

    for idx, entry in enumerate(titles_json):
        walk(entry, idx, None, 0, True, False)
    return result


def parse_markdown_headings(lines: Sequence[str]) -> List[Heading]:
    headings: List[Heading] = []
    for line_num, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if not match:
            continue
        headings.append(Heading(match.group(2).strip(), line_num, len(match.group(1))))
    return headings


def is_title_match(markdown_title: str, toc_title: str) -> Tuple[bool, float, bool]:
    if markdown_title == toc_title:
        return True, 1.0, True
    if markdown_title.upper() == toc_title.upper():
        return True, 1.0, True

    markdown_normalized = normalize_for_match(markdown_title)
    toc_normalized = normalize_for_match(toc_title)
    markdown_simplified = to_simplified(markdown_title)
    toc_simplified = to_simplified(toc_title)
    markdown_simplified_norm = normalize_for_match(markdown_simplified)
    toc_simplified_norm = normalize_for_match(toc_simplified)

    if markdown_normalized and markdown_normalized == toc_normalized:
        return True, 1.0, True
    if markdown_simplified_norm and markdown_simplified_norm == toc_simplified_norm:
        return True, 1.0, True

    def containment_score(left: str, right: str) -> float:
        if not right:
            return 0.0
        if right in left:
            ratio = len(right) / max(len(left), 1)
            return 0.88 + min(0.1, ratio * 0.1)
        return 0.0

    best_score = max(
        containment_score(markdown_normalized, toc_normalized),
        containment_score(markdown_simplified_norm, toc_simplified_norm),
    )

    markdown_chinese = extract_chinese(markdown_simplified)
    toc_chinese = extract_chinese(toc_simplified)
    if markdown_chinese and toc_chinese:
        best_score = max(best_score, fuzz.partial_ratio(markdown_chinese, toc_chinese) / 100.0)

    markdown_tokens = normalize_for_tokens(markdown_title)
    toc_tokens = normalize_for_tokens(toc_title)
    markdown_simplified_tokens = normalize_for_tokens(markdown_simplified)
    toc_simplified_tokens = normalize_for_tokens(toc_simplified)

    if markdown_tokens and toc_tokens:
        best_score = max(best_score, fuzz.token_set_ratio(" ".join(markdown_tokens), " ".join(toc_tokens)) / 100.0)
    if markdown_simplified_tokens and toc_simplified_tokens:
        best_score = max(best_score, fuzz.token_set_ratio(" ".join(markdown_simplified_tokens), " ".join(toc_simplified_tokens)) / 100.0)
    if markdown_normalized and toc_normalized:
        best_score = max(best_score, fuzz.partial_ratio(markdown_normalized, toc_normalized) / 100.0)
    if markdown_simplified_norm and toc_simplified_norm:
        best_score = max(best_score, fuzz.partial_ratio(markdown_simplified_norm, toc_simplified_norm) / 100.0)

    normalized_length = len(toc_normalized)
    if normalized_length <= 2:
        threshold = 0.9
    elif normalized_length <= 4:
        threshold = 0.88
    else:
        threshold = 0.85
    return (best_score >= threshold, best_score, False)


def bm25_tokenize(text: str) -> List[str]:
    text = to_simplified(text)
    text = unicodedata.normalize("NFKC", text)
    tokens = re.findall(r"[A-Z0-9]+", text.upper())
    tokens.extend([char for char in text if "\u4e00" <= char <= "\u9fff"])
    return tokens


def bm25_scores(query_tokens: Sequence[str], docs_tokens: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75) -> List[float]:
    if not docs_tokens:
        return []
    num_docs = len(docs_tokens)
    average_length = sum(len(doc) for doc in docs_tokens) / max(num_docs, 1)
    doc_frequency = Counter()
    for doc in docs_tokens:
        for token in set(doc):
            doc_frequency[token] += 1
    idf = {token: math.log((num_docs - freq + 0.5) / (freq + 0.5) + 1) for token, freq in doc_frequency.items()}

    scores: List[float] = []
    for doc in docs_tokens:
        doc_term_freq = Counter(doc)
        doc_length = len(doc)
        score = 0.0
        for token in query_tokens:
            if token not in doc_term_freq:
                continue
            term_freq = doc_term_freq[token]
            denominator = term_freq + k1 * (1 - b + b * doc_length / max(average_length, 1e-9))
            score += idf.get(token, 0.0) * (term_freq * (k1 + 1)) / denominator
        scores.append(score)
    return scores


def bm25_coverage_ratio(query_tokens: Sequence[str], doc_tokens: Sequence[str]) -> float:
    query_set = set(query_tokens)
    if not query_set:
        return 0.0
    return len(query_set & set(doc_tokens)) / len(query_set)


def bm25_min_coverage(token_count: int) -> float:
    if token_count <= 2:
        return 1.0
    if token_count <= 4:
        return 0.9
    if token_count <= 8:
        return 0.75
    return 0.6


def bm25_max_len_ratio(token_count: int) -> float:
    if token_count <= 4:
        return 2.4
    if token_count <= 8:
        return 2.2
    return 2.4


def flatten_titles_in_order(titles_json: Sequence[Any]) -> List[str]:
    ordered: List[str] = []

    def walk(item: Any) -> None:
        if isinstance(item, str):
            ordered.append(item)
            return
        if not isinstance(item, dict):
            return
        title = item.get("title")
        if title:
            ordered.append(title)
        for subtitle in item.get("subtitles") or []:
            walk(subtitle)

    for top_level_item in titles_json:
        walk(top_level_item)
    return ordered


def find_anchor_window(
    toc_titles_in_order: Sequence[str],
    target_title: str,
    anchored_titles: Set[str],
    headings: Sequence[Heading],
) -> AnchorWindow:
    title_to_lines: Dict[str, List[int]] = {}
    for heading in headings:
        title_to_lines.setdefault(heading.title, []).append(heading.line_num)

    current_index = toc_titles_in_order.index(target_title)
    prev_title = next((toc_titles_in_order[idx] for idx in range(current_index - 1, -1, -1) if toc_titles_in_order[idx] in anchored_titles), None)
    next_title = next((toc_titles_in_order[idx] for idx in range(current_index + 1, len(toc_titles_in_order)) if toc_titles_in_order[idx] in anchored_titles), None)

    start_line = 0
    end_line = headings[-1].line_num if headings else 0
    if prev_title:
        for heading in headings:
            matched, _, _ = is_title_match(heading.title, prev_title)
            if matched:
                start_line = heading.line_num + 1
                break
    if next_title:
        for heading in headings:
            matched, _, _ = is_title_match(heading.title, next_title)
            if matched:
                end_line = heading.line_num - 1
                break
    if start_line > end_line:
        start_line = 0
        end_line = headings[-1].line_num if headings else 0
    return AnchorWindow(start_line=start_line, end_line=end_line, prev_title=prev_title, next_title=next_title)


def insert_title_at_line(lines: List[str], title: str, level: int, line_num: int) -> None:
    bounded_line = max(0, min(line_num, len(lines)))
    lines.insert(bounded_line, f"{'#' * level} {title}\n")


def choose_agentic_insert_line(
    target_title: str,
    target_level: int,
    lines: Sequence[str],
    window: AnchorWindow,
    llm_client: Optional[LLMClient],
) -> int:
    if llm_client is None:
        return window.end_line + 1

    visible_lines = []
    for line_num in range(window.start_line, min(window.end_line + 1, len(lines))):
        text = lines[line_num].rstrip("\n")
        if text.strip():
            visible_lines.append({"line": line_num + 1, "text": text})

    prompt = {
        "target_title": target_title,
        "target_level": target_level,
        "previous_anchor": window.prev_title,
        "next_anchor": window.next_title,
        "visible_lines": visible_lines,
        "instruction": (
            "Return JSON only with the schema {\"insert_before_line\": integer}. "
            "Choose the line where this heading should be inserted so that the document structure remains coherent."
        ),
    }
    message = [{"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}]
    response_text = llm_client.chat_text(message, max_tokens=512, temperature=0.1)
    parsed = extract_json_payload(response_text)
    if not isinstance(parsed, dict) or "insert_before_line" not in parsed:
        return window.end_line + 1
    insert_before_line = int(parsed["insert_before_line"])
    return max(0, min(insert_before_line - 1, len(lines)))


def align_document(
    *,
    markdown_content: str,
    titles_json_path: str,
    llm_client: Optional[LLMClient] = None,
) -> AlignmentResult:
    titles_json = json.loads(Path(titles_json_path).read_text(encoding="utf-8"))
    toc_titles = flatten_toc(titles_json)
    ordered_titles = flatten_titles_in_order(titles_json)
    stats = {
        "exact_match": 0,
        "bm25_match": 0,
        "agentic_insert": 0,
    }

    lines = markdown_content.splitlines(True)
    if markdown_content and not markdown_content.endswith("\n"):
        lines[-1] = lines[-1] + "\n"
    doc_is_traditional = is_traditional_text(markdown_content)
    headings = parse_markdown_headings(lines)

    matched_markdown_lines: Set[int] = set()
    matched_toc_titles: Set[str] = set()
    unmatched_toc: List[TocTitle] = []

    # Stage 1: exact matching.
    for toc_title in toc_titles:
        found = False
        for heading in headings:
            if heading.line_num in matched_markdown_lines:
                continue
            matched, _, exact = is_title_match(heading.title, toc_title.title)
            if matched and exact:
                display_title = maybe_to_traditional(heading.title, doc_is_traditional) or heading.title
                lines[heading.line_num] = f"{'#' * toc_title.level} {display_title}\n"
                matched_markdown_lines.add(heading.line_num)
                matched_toc_titles.add(toc_title.title)
                stats["exact_match"] += 1
                found = True
                break
        if not found:
            unmatched_toc.append(toc_title)

    # Refresh headings after level normalization.
    headings = parse_markdown_headings(lines)

    # Stage 2: BM25 matching for remaining ToC titles.
    still_unmatched: List[TocTitle] = []
    available_headings = [heading for heading in headings if heading.line_num not in matched_markdown_lines]
    for toc_title in unmatched_toc:
        query_tokens = bm25_tokenize(toc_title.title)
        if not query_tokens or not available_headings:
            still_unmatched.append(toc_title)
            continue
        docs_tokens = [bm25_tokenize(heading.title) for heading in available_headings]
        scores = bm25_scores(query_tokens, docs_tokens)
        minimum_coverage = bm25_min_coverage(len(set(query_tokens)))
        maximum_ratio = bm25_max_len_ratio(len(set(query_tokens)))

        best_candidate_index = -1
        best_score = 0.0
        for index, heading in enumerate(available_headings):
            doc_tokens = docs_tokens[index]
            if not doc_tokens:
                continue
            coverage = bm25_coverage_ratio(query_tokens, doc_tokens)
            if coverage < minimum_coverage:
                continue
            length_ratio = len(doc_tokens) / max(len(query_tokens), 1)
            if length_ratio > maximum_ratio:
                continue
            score = scores[index]
            matched, fuzzy_score, _ = is_title_match(heading.title, toc_title.title)
            combined_score = max(score, fuzzy_score)
            if matched and combined_score > best_score:
                best_candidate_index = index
                best_score = combined_score

        if best_candidate_index == -1:
            still_unmatched.append(toc_title)
            continue

        best_heading = available_headings.pop(best_candidate_index)
        display_title = maybe_to_traditional(best_heading.title, doc_is_traditional) or best_heading.title
        lines[best_heading.line_num] = f"{'#' * toc_title.level} {display_title}\n"
        matched_markdown_lines.add(best_heading.line_num)
        matched_toc_titles.add(toc_title.title)
        stats["bm25_match"] += 1

    # Stage 3: agentic insertion for unresolved ToC titles.
    headings = parse_markdown_headings(lines)
    for toc_title in still_unmatched:
        anchor_window = find_anchor_window(ordered_titles, toc_title.title, matched_toc_titles, headings)
        display_title = maybe_to_traditional(toc_title.title, doc_is_traditional) or toc_title.title
        insert_line = choose_agentic_insert_line(display_title, toc_title.level, lines, anchor_window, llm_client)
        insert_title_at_line(lines, display_title, toc_title.level, insert_line)
        matched_toc_titles.add(toc_title.title)
        stats["agentic_insert"] += 1
        headings = parse_markdown_headings(lines)

    aligned_markdown = "".join(lines).rstrip("\n")
    return AlignmentResult(aligned_markdown=aligned_markdown, unmatched_titles=[(item.title, item.level, item.index, item.parent) for item in still_unmatched], stats=stats)
