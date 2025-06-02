# 資料格式規範

## 檔案結構

- `kiger.json` - Kiger 資料
- `character.json` - 角色資料

## Kiger 資料格式 (kiger.json)

```json
{
  "cos_001": {
    // Kiger 物件
  }
}
```

### Kiger 物件規範

| 欄位名稱       | 類型    | 必填 | 說明                              |
| -------------- | ------- | ---- | --------------------------------- |
| `id`           | string  | ✓    | Kiger 唯一識別碼，格式：`cos_xxx` |
| `name`         | string  | ✓    | Kiger 名稱                        |
| `bio`          | string  | ✓    | 個人簡介                          |
| `profileImage` | string  | ✓    | 頭像圖片 URL                      |
| `isActive`     | boolean | ✓    | 是否為活躍狀態                    |
| `socialMedia`  | object  | ✓    | 社交媒體資訊                      |
| `Characters`   | array   | ✓    | 角色列表                          |
| `createdAt`    | string  | ✓    | 建立時間，ISO 8601 格式           |
| `updatedAt`    | string  | ✓    | 最後更新時間，ISO 8601 格式       |

### socialMedia 物件規範

| 欄位名稱    | 類型   | 必填 | 說明           |
| ----------- | ------ | ---- | -------------- |
| `instagram` | string | ✗    | Instagram 帳號 |
| `twitter`   | string | ✗    | Twitter 帳號   |
| `facebook`  | string | ✗    | Facebook 頁面  |
| `tiktok`    | string | ✗    | TikTok 帳號    |
| `pixiv`     | string | ✗    | Pixiv 帳號名稱 |
| `website`   | string | ✗    | 個人網站 URL   |

### Characters 陣列元素規範

| 欄位名稱      | 類型   | 必填 | 說明                                  |
| ------------- | ------ | ---- | ------------------------------------- |
| `characterId` | string | ✓    | 角色 ID，對應 character.json 中的 key |
| `maker`       | string | ✗    | 製作店家                              |
| `images`      | array  | ✓    | 圖片 URL 陣列                         |

### 範例
```json
{
  "SakuraSnow": {
    "id": "SakuraSnow",
    "name": "櫻花小雪",
    "bio": "專業kiger",
    "profileImage": "https://example.com/profile.jpg",
    "position":"",
    "isActive": true,
    "socialMedia": {
      "instagram": "@sakurasnow_cos",
      "twitter": "@sakurasnow",
      "facebook": "SakuraSnowCosplay",
      "tiktok": "@sakurasnow_cos",
      "pixiv": "sakurasnow",
      "website": "https://sakurasnow.com"
    },
    "Characters": [
      {
        "characterId": "Ganyu",
        "maker":"example"
        "images": [
          "https://example.com/profile.jpg"
        ]
      }
    ],
    "createdAt": "2024-06-01T10:00:00Z",
    "updatedAt": "2024-06-02T15:30:00Z"
  }
}
```

## 角色資料格式 (character.json)

```json
{
  "Ganyu": {
    // 角色物件
  }
}
```

### 角色物件規範

| 欄位名稱        | 類型   | 必填 | 說明                                                        |
| --------------- | ------ | ---- | ----------------------------------------------------------- |
| `name`          | string | ✓    | 角色中文名稱                                                |
| `originalName`  | string | ✓    | 角色原始名稱                                                |
| `type`          | string | ✓    | 角色類型，可選值：`game`, `vtuber`, `anime`,  `oc`, `other` |
| `officialImage` | string | ✓    | 官方角色圖片 URL                                            |
| `source`        | object | ✓    | 來源作品資訊                                                |

### source 物件規範

| 欄位名稱      | 類型   | 必填 | 說明        |
| ------------- | ------ | ---- | ----------- |
| `title`       | string | ✓    | 作品標題    |
| `company`     | string | ✓    | 公司/製作方 |
| `releaseYear` | number | ✓    | 發布年份    |

### 範例
```json
{
  "Ganyu": {
    "name": "甘雨",
    "originalName": "Ganyu",
    "type": "game",
    "officialImage": "https://example.com/ganyu.jpg",
    "source": {
      "title": "原神",
      "company": "miHoYo",
      "releaseYear": 2020
    }
  }
}
```




## 商家資料 (maker.json)

```json
{
  "Cyberloafing_S": {
    // 店家物件
  }
}
```

### 角色物件規範

| 欄位名稱       | 類型   | 必填 | 說明         |
| -------------- | ------ | ---- | ------------ |
| `name`         | string | ✓    | 店家中文名稱 |
| `originalName` | string | ✓    | 店家原始名稱 |
| `Avatar`       | string | ✓    | 店家圖片 URL |
| `socialMedia`  | object | ✓    | 社交媒體資訊 |

### socialMedia 物件規範

| 欄位名稱   | 類型   | 必填 | 說明          |
| ---------- | ------ | ---- | ------------- |
| `twitter`  | string | ✗    | Twitter 帳號  |
| `facebook` | string | ✗    | Facebook 頁面 |
| `taobao`   | string | ✗    | taobao 帳號   |
| `amazon`   | string | ✗    | amazon 帳號   |
| `website`  | string | ✗    | 個人網站 URL  |

### 範例
```json
{
  "Cyberloafing_S": {
    "name": "摸鱼工坊",
    "originalName": "Cyberloafing_S",
    "Avatar": "https://example.com/ganyu.jpg",
    "socialMedia": {
      "twitter": "Cyberloafing_S",
      "facebook": "Cyberloafing_S",
      "taobao":"Cyberloafing_S",
      "amazon":"Cyberloafing_S",
      "website": "https://example.com"
    }
  }
}
```

## 資料規範

### ID 命名規則
- Kiger ID：通常使用twitter用戶名稱
- character ID：使用英文角色名稱（例：`Ganyu`, `Fubuki`）

### 時間格式
- 統一使用 ISO 8601 格式：`YYYY-MM-DDTHH:mm:ssZ`
- 範例：`2024-06-01T10:00:00Z`


### 角色類型值
- `game` - 遊戲角色
- `vtuber` - 虛擬YouTuber
- `anime` - 動畫角色
- `oc` - 原創角色
- `other` - 其他類型