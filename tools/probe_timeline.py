import urllib.request, json, re, sys
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
H = "KobeissiLetter"
urls = [
  f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{H}",
  f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{H}?showReplies=false",
  f"https://api.fxtwitter.com/2/profile/{H}/statuses",
  f"https://api.fxtwitter.com/{H}/statuses",
  f"https://api.fxtwitter.com/2/profile/{H}",
  f"https://nitter.net/{H}/rss",
  f"https://xcancel.com/{H}/rss",
  f"https://nitter.poast.org/{H}/rss",
  f"https://nitter.privacydev.net/{H}/rss",
  f"https://rss.xcancel.com/{H}/rss",
]
for u in urls:
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20)
        b = r.read().decode("utf-8", "replace")
        print("=== OK", r.status, u, len(b))
        dates = re.findall(r'"created_at":"([^"]+)"', b)[:5] or re.findall(r"<pubDate>([^<]+)</pubDate>", b)[:5]
        print("dates:", dates)
        print(b[:1500].replace("\n", " "))
    except Exception as e:
        print("=== FAIL", u, repr(e)[:200])
