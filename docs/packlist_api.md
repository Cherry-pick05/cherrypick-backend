# 패킹 리스트 / 아이템 API 정리

본 문서는 CherryPick 앱에서 기기 기반 사용자 인증을 거친 뒤 사용하는 패킹 리스트 관련 API를 정리한 문서입니다. 대부분의 API는 `/v1/...` 경로에 노출되며, `/healthz`, `/ws` 등 일부 공용 엔드포인트만 루트(`/`)에 그대로 노출됩니다. 별도 언급이 없는 한 HTTPS + JSON Body를 사용합니다.

---

## 0. 공통 규칙
| 항목 | 내용 |
| --- | --- |
| 인증 헤더 | `X-Device-UUID`, `X-Device-Token` (`app.core.config`의 설정과 동일) |
| 오류 포맷 | `{"detail": "error_code"}` 또는 FastAPI 기본 Validation 오류 |
| 식별자 타입 | 대부분 `int`(Snowflake 아님). 테스트 환경에서는 SQLite, 운영 환경은 MySQL |
| 기본 언어 | `locale` 미지정 시 서버 기본값(`settings.supported_locales[0]`) |

---

## 1. 디바이스 등록·갱신
기기 UUID → 사용자 매핑을 위해 최초 1회 등록 필요.

### 1.1 `POST /devices/register`
- Body: `{ "device_uuid": "...", "app_version": "...", "os": "...", "model": "...", "locale": "ko-KR?", "timezone": "Asia/Seoul" }`
- Response: `{ "device_token": "...", "feature_flags": {...}, "ab_test_bucket": "control", "expires_in": 86400 }`

### 1.2 `POST /devices/refresh`
- Body는 변경 가능한 필드만 포함.
- 응답 스펙은 register와 동일.

---

## 2. 아이템 분류 / 미리보기 / 저장

### 2.1 `POST /v1/items/classify`
| 항목 | 값 |
| --- | --- |
| Request | `{ "label": "휴대폰 배터리", "locale": "ko-KR?", "req_id": "선택" }` |
| Response | `req_id`, `canonical`, `confidence`, `candidates`, `categories[]`, `abstain`, `decided_by`, `norm_label`, `signals`, `model_info` |
| 비고 | 자동 저장 없음. 사용자가 `/v1/items/save` 호출해야 DB 반영. **디버깅/ 내부용(프론트 사용 x)** |

### 2.2 `POST /v1/items/preview`
- Request: `PreviewRequest` (`label`, `locale`, `req_id?`, `itinerary`, `segments[]`, `item_params`, `duty_free`)
- Response: `PreviewResponse` (`state`, `resolved`, `engine`, `narration`, `ai_tips`, `flags`)
- 주 사용처: 저장 전에 LLM·룰엔진 결과 확인.

### 2.3 `POST /v1/items/save`
| 필드 | 설명 |
| --- | --- |
| `req_id` | preview/classify에서 사용한 식별자 |
| `preview` | `PreviewResponse` 전체(JSON). 서버가 그대로 저장 |
| `bag_id` | 저장할 대상 가방. 사용자 소유 및 `trip_id` 일치 필수 |
| `trip_id` | 선택. 없으면 `bag.trip_id` 사용 |
| `image_id` | 선택. 캡처 이미지와 연결 시 사용 |

- 처리 흐름:
  1. bag 소유권/트립 일치 검증
  2. `regulation_matches` 레코드 생성 (`decided_by="user"`, `source="manual"`)
  3. 동일 preview 스냅샷을 참조하는 `bag_items` 레코드 생성 (`status=todo`, `quantity=1`)
  4. Response: `{ "match_id": ..., "bag_item_id": ..., "req_id": "...", "saved": true }`

---

## 3. 트립 & 가방

트립 생성 시 기본 가방 두 개(`carry_on`, `checked`)가 자동 생성되며, 사용자 정의 가방도 `/trips/{trip_id}/bags` 엔드포인트를 통해 추가할 수 있습니다. 기본 가방 할당은 `TripService` 내부 로직에서 처리하므로, 추가 가방을 만들어도 체크리스트 저장 로직과 일관성이 보장됩니다.

