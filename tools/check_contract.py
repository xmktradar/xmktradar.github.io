"""Fail fast when index.html no longer has the shape the Update site build relies on.

Run first in Build check (every PR) so a structural change shows a clear reason instead of a
mysterious failure deep inside the 4-hourly rebuild.

The build (slim_pages.py, sitedata.py, build_langs.py, stats.js, og.js, check.js, stock_pages.js)
needs, in the master index.html and in zh/ en/ ko/ index.html:
  1. exactly one <script type="application/json" id="dash-data"> block (no extra attributes), holding
     the data inline (full, or the slim form with "_ext" that slim_pages.py writes);
  2. the dashboard app inline as top-level code, so its functions (consGroups, rawIn, postsIn,
     dailyWindow, render, paintChrome) and TODAY are globals the build tools call;
  3. no app code moved to an external file (assets/dash-app-*.js): build_langs.py only translates
     the page itself, so an external copy would go stale in en/ko.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ['index.html', 'zh/index.html', 'en/index.html']
EXACT = '<script type="application/json" id="dash-data">'
ANY_TAG = re.compile(r'<script\b[^>]*\bid="dash-data"[^>]*>')
GLOBALS = ['consGroups', 'rawIn', 'postsIn', 'dailyWindow', 'render', 'paintChrome']


def fail(msgs):
    for m in msgs:
        print('::error::' + m)
    print('See tools/check_contract.py for the page structure the Update site build needs.')
    sys.exit(1)


def main():
    errs = []
    for rel in PAGES:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            errs.append(rel + ': missing')
            continue
        s = open(path, encoding='utf-8').read()
        tags = ANY_TAG.findall(s)
        if len(tags) != 1:
            errs.append('%s: expected 1 dash-data block, found %d' % (rel, len(tags)))
            continue
        if tags[0] != EXACT:
            errs.append('%s: dash-data tag must be exactly %s (found %s); keep the data inline' % (rel, EXACT, tags[0]))
            continue
        start = s.index(EXACT) + len(EXACT)
        blob = s[start:s.index('</script>', start)]
        try:
            data = json.loads(blob.replace('<\\/', '</'))
        except ValueError as e:
            errs.append('%s: dash-data is not valid JSON (%s)' % (rel, e))
            continue
        if not isinstance(data, dict) or not data.get('meta'):
            errs.append(rel + ': dash-data has no meta; the data must stay inline')
        if re.search(r'assets/dash-app[^"\']*\.js', s):
            errs.append(rel + ': loads assets/dash-app-*.js; the app must stay inline in the page')
        for name in GLOBALS:
            if not re.search(r'(^|\n)\s*(async\s+)?function\s+%s\s*\(|(^|\n)\s*(const|let|var)\s+%s\s*=' % (name, name), s):
                errs.append('%s: top-level %s() not found; the app must be inline top-level code, not wrapped in a function' % (rel, name))
                break
    if errs:
        fail(errs)
    print('page structure ok: ' + ', '.join(PAGES))


if __name__ == '__main__':
    main()
