"""Asia/Seoul posting dates for data/social-posts.json.

`date` stays the HKT social day or the ET trade date. `date_kst` is the
calendar date in Asia/Seoul of the intended post time.

python3 tools/date_kst.py [data/social-posts.json]
python3 tools/share.py --backfill-date-kst [data/social-posts.json]

The backfill only adds `date_kst` and, when why_posts is a list,
`why_posts_date_kst`. It does not change post text or any existing `date`.
"""
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')
NY = ZoneInfo('America/New_York')
# 07:00 HKT, when the weekend social run starts, is 08:00 KST.
WEEKEND_KST = '08:00'
# three_lines is the earliest weekday slot.
EARLIEST_DAILY_KST = '08:30'
_DAY = re.compile(r'(\d{4}-\d{2}-\d{2})')
_HHMM = re.compile(r'^(\d{1,2}):(\d{2})$')


def as_day(value):
    m = _DAY.match(str(value or '').strip())
    return m.group(1) if m else ''


def parse_hhmm(value):
    m = _HHMM.match(str(value or '').strip())
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def kst_date(day, hhmm):
    """Seoul calendar date of a KST clock on the posting day's calendar date."""
    day = as_day(day)
    hm = parse_hhmm(hhmm)
    if not day or not hm:
        return ''
    y, mo, d = (int(p) for p in day.split('-'))
    dt = datetime(y, mo, d, hm[0], hm[1], tzinfo=KST)
    return dt.date().isoformat()


def et_post_dt(day, hhmm):
    """America/New_York datetime of an intraday post. None when the clock is missing."""
    day = as_day(day)
    hm = parse_hhmm(hhmm)
    if not day or not hm:
        return None
    y, mo, d = (int(p) for p in day.split('-'))
    return datetime(y, mo, d, hm[0], hm[1], tzinfo=NY)


def et_post_date_kst(day, hhmm):
    """Seoul calendar date of an ET post time. Not the US trade date."""
    dt = et_post_dt(day, hhmm)
    if dt is None:
        return ''
    return dt.astimezone(KST).date().isoformat()


def _place(obj, key, value, after=None):
    """Set `key` without moving it when it is already present."""
    if not isinstance(obj, dict) or not value:
        return
    if key in obj:
        obj[key] = value
        return
    if after and after in obj:
        rebuilt = {}
        for k, v in obj.items():
            rebuilt[k] = v
            if k == after:
                rebuilt[key] = value
        obj.clear()
        obj.update(rebuilt)
        return
    obj[key] = value


def _place_before(obj, before_key, key, value):
    if not isinstance(obj, dict) or not value:
        return
    if key in obj:
        obj[key] = value
        return
    if before_key not in obj:
        obj[key] = value
        return
    rebuilt = {}
    for k, v in obj.items():
        if k == before_key:
            rebuilt[key] = value
        rebuilt[k] = v
    obj.clear()
    obj.update(rebuilt)


def atomic_posting_day(sp, atomic_day=None):
    """Day whose KST clocks the atomic slots use.

    An explicit day wins (the weekend run's Saturday, or the weekday merge).
    Otherwise a `weekend` object means the weekend run replaced atomic posts.
    A weekday file with no weekend uses the top-level date.
    """
    forced = as_day(atomic_day)
    if forced:
        return forced
    if not isinstance(sp, dict):
        return ''
    weekend = sp.get('weekend')
    if isinstance(weekend, dict):
        day = as_day(weekend.get('date'))
        if day:
            return day
    return as_day(sp.get('date'))


def _consider(bucket, posting_day, hhmm, only_day):
    day = as_day(posting_day)
    if not day or (only_day and day != only_day):
        return
    hm = parse_hhmm(hhmm)
    if not hm:
        return
    dk = kst_date(day, hhmm)
    if dk:
        bucket.append((day, hm[0] * 60 + hm[1], dk))