### 3.0 `POST /v1/trips/lookup-flight`
- Body: `{ "flight_code": "AA6", "code_type": "iata" }` (`code_type`: `iata` or `icao`)
- Response: 항공편의 출발/도착 공항, 터미널/게이트, UTC/로컬 시간, 항공사/기종, 추천 segment(`segment_hint`)가 포함된 JSON
- 사용처: 사용자가 항공편 번호만 입력하면 AirLabs API를 통해 여정 데이터를 자동 완성한 뒤, 제출 전에 다시 확인할 수 있도록 함
- 주의: AirLabs API Key (`AIRLABS_API_KEY`) 설정이 필요하며, 실시간 운항 변경이 있을 수 있으므로 제출 전 최신 정보 확인 필요
### 3.1 `GET /v1/trips/{trip_id}/bags`
- Response: `{ "items": [ { "bag_id", "trip_id", "name", "bag_type", "is_default", "sort_order", "total_items", "packed_items", "created_at", "updated_at" }, ... ] }`
- 사용처: 트립 상세 화면에서 가방 목록과 각 가방의 진행 상황(총 아이템 수, 완료 수)을 한 번에 보여줄 때 사용.

### 3.2 `POST /v1/trips/{trip_id}/bags`
- Body: `{ "name": "스포츠 장비", "bag_type": "custom", "sort_order": 3 }`
- 제약: `is_default=true` 금지, 동일 트립 내 `bag_type="carry_on"/"checked"`는 기본 가방만 존재. `bag_type="custom"`은 다수 생성 가능.
- Response: `BagSummary`
- 동작: TripService에서 기본 가방을 자동으로 채우며, 가방 생성 API는 `user_id`, `trip_id`를 서버에서 강제 세팅하므로 모든 체크리스트 저장 로직과 연동됩니다.

### 3.3 `PATCH /v1/bags/{bag_id}`
- Body: `{ "name"?, "bag_type"?, "sort_order"? }`
- 기본 가방은 `bag_type` 변경 불가, 삭제도 불가.
- 사용처: 사용자가 커스텀 가방 이름을 수정하거나 UI 정렬 순서를 바꿀 때.

### 3.4 `DELETE /v1/bags/{bag_id}`
- 기본 가방 삭제 불가(`400 cannot_delete_default_bag`).
- 성공 시 `204 No Content`.
- 사용처: 커스텀 가방을 정리할 때. 삭제되면 연결된 체크리스트 아이템도 함께 제거됩니다(ON DELETE CASCADE).

### 3.5 `GET /v1/trips/{trip_id}/items`
- 목적: 하나의 트립에 속한 모든 체크리스트 아이템을 최근 업데이트 순으로 확인.
- Response 항목:
  - `item_id`, `bag_id`, `bag_name`, `title`, `status("todo"|"packed")`, `quantity`, `note`
  - `regulation_match_id`, `raw_label`, `norm_label`, `canonical_key`, `preview_snapshot`
  - `updated_at`
- 사용처: 트립 상세 화면에서 “모든 아이템” 탭을 구현하거나, 무한 스크롤 형태로 최신 저장 내역을 보여줄 때.

### 3.6 `PATCH /v1/trips/{trip_id}/duration`
- Body: `{ "start_date": "2025-03-01"?, "end_date": "2025-03-10"? }` (둘 중 하나 이상 필수. 요청 후 최종적으로 두 값 모두 채워져 있어야 합니다.)
- 검증: `start_date <= end_date`, 최종 값 중 하나라도 `null`이면 `400 duration_incomplete`. 바뀐 값이 없으면 `400 duration_missing`.
- Response: `{ "trip_id": 12, "start_date": "2025-03-01", "end_date": "2025-03-10", "needs_duration": false }`
- 에러 코드: `400 invalid_date_range`, `400 duration_incomplete`, `400 duration_missing`, `404/403 trip_not_found`.
- 비고: 모든 Trip 상세/리스트 응답에는 `needs_duration` 필드가 포함되어 있어, 추천 시스템은 이 값이 `false`일 때만 호출 가능합니다.

---

## 4. 체크리스트 아이템

### 4.1 `GET /v1/bags/{bag_id}/items`
| 파라미터 | 설명 |
| --- | --- |
| `limit` | 1~100, 기본 20 |
| `offset` | 페이지 시작 위치 |
| Response | `{ "items": [BagItemDetail], "next_offset": 20?, "has_more": bool }` |

`BagItemDetail` 구성:
```
{
  "item_id": 10,
  "bag_id": 3,
  "trip_id": 2,
  "title": "Lithium battery",
  "status": "todo",
  "quantity": 1,
  "note": "충전 금지",
  "regulation_match_id": 55,
  "preview_snapshot": {...},
  "created_at": "...",
  "updated_at": "..."
}
```

