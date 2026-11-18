#!/usr/bin/env python3
"""Keep the consensus board linked from the homepage tabs. Idempotent."""
from pathlib import Path

LINK = {
    "index.html": '<a class="tab-earn" href="/zh/board/">共識</a>',
    "zh/index.html": '<a class="tab-earn" href="/zh/board/">共識</a>',
    "en/index.html": '<a class="tab-earn" href="/zh/board/">Consensus</a>',
}
ANCHOR = {
    "index.html": 'id="tab-tracked">追蹤名單</button>',
    "zh/index.html": 'id="tab-tracked">追蹤名單</button>',
    "en/index.html": 'id="tab-tracked">Tracked list</button>',
}

ROOT = Path(__file__).resolve().parents[1]
page = ROOT / "zh" / "board" / "index.html"
if not page.is_file():
    raise SystemExit("zh/board/index.html missing")

for rel, link in LINK.items():
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    if 'href="/zh/board/"' in text:
        print("already linked", rel)
        continue
    anchor = ANCHOR[rel]
    if anchor not in text:
        raise SystemExit(f"anchor missing in {rel}")
    text = text.replace(anchor, anchor + "\n      " + link, 1)
    path.write_text(text, encoding="utf-8")
    print("linked", rel)
