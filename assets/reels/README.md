# Instagram Reels drop folder

The video teammate drops finished Reels here. JSON never invents a file: `ig_reel.video_path` is this relative path only when the mp4 exists in the repo at generation time (`python3 tools/share.py`, `python3 tools/macro_week.py`, or `python3 tools/ig_boost.py --apply`). Otherwise `video_path` is `null`. `video_expected_path` is always the convention string so you know where to put the file.

## Path

```
assets/reels/<date_kst>-<slot>.mp4
```

- `date_kst` is the Asia/Seoul calendar date of the intended post time (`YYYY-MM-DD`).
- `slot` is `daily` for the weekday social Reel, `macro-week` for the Saturday macro Reel.
- For `macro-week`, that date is the Saturday the post goes out (zh 20:00, en 20:30, ko 21:00 HKT). 20:00 HKT is 21:00 KST, so the Seoul date is that same Saturday. `data/macro-week.json` `date` is this Saturday, including a preview whose `date` is still in the future. `from` / `to` are the data window. A preview can have `to` equal to today and `date` equal to next Saturday. The filename uses `date`, not `to`.

Examples:

- `assets/reels/2026-10-26-daily.mp4`
- `assets/reels/2026-10-31-macro-week.mp4`

## File

- 1080×1920 mp4
- H.264
- ≤90 seconds
- No personal names, no character mascots
- Handle `@thecrowdtape` on screen is OK; do not put URLs on the video