### 4.2 `GET /v1/bag-items/{item_id}`
- 단일 아이템 상세 조회. 응답은 `BagItemDetail`.
- 사용처: 사용자가 체크리스트에서 아이템을 눌렀을 때 preview 스냅샷/규정 정보를 다시 보여줄 때.

### 4.3 `PATCH /v1/bag-items/{item_id}`
- Body 필드 (모두 선택):
  - `bag_id`: 다른 가방으로 이동. 이동 시 `trip_id`도 새 가방에 맞춰 변경.
  - `title`, `quantity(1~1000)`, `note`, `status("todo"|"packed")`
- Response: 갱신된 `BagItemDetail`.
- 사용처: 체크리스트 편집(완료 체크, 수량 조정, 메모 입력, 가방 이동)을 서버에 반영할 때.

---

## 5. 트립 생성/수정 시 참고
- `POST /v1/trips` Body는 `TripCreate` (`title`, `from_airport`, `to_airport`, `start_date`, `end_date`, `segments[]`, `via_airports[]`, `tags[]`, `note`).
- 트립 생성/수정 시 `TripService`가 자동으로 `carry_on`, `checked` 기본 가방을 채우므로 클라이언트는 별도로 호출할 필요가 없습니다.
- 트립 아카이브: `POST /v1/trips/{trip_id}/archive`를 호출하면 `archived_at` 타임스탬프가 채워지고 `active=False`로 전환되어 기본 목록에서 숨겨집니다. 사용자는 필요 시 `GET /v1/trips?status=archived`로만 조회 가능하며, `POST /v1/trips/{trip_id}/set_active`로 다시 활성화할 수 있습니다.
- 트립 삭제 시(`DELETE /v1/trips/{trip_id}?purge=true`) 해당 트립의 가방·아이템도 `ON DELETE CASCADE`로 삭제되며, 규정 매칭 로그는 `trip_id`가 NULL 로 전환됩니다.

---

## 6. 예시 플로우
1. **디바이스 등록**: `/devices/register` → `device_token` 획득.
2. **트립 생성**: `/v1/trips` → 기본 가방 2개 자동 생성.
3. **(선택) 추가 가방 생성**: `/v1/trips/{trip_id}/bags` POST로 필요 가방을 추가 생성.
4. **미리보기**: `/v1/items/preview` → Allow/Limited 정보 확인.
5. **가방 선택 후 저장**: `/v1/items/save` (필수: `bag_id`).
6. **체크리스트 조회**: `/v1/trips/{trip_id}/items` 또는 `/v1/bags/{bag_id}/items`.
7. **사용자 편집**: `/v1/bag-items/{item_id}` PATCH로 상태, 수량, 메모, 가방 이동 관리.

---

## 7. 기타 가용 API 요약
| 분류 | 메서드 & 경로 | 설명 |
| --- | --- | --- |
| 건강 체크 | `GET /healthz` | 간단한 서비스 상태 확인 |
| 부트스트랩 | `POST /bootstrap/consent` | 이용약관/개인정보 동의 기록 |
| 부트스트랩 | `GET /bootstrap/config` | 앱에 필요한 플래그/설정 제공 |
| 디바이스 | `POST /devices/refresh` | 기존 디바이스 프로필 갱신 및 토큰 재발급 |
| 트립 | `GET /v1/trips` | 상태(active/archived/all) 필터 + 페이지네이션 |
| 트립 | `GET /v1/trips/{trip_id}` | 상세 조회 |
| 트립 | `POST /v1/trips/{trip_id}/archive` | 트립을 “보관” 상태로 전환(목록에서 숨김) |
| 트립 | `POST /v1/trips/{trip_id}/set_active` | 해당 트립을 활성 트립으로 지정 |
| 트립 | `DELETE /v1/trips/{trip_id}?purge=true` | 트립 및 연결 레코드 삭제 |
| 트립 추천 | `GET /v1/trips/{trip_id}/recommendation` | 여행별 맞춤 추천(LLM/외부 데이터 기반) |
| 짐 추천 | `POST /v1/trips/{trip_id}/recommendations/outfit` | 기후 요약 기반 LLM 짐 추천 |
| 날씨 요약 | `GET /v1/climate/trips/{trip_id}/recent` | Meteostat Point Normals 기반 기간별 기후 요약 |
## 8. 기후 요약 API
- `503 meteostat_api_key_missing`, `503 meteostat_unavailable`, `503 meteostat_no_data`

## 9. AI 짐 추천 API

