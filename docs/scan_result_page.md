1. **아이템 인식 정보**
    - 썸네일(촬영 컷/상품컷)
    - 표준 품목명(예: 화장품-토너) + 카테고리 칩(액체류/LAGs, 에어로졸, 리튬배터리 등)
    - 추출 파라미터 칩: 용량(ml), 도수(%ABV), 배터리(Wh/mAh·V), 개수, 분말(g), 가연성 여부 등
    - 인식 신뢰도(%) + “추가 확인 필요” 배지(임계치 이하일 때)
    (`confidence < 0.7`이면 화면 상단에 “정보 확인 필요” 배지 표시.)
2. **여정 요약(판정 컨텍스트)**
    - 출발/경유/도착 공항·국가, 환승 재검색 여부
    - 항공사(구간별), 좌석/운임(옵션)
3. **판정 카드**
    - **기내 수하물**: 허용 / 조건부 허용 / 금지
    - **위탁 수하물**: 허용 / 조건부 허용 / 금지
    
    (아이콘 + 색상: 허용=초록, 조건부=노랑, 금지=빨강)
    
4. **조건/주의사항(핵심 조건만 Bullet)**
    - 예: “100ml 이하 용기에 담아 1L 지퍼백”, “스페어 배터리 위탁 금지, 단자 절연”, “STEB 봉인 유지 필요”, “항공사 승인 필요(101–160Wh 2개 한도)” 등
5. **근거/출처 요약**
    - 적용된 규정 레이어 표시: 보안(TSA/인천/MLIT) / 위험물(ICAO/49 CFR/PackSafe) / 항공사(KE/7C)
    - 출처 제목 2–3개
6. ai comment
    1. 예: “AI 추천: 이 보조배터리는 기내 반입이 가능해요. 위탁 수하물 보다는 휴대 수화물로 넣으세요!”
7. **행동 버튼**
    - 짐 리스트에 추가
    - 규정 상세 보기(조건 펼쳐보기)
    - 다시 스캔 / 다른 품목으로 변경
8. **예외/경고 배너**
    - 경유지 재검색 있음(STEB 필요 등), 미국 도착 후 환승 시 TSA 재검색, 세관/검역 별도 규정

---

# JSON 예시

```json
{
  "ui_context": {
    "itinerary": {"from":"ICN","via":["PVG"],"to":"LAX","has_rescreening": true},
    "airlines": [{"leg":"ICN-PVG","carrier":"KE"},{"leg":"PVG-LAX","carrier":"MU"}],
    "duty_free": {"is_df": true, "steb_sealed": true}
  },
  "item": {
    "display_name": "화장품(토너)",
    "category": "cosmetics_liquid",
    "params": {"volume_ml": 150},
    "confidence": 0.92
  },
  "decision": {
    "carry_on": {"status":"limit","badges":["LAGs 100ml","1L 지퍼백"], "reason_codes":["SEC_KR_LAGS","SEC_US_311"]},
    "checked":  {"status":"allow","badges":[],"reason_codes":[]}
  },
  "conditions": {
    "lags_100ml": true,
    "zip_bag_1l": true,
    "steb_required": true,
    "airline_approval": false
  },
  "sources": [
    {"title":"TSA What Can I Bring? (Liquids)","org":"TSA","last_checked":"2025-11-10"},
    {"title":"인천공항 액체류 반입안내","org":"IIAC","last_checked":"2025-11-10"}
  ]
}

```

---

# LLM 프롬프트 (한국어, 바로 사용 가능)

## 1) **설명 생성 프롬프트** (시스템 메시지)

