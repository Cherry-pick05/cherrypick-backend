# 패킹 리스트 / 아이템 API 정리

본 문서는 CherryPick 앱에서 기기 기반 사용자 인증을 거친 뒤 사용하는 패킹 리스트 관련 API를 정리한 문서입니다. 모든 엔드포인트는 FastAPI 기준 base path(`/v1` 혹은 `/items`) 아래에 노출되며, 별도의 언급이 없는 한 HTTPS + JSON Body를 사용합니다.

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

### 2.1 `POST /items/classify`
| 항목 | 값 |
| --- | --- |
| Request | `{ "label": "휴대폰 배터리", "locale": "ko-KR?", "req_id": "선택" }` |
| Response | `req_id`, `canonical`, `confidence`, `candidates`, `categories[]`, `abstain`, `decided_by`, `norm_label`, `signals`, `model_info` |
| 비고 | 자동 저장 없음. 사용자가 `/items/save` 호출해야 DB 반영 |

### 2.2 `POST /items/preview`
- Request: `PreviewRequest` (`label`, `locale`, `req_id?`, `itinerary`, `segments[]`, `item_params`, `duty_free`)
- Response: `PreviewResponse` (`state`, `resolved`, `engine`, `narration`, `ai_tips`, `flags`)
- 주 사용처: 저장 전에 LLM·룰엔진 결과 확인.

### 2.3 `POST /items/save`
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

트립 생성 시 기본 가방 두 개(`carry_on`, `checked`)가 자동 생성되며, 사용자 정의 가방도 `/trips/{trip_id}/bags` 엔드포인트를 통해 추가할 수 있습니다. `BagService.create_bag`이 트립/사용자 일관성을 검증하므로 기본 가방 외 확장도 안전하게 동작합니다.

### 3.1 `GET /v1/trips/{trip_id}/bags`
- Response: `{ "items": [ { "bag_id", "trip_id", "name", "bag_type", "is_default", "sort_order", "total_items", "packed_items", "created_at", "updated_at" }, ... ] }`
- 사용처: 트립 상세 화면에서 가방 목록과 각 가방의 진행 상황(총 아이템 수, 완료 수)을 한 번에 보여줄 때 사용.

### 3.2 `POST /v1/trips/{trip_id}/bags`
- Body: `{ "name": "스포츠 장비", "bag_type": "custom", "sort_order": 3 }`
- 제약: `is_default=true` 금지, 동일 트립 내 `bag_type="carry_on"/"checked"`는 기본 가방만 존재. `bag_type="custom"`은 다수 생성 가능.
- Response: `BagSummary`
- 동작: TripService → BagService를 통해 `user_id`, `trip_id`를 강제로 세팅하므로 기본 가방 외 가방을 추가해도 모든 체크리스트 저장 로직과 연동됩니다.

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
4. **미리보기**: `/items/preview` → Allow/Limited 정보 확인.
5. **가방 선택 후 저장**: `/items/save` (필수: `bag_id`).
6. **체크리스트 조회**: `/v1/trips/{trip_id}/items` 또는 `/v1/bags/{bag_id}/items`.
7. **사용자 편집**: `/v1/bag-items/{item_id}` PATCH로 상태, 수량, 메모, 가방 이동 관리.

---

## 7. 기타 가용 API 요약
| 분류 | 메서드 & 경로 | 설명 |
| --- | --- | --- |
| 건강 체크 | `GET /v1/health` | 간단한 서비스 상태 확인 |
| 부트스트랩 | `POST /bootstrap/consent` | 이용약관/개인정보 동의 기록 |
| 부트스트랩 | `GET /bootstrap/config` | 앱에 필요한 플래그/설정 제공 |
| 디바이스 | `POST /devices/refresh` | 기존 디바이스 프로필 갱신 및 토큰 재발급 |
| 트립 | `GET /v1/trips` | 상태(active/archived/all) 필터 + 페이지네이션 |
| 트립 | `GET /v1/trips/{trip_id}` | 상세 조회 |
| 트립 | `POST /v1/trips/{trip_id}/archive` | 트립을 “보관” 상태로 전환(목록에서 숨김) |
| 트립 | `POST /v1/trips/{trip_id}/set_active` | 해당 트립을 활성 트립으로 지정 |
| 트립 | `DELETE /v1/trips/{trip_id}?purge=true` | 트립 및 연결 레코드 삭제 |
| 트립 추천 | `GET /v1/trips/{trip_id}/recommendation` | 여행별 맞춤 추천(LLM/외부 데이터 기반) |
| 가방 | `PATCH /v1/bags/{bag_id}` | 이름/정렬 순서/타입(커스텀 가방만) 수정 |
| 가방 | `DELETE /v1/bags/{bag_id}` | 기본 가방 제외 삭제 |
| 아이템 | `POST /items/decide` | (디버깅/내부용) 룰엔진 단독 호출 |
| 미디어 | `/v1/media/*` | 이미지 업로드, 상태 조회 (패킹 리스트와 간접 연관) |

위 목록은 현재 코드베이스에서 정상 동작 중인 API만 포함했으며, 새로운 엔드포인트가 추가되면 이 섹션 또한 함께 갱신해 주세요.

이 문서는 `2025-11-22` 기준 코드(`main` 브랜치)와 동일합니다. 새로운 엔드포인트가 추가되거나 스키마가 변경되면 본 파일을 함께 업데이트 해주세요.


