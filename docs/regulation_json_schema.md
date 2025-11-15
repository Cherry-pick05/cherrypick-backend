# 규정 JSON 파일 스키마

## 파일 구조

규정 데이터는 JSON 파일로 저장하며, 각 파일은 하나의 항공사 또는 국가의 규정을 포함합니다.

## 기본 구조

```json
{
  "scope": "airline" | "country",
  "code": "string",
  "name": "string",
  "rules": [
    {
      "item_category": "string",
      "constraints": {},
      "severity": "info" | "warn" | "block",
      "notes": "string (optional)"
    }
  ]
}
```

## 필드 설명

### 최상위 필드

- **scope** (필수): `"airline"` 또는 `"country"`
  - `"airline"`: 항공사별 규정
  - `"country"`: 국가별 규정

- **code** (필수): 항공사 코드 또는 국가 코드
  - 항공사: `"KE"` (대한항공), `"OZ"` (아시아나항공), `"DL"` (델타항공) 등
  - 국가: `"KR"` (한국), `"US"` (미국), `"JP"` (일본) 등 (ISO 3166-1 alpha-2)

- **name** (선택): 항공사명 또는 국가명 (읽기 쉬운 이름)
  - 예: `"대한항공"`, `"한국"`

- **rules** (필수): 규정 배열
  - 각 항목은 하나의 규정을 나타냅니다

### Rule 필드

- **item_category** (필수): 아이템 카테고리
  - 예: `"carry_on"`, `"checked"`, `"prohibited"`, `"restricted_liquids"`, `"electronics"` 등

- **constraints** (필수): 규정 제약사항 (JSON 객체)
  - 자유로운 구조로 정의 가능
  - 조건 필드 (선택사항): `route_type`, `cabin_class`, `fare_class`
  - 조건 필드가 없거나 null이면 모든 경우에 적용되는 공통 규정
  - 예시:
    ```json
    {
      "route_type": "international",  // 선택: "domestic" | "international" | null
      "cabin_class": "economy",  // 선택: "economy" | "business" | "first" | "prestige" | null
      "max_weight_kg": 7,
      "max_size_cm": {
        "length": 55,
        "width": 40,
        "height": 20
      },
      "max_pieces": 1,
      "allowed_items": ["laptop", "camera", "handbag"],
      "restricted_items": ["liquids_over_100ml"]
    }
    ```

- **severity** (필수): 규정 심각도
  - `"info"`: 정보성 규정 (경고 없음)
  - `"warn"`: 경고 규정 (주의 필요)
  - `"block"`: 금지 규정 (반입 불가)

- **notes** (선택): 추가 메모 또는 설명
  - 예: `"기내 반입 가능한 소형 수하물"`, `"위탁 수하물 포함"`

## 예시 파일

### 항공사 규정 예시

**`data/regulations/airline_KE.json`** (대한항공):