### 9.1 `POST /v1/trips/{trip_id}/recommendations/outfit`
- Body (선택):
  ```
  {
    "years": 3,
    "aggregation": "weighted",   // weighted | simple
    "locale": "ko-KR"
  }
  ```
- 전제 조건:
  - Trip에 `start_date`, `end_date`, `to_airport`가 설정되어 있어야 하며, 필요 시 `PATCH /v1/trips/{trip_id}/duration`으로 기간을 먼저 채워야 합니다.
  - `METEOSTAT_API_KEY`, `GEMINI_API_KEY`가 설정되어 있어야 합니다.
- 처리 흐름:
  1. 내부적으로 `TripClimateService`를 호출하여 Meteostat Point Normals 기반 기후 요약을 얻습니다.
  2. 기후 요약을 System 프롬프트(의류 추천 전용)와 함께 Gemini 모델에 전달합니다.
  3. 모델 응답(JSON)을 검증해 `title`, `description`, `items[3~4개]`, `facts` 블록을 반환합니다.
- Response 예시:
  ```json
  {
    "trip_id": 42,
    "climate": { ... 기후 요약 ... },
    "recommendation": {
      "title": "은은히 번지는 봄기류",
      "description": "낮에는 15°C 남짓으로 온화하고 밤에는 7°C 안팎으로 선선해요. 서울보다 약간 습해 가벼운 겉옷이 있으면 안심돼요.",
      "items": [
        {
          "key": "light_jacket",
          "label": "얇은 재킷을 챙기세요",
          "priority": "high",
          "why": "아침저녁 기온이 내려가도 체온을 지켜줘요"
        },
        {
          "key": "folding_umbrella",
          "label": "접이식 우산이 있으면 안심이에요",
          "priority": "medium",
          "why": "비가 잦은 편이라 대비하면 좋아요"
        }
      ],
      "facts": {
        "basis": "historical_normals",
        "date_span": ["2025-05-10","2025-05-13"],
        "temp_c": { "min": 7, "max": 15, "mean": 12 },
        "precip_mm": 45.2,
        "pop": null,
        "condition": "Historical normals"
      }
    }
  }
  ```
- 오류 코드:
  - `400 invalid_years_range`, `400 invalid_aggregation`
  - `409 trip_duration_required`
  - `422 destination_missing`, `422 destination_coordinates_unavailable`
  - `503 meteostat_api_key_missing`, `503 meteostat_unavailable`
  - `503 llm_unavailable`, `502 llm_invalid_payload`

### 8.1 `GET /v1/climate/trips/{trip_id}/recent`
- Query
  - `years` (기본 3, 1~5): 현재 Meteostat 기본 normals(1991–2020 등)를 사용하므로 계산에는 영향이 없으며, 향후 커스텀 기간 옵션을 위한 자리입니다.
  - `aggregation` (`weighted` | `simple`, 기본 weighted): 여행 구간 내 월별 일수 비중을 반영할지 여부
