"""Meta One Advanced promo UTMs (until 2026-11-28 HKT): utm_medium=organic,
utm_campaign=meta_one_nov28_<slot>, utm_source = platform full name.

  python3 tools/test_utm_promo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import utm  # noqa: E402

os.environ.pop('UTM_PROMO', None)
assert utm.promo_on('2026-10-29') and utm.promo_on('2026-11-28') and not utm.promo_on('2026-11-29')

os.environ['UTM_PROMO'] = '1'
for src, want in (('ig', 'instagram'), ('fb', 'facebook'), ('threads', 'threads'), ('x', 'x')):
    for slot in ('earnings', 'daily', 'snapshot', 'top5', 'tutorial'):
        got = utm.tag_url('https://thecrowdtape.com/zh/?a=1#z', src, slot)
        assert got == f'https://thecrowdtape.com/zh/?a=1&utm_source={want}&utm_medium=organic&utm_campaign=meta_one_nov28_{slot}#z', got
        # retagging is idempotent and never doubles the prefix
        assert utm.tag_url(got, src, 'meta_one_nov28_' + slot) == got
old = 'https://thecrowdtape.com/en/?utm_source=x&utm_medium=social&utm_campaign=daily'
assert utm.tag_url(old, 'x', 'earnings').endswith('utm_medium=organic&utm_campaign=meta_one_nov28_earnings')
assert utm.existing_campaign('https://thecrowdtape.com/?utm_campaign=meta_one_nov28_newsletter') == 'newsletter'
assert utm.tag_url('https://thecrowdtape.com/og/x.png', 'x', 'daily') == 'https://thecrowdtape.com/og/x.png'

os.environ['UTM_PROMO'] = '0'
assert utm.tag_url('https://thecrowdtape.com/en/', 'x', 'daily').endswith('utm_medium=social&utm_campaign=daily')
print('ok test_utm_promo')
