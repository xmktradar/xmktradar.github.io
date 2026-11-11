"""Unprefixed URLs always redirect to /zh/, and homepage x-default is /zh/.

GitHub Pages cannot emit HTTP 301. The helpers are the repo-side stand-in
(hostname-guarded location.replace, meta refresh, canonical). Engineering Lead
adds the real 301 at the edge.

Run from the repo root: python3 tools/test_root_redirect.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_langs  # noqa: E402
import checklist  # noqa: E402


def test_subpage_stub():
    html = '<html><head><title>full page</title></head><body><p>每月訪客</p></body></html>'
    stub = build_langs.with_root_redirect(html, 'about')
    assert '每月訪客' not in stub
    assert '<title>full page</title>' not in stub
    assert 'location.replace("/zh/about/"+location.search+location.hash)' in stub
    assert '/"+l+"/' not in stub
    assert 'navigator.language' not in stub
    assert 'ct-lang' not in stub
    assert 'rel="canonical" href="https://thecrowdtape.com/zh/about/"' in stub
    assert 'http-equiv="refresh" content="0;url=/zh/about/"' in stub
    assert 'name="robots" content="noindex"' in stub
    assert 'github\\.io|thecrowdtape\\.com' in stub
    nested = checklist.with_nested_root_redirect(html, 'checklist/earnings')
    assert 'location.replace("/zh/checklist/earnings/"+location.search+location.hash)' in nested
    assert '/"+l+"/' not in nested
    assert '每月訪客' not in nested
    assert nested == build_langs.with_root_redirect(html, 'checklist/earnings')
    try:
        build_langs.with_root_redirect(html, '../etc')
    except ValueError:
        pass
    else:
        raise AssertionError('bad segment should fail')


def test_homepage_xdefault_and_redirect():
    root = build_langs.head_tags(None)
    zh = build_langs.head_tags('zh')
    en = build_langs.head_tags('en')
    needle = 'hreflang="x-default" href="https://thecrowdtape.com/zh/"'
    bare = 'hreflang="x-default" href="https://thecrowdtape.com/"'
    for tags in (root, zh, en):
        assert needle in tags
        assert bare not in tags.replace(needle, '')
        assert 'ct-lang' in tags
    assert 'location.replace("/zh/"+location.search+location.hash)' in root
    assert '/"+l+"/' not in root
    assert 'navigator.language' not in root
    assert 'github\\.io|thecrowdtape\\.com' in root
    assert 'location.replace' not in zh
    assert 'location.replace' not in en
    # Language pages still remember the click and the page language.
    assert 'localStorage.setItem(k,"zh")' in zh
    assert 'localStorage.setItem(k,"en")' in en
    assert 'localStorage.setItem(k,a.dataset.lang)' in root


def main():
    test_subpage_stub()
    test_homepage_xdefault_and_redirect()
    print('test_root_redirect: ok')


if __name__ == '__main__':
    main()
