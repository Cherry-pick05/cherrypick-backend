# 규정 조건 필드 가이드 (국내선/국제선, 좌석 등급)

## 개요

항공사 수하물 규정은 노선 타입(국내선/국제선)과 좌석 등급에 따라 다를 수 있습니다. 이를 위해 `constraints` 필드에 조건 필드를 추가하여 표현합니다.

## 조건 필드

### route_type (노선 타입)
- `"domestic"`: 국내선
- `"international"`: 국제선
- `null` 또는 필드 없음: 모든 노선에 적용

### cabin_class (좌석 등급)
- `"economy"`: 일반석
- `"business"`: 비즈니스석
- `"first"`: 일등석
- `"prestige"`: 프레스티지석 (대한항공 등)
- `null` 또는 필드 없음: 모든 좌석 등급에 적용

### fare_class (운임 등급) - 선택사항
- `"standard"`: 스탠다드 운임
- `"flex"`: 플렉스 운임
- `"discount"`: 할인 운임
- `null` 또는 필드 없음: 모든 운임 등급에 적용

## 규정 저장 전략

### 1. 조건별 규정 분리 저장
같은 `item_category`라도 조건이 다르면 별도의 규정으로 저장합니다.

**예시: 대한항공 기내 수하물**
- 국제선 일반석: `item_category: "carry_on"`, `constraints.route_type: "international"`, `constraints.cabin_class: "economy"`
- 국제선 프레스티지석: `item_category: "carry_on"`, `constraints.route_type: "international"`, `constraints.cabin_class: "prestige"`
- 국내선 일반석: `item_category: "carry_on"`, `constraints.route_type: "domestic"`, `constraints.cabin_class: "economy"`

### 2. 중복 체크 로직
`regulation_collector.py`의 `save_regulation` 메서드에서 중복 체크 시:
- 기존: `scope`, `code`, `item_category`만 체크
- 변경: `scope`, `code`, `item_category`, `constraints.route_type`, `constraints.cabin_class`, `constraints.fare_class` 모두 체크

```python
# 중복 체크 로직 예시
existing = self.db.query(RegulationRule).filter(
    RegulationRule.scope == scope,
    RegulationRule.code == code,
    RegulationRule.item_category == item_category,
    # constraints JSON에서 조건 필드 추출하여 비교
    RegulationRule.constraints['route_type'].astext == constraints.get('route_type'),
    RegulationRule.constraints['cabin_class'].astext == constraints.get('cabin_class'),
    RegulationRule.constraints['fare_class'].astext == constraints.get('fare_class')
).first()
```

### 3. DB 모델 Unique Constraint 수정 필요
현재 `regulation_rules` 테이블의 unique constraint:
```sql
UNIQUE KEY `uq_rules_scope_code_cat` (`scope`, `code`, `item_category`)
```

이 constraint는 같은 `item_category`에 대해 하나의 규정만 저장할 수 있게 제한합니다. 하지만 조건 필드를 도입하면 같은 `item_category`라도 여러 규정이 필요하므로, 이 constraint를 제거하거나 수정해야 합니다.

**옵션 1: Unique constraint 제거**
- 같은 `item_category`에 대해 여러 규정 저장 가능
- 애플리케이션 레벨에서 중복 체크

**옵션 2: 조건 필드를 별도 컬럼으로 분리**
- `route_type`, `cabin_class`, `fare_class`를 별도 컬럼으로 추가
- Unique constraint: `(scope, code, item_category, route_type, cabin_class, fare_class)`
- Migration 필요

**권장: 옵션 1 (유연성 우선)**
- 조건 필드 조합이 다양할 수 있음
- JSON constraints에 모든 조건을 저장하는 것이 유연함
- 애플리케이션 레벨에서 중복 체크 구현

## 규정 조회 및 매칭 로직

### 규정 조회 시 필터링
```python
def get_regulations(
    self,
    scope: str,
    code: str,
    item_category: str,
    route_type: Optional[str] = None,
    cabin_class: Optional[str] = None,
    fare_class: Optional[str] = None
) -> list[RegulationRule]:
    """
    조건에 맞는 규정 조회
    
    매칭 우선순위:
    1. 모든 조건이 일치하는 규정
    2. route_type, cabin_class 일치하는 규정
    3. route_type만 일치하는 규정
    4. cabin_class만 일치하는 규정
    5. 조건이 없는 공통 규정
    """
    query = self.db.query(RegulationRule).filter(
        RegulationRule.scope == scope,
        RegulationRule.code == code,
        RegulationRule.item_category == item_category
    )
    
    # 조건별 필터링 및 정렬
    # ...
```

### 규정 매칭 예시
**시나리오**: 국제선 프레스티지석 기내 수하물 규정 조회

1. `route_type: "international"`, `cabin_class: "prestige"` 규정이 있으면 해당 규정 적용
2. 없으면 `route_type: "international"`, `cabin_class: null` 규정 적용
3. 없으면 `route_type: null`, `cabin_class: "prestige"` 규정 적용
4. 없으면 `route_type: null`, `cabin_class: null` 공통 규정 적용

## 크롤링 시 고려사항

### 항공사 사이트 크롤링
항공사 사이트에서 규정을 크롤링할 때:
1. 노선 타입별 탭/섹션 확인 (국내선/국제선)
2. 좌석 등급별 규정 확인 (일반석/비즈니스석/일등석/프레스티지석)
3. 각 조합별로 별도 규정으로 저장

### 데이터 정규화
크롤링한 원시 데이터를 표준 스키마로 변환할 때:
- 노선 타입 감지: URL, 탭, 섹션 제목 등에서 추출
- 좌석 등급 감지: 테이블 헤더, 섹션 제목 등에서 추출
- 조건 필드 자동 추출 및 적용

## 구현 작업

1. **DB Migration**: `regulation_rules` 테이블의 unique constraint 수정/제거
2. **regulation_collector.py**: 중복 체크 로직 업데이트 (조건 필드 포함)
3. **regulation_collector.py**: 조회 메서드에 조건 필드 필터링 추가
4. **regulation_normalizer.py**: 크롤링 데이터에서 조건 필드 추출
5. **regulation_scraper.py**: 항공사별 스크래퍼에서 조건 필드 추출 로직 추가

