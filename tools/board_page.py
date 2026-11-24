#!/usr/bin/env python3
"""Keep the homepage consensus tab pointing at the in-page follow-through. Idempotent."""
import re
from pathlib import Path

LINKS = {
    "index.html": ('<a class="tab-earn" href="#follow">共識</a>', 'id="tab-tracked">追蹤名單</button>'),
    "zh/index.html": ('<a class="tab-earn" href="#follow">共識</a>', 'id="tab-tracked">追蹤名單</button>'),
    "en/index.html": ('<a class="tab-earn" href="#follow">Consensus</a>', 'id="tab-tracked">Tracked list</button>'),
}

ROOT = Path(__file__).resolve().parents[1]

for rel, (link, anchor) in LINKS.items():
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    if link in text:
        print("already linked", rel)
        continue
    text2, n = re.subn(r'<a class="tab-earn" href="[^"]*">(?:共識|Consensus)</a>', link, text, count=1)
    if n:
        path.write_text(text2, encoding="utf-8")
        print("retargeted", rel)
        continue
    if anchor not in text:
        raise SystemExit(f"anchor missing in {rel}")
    path.write_text(text.replace(anchor, anchor + "\n      " + link, 1), encoding="utf-8")
    print("linked", rel)

# en/board is not regenerated here. Keep its weekly CTA on /en/weekly/. zh/board stays /zh/weekly/.
en_board = ROOT / "en" / "board" / "index.html"
if en_board.is_file():
    board = en_board.read_text(encoding="utf-8")
    old, new = 'href="/zh/weekly/"', 'href="/en/weekly/"'
    if old in board:
        en_board.write_text(board.replace(old, new), encoding="utf-8")
        print("en board weekly href -> /en/weekly/")
    else:
        print("en board weekly href already /en/weekly/")
else:
    print("en board missing, skip weekly href")

from pay_moments import inject_all
inject_all()
