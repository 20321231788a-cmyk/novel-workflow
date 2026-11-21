"""Read-only chapter length gate. UTF-8 Markdown/TXT; no prose rewriting."""
import argparse
import hashlib
import json
import re
from pathlib import Path

HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
CHAPTER = re.compile(r"^\s*(?:#{1,6}\s*)?第([0-9零〇一二三四五六七八九十百千万两]+)章(?:\s|[：:、.]|[^0-9零〇一二三四五六七八九十百千万两]).*$|^\s*(?:#{1,6}\s*)?第([0-9零〇一二三四五六七八九十百千万两]+)章\s*$")
NOTE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:作者的话|作者有话说|作者说明|写作说明|创作说明|校验说明|字数说明|校验记录|技法使用记录|附注|备注)(?:\s|[：:]|$)")


def inspect(path, minimum):
    path = Path(path).resolve()
    raw = path.read_bytes()
    rows, current, fence, note, front = [], None, None, False, False
    for lineno, line in enumerate(raw.decode('utf-8-sig').splitlines(), 1):
        stripped = line.strip()
        if lineno == 1 and stripped == '---':
            front = True
            continue
        if front:
            if stripped == '---':
                front = False
            continue
        marker = re.match(r'^\s*(`{3,}|~{3,})', line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence:
            continue
        match = CHAPTER.match(line)
        if match:
            current = {'chapter': match.group(1) or match.group(2), 'heading': stripped,
                       'heading_line': lineno, 'effective_han': 0}
            rows.append(current)
            note = False
            continue
        if NOTE.match(line):
            note = True
        if current is None or note or re.match(r'^\s*#{1,6}\s', line):
            continue
        current['effective_han'] += len(HAN.findall(line))
    for row in rows:
        row['meets_minimum'] = row['effective_han'] >= minimum
        row['shortfall'] = max(0, minimum - row['effective_han'])
    ids = [r['chapter'] for r in rows]
    errors = []
    if not rows:
        errors.append('未识别独立章标题；请提供带第X章标题的正文，不能用整本总数代替逐章校验。')
    if len(ids) != len(set(ids)):
        errors.append('章号重复，须先核对分章。')
    if fence or front:
        errors.append('围栏或前置信息未闭合，不能确认正文统计范围。')
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
            'chapters': rows, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', type=Path)
    parser.add_argument('--min-han', type=int, default=1700)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.min_han < 1:
        parser.error('--min-han must be positive')
    if args.output and (args.output.resolve() in {p.resolve() for p in args.paths} or args.output.exists()):
        parser.error('报告须使用新的输出路径，不能覆盖输入或已有文件。')
    try:
        inputs = [inspect(p, args.min_han) for p in args.paths]
    except (OSError, UnicodeError) as exc:
        parser.error(str(exc))
    code = 2 if any(x['errors'] for x in inputs) else (1 if any(not c['meets_minimum'] for x in inputs for c in x['chapters']) else 0)
    result = {'schema': 'novel.chapter-length.v1', 'read_only': True, 'minimum_han': args.min_han,
              'count_scope': 'U+3400—U+4DBF及U+4E00—U+9FFF；不计章标题、Markdown标题、章前说明、YAML头、代码围栏及显式说明区段；正常对白和系统记录计入。',
              'manual_boundary_check': '散落正文中且未标记的作者说明无法自动识别，须人工核对范围；通过字数不等于通过故事与事实核验。',
              'inputs': inputs, 'exit_code': code}
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(encoded)
    else:
        print(encoded, end='')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
