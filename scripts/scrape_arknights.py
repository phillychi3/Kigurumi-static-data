import json
from urllib import request, error

urlcn = "https://raw.githubusercontent.com/arkntools/arknights-toolbox-data/e045e7c8536ccf0cf9d1508b2dbb19ca243a2e7f/assets/locales/cn/character.json"
urltw = "https://raw.githubusercontent.com/arkntools/arknights-toolbox-data/e045e7c8536ccf0cf9d1508b2dbb19ca243a2e7f/assets/locales/tw/character.json"
avatar_base_url = "https://data.arkntools.app/img/avatar/"

try:
    with request.urlopen(urlcn) as response:
        response_text = response.read().decode("utf-8")
        character_data_cn_raw = json.loads(response_text)

    with request.urlopen(urltw) as response:
        response_text = response.read().decode("utf-8")
        character_data_tw_raw = json.loads(response_text)

    transformed_data = {}
    for char_id, char_name in character_data_cn_raw.items():
        if char_id in character_data_tw_raw:
            char_name = character_data_tw_raw[char_id]
        transformed_data[char_id] = {
            "name": char_name,
            "originalName": char_id,
            "type": "game",
            "officialImage": f"{avatar_base_url}{char_id}.png",
            "source": {"title": "明日方舟", "company": "鷹角網路", "releaseYear": 2019},
        }

    with open("arknights_characters.json", "w", encoding="utf-8") as f:
        json.dump(transformed_data, f, ensure_ascii=False, indent=2)

    print(
        f"Done! Wrote {len(transformed_data)} characters to arknights_characters.json"
    )


except error.URLError as e:
    print(f"Error fetching data: {e}")
except json.JSONDecodeError as e:
    print(f"Error decoding JSON: {e}")
