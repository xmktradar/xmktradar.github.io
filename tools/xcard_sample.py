"""Dev helper: rebuild today's x_trilingual entries from data/social-posts.json and draw their per-ticker cards.

Not used by the update-site workflow. Needs work/stats.json (see tools/ig_sample.js steps 1-2) for account counts;
without it the cards still draw from dash-data prices only.
Usage: python3 tools/xcard_sample.py OUTDIR [--write]   (--write also saves data/social-posts.json)
"""
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from share import x_entry, work, write_json, LANGS  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    outdir = args[0] if args else work('xcards')
    sp = json.load(open('data/social-posts.json', encoding='utf-8'))
    if os.path.exists(work('xcards.json')):
        os.remove(work('xcards.json'))
    tri = {}
    for kind in ('premarket', 'afterclose'):
        e = x_entry(sp, kind)
        if e:
            tri[kind] = e
            m = re.search(r'\$([A-Z]{1,6})\b', e['text'])
            print(f"{kind}: text ticker {m.group(1) if m else None} image_ticker {e['image_ticker']} image {e['image']}")
    if os.path.exists(work('xcards.json')):
        subprocess.run(['node', 'tools/xcard.js', work('xcards.json'), outdir], check=True)
    if '--write' in sys.argv:
        sp['x_trilingual'] = tri
        write_json('data/social-posts.json', sp, indent=1)


if __name__ == '__main__':
    main()