```
당신은 항공 수하물 규정 안내 앱의 UX 라이터입니다.
입력 JSON은 규칙 엔진의 최종 판정 결과이며, 이를 바탕으로 사용자에게 보여줄 짧은 문구를 생성합니다.

절대 규칙:
- 새로운 규정이나 수치를 추가하지 마세요. 입력 JSON의 정보만 재서술하세요.
- 결론(허용/조건부/금지)을 바꾸지 마세요.
- 가장 중요한 조건을 먼저, 2~4개의 불릿으로 간결히.
- 출처는 최대 3개까지 '기관/제목'으로만 나열(링크 X).
- 말투는 ‘짧고 단정하게’. 경고는 이모지(⚠️, ✅, ❌)를 사용해도 좋습니다.

출력 스키마(JSON, 문자열 필드만):
{
  "title": string,                     // 예: "화장품(토너) · 150ml"
  "carry_on_card": {"status_label": "허용|조건부 허용|금지", "short_reason": string},
  "checked_card":  {"status_label": "허용|조건부 허용|금지", "short_reason": string},
  "bullets": [string, ...],            // 핵심 조건/주의 2~4개
  "badges": [string, ...],             // 예: "액체류", "STEB 필요", "항공사 승인"
  "footnote": string,                  // 경유/세관 등 한 줄
  "sources": [string, ...]             // "TSA What Can I Bring? (Liquids)", "인천공항 액체류 안내"
}

입력:
<ENGINE_JSON>

```

## 2) **입력 파라미터 추출 프롬프트** (사용자 자유입력 → 표준 키/수치, 함수콜/JSON 강제)

```
역할: 텍스트에서 수하물 판정에 필요한 파라미터를 구조화하세요.
출력은 반드시 유효한 JSON만. 추정하지 말고 모르면 null, confidence<0.6.

스키마:
{
  "item_key": "string",                 // 표준 키: cosmetics_liquid, lithium_battery_spare, aerosol, knife, alcohol_beverage ...
  "params": {
    "volume_ml": number|null,
    "wh": number|null,
    "count": number|null,
    "abv_percent": number|null,
    "bag": "carry_on|checked|unknown"
  },
  "confidence": number                  // 0~1
}

동의어 사전(예시):
- "토너","로션","세럼" → cosmetics_liquid
- "보조배터리","파워뱅크" → lithium_battery_spare
- "헤어스프레이" → aerosol
- "소주/위스키/와인" → alcohol_beverage

규칙:
- 단위가 없으면 추정 금지.
- 숫자 표기는 정수/소수 모두 허용.
- bag이 언급되지 않으면 "unknown".

사용자 입력:
<FREE_TEXT>

```

## 3) **파서 보조 프롬프트** (공식 문서 문단 → 정량값만 뽑기, 선택)

```
역할: 규정 문단에서 정량 조건만 추출합니다. 문구를 해석하지 말고 수치만.
출력 JSON:
{
  "max_wh": number|null,
  "max_count": number|null,
  "max_volume_ml": number|null,
  "max_weight_kg": number|null,
  "steb_required": boolean|null,
  "airline_approval": boolean|null
}
규칙:
- 값이 보이지 않으면 null.
- 단위 변환 금지(텍스트에 ml이면 ml 그대로 숫자만).
- True/False는 문장 내 명시(예: "승인 필요" → airline_approval:true).
문단:
<TEXT_SNIPPET>

```

---

# 예시: 위 스크린샷 JSON → LLM 출력

**입력(요약)**

- item: 화장품(토너), volume=150ml
- decision: carry_on=조건부(100ml/1L 지퍼백), checked=허용
- sources: TSA Liquids, 인천공항 LAGs

**LLM 출력 예**

```json
{
  "title": "화장품(토너) · 150ml",
  "carry_on_card": {
    "status_label": "조건부 허용",
    "short_reason": "100ml 이하 용기에 담아 1L 지퍼백 1개로만 반입 가능"
  },
  "checked_card": {
    "status_label": "허용",
    "short_reason": "위탁 수하물은 용량 제한 없음(파손 방지 포장 권장)"
  },
  "bullets": [
    "현재 용량 150ml → 기내 반입 시 100ml 이하 용기로 분할 필요",
    "경유지 재검색 시 지퍼백 규정 동일 적용",
    "면세 구매 시 STEB 봉인 및 영수증 보관"
  ],
  "badges": ["액체류", "STEB 필요"],
  "footnote": "보안 규정과 별개로 세관/검역 규정은 도착국 기준으로 적용됩니다.",
  "sources": ["TSA What Can I Bring? (Liquids)", "인천공항 액체류 안내"]
}

```

---