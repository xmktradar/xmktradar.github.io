# Downloads current X profile pictures for every tracked handle into avatars/.
import json, re, sys, time, urllib.request
from pathlib import Path

html = Path("index.html").read_text(encoding="utf-8")
a = html.index('id="dash-data">') + 15
data = json.loads(html[a:html.index("</script>", a)])
out = Path("avatars"); out.mkdir(exist_ok=True)
report = {}
for acc in data["tracked"]["accounts"]:
    h = acc["handle"]
    plat = acc.get("platform")
    url = f"https://unavatar.io/{'x' if plat != 'truthsocial' else 'x'}/{h}?fallback=false"
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body, ctype = r.read(), r.headers.get("Content-Type", "")
            if not ctype.startswith("image/") or len(body) < 200:
                raise ValueError(f"not an image: {ctype} {len(body)}")
            ext = ctype.split("/")[1].split(";")[0].replace("jpeg", "jpg")
            (out / f"{h.lower()}.{ext}").write_bytes(body)
            report[h] = f"ok {ctype} {len(body)}"
            break
        except Exception as e:
            report[h] = f"fail {e}"
            time.sleep(3)
    time.sleep(1)
(out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
print(sum(v.startswith("ok") for v in report.values()), "of", len(report), "downloaded")