def earliest_on_posting_day(sp, day, atom_day):
    """KST date of the earliest suggested clock that belongs to `day`."""
    bucket = []
    three = sp.get('three_lines') if isinstance(sp, dict) else None
    if isinstance(three, dict):
        _consider(bucket, three.get('date') or day, three.get('suggested_kst') or EARLIEST_DAILY_KST, day)
    why = sp.get('why_posts') if isinstance(sp, dict) else None
    if isinstance(why, list):
        for item in why:
            if isinstance(item, dict) and item.get('suggested_kst'):
                _consider(bucket, item.get('date') or day, item['suggested_kst'], day)
    elif isinstance(why, dict) and why.get('suggested_kst'):
        _consider(bucket, why.get('date') or day, why['suggested_kst'], day)
    if atom_day == day:
        atomic = sp.get('atomic_posts') if isinstance(sp, dict) else None
        if isinstance(atomic, list):
            for item in atomic:
                if isinstance(item, dict) and item.get('slot_kst'):
                    _consider(bucket, atom_day, item['slot_kst'], day)
        elif isinstance(atomic, dict) and (atomic.get('slot_kst') or atomic.get('suggested_kst')):
            _consider(bucket, atom_day, atomic.get('slot_kst') or atomic.get('suggested_kst'), day)
    weekend = sp.get('weekend') if isinstance(sp, dict) else None
    if isinstance(weekend, dict):
        _consider(bucket, weekend.get('date'), WEEKEND_KST, day)
    if not bucket:
        return kst_date(day, EARLIEST_DAILY_KST)
    bucket.sort()
    return bucket[0][2]


def stamp_intraday(intra):
    """Set date_kst on the intraday object and each slot. Other keys stay."""
    if not isinstance(intra, dict):
        return intra
    et_day = as_day(intra.get('date'))
    slots = intra.get('slots') if isinstance(intra.get('slots'), dict) else None
    best_dt = None
    best = ''
    if slots:
        for sl in slots.values():
            if not isinstance(sl, dict):
                continue
            post = sl.get('post_et')
            slot_day = as_day(sl.get('date')) or et_day
            dk = et_post_date_kst(slot_day, post)
            if not dk:
                continue
            _place(sl, 'date_kst', dk, after='date' if 'date' in sl else 'post_et')
            dt = et_post_dt(slot_day, post)
            if dt is not None and (best_dt is None or dt < best_dt):
                best_dt = dt
                best = dk
    if best:
        _place(intra, 'date_kst', best, after='date' if 'date' in intra else None)
    return intra


def apply_date_kst(sp, atomic_day=None):
    """Add date_kst keys on a social-posts object. Existing `date` values stay.

    `atomic_day` is the posting day for atomic slots when the caller just built
    them (weekday merge vs Saturday run). Without it, a weekend object means
    the atomic posts belong to that Saturday or Sunday.
    """
    if not isinstance(sp, dict):
        return sp
    posting = as_day(sp.get('date'))
    atom_day = atomic_posting_day(sp, atomic_day)

    three = sp.get('three_lines')
    if isinstance(three, dict):
        day = as_day(three.get('date')) or posting
        clock = three.get('suggested_kst') or EARLIEST_DAILY_KST
        if day:
            _place(three, 'date_kst', kst_date(day, clock), after='date' if 'date' in three else 'suggested_kst')

    why = sp.get('why_posts')
    if isinstance(why, list):
        ranked = []
        for item in why:
            if not isinstance(item, dict) or not item.get('suggested_kst'):
                continue
            day = as_day(item.get('date')) or posting
            clock = item['suggested_kst']
            dk = kst_date(day, clock) if day else ''
            if not dk:
                continue
            _place(item, 'date_kst', dk, after='date' if 'date' in item else 'suggested_kst')
            hm = parse_hhmm(clock)
            ranked.append((day, hm[0] * 60 + hm[1], dk))
        if ranked:
            ranked.sort()
            _place_before(sp, 'why_posts', 'why_posts_date_kst', ranked[0][2])
    elif isinstance(why, dict):
        day = as_day(why.get('date')) or posting
        clock = why.get('suggested_kst') or '09:00'
        if day:
            _place(why, 'date_kst', kst_date(day, clock), after='date' if 'date' in why else 'suggested_kst')

    weekend = sp.get('weekend')
    if isinstance(weekend, dict):
        day = as_day(weekend.get('date')) or posting
        if day:
            _place(weekend, 'date_kst', kst_date(day, WEEKEND_KST), after='date' if 'date' in weekend else None)

    atomic = sp.get('atomic_posts')
    if isinstance(atomic, list) and atom_day:
        for item in atomic:
            if isinstance(item, dict) and item.get('slot_kst'):
                _place(item, 'date_kst', kst_date(atom_day, item['slot_kst']), after='slot_kst')
    elif isinstance(atomic, dict) and atom_day:
        clock = atomic.get('slot_kst') or atomic.get('suggested_kst') or '09:00'
        _place(atomic, 'date_kst', kst_date(atom_day, clock), after='date' if 'date' in atomic else 'slot_kst')

    intra = sp.get('intraday')
    if isinstance(intra, dict):
        stamp_intraday(intra)

    if posting:
        _place(sp, 'date_kst', earliest_on_posting_day(sp, posting, atom_day), after='date')
    return sp


