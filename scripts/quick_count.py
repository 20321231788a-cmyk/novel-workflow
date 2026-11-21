import sys
import re
from pathlib import Path

han = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff]')
for p in sys.argv[1:]:
    txt = Path(p).read_text(encoding='utf-8')
    # strip chapter headers like '# 第X章 标题'
    lines = txt.splitlines()
    body_lines = [l for l in lines if not l.strip().startswith('#') and not l.strip().startswith('---')]
    count = len(han.findall('\n'.join(body_lines)))
    print(f"{p}: effective_han = {count}")
