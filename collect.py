import os, re, csv, requests
from io import BytesIO
from PIL import Image
import imagehash
import praw

# ---- fill these in ----
BING_KEY = "YOUR_BING_SEARCH_V7_SUBSCRIPTION_KEY"
BING_ENDPOINT_BASE = "https://api.bing.microsoft.com"  
REDDIT_CLIENT_ID = "YOUR_REDDIT_CLIENT_ID"
REDDIT_CLIENT_SECRET = "YOUR_REDDIT_CLIENT_SECRET"
REDDIT_USER_AGENT = "yourapp/0.1 by u/yourusername"
REDDIT_USERNAME = "YOUR_REDDIT_USERNAME"
REDDIT_PASSWORD = "YOUR_REDDIT_PASSWORD"

BING_COUNT = 50
REDDIT_LIMIT = 50

ROOT = "images"
BMR_DIR = os.path.join(ROOT, "BMR")
RASH_DIR = os.path.join(ROOT, "RASH")
os.makedirs(BMR_DIR, exist_ok=True)
os.makedirs(RASH_DIR, exist_ok=True)

META = os.path.join(ROOT, "dataset_metadata.csv")
if not os.path.exists(META):
    with open(META, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["filename","label","source","query","url"])

hashes = set()

def bing_endpoint():
    return BING_ENDPOINT_BASE.rstrip("/") + "/images/search"

def sanitize(name):
    name = name.split("?")[0].split("#")[0]
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def next_num(folder, prefix):
    n = 0
    for fn in os.listdir(folder):
        if fn.startswith(prefix) and fn.lower().endswith(".jpg"):
            m = re.search(rf"{re.escape(prefix)}(\d+)\.jpg$", fn, re.I)
            if m:
                n = max(n, int(m.group(1)))
    return n + 1

def open_image(url):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    img = Image.open(BytesIO(r.content))
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img

def save_meta(fn, label, src, q, url):
    with open(META, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([fn,label,src,q,url])

def save_one(url, label, q, src, counters):
    try:
        img = open_image(url)
    except Exception as e:
        print(f"[{src}] fail get: {url} ({e})")
        return False
    try:
        h = str(imagehash.average_hash(img))
    except Exception as e:
        print(f"[{src}] fail hash: {url} ({e})")
        return False
    if h in hashes:
        print(f"[{src}] dup: {url}")
        return False
    hashes.add(h)

    if label == "BMR":
        folder, prefix = BMR_DIR, "BMR_WEB_"
    else:
        folder, prefix = RASH_DIR, "RASH_WEB_"

    if label not in counters:
        counters[label] = next_num(folder, prefix)

    fn = f"{prefix}{counters[label]}.jpg"
    counters[label] += 1

    try:
        path = os.path.join(folder, fn)
        img.save(path, "JPEG", quality=90)
        save_meta(fn, label, src, q, url)
        print(f"saved: {path}  [{src}]  {q}")
        return True
    except Exception as e:
        print(f"[{src}] fail save: {url} ({e})")
        return False

def fetch_bing(q, label, counters):
    headers = {"Ocp-Apim-Subscription-Key": BING_KEY}
    params = {"q": q, "mkt": "en-US", "count": BING_COUNT}
    try:
        r = requests.get(bing_endpoint(), headers=headers, params=params, timeout=15)
        r.raise_for_status()
        for item in r.json().get("value", []):
            url = item.get("contentUrl")
            if url:
                save_one(url, label, q, "Bing", counters)
    except Exception as e:
        print(f"[Bing] error {q}: {e}")

def fetch_reddit(q, label, counters, subreddit="all"):
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
        username=REDDIT_USERNAME,
        password=REDDIT_PASSWORD
    )
    try:
        for s in reddit.subreddit(subreddit).search(q, limit=REDDIT_LIMIT):
            save_one(s.url, label, q, "Reddit", counters)
    except Exception as e:
        print(f"[Reddit] error {q}: {e}")

BMR_Q = [
    "butterfly malar rash",
    "lupus rash",
    "malar rash",
    "discoid rash",
    "rash across cheeks",
    "facial inflammation",
    "stress rash on face",
]

RASH_Q = [
    "facial eczema",
    "chronic skin condition on face",
    "rosacea on face",
    "fifth disease on face",
    "impetigo on face",
    "chickenpox on face",
    "ringworm on face",
    "allergic eczema on face",
]

def main():
    counters = {}
    print("start…")
    for q in BMR_Q:
        fetch_bing(q, "BMR", counters)
        fetch_reddit(q, "BMR", counters)
    for q in RASH_Q:
        fetch_bing(q, "RASH", counters)
        fetch_reddit(q, "RASH", counters)
    print("done. images in:", ROOT)
    print("meta:", META)

if __name__ == "__main__":
    main()