def collect_stamps(sp):
    """(label, value) for every date_kst / why_posts_date_kst on the file."""
    rows = []
    if not isinstance(sp, dict):
        return rows
    if sp.get('date_kst'):
        rows.append(('date_kst', sp['date_kst']))
    if sp.get('why_posts_date_kst'):
        rows.append(('why_posts_date_kst', sp['why_posts_date_kst']))
    three = sp.get('three_lines')
    if isinstance(three, dict) and three.get('date_kst'):
        rows.append(('three_lines.date_kst', three['date_kst']))
    why = sp.get('why_posts')
    if isinstance(why, list):
        for i, item in enumerate(why):
            if isinstance(item, dict) and item.get('date_kst'):
                rows.append((f'why_posts[{i}].date_kst', item['date_kst']))
    elif isinstance(why, dict) and why.get('date_kst'):
        rows.append(('why_posts.date_kst', why['date_kst']))
    weekend = sp.get('weekend')
    if isinstance(weekend, dict) and weekend.get('date_kst'):
        rows.append(('weekend.date_kst', weekend['date_kst']))
    atomic = sp.get('atomic_posts')
    if isinstance(atomic, list):
        for i, item in enumerate(atomic):
            if isinstance(item, dict) and item.get('date_kst'):
                rows.append((f'atomic_posts[{i}].date_kst', item['date_kst']))
    elif isinstance(atomic, dict) and atomic.get('date_kst'):
        rows.append(('atomic_posts.date_kst', atomic['date_kst']))
    intra = sp.get('intraday')
    if isinstance(intra, dict):
        if intra.get('date_kst'):
            rows.append(('intraday.date_kst', intra['date_kst']))
        slots = intra.get('slots') if isinstance(intra.get('slots'), dict) else {}
        for name, sl in slots.items():
            if isinstance(sl, dict) and sl.get('date_kst'):
                rows.append((f'intraday.slots.{name}.date_kst', sl['date_kst']))
    return rows


def backfill_file(path):
    """Add date_kst keys to an existing social-posts file and print them."""
    from sitedata import read_json, write_json
    data = read_json(path)
    if not isinstance(data, dict):
        raise SystemExit(f'backfill-date-kst: {path} is not a JSON object')
    apply_date_kst(data)
    write_json(path, data, indent=1)
    for label, value in collect_stamps(data):
        print(f'{label}={value}')
    return data


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    path = 'data/social-posts.json'
    for arg in argv:
        if not arg.startswith('-'):
            path = arg
    backfill_file(path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
