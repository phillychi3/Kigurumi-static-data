import json
import urllib.request


def fetch_page(page_num, lang="en-us", page_size=30):
    url = "https://sg-wiki-api.hoyolab.com/hoyowiki/hsr/wapi/get_entry_page_list"
    payload = json.dumps(
        {
            "filters": [],
            "menu_id": "104",
            "page_num": page_num,
            "page_size": page_size,
            "use_es": True,
        }
    ).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Referer": "https://wiki.hoyolab.com/",
            "Origin": "https://wiki.hoyolab.com",
            "x-rpc-language": lang,
            "x-rpc-wiki_app": "hsr",
        },
    )

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_all(lang="en-us"):
    all_chars = []
    page = 1
    while True:
        data = fetch_page(page, lang)
        chars = data["data"]["list"]
        total = int(data["data"]["total"])
        all_chars.extend(chars)
        print(
            f"  [{lang}] Page {page}: got {len(chars)} chars (total so far: {len(all_chars)}/{total})"
        )
        if len(all_chars) >= total or len(chars) == 0:
            break
        page += 1
    return all_chars


en_chars = fetch_all("en-us")


zhtw_chars = fetch_all("zh-tw")


zhtw_map = {}
for c in zhtw_chars:
    zhtw_map[c["entry_page_id"]] = c["name"]

print(f"\nEN chars: {len(en_chars)}, zh-TW chars: {len(zhtw_chars)}")


result = {}
for c in en_chars:
    en_name = c["name"]
    page_id = c["entry_page_id"]
    zh_name = zhtw_map.get(page_id, en_name)
    icon_url = c["icon_url"]

    result[en_name] = {
        "name": zh_name,
        "originalName": en_name,
        "type": "game",
        "officialImage": icon_url,
        "source": {"title": "崩壞：星穹鐵道", "company": "miHoYo", "releaseYear": 2023},
    }

with open("hsr_characters.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\nDone! Wrote {len(result)} characters to hsr_characters.json")
