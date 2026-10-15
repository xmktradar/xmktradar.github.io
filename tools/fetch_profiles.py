# One-off: download X profile (name, bio, counts) and profile picture for new handles into profiles/.
import json, os, time, urllib.request
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0"}

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read(), r.headers.get("Content-Type", "")

out = Path("profiles"); out.mkdir(exist_ok=True)
info = {}
for h in [x for x in os.environ["ONLY"].split(",") if x]:
    try:
        body, _ = get(f"https://api.fxtwitter.com/{h}")
        u = json.loads(body).get("user") or {}
        info[h] = {k: u.get(k) for k in ("screen_name", "name", "description", "followers", "tweets", "joined", "protected")}
        av = u.get("avatar_url")
        if av:
            img, ctype = get(av.replace("_normal.", "_200x200."))
            ext = ctype.split("/")[1].split(";")[0].replace("jpeg", "jpg")
            (out / f"{h.lower()}.{ext}").write_bytes(img)
        # latest post time, to see how active the account is
        try:
            body, _ = get(f"https://api.fxtwitter.com/2/profile/{h}/statuses?count=40")
            rows = json.loads(body).get("results") or []
            ts = []
            for e in rows:
                for st in (e.get("statuses") if e.get("type") == "thread" else [e]):
                    if st and st.get("created_timestamp"):
                        ts.append(st["created_timestamp"])
            info[h]["recent"] = sorted(ts, reverse=True)
            info[h]["cashtag_posts"] = sum(1 for e in rows for st in (e.get("statuses") if e.get("type") == "thread" else [e]) if st and "$" in (st.get("text") or ""))
        except Exception as e:
            info[h]["recent_error"] = str(e)
    except Exception as e:
        info[h] = {"error": str(e)}
        try:  # fallback: picture only, from unavatar
            img, ctype = get(f"https://unavatar.io/x/{h}?fallback=false")
            if ctype.startswith("image/"):
                (out / f"{h.lower()}.{ctype.split('/')[1].split(';')[0].replace('jpeg', 'jpg')}").write_bytes(img)
                info[h]["unavatar"] = True
        except Exception as e2:
            info[h]["unavatar_error"] = str(e2)
    time.sleep(3)
(out / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
print(sum("error" not in v for v in info.values()), "of", len(info), "ok")
