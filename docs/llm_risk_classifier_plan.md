# LLM 기반 위험물 분류·판정 파이프라인

## 배경
- 기존 다단계 흐름에서는 “후드티”, “칫솔”처럼 일상 품목도 규칙 엔진까지 흘러가면서 불필요한 검토가 발생.
- 반대로 에어로졸·배터리 등 위험군은 필수 파라미터 누락 때문에 손으로 재확인해야 하는 경우가 잦음.
- 목표: **LLM 1회 함수콜**로 분류/파라미터/판정 초안을 동시에 받아 즉시 통과·검토를 가르고, 백엔드는 **얇은 가드**로 안전망만 담당.

## 전체 흐름 요약
1. **LLM 함수콜(단일)**  
   - 입력: 라벨·로케일·여정/구간·초기 파라미터 힌트.  
   - 출력: `canonical`(위험군 닫힌 집합/또는 `benign_general`), 추출 파라미터, `carry_on`/`checked` 초안, `signals`.
2. **백엔드 가드**  
   - JSON 스키마 검증 → enum/type 보장.  
   - 위험군이면 필수 파라미터 체크, 레이어 병합(`merge_layers`) 실행, 충돌 감지.  
   - 추가 플래그: 신뢰도/근거 부족, LLM 실패 시 자동 `needs_review`.
3. **결과 정리**  
   - 비위험군(`benign_general`)은 즉시 허용(`state=complete`).  
   - 위험군이거나 가드 플래그 켜지면 `state=needs_review` + 부족한 필드/충돌 정보를 프런트에 전달.

## LLM 함수콜 스키마

```json
{
  "input": {
    "label": "string",
    "locale": "ko-KR",
    "itinerary": {
      "from": "ICN",
      "to": "LAX",
      "via": ["PVG"],
      "rescreening": true
    },
    "segments": [
      {"leg": "ICN-PVG", "operating": "KE", "cabin_class": "economy"}
    ],
    "item_params": {
      "volume_ml": null,
      "wh": null,
      "count": null,
      "weight_kg": null,
      "abv_percent": null,
      "blade_length_cm": null
    }
  },
  "output": {
    "canonical": "aerosol_toiletry|...|benign_general",
    "params": {
      "volume_ml": null,
      "wh": null,
      "count": null,
      "weight_kg": null,
      "abv_percent": null,
      "blade_length_cm": null
    },
    "carry_on": {"status": "allow|limit|deny", "badges": ["string"]},
    "checked":  {"status": "allow|limit|deny", "badges": ["string"]},
    "needs_review": false,
    "signals": {
      "matched_terms": ["string"],
      "confidence": 0.0,
      "notes": "optional model comment"
    },
    "model_info": {"name": "gemini-1.5", "temperature": 0.0}
  }
}
```

- LLM 시스템 프롬프트 핵심:  
  1. **`ALLOWED_RISK_KEYS` 중 하나 선택**, 없으면 `benign_general`.  
  2. **숫자 추정 금지**, 근거 없으면 `null`.  
  3. **보수적 초안**: 에어로졸/액체 `limit`, 스페어 배터리 `carry_on allow + checked deny` 등.  
  4. `signals.matched_terms` 2~4개, **반드시 입력 텍스트에서 발췌**.  
  5. **JSON only**, `temperature=0`로 결정론 유지.

## JSON 스키마 검증
- 백엔드에서 `pydantic`/`jsonschema`로 **엄격 검증**:  
  - `canonical`: enum(`ALLOWED_RISK_KEYS ∪ {benign_general}`)  
  - `carry_on.status`/`checked.status`: enum(`allow|limit|deny`)  
  - `params` 필드는 `number|null`, NaN 금지.  
  - `signals.confidence`: 0~1, `matched_terms` 길이 2~4.  
  - 검증 실패 → LLM 실패 취급(`state=needs_review`, `flags.validation_error=true`).

## 위험군 닫힌 집합

```text
ALLOWED_RISK_KEYS = {
  # batteries/electric
  "lithium_battery_spare","lithium_battery_installed","power_bank",
  "smart_luggage_battery","e_bike_scooter_battery","button_cell_battery",
  "ni_mh_nicd_battery","wet_cell_battery","wheelchair_battery","e_cigarette",
  # aerosols/sprays
  "aerosol_toiletry","aerosol_non_toiletry","spray_paint",
  "bear_spray_capsaicin","compressed_gas_spray",
  # liquids & gels & alcohol
  "cosmetics_liquid","perfume","nail_polish","nail_polish_remover_acetone",
  "hand_sanitizer_alcohol","medicine_liquid","food_liquid","alcohol_beverage",
  "duty_free_liquids_steb",
  # flammables
  "lighter_disposable","lighter_zippo","matches_safety","matches_strike_anywhere",
  "fuel_camping_stove","gas_canister_butane_propane","alcohol_fuel_methanol",
  "solid_fuel_tablets",
  # gases/cylinders
  "co2_cartridge_small","oxygen_cylinder_medical","scuba_tank","camping_gas_canister",
  # dry ice
  "dry_ice",
  # security tools/weapons
  "knife","scissors","multi_tool","firearm","ammunition","taser_stun_gun","realistic_toy_gun",
  # hazardous chemicals
  "corrosive_liquid","oxidizer","toxic_substance_pesticide","mercury_thermometer",
  "paint_oil_based","adhesive_resin_epoxy","bleach","peroxide_solution",
  # special/misc
  "magnet_strong","heat_tool_soldering_iron","hoverboard","power_tool_battery",
  # sport/safety
  "avalanche_rescue_pack","lifejacket_co2",
  # biological
  "biological_sample_noninfectious","infectious_substance"
}
```