- 전제 조건: 트립에 `start_date`, `end_date`, `to_airport`가 모두 존재해야 하며, 누락 시 `409 trip_duration_required` 또는 `422 destination_missing`.
- 처리 흐름:
  1. Trip 목적지 공항 → AirLabs `airports` API를 통해 위경도/고도를 조회하고 Redis에 7일 캐시. 키가 없으면 로컬 공항 디렉터리(airportsdata)로 폴백. [AirLabs 문서](https://airlabs.co/api/v9/airports?iata_code=CDG&api_key=34d9c533-a58e-4c42-8650-38629651728e)
  2. 해당 좌표를 Meteostat Point Normals API(`GET https://meteostat.p.rapidapi.com/point/normals`)에 전달해 월별 평균 기온·강수량 등을 얻는다. `years` 파라미터는 `start`, `end` 연도로 변환되어 API에 전달된다. [Meteostat Point Normals](https://dev.meteostat.net/api/point/normals.html)
  3. 응답 중 여행 기간에 해당하는 월만 추려 월별 요약(`months_breakdown`)을 만들고, 사용자가 선택한 aggregation 방식에 따라 최종 `recent_stats`를 계산한다.
- Response 예시:
```
{
  "trip_id": 42,
  "input": {
    "latitude": 48.86,
    "longitude": 2.35,
    "start": "2025-05-10",
    "end": "2025-06-02",
    "years": 3,
    "aggregation": "weighted"
  },
  "point": { "latitude": 48.86, "longitude": 2.35, "altitude_m": 65.0 },
  "period": { "months": [5,6], "days_per_month": {"5":22,"6":2}, "total_days": 24 },
  "basis": "point-normals(2022-2024)",
  "recent_stats": {
    "t_mean_c": 17.3,
    "t_min_c": 11.0,
    "t_max_c": 22.1,
    "precip_days": 11.4,
    "precip_sum_mm": 96.2
  },
  "months_breakdown": [
    { "month": 5, "t_mean_c": 16.8, "t_min_c": 11.2, "t_max_c": 21.0, "precip_sum_mm": 62.3 },
    { "month": 6, "t_mean_c": 18.5, "t_min_c": 12.0, "t_max_c": 23.5, "precip_sum_mm": 33.9 }
  ],
  "used_years": [2022, 2024],
  "degraded": false,
  "source": ["Meteostat Point Normals (48.86,2.35)"],
  "generated_at": "2025-11-23T07:58:00Z"
}
```
- 오류 코드:
  - `400 invalid_years_range`, `400 invalid_aggregation`, `400 invalid_date_range`
  - `409 trip_duration_required`
  - `422 destination_missing`, `422 destination_coordinates_unavailable`
  - `503 meteostat_api_key_missing`, `503 meteostat_unavailable`, `503 meteostat_no_data`

| 레퍼런스 | `GET /v1/reference/cabin_classes` | 좌석 등급 목록(airline_code=KE/TW 등으로 항공사별 조회) |
| 가방 | `PATCH /v1/bags/{bag_id}` | 이름/정렬 순서/타입(커스텀 가방만) 수정 |
| 가방 | `DELETE /v1/bags/{bag_id}` | 기본 가방 제외 삭제 |
| 아이템 | `POST /v1/items/decide` | (디버깅/내부용) 룰엔진 단독 호출 |
| 미디어 | `/v1/media/*` | 이미지 업로드, 상태 조회 (패킹 리스트와 간접 연관) |

---

## 10. 환율(FX) API

Frankfurter(ECB reference rates) 단일 소스를 사용하며, 최신 환율은 영업일 16:00 CET 기준 참조치입니다. 내부적으로 Redis 캐시를 사용해 최신 60초, 과거 24시간 TTL을 적용합니다.

### 10.1 `GET /v1/fx/quote`
- Query: `base=USD`, `symbols=KRW,JPY`
- Response:
  ```json
  {
    "as_of": "2025-11-21",
    "base": "USD",
    "rates": { "KRW": 1474.29, "JPY": 156.74 },
    "source": "ECB via Frankfurter"
  }
  ```
- 주의: 주말/공휴일에는 직전 영업일 기준 `as_of`가 반환됩니다.

### 10.2 `POST /v1/fx/convert`
- Body: `{ "amount": 120.5, "base": "USD", "symbol": "KRW" }`
- 내부적으로 `/quote` 캐시를 사용해 `converted = round(amount * rate, 2)`
- Response:
  ```json
  {
    "base": "USD",
    "symbol": "KRW",
    "amount": 120.5,
    "rate": 1474.29,
    "converted": 177698.75,
    "as_of": "2025-11-21",
    "source": "ECB via Frankfurter"
  }
  ```

### 10.3 `GET /v1/fx/quote/date`
- Query: `date=2025-01-15`, `base=USD`, `symbols=KRW`
- 미래 날짜 지정 시 `400 invalid_date`
- 과거 영업일 데이터는 Frankfurter `/v1/{date}`를 그대로 프록시

### 10.4 `POST /v1/fx/convert/date`
- Body: `{ "date": "2025-01-15", "amount": 1, "base": "USD", "symbol": "KRW" }`
- 주말/공휴일이면 직전 영업일 환율을 사용

### 10.5 `GET /v1/fx/currencies`
- Response: `{ "currencies": { "USD": "United States Dollar", "KRW": "South Korean Won", ... } }`
- 캐시 TTL 24시간. 프런트에서 통화 선택 UI에 사용

#### 공통 오류 코드
| 코드 | 설명 |
| --- | --- |
| `invalid_currency` | 지원하지 않는 통화 코드 |
| `invalid_date` | 미래 일자 또는 형식 오류 |
| `service_unavailable` | Frankfurter 응답 실패/타임아웃 |

위 목록은 현재 코드베이스에서 정상 동작 중인 API만 포함했으며, 새로운 엔드포인트가 추가되면 이 섹션 또한 함께 갱신해 주세요.

이 문서는 `2025-11-22` 기준 코드(`main` 브랜치)와 동일합니다. 새로운 엔드포인트가 추가되거나 스키마가 변경되면 본 파일을 함께 업데이트 해주세요.