```json
{
  "scope": "airline",
  "code": "KE",
  "name": "대한항공",
  "rules": [
    {
      "item_category": "carry_on",
      "constraints": {
        "route_type": "international",
        "cabin_class": "economy",
        "max_weight_kg": 7,
        "max_size_cm": {
          "length": 55,
          "width": 40,
          "height": 20
        },
        "max_pieces": 1,
        "allowed_items": ["laptop", "camera", "handbag", "coat"]
      },
      "severity": "warn",
      "notes": "국제선 일반석 기내 반입 가능한 소형 수하물 1개"
    },
    {
      "item_category": "carry_on",
      "constraints": {
        "route_type": "international",
        "cabin_class": "prestige",
        "max_weight_kg": 7,
        "max_size_cm": {
          "length": 55,
          "width": 40,
          "height": 20
        },
        "max_pieces": 2,
        "allowed_items": ["laptop", "camera", "handbag", "coat"]
      },
      "severity": "warn",
      "notes": "국제선 프레스티지석 기내 반입 가능한 소형 수하물 2개"
    },
    {
      "item_category": "checked",
      "constraints": {
        "route_type": "international",
        "cabin_class": "economy",
        "max_weight_kg": 23,
        "max_pieces": 2,
        "overweight_fee_per_kg": 100,
        "max_total_weight_kg": 45
      },
      "severity": "warn",
      "notes": "국제선 일반석 기준 위탁 수하물 규정"
    },
    {
      "item_category": "checked",
      "constraints": {
        "route_type": "international",
        "cabin_class": "prestige",
        "max_weight_kg": 32,
        "max_pieces": 2,
        "overweight_fee_per_kg": 100,
        "max_total_weight_kg": 64
      },
      "severity": "warn",
      "notes": "국제선 프레스티지석 기준 위탁 수하물 규정"
    },
    {
      "item_category": "prohibited",
      "constraints": {
        "prohibited_items": [
          "explosives",
          "flammable_liquids",
          "weapons",
          "sharp_objects",
          "liquids_over_100ml"
        ]
      },
      "severity": "block",
      "notes": "기내 반입 금지 물품"
    },
    {
      "item_category": "restricted_liquids",
      "constraints": {
        "max_container_ml": 100,
        "max_total_ml": 1000,
        "must_be_in_transparent_bag": true,
        "items_per_container": 1
      },
      "severity": "warn",
      "notes": "액체류 제한 규정"
    }
  ]
}
```

### 국가 규정 예시

**`data/regulations/country_US.json`** (미국):

```json
{
  "scope": "country",
  "code": "US",
  "name": "미국",
  "rules": [
    {
      "item_category": "prohibited",
      "constraints": {
        "prohibited_items": [
          "weapons",
          "explosives",
          "certain_foods",
          "plants_without_permit",
          "animal_products"
        ],
        "customs_declaration_required": true
      },
      "severity": "block",
      "notes": "미국 입국 금지 물품"
    },
    {
      "item_category": "restricted_foods",
      "constraints": {
        "allowed_foods": ["commercially_packaged_foods"],
        "restricted_foods": ["fresh_fruits", "fresh_vegetables", "meat_products"],
        "max_amount_kg": 10
      },
      "severity": "warn",
      "notes": "식품 반입 제한 규정"
    }
  ]
}
```

**`data/regulations/country_KR.json`** (한국):

```json
{
  "scope": "country",
  "code": "KR",
  "name": "한국",
  "rules": [
    {
      "item_category": "prohibited",
      "constraints": {
        "prohibited_items": [
          "weapons",
          "drugs",
          "counterfeit_goods",
          "certain_plants"
        ]
      },
      "severity": "block",
      "notes": "한국 입국 금지 물품"
    },
    {
      "item_category": "restricted_alcohol",
      "constraints": {
        "max_amount_ml": 1000,
        "max_abv_percent": 60,
        "duty_free_allowance": true
      },
      "severity": "info",
      "notes": "주류 반입 제한"
    }
  ]
}
```

## 파일 명명 규칙

- 항공사: `airline_{CODE}.json` (예: `airline_KE.json`)
- 국가: `country_{CODE}.json` (예: `country_US.json`)
- 파일 위치: `data/regulations/` 디렉토리

## Constraints 필드 권장 구조

### 조건 필드 (선택사항)
규정이 특정 조건에만 적용되는 경우 사용합니다. 조건 필드가 없거나 null이면 모든 경우에 적용됩니다.

```json
{
  "route_type": "domestic" | "international" | null,  // null이면 모두 적용
  "cabin_class": "economy" | "business" | "first" | "prestige" | null,  // null이면 모든 좌석 등급
  "fare_class": "standard" | "flex" | "discount" | null  // 운임 등급 (선택사항)
}
```

### Carry-on (기내 수하물)

**예시: 국제선 일반석 기내 수하물**
```json
{
  "route_type": "international",
  "cabin_class": "economy",
  "max_weight_kg": 7,
  "max_size_cm": {
    "length": 55,
    "width": 40,
    "height": 20
  },
  "max_pieces": 1,
  "allowed_items": ["laptop", "camera"],
  "restricted_items": ["liquids_over_100ml"]
}
```

