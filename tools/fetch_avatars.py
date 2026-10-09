# Downloads current X profile pictures for every tracked handle into avatars/.
# Source 1: api.fxtwitter.com profile JSON (avatar on pbs.twimg.com); source 2: unavatar.io.
import json, time, urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read(), r.headers.get("Content-Type", "")

def via_fxtwitter(h):
    body, _ = get(f"https://api.fxtwitter.com/{h}")
    av = json.loads(body)["user"]["avatar_url"]
    return get(av.replace("_normal.", "_200x200."))

def via_unavatar(h):
    return get(f"https://unavatar.io/x/{h}?fallback=false")

html = Path("index.html").read_text(encoding="utf-8")
a = html.index('id="dash-data">') + 15
data = json.loads(html[a:html.index("</script>", a)])
out = Path("avatars"); out.mkdir(exist_ok=True)
report = {}
for acc in data["tracked"]["accounts"]:
    h = acc["handle"]
    report[h] = "fail"
    for name, fn in (("fxtwitter", via_fxtwitter), ("unavatar", via_unavatar)):
        try:
            body, ctype = fn(h)
            if not ctype.startswith("image/") or len(body) < 200:
                raise ValueError(f"not an image: {ctype} {len(body)}")
            ext = ctype.split("/")[1].split(";")[0].replace("jpeg", "jpg")
            (out / f"{h.lower()}.{ext}").write_bytes(body)
            report[h] = f"ok {name} {ctype} {len(body)}"
            break
        except Exception as e:
            report[h] = f"fail {name}: {e}"
    time.sleep(0.5)
(out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
print(sum(v.startswith("ok") for v in report.values()), "of", len(report), "downloaded")
