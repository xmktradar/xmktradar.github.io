#!/usr/bin/env python3
"""Keep the consensus board linked from the homepage tabs. Idempotent."""
import re
from pathlib import Path

LINKS = {
    "index.html": ("/zh/board/", '<a class="tab-earn" href="/zh/board/">共識</a>', 'id="tab-tracked">追蹤名單</button>'),
    "zh/index.html": ("/zh/board/", '<a class="tab-earn" href="/zh/board/">共識</a>', 'id="tab-tracked">追蹤名單</button>'),
    "en/index.html": ("/en/board/", '<a class="tab-earn" href="/en/board/">Consensus</a>', 'id="tab-tracked">Tracked list</button>'),
}

ROOT = Path(__file__).resolve().parents[1]
for rel in ("zh/board/index.html", "en/board/index.html"):
    if not (ROOT / rel).is_file():
        raise SystemExit(rel + " missing")

for rel, (href, link, anchor) in LINKS.items():
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    if f'href="{href}"' in text:
        print("already linked", rel)
        continue
    text2, n = re.subn(r'<a class="tab-earn" href="/(?:zh|en)/board/">[^<]*</a>', link, text, count=1)
    if n:
        path.write_text(text2, encoding="utf-8")
        print("retargeted", rel)
        continue
    if anchor not in text:
        raise SystemExit(f"anchor missing in {rel}")
    path.write_text(text.replace(anchor, anchor + "\n      " + link, 1), encoding="utf-8")
    print("linked", rel)