**예시: 국내선 일반석 기내 수하물**
```json
{
  "route_type": "domestic",
  "cabin_class": "economy",
  "max_weight_kg": 10,
  "max_size_cm": {
    "length": 55,
    "width": 40,
    "height": 20
  },
  "max_pieces": 1
}
```

**예시: 국제선 프레스티지석 기내 수하물**
```json
{
  "route_type": "international",
  "cabin_class": "prestige",
  "max_weight_kg": 7,
  "max_size_cm": {
    "length": 55,
    "width": 40,
    "height": 20
  },
  "max_pieces": 2,  // 프레스티지석은 2개 허용
  "allowed_items": ["laptop", "camera", "handbag", "coat"]
}
```

### Checked (위탁 수하물)

**예시: 국제선 일반석 위탁 수하물**
```json
{
  "route_type": "international",
  "cabin_class": "economy",
  "max_weight_kg": 23,
  "max_pieces": 2,
  "overweight_fee_per_kg": 100,
  "max_total_weight_kg": 45,
  "max_size_cm": {
    "length": 158,
    "width": 158,
    "height": 158
  }
}
```

**예시: 국제선 프레스티지석 위탁 수하물**
```json
{
  "route_type": "international",
  "cabin_class": "prestige",
  "max_weight_kg": 32,  // 프레스티지석은 더 많이 허용
  "max_pieces": 2,
  "overweight_fee_per_kg": 100,
  "max_total_weight_kg": 64
}
```

**예시: 모든 노선/좌석 등급에 공통 적용되는 규정**
```json
{
  "max_size_cm": {
    "length": 300,
    "width": 300,
    "height": 300
  },
  "notes": "모든 위탁 수하물 최대 크기 제한"
}
```

### Prohibited (금지 물품)
```json
{
  "prohibited_items": ["weapons", "explosives", "flammable_liquids"],
  "customs_declaration_required": true
}
```

### Restricted Liquids (액체류 제한)
```json
{
  "max_container_ml": 100,
  "max_total_ml": 1000,
  "must_be_in_transparent_bag": true,
  "items_per_container": 1
}
```

## 규정 매칭 로직

규정을 조회할 때는 다음 조건으로 필터링합니다:
1. `scope`, `code`로 기본 필터링
2. `item_category`로 카테고리 필터링
3. `constraints` 내의 조건 필드로 추가 필터링:
   - `route_type`: 여행 노선 타입과 일치하거나 null
   - `cabin_class`: 좌석 등급과 일치하거나 null
   - `fare_class`: 운임 등급과 일치하거나 null (선택사항)
4. 여러 규정이 매칭되는 경우, 가장 구체적인 규정(조건이 많은 것)을 우선 적용

**예시**: 국제선 프레스티지석 기내 수하물 규정 조회
- `route_type: "international"`, `cabin_class: "prestige"` 규정이 있으면 해당 규정 적용
- 없으면 `route_type: "international"`, `cabin_class: null` 규정 적용
- 그것도 없으면 `route_type: null`, `cabin_class: null` 공통 규정 적용

## 유효성 검사

JSON 파일을 로드할 때 다음을 검증합니다:
- `scope`는 `"airline"` 또는 `"country"`여야 함
- `code`는 비어있지 않아야 함
- `rules`는 배열이어야 하며, 최소 1개 이상의 규정이 있어야 함
- 각 `rule`의 `item_category`, `constraints`, `severity`는 필수
- `severity`는 `"info"`, `"warn"`, `"block"` 중 하나여야 함
- `constraints.route_type`은 `"domestic"`, `"international"`, 또는 null이어야 함
- `constraints.cabin_class`는 `"economy"`, `"business"`, `"first"`, `"prestige"`, 또는 null이어야 함


