"""Read-only, descriptive comparison of Chinese novel drafts. Not an AI detector."""
import argparse
import hashlib
import json
import re
from pathlib import Path

HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
CHAPTER = re.compile(r"^#{1,6}\s+第(\d+)章[^\n]*", re.M)
MARKERS = ("狠狠", "瞬间", "死死", "冰冷", "滔天", "一字一顿", "如遭", "一抹", "说明", "确认", "记录")


def describe(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    headings = list(CHAPTER.finditer(text))
    sections = []
    warnings = []
    if headings:
        for i, m in enumerate(headings):
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            sections.append((int(m.group(1)), m.group(), m.end(), end))
        ids = [x[0] for x in sections]
        if len(ids) != len(set(ids)):
            warnings.append("重复章号，不能自动认定章节一一对应。")
    else:
        sections = [(None, "未识别分章", 0, len(text))]
        warnings.append("未识别Markdown数字章标题，使用全文范围；标题行不计正文。")
    rows = []
    cumulative = 0
    for number, heading, start, end in sections:
        body = text[start:end]
        # Preserve offsets for source-line references while excluding headings.
        counted_body = re.sub(r"^#{1,6}\s+[^\n]*$", lambda m: " " * len(m.group()), body, flags=re.M)
        han = len(HAN.findall(counted_body))
        cumulative += han
        paragraphs = [x.strip() for x in re.split(r"\n\s*\n", counted_body) if x.strip()]
        markers = {}
        for term in MARKERS:
            positions = list(re.finditer(re.escape(term), counted_body))
            markers[term] = {
                "count": len(positions),
                "per_1000_han": round(len(positions) * 1000 / han, 3) if han else None,
                "first_lines": [text.count("\n", 0, start + m.start()) + 1 for m in positions[:5]],
            }
        rows.append({
            "chapter": number, "heading": heading,
            "heading_line": text.count("\n", 0, headings[len(rows)].start()) + 1 if headings else None,
            "han_count": han, "cumulative_han": cumulative,
            "paragraph_count": len(paragraphs),
            "mean_paragraph_han": round(han / len(paragraphs), 2) if paragraphs else None,
            "exclamation_count": len(re.findall(r"[!！]", counted_body)),
            "question_count": len(re.findall(r"[?？]", counted_body)),
            "markers": markers,
        })
    return {
        "path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
        "count_scope": "Markdown章节正文；不计标题、前言、标点、空白、数字、字母。汉字范围U+3400—U+4DBF及U+4E00—U+9FFF。",
        "warnings": warnings, "chapters": rows, "total_han": cumulative,
        "total_exclamations": sum(x["exclamation_count"] for x in rows),
        "total_questions": sum(x["question_count"] for x in rows),
        "total_markers": {term: sum(x["markers"][term]["count"] for x in rows) for term in MARKERS},
    }


def compare(original, polished):
    left, right = describe(original), describe(polished)
    keys_left = [x["chapter"] for x in left["chapters"]]
    keys_right = [x["chapter"] for x in right["chapters"]]
    aligned = keys_left == keys_right and None not in keys_left and len(keys_left) == len(set(keys_left))
    return {
        "schema": "story-deslop.draft-comparison.v1",
        "purpose": "可复核的描述统计，只定位文本差异，不推断AI来源、情绪质量或检测器因果。",
        "original": left, "polished": right,
        "chapter_numbers_align": aligned,
        "alignment_note": "章号一致仍需人工核对是否讲述同一事件；不代表情节或事实一致。",
        "han_delta": right["total_han"] - left["total_han"],
        "ai_score": None, "emotion_score": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("polished", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.resolve() in {args.original.resolve(), args.polished.resolve()}:
        parser.error("输出路径不能覆盖任一输入文件。")
    result = compare(args.original, args.polished)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
