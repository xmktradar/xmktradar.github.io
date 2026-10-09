"""Shared helpers for the site update pipeline: read/write the data block in index.html,
call the xAI (Grok) API, and HKT time helpers."""
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

HK = timezone(timedelta(hours=8))
ET = timezone(timedelta(hours=-4))
BLOCK = re.compile(r'(<script type="application/json" id="dash-data">)(.*?)(</script>)', re.S)
WORK = os.environ.get('WORK_DIR', 'work')


def load(html='index.html'):
    s = open(html, encoding='utf-8').read()
    return json.loads(BLOCK.search(s).group(2).replace('<\\/', '</'))


def save(d, html='index.html'):
    s = open(html, encoding='utf-8').read()
    blob = json.dumps(d, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    s = BLOCK.sub(lambda m: m.group(1) + blob + m.group(3), s, count=1)
    open(html, 'w', encoding='utf-8').write(s)


def work(name):
    os.makedirs(WORK, exist_ok=True)
    return os.path.join(WORK, name)


def read_json(path, default=None):
    try:
        return json.load(open(path, encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, obj, indent=None):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
        if indent:
            f.write('\n')


def now_hk():
    return datetime.now(HK)


def parse_iso(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def notice(msg, level='notice'):
    """Print a GitHub Actions annotation so the run page shows what happened."""
    print(f'::{level}::{msg}' if os.environ.get('GITHUB_ACTIONS') else f'[{level}] {msg}', flush=True)


# ---------- xAI (Grok) ----------
XAI = 'https://api.x.ai/v1'
_model = None


def _xai(path, body=None, timeout=300):
    key = os.environ.get('XAI_API_KEY')
    if not key:
        raise RuntimeError('XAI_API_KEY 未設定')
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(XAI + path, data=data, method='POST' if body is not None else 'GET',
                                 headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def model():
    """XAI_MODEL if set; otherwise the best text model the key can use (a fast Grok 4 first)."""
    global _model
    if _model:
        return _model
    if os.environ.get('XAI_MODEL'):
        _model = os.environ['XAI_MODEL']
        return _model
    ids = [m['id'] for m in _xai('/models').get('data', [])]
    text = [i for i in ids if i.startswith('grok') and not re.search(r'image|vision|imagine|video|voice|code', i)]
    if not text:
        raise RuntimeError('xAI 帳戶冇可用嘅 Grok 文字模型：' + ', '.join(ids))

    def rank(i):
        v = re.search(r'grok-(\d+(?:\.\d+)?)', i)
        return (float(v.group(1)) if v else 0, 'fast' in i, 'non-reasoning' in i, -len(i))
    _model = sorted(text, key=rank, reverse=True)[0]
    return _model


def grok_json(system, user, tries=3, max_tokens=16000):
    """Ask Grok for a JSON object. Retries on bad JSON or transient HTTP errors."""
    last = None
    for i in range(tries):
        try:
            r = _xai('/chat/completions', {
                'model': model(), 'temperature': 0.2, 'max_tokens': max_tokens,
                'response_format': {'type': 'json_object'},
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]})
            txt = r['choices'][0]['message']['content'].strip()
            txt = re.sub(r'^```(?:json)?\s*|\s*```$', '', txt)
            return json.loads(txt)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')[:300]
            last = f'HTTP {e.code} {body}'
            if e.code in (401, 403):
                raise RuntimeError('xAI 拒絕：' + last)
            if e.code == 402 or 'credit' in body.lower() or 'quota' in body.lower():
                raise RuntimeError('xAI 用量不足：' + last)
            time.sleep(5 * (i + 1))
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            last = f'回覆唔係合法 JSON：{e}'
        except (urllib.error.URLError, TimeoutError) as e:
            last = str(e)
            time.sleep(5 * (i + 1))
    raise RuntimeError(last or 'Grok 失敗')