- 리스트 **외의 모든 품목**은 자동으로 `benign_general`.  
- 실제 운용 키는 `data/taxonomy/risk_keys.json`에서 로드하며, 운영자가 파일/DB를 통해 업데이트 → 재기동 없이 핫리로드(추후 확장).  
- 필요 시 별도 관리 도구에서 이 파일을 편집하거나 DB 싱크하도록 구성.

## 필수 파라미터 매핑

| Canonical | 요구 파라미터 |
| --- | --- |
| `aerosol_*`, `cosmetics_liquid`, `perfume`, `medicine_liquid`, `food_liquid`, `duty_free_liquids_steb`, `alcohol_beverage` | `volume_ml` (필수), `count`(선택) |
| `alcohol_beverage` 추가 | `abv_percent` (필수) |
| `lithium_battery_*`, `power_bank`, `smart_luggage_battery`, `power_tool_battery`, `wheelchair_battery`, `e_bike_scooter_battery` | `wh` + `count` (둘 다 필수) |
| `button_cell_battery`, `ni_mh_nicd_battery`, `wet_cell_battery` | `wh` **또는** `count` 중 하나라도 없으면 리뷰 |
| `dry_ice` | `weight_kg` |
| `knife`, `scissors`, `multi_tool` | `blade_length_cm` |
| `co2_cartridge_small`, `oxygen_cylinder_medical`, `camping_gas_canister`, `compressed_gas_spray` | `count` |

- 매핑은 서버 상수(dict)로 관리, **가드 로직에서 반복 사용**.  
- 필수값 누락 시 `flags.missing_params`에 키를 기록하고 자동 `needs_review`.

## needs_review 조건
1. `canonical != benign_general` 이고 필수 파라미터 누락.
2. `merge_layers` 결과 `conflict=True` (보안 vs 항공사 등).  
3. `signals.confidence < threshold` (예: 0.65) 또는 `matched_terms` 길이 <2.  
4. JSON 검증 실패 / 파싱 오류 / LLM 타임아웃.  
5. `carry_on`·`checked` 템플릿이 내부 룰과 상충(예: 스페어 배터리인데 checked=allow).  
6. 운영자가 지정한 override (예: 특정 경유국/항공사 위험군 항상 리뷰).

`state = "complete"` 는 위 조건이 모두 False일 때만 설정.

## carry_on/checked 초안 템플릿
- 위험군별 기본 패턴을 서버 딕셔너리 `DEFAULT_DECISIONS` 로 관리:
  - 예) `lithium_battery_spare`: `carry_on=("allow", ["휴대만 허용"])`, `checked=("deny", ["위탁 금지"])`
  - `aerosol_toiletry`: 두 구간 모두 `limit`, `badges=["500ml 이하", "총 2L"]`
- 템플릿은 LLM 프롬프트에서도 공유하여 **모델 교체 없이 서버 핫픽스 가능**.

## 실패/폴백 전략
- LLM 에러/타임아웃/JSON 불가 시:
  - `state="needs_review"`, `resolved.canonical=null`, `flags.llm_error` 삽입.
  - 프런트에는 “AI 응답 지연 → 수동 검토” 메시지.
- 재시도 정책: 동일 라벨 3분 캐싱으로 폭주 방지.

## 로깅 & 모니터링
- LLM 응답 / 검증 실패 / needs_review 사유를 구조화된 로그로 남김.  
- `missing_params`·`low_confidence` 건수를 메트릭으로 전송 → 프롬프트 튜닝 지표.

## 기대 동작
- “후드티”  
  - `canonical=benign_general`, `carry_on/checked=allow`, `needs_review=false`.
- “헤어 스프레이 350ml”  
  - `canonical=aerosol_toiletry`, `params.volume_ml=350`.  
  - 필수 파라미터 충족 → 레이어 병합 후 경유지 LAGs 조건만 적용.  
  - 만약 `rescreening`에 따라 STEB 요구 등 충돌 시 `needs_review=true`.
- “보조배터리 200Wh 3개”  
  - `canonical=lithium_battery_spare`, `params.wh=200`, `count=3`.  
  - 가드에서 개수 초과 감지 → `merge_layers` 조건 미충족, `flags.conflict` = true → 리뷰.

## 운영 팁
- `ALLOWED_RISK_KEYS`·필수 파라미터 테이블을 별도 YAML/JSON으로 분리해 **운영자가 Hot reload** 가능하게.  
- `signals.matched_terms` 는 BI 용도로도 활용하므로 `benign_general` 케이스에도 최소 2개를 요구.  
- 프롬프트와 서버 상수를 동일 소스에서 생성하도록 `jinja` 템플릿화하면 drift 방지.


