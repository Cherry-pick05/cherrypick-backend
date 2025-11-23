# Reference API curl 테스트 명령어

기본 URL: `http://localhost:8000` (필요시 변경)

## 1. 국가 목록 조회

### 전체 국가 목록
```bash
curl -X GET "http://localhost:8000/v1/reference/countries" \
  -H "Content-Type: application/json"
```

### 국가 검색 (한국)
```bash
curl -X GET "http://localhost:8000/v1/reference/countries?q=한국" \
  -H "Content-Type: application/json"
```

### 국가 검색 (코드: KR)
```bash
curl -X GET "http://localhost:8000/v1/reference/countries?q=KR" \
  -H "Content-Type: application/json"
```

### 모든 국가 조회 (active_only=false)
```bash
curl -X GET "http://localhost:8000/v1/reference/countries?active_only=false" \
  -H "Content-Type: application/json"
```

### 지역 필터링
```bash
curl -X GET "http://localhost:8000/v1/reference/countries?region=Asia" \
  -H "Content-Type: application/json"
```

## 2. 공항 목록 조회

### 전체 공항 목록
```bash
curl -X GET "http://localhost:8000/v1/reference/airports" \
  -H "Content-Type: application/json"
```

### 공항 검색 (인천)
```bash
curl -X GET "http://localhost:8000/v1/reference/airports?q=인천" \
  -H "Content-Type: application/json"
```

### 공항 검색 (코드: ICN)
```bash
curl -X GET "http://localhost:8000/v1/reference/airports?q=ICN" \
  -H "Content-Type: application/json"
```

### 국가별 공항 조회 (KR)
```bash
curl -X GET "http://localhost:8000/v1/reference/airports?country_code=KR" \
  -H "Content-Type: application/json"
```

### 결과 개수 제한 (limit=5)
```bash
curl -X GET "http://localhost:8000/v1/reference/airports?limit=5" \
  -H "Content-Type: application/json"
```

### 복합 조건 (국가 + 검색어 + limit)
```bash
curl -X GET "http://localhost:8000/v1/reference/airports?country_code=KR&q=서울&limit=10" \
  -H "Content-Type: application/json"
```

## 3. 항공사 목록 조회

### 전체 항공사 목록
```bash
curl -X GET "http://localhost:8000/v1/reference/airlines" \
  -H "Content-Type: application/json"
```

### 항공사 검색 (대한항공)
```bash
curl -X GET "http://localhost:8000/v1/reference/airlines?q=대한항공" \
  -H "Content-Type: application/json"
```

### 항공사 검색 (코드: KE)
```bash
curl -X GET "http://localhost:8000/v1/reference/airlines?q=KE" \
  -H "Content-Type: application/json"
```

### 모든 항공사 조회 (active_only=false)
```bash
curl -X GET "http://localhost:8000/v1/reference/airlines?active_only=false" \
  -H "Content-Type: application/json"
```

## 4. 좌석 등급 목록 조회

### 기본 좌석 등급
```bash
curl -X GET "http://localhost:8000/v1/reference/cabin_classes" \
  -H "Content-Type: application/json"
```

### 대한항공 좌석 등급
```bash
curl -X GET "http://localhost:8000/v1/reference/cabin_classes?airline_code=KE" \
  -H "Content-Type: application/json"
```

### 대만항공 좌석 등급
```bash
curl -X GET "http://localhost:8000/v1/reference/cabin_classes?airline_code=TW" \
  -H "Content-Type: application/json"
```

## 실행 방법

### 스크립트 실행
```bash
# 기본 URL 사용
./test_reference_api.sh

# 다른 URL 사용
BASE_URL=http://your-server:8000 ./test_reference_api.sh
```

### jq 없이 실행 (JSON 포맷팅 없음)
스크립트에서 `jq`가 없어도 동작하지만, JSON이 포맷팅되지 않습니다.

### 개별 명령어 실행
위의 curl 명령어를 복사하여 터미널에서 직접 실행할 수 있습니다.

