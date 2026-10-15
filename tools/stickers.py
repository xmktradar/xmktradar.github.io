# Draw the missing character expression stickers with Google's free Gemini image model.
# Each character's sheet.jpg is sent as the reference so every sticker keeps the same face, hair and outfit.
# Only stickers that don't exist yet are drawn; run again after a quota stop to finish the rest.
# Needs secret GEMINI_API_KEY (free key from aistudio.google.com). Run by the "Draw character stickers" workflow.
import base64, io, json, os, sys, time, urllib.error, urllib.request
from PIL import Image

KEY = os.environ.get('GEMINI_API_KEY', '')
MODELS = [m for m in (os.environ.get('GEMINI_IMAGE_MODEL') or 'gemini-2.5-flash-image,gemini-2.0-flash-preview-image-generation').split(',') if m]
PROMPT = ('Same character as the reference sheet, same face, hair colours, outfit and art style '
          '(clean anime illustration, soft shading). Bust-up portrait, facing the viewer, plain white background, '
          'no text, no logo. Expression and pose: {e}. Square 1:1 image.')
LIMIT = int(os.environ.get('STICKER_LIMIT') or 45)


def call(model, sheet, text):
    body = {'contents': [{'parts': [{'text': text}, {'inline_data': {'mime_type': 'image/jpeg', 'data': sheet}}]}],
            'generationConfig': {'responseModalities': ['TEXT', 'IMAGE']}}
    req = urllib.request.Request(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
                                 json.dumps(body).encode(), {'Content-Type': 'application/json', 'x-goog-api-key': KEY})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.load(r)
    for c in d.get('candidates', []):
        for p in c.get('content', {}).get('parts', []):
            b = p.get('inlineData') or p.get('inline_data')
            if b and b.get('data'):
                return base64.b64decode(b['data'])
    raise RuntimeError('no image in reply: ' + json.dumps(d)[:300])


def main():
    if not KEY:
        sys.exit('::error::未設定 GEMINI_API_KEY')
    d = json.load(open('assets/characters/characters.json', encoding='utf-8'))
    todo = [(c['id'], e) for e in d['expressions'] for c in d['characters']
            if not os.path.exists(f"assets/characters/{c['id']}/{e['id']}.png")]
    print(len(todo), 'stickers missing')
    sheets = {c['id']: base64.b64encode(open(c['sheet'], 'rb').read()).decode() for c in d['characters']}
    model, done = MODELS[0], 0
    for cid, e in todo[:LIMIT]:
        text = PROMPT.format(e=e['cast'][cid]['imagine_en'])
        for attempt in range(4):
            try:
                img = call(model, sheets[cid], text)
                break
            except urllib.error.HTTPError as err:
                msg = err.read().decode()[:400]
                print('HTTP', err.code, model, msg)
                if err.code == 404 and len(MODELS) > 1 and model != MODELS[-1]:
                    model = MODELS[MODELS.index(model) + 1]
                    continue
                if err.code == 429 and 'PerDay' not in msg and attempt < 3:
                    time.sleep(60)
                    continue
                print('stop:', done, 'drawn this run')
                return
            except Exception as err:  # no image in reply: try once more
                print('retry', cid, e['id'], err)
        else:
            continue
        im = Image.open(io.BytesIO(img)).convert('RGB')
        s = min(im.size)
        im = im.crop(((im.width - s) // 2, 0, (im.width - s) // 2 + s, s)).resize((512, 512), Image.LANCZOS)
        im.save(f"assets/characters/{cid}/{e['id']}.png", optimize=True)
        done += 1
        print('drew', cid, e['id'], 'with', model)
        time.sleep(8)
    print(done, 'drawn this run')


if __name__ == '__main__':
    main()
