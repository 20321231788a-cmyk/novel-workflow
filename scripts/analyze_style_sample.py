"""Analyze uploaded fiction or author sample prose to extract acoustic & style metrics.

Used when initializing or updating a book's `本书文风锚点.md`. Read-only on inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
from collections import Counter
from pathlib import Path

HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
QUOTE_RE = re.compile(r"“([^”]+)”|「([^」]+)」")
SENT_SPLIT_RE = re.compile(r"[。！？!?…]+")

COLLOQUIAL_MARKERS = [
    "说白了", "合着", "得亏", "压根", "干脆", "反手", "顺手", "偏偏", "哪怕",
    "说到底", "真就", "纯纯", "总不能", "哪有", "倒好", "愣是", "压根儿",
    "大概率", "说实在的", "明摆着", "冷不丁", "巴不得", "犯不着", "索性",
    "好家伙", "至于", "更别提", "说不上", "八成", "十有八九", "眨眼", "当场",
]

EXPLANATION_MARKERS = [
    "因为", "意味着", "换句话说", "原因很简单", "按照", "一旦", "只要",
    "之所以", "毕竟", "原本", "准确地说", "说穿了", "凭着", "靠着",
]


def count_han(text: str) -> int:
    return len(HAN_RE.findall(text))


def load_clean_paragraphs(path: Path, max_chars: int) -> tuple[str, list[str], int]:
    raw_bytes = path.read_bytes()
    sha = hashlib.sha256(raw_bytes).hexdigest()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw_bytes.decode("utf-8", errors="replace")

    if max_chars > 0 and len(text) > max_chars:
        text = text[:max_chars]

    lines = text.splitlines()
    blank_lines = sum(1 for ln in lines if not ln.strip())
    paragraphs: list[str] = []
    in_fence = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("```") or s.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence or not s:
            continue
        if re.match(r"^#{1,6}\s", s) or re.match(r"^第[0-9零〇一二三四五六七八九十百千万两]+章", s):
            continue
        if count_han(s) >= 2:
            paragraphs.append(s)
    return sha, paragraphs, blank_lines


def analyze_paragraphs(paragraphs: list[str], blank_lines: int) -> dict:
    if not paragraphs:
        raise ValueError("未在输入文件中识别到有效中文正文段落。")

    para_han_lengths = [count_han(p) for p in paragraphs]
    total_han = sum(para_han_lengths)

    sentence_lengths: list[int] = []
    dialogue_han = 0
    dialogue_paras = 0
    consecutive_dialogue_run = 0
    pingpong_runs = 0

    for p in paragraphs:
        quotes = [m.group(1) or m.group(2) or "" for m in QUOTE_RE.finditer(p)]
        if quotes:
            dialogue_paras += 1
            q_han = sum(count_han(q) for q in quotes)
            dialogue_han += q_han
            if q_han >= max(1, count_han(p)) * 0.75:
                consecutive_dialogue_run += 1
            else:
                if consecutive_dialogue_run >= 3:
                    pingpong_runs += 1
                consecutive_dialogue_run = 0
        else:
            if consecutive_dialogue_run >= 3:
                pingpong_runs += 1
            consecutive_dialogue_run = 0

        for seg in SENT_SPLIT_RE.split(p):
            h = count_han(seg)
            if h > 0:
                sentence_lengths.append(h)

    if consecutive_dialogue_run >= 3:
        pingpong_runs += 1

    joined = "\n".join(paragraphs)
    k_factor = 1000.0 / max(1, total_han)

    short_sents = sum(1 for x in sentence_lengths if x <= 12)
    mid_sents = sum(1 for x in sentence_lengths if 13 <= x <= 28)
    long_sents = sum(1 for x in sentence_lengths if x > 28)
    sent_total = max(1, len(sentence_lengths))

    short_paras = sum(1 for x in para_han_lengths if x <= 20)
    mid_paras = sum(1 for x in para_han_lengths if 21 <= x <= 70)
    long_paras = sum(1 for x in para_han_lengths if x > 70)
    para_total = len(para_han_lengths)

    colloquial_hits = Counter()
    for term in COLLOQUIAL_MARKERS:
        c = joined.count(term)
        if c > 0:
            colloquial_hits[term] = c

    explanation_hits = Counter()
    for term in EXPLANATION_MARKERS:
        c = joined.count(term)
        if c > 0:
            explanation_hits[term] = c

    punct_per_1k = {
        "exclamation": round((joined.count("！") + joined.count("!")) * k_factor, 2),
        "question": round((joined.count("？") + joined.count("?")) * k_factor, 2),
        "ellipsis": round((joined.count("……") + joined.count("…") // 2) * k_factor, 2),
        "em_dash": round(joined.count("——") * k_factor, 2),
        "semicolon": round((joined.count("；") + joined.count(";")) * k_factor, 2),
    }

    # Locate candidate windows (~350-500 han) for conflict, inner monologue/explanation, and interaction
    windows = _extract_candidate_windows(paragraphs, para_han_lengths)

    return {
        "total_effective_han": total_han,
        "paragraph_count": para_total,
        "blank_line_ratio": round(blank_lines / max(1, para_total), 2),
        "paragraph_han_stats": {
            "mean": round(statistics.mean(para_han_lengths), 1),
            "median": round(statistics.median(para_han_lengths), 1),
            "short_le_20_ratio": round(short_paras / para_total, 3),
            "medium_21_70_ratio": round(mid_paras / para_total, 3),
            "long_gt_70_ratio": round(long_paras / para_total, 3),
        },
        "sentence_han_stats": {
            "count": len(sentence_lengths),
            "mean": round(statistics.mean(sentence_lengths), 1) if sentence_lengths else 0,
            "median": round(statistics.median(sentence_lengths), 1) if sentence_lengths else 0,
            "short_le_12_ratio": round(short_sents / sent_total, 3),
            "medium_13_28_ratio": round(mid_sents / sent_total, 3),
            "long_gt_28_ratio": round(long_sents / sent_total, 3),
        },
        "dialogue_profile": {
            "paragraphs_with_quotes_ratio": round(dialogue_paras / para_total, 3),
            "quoted_han_ratio": round(dialogue_han / max(1, total_han), 3),
            "pingpong_3plus_runs": pingpong_runs,
        },
        "punctuation_per_1k_han": punct_per_1k,
        "top_colloquial_markers": dict(colloquial_hits.most_common(12)),
        "top_explanation_markers": dict(explanation_hits.most_common(10)),
        "candidate_windows_preview": windows,
    }


def _extract_candidate_windows(paragraphs: list[str], lengths: list[int]) -> list[dict]:
    """Build ~350-550 Han sliding windows and pick top representative slices."""
    windows = []
    n = len(paragraphs)
    idx = 0
    while idx < n:
        acc_han = 0
        end = idx
        while end < n and acc_han < 380:
            acc_han += lengths[end]
            end += 1
        if acc_han < 150 and windows:
            break
        chunk = "\n".join(paragraphs[idx:end])
        q_count = len(QUOTE_RE.findall(chunk))
        exp_score = sum(chunk.count(w) for w in EXPLANATION_MARKERS) + sum(chunk.count(w) for w in COLLOQUIAL_MARKERS)
        excl_score = chunk.count("！") + chunk.count("？")
        windows.append({
            "para_range": f"P{idx + 1}-P{end}",
            "han": acc_han,
            "quotes": q_count,
            "voice_markers": exp_score,
            "tension_punct": excl_score,
            "preview": chunk[:160] + ("…" if len(chunk) > 160 else ""),
        })
        idx = max(idx + 1, end)

    if not windows:
        return []

    by_tension = max(windows, key=lambda w: w["tension_punct"] * 2 + w["quotes"])
    by_voice = max(windows, key=lambda w: w["voice_markers"] * 2 - w["quotes"])
    picked = []
    seen = set()
    for tag, item in (("高冲突/互动候选窗口", by_tension), ("高心声/解释候选窗口", by_voice)):
        if item["para_range"] not in seen:
            seen.add(item["para_range"])
            picked.append({"suggested_role": tag, **item})
    if len(windows) >= 3:
        mid = windows[len(windows) // 2]
        if mid["para_range"] not in seen:
            picked.append({"suggested_role": "中段叙事推进候选窗口", **mid})
    return picked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to sample TXT/MD file")
    parser.add_argument("--max-chars", type=int, default=40000, help="Max characters to scan for large novels")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()

    sha, paragraphs, blanks = load_clean_paragraphs(args.path.resolve(), args.max_chars)
    metrics = analyze_paragraphs(paragraphs, blanks)
    report = {
        "schema": "novel-workflow.style-sample-analysis.v1",
        "source_path": str(args.path.resolve()),
        "source_sha256": sha,
        "sampled_max_chars": args.max_chars,
        "metrics": metrics,
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
