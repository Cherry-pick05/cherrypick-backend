# CherryPick Backend

항공 수하물 규정 검증 및 위험물 분류를 위한 백엔드 API 서버입니다.

## 목차

- [주요 기능](#주요-기능)
- [기술 스택](#기술-스택)
- [시작하기](#시작하기)
- [환경 설정](#환경-설정)
- [데이터베이스 마이그레이션](#데이터베이스-마이그레이션)
- [API 문서](#api-문서)
- [프로젝트 구조](#프로젝트-구조)
- [주요 시스템](#주요-시스템)
- [개발 가이드](#개발-가이드)
- [참고 문서](#참고-문서)

## 주요 기능

### 1. 항공 수하물 규정 관리
- 항공사별, 국가별, 국제기구(IATA/ICAO) 규정 수집 및 관리
- 규정 스크래핑 및 자동 업데이트
- 규정 조건 기반 검증 (국내선/국제선, 좌석 등급 등)

### 2. LLM 기반 위험물 분류 시스템
- Google Gemini를 활용한 실시간 위험물 자동 분류
- 위험군 닫힌 집합 기반 분류 (`risk_keys.json`)
- 파라미터 자동 추출 (용량, 전력량, 개수 등)
- 신뢰도 기반 검토 플래그 설정

### 3. 규칙 엔진
- 다층 규정 레이어 병합 (보안, 항공사, 국가)
- 규정 충돌 감지 및 해결
- 기내/위탁 수하물 판정

### 4. 디바이스 관리
- 디바이스 부트스트랩
- 디바이스 토큰 기반 인증
- 사용자 동의 관리

### 5. 여정 & 패킹 리스트 관리
- 여정 및 구간(Segment) 정보 관리
- 경유지 재검색(LAGs) 조건 처리
- 트립별 가방(기내/위탁 기본 포함)과 체크리스트 아이템 관리

### 6. 추천 시스템
- LLM 기반 수하물 추천
- 날씨 및 환율 정보 통합

### 7. 미디어 관리
- S3 기반 이미지 업로드 및 관리
- 아이템 이미지 크롭 및 저장

## 기술 스택

### Backend Framework
- **FastAPI**: 고성능 비동기 웹 프레임워크
- **Uvicorn**: ASGI 서버

### 데이터베이스
- **MySQL 8.0**: 메인 데이터베이스
- **SQLAlchemy 2.0**: ORM
- **Alembic**: 데이터베이스 마이그레이션

### 캐싱 & 스토리지
- **Redis**: 캐싱 및 세션 관리
- **AWS S3 / LocalStack**: 이미지 스토리지

### AI/ML
- **Google Gemini API**: LLM 기반 분류 및 추천

### 스크래핑
- **BeautifulSoup4**: HTML 파싱
- **Playwright**: 동적 콘텐츠 스크래핑
- **PDFplumber**: PDF 파싱

### 기타
- **Pydantic**: 데이터 검증
- **Cryptography**: 암호화
- **Boto3**: AWS SDK

## 시작하기

### 사전 요구사항

- Python 3.11 또는 3.12
- Poetry (의존성 관리)
- Docker & Docker Compose (로컬 개발 환경)

### 설치

1. 저장소 클론
```bash
git clone <repository-url>
cd cherrypick-backend
```

2. 의존성 설치
```bash
poetry install
```

3. 환경 변수 설정
```bash
cp env.example .env
# .env 파일을 편집하여 필요한 값 설정
```

4. Docker 서비스 시작
```bash
docker-compose up -d
```

5. 데이터베이스 마이그레이션 실행
```bash
poetry run python run_migration.py
```

6. 서버 실행
```bash
poetry run uvicorn app.main:app --reload --port 8000
```

서버가 `http://localhost:8000`에서 실행됩니다.

## 환경 설정

주요 환경 변수는 `env.example` 파일을 참고하세요:

### 필수 설정

```bash
# 애플리케이션
APP_ENV=local
APP_NAME=cherrypick
PORT=8000

# 데이터베이스
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=cp_user
MYSQL_DB=cherrypick

# Redis
REDIS_URL=redis://localhost:6379/0

# AWS S3 (로컬 개발시 LocalStack 사용)
S3_BUCKET=cherrypick-item-crops
AWS_REGION=ap-northeast-2
AWS_ENDPOINT_URL=http://localhost:4566

# CORS
CORS_ORIGINS=*
CLIENT_ID_HEADER=X-Client-Id
```

### 선택적 설정

```bash
# Google Gemini API
GEMINI_MODEL=models/gemini-2.5-flash-lite

# LLM 분류기 설정
LLM_CLASSIFIER_ENABLED=true
LLM_CLASSIFIER_TEMPERATURE=0.0
LLM_CLASSIFIER_MAX_TOKENS=256
LLM_CLASSIFIER_TIMEOUT_SEC=8.0
LLM_CLASSIFIER_CACHE_TTL_SECONDS=604800
LLM_CLASSIFIER_CONFIDENCE_THRESHOLD=0.7

# 외부 API
WEATHER_API_KEY=your_openweather_api_key
KOREAEXIM_API_KEY=your_koreaexim_authkey

# 국토교통부 세계공항 데이터
MOLIT_SERVICE_KEY=72e8af88c6a182885c860951dc2f997b312678d084836403dbd4b874b2e334cf
MOLIT_AIRPORT_DATASET_ID=uddi:12f91d16-ea50-48d1-bdc3-df8410f22542
MOLIT_AIRPORT_BASE_URL=https://api.odcloud.kr/api/3051587/v1
```

## 데이터베이스 마이그레이션

Alembic을 사용하여 데이터베이스 스키마를 관리합니다.

### 마이그레이션 실행

```bash
# 최신 마이그레이션 적용
poetry run python run_migration.py

# 또는 Alembic 직접 사용
poetry run alembic upgrade head
```

### 새 마이그레이션 생성

```bash
poetry run alembic revision --autogenerate -m "설명"
poetry run alembic upgrade head
```

## API 문서

서버 실행 후 다음 URL에서 API 문서를 확인할 수 있습니다:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### 주요 API 엔드포인트

- `GET /v1/health` - 헬스 체크
- `POST /v1/bootstrap` - 디바이스 부트스트랩
- `GET /v1/devices` - 디바이스 정보 조회
- `POST /v1/items` - 아이템 분류 요청
- `GET /v1/trips` - 여정 조회
- `POST /v1/trips` - 여정 생성
- `GET /v1/trips/{trip_id}/bags` - 트립별 가방/체크리스트 조회
- `POST /v1/trips/{trip_id}/bags` - 가방 생성
- `PATCH /v1/bag-items/{item_id}` - 체크리스트 아이템 수정(상태/수량/가방 이동)
- `POST /v1/media/upload` - 이미지 업로드
- `WS /v1/ws` - WebSocket 연결
- `GET /v1/countries` - 국가 레퍼런스 목록(검색/지역 필터)
- `GET /v1/airports` - 공항 레퍼런스 목록(검색/국가 필터)

## 프로젝트 구조

```
cherrypick-backend/
├── alembic/              # 데이터베이스 마이그레이션
│   └── versions/
├── app/
│   ├── api/              # API 라우터
│   │   ├── bootstrap.py  # 디바이스 부트스트랩
│   │   ├── devices.py    # 디바이스 관리
│   │   ├── items.py      # 아이템 분류/저장
│   │   ├── trips.py      # 여정 관리
│   │   ├── bags.py       # 가방·체크리스트 API
│   │   ├── media.py      # 미디어 업로드
│   │   ├── ws.py         # WebSocket
│   │   └── routes.py      # 라우터 통합
│   ├── core/             # 핵심 설정
│   │   ├── config.py     # 환경 설정
│   │   └── cache.py      # Redis 캐싱
│   ├── db/               # 데이터베이스
│   │   ├── models/       # SQLAlchemy 모델
│   │   ├── base.py       # 베이스 클래스
│   │   └── session.py    # DB 세션
│   ├── schemas/          # Pydantic 스키마
│   │   ├── decision.py   # 판정 스키마
│   │   ├── preview.py    # 미리보기 스키마
│   │   ├── checklist.py  # 가방/체크리스트 스키마
│   │   └── recommendation.py  # 추천 스키마
│   ├── services/         # 비즈니스 로직
│   │   ├── llm_classifier.py      # LLM 분류기
│   │   ├── llm_decision.py        # LLM 판정
│   │   ├── rule_engine.py         # 규칙 엔진
│   │   ├── risk_guard.py          # 위험 가드
│   │   ├── recommendation.py      # 추천 시스템
│   │   ├── bag_service.py         # 가방/체크리스트 서비스 로직
│   │   ├── regulation_*.py        # 규정 관리
│   │   └── ...
│   ├── tasks/            # 백그라운드 작업
│   └── main.py           # FastAPI 앱 진입점
├── data/
│   ├── regulations/      # 규정 JSON 파일
│   └── taxonomy/         # 분류 체계
│       ├── taxonomy.json
│       ├── risk_keys.json
│       ├── benign_keys.json
│       └── synonyms.json
├── docs/                 # 문서
├── tests/                # 테스트
├── docker-compose.yml    # 로컬 개발 환경
├── pyproject.toml        # 프로젝트 설정
└── README.md
```

## 주요 시스템

### 1. LLM 기반 위험물 분류 파이프라인

LLM을 사용하여 단일 함수 호출로 위험물 분류, 파라미터 추출, 초기 판정을 수행합니다.

**흐름:**
1. LLM 함수 호출: 라벨, 여정 정보, 초기 파라미터 힌트 입력
2. 출력: `canonical` (위험군 또는 `benign_general`), 추출 파라미터, `carry_on`/`checked` 초안
3. 백엔드 가드: JSON 스키마 검증, 필수 파라미터 체크, 레이어 병합, 충돌 감지
4. 결과 정리: 비위험군은 즉시 허용, 위험군은 검토 필요 플래그 설정

자세한 내용은 [`docs/llm_risk_classifier_plan.md`](docs/llm_risk_classifier_plan.md) 참고.

### 2. 규정 수집 시스템

항공사 및 국가별 규정을 자동으로 수집하고 관리합니다.

**주요 기능:**
- 정적/동적 웹 스크래핑
- PDF 파싱
- 규정 정규화 및 저장
- 주기적 자동 업데이트

자세한 내용은 [`docs/regulation_implementation_guide.md`](docs/regulation_implementation_guide.md) 참고.

### 3. 규칙 엔진

다층 규정 레이어를 병합하여 최종 판정을 수행합니다.

**레이어 구조:**
- 보안 규정 (국가별)
- 항공사 규정
- 국제 규정 (IATA/ICAO)

**주요 기능:**
- 레이어 병합 (`merge_layers`)
- 규정 충돌 감지
- 조건 기반 필터링 (국내선/국제선, 좌석 등급 등)

### 4. 위험 가드 시스템

LLM 결과를 검증하고 안전장치를 제공합니다.

**검증 항목:**
- JSON 스키마 검증
- 필수 파라미터 체크
- 위험군 닫힌 집합 검증
- 신뢰도 임계값 체크
- 규정 충돌 감지

## 개발 가이드

### 코드 스타일

프로젝트는 다음 도구를 사용합니다:

- **Black**: 코드 포맷팅
- **isort**: import 정렬
- **Ruff**: 린팅

```bash
# 포맷팅
poetry run black .
poetry run isort .

# 린팅
poetry run ruff check .
```

### 테스트

```bash
poetry run pytest
```

### 규정 데이터 로드

규정 JSON 파일을 데이터베이스에 로드:

```bash
poetry run python load_regulations.py
```

### 세계 공항/국가 디렉터리 동기화

국토교통부 세계 공항 데이터를 DB/캐시에 적재합니다.

```bash
poetry run python -m app.tasks.sync_airports --log-level INFO
```

동기화 후 `/v1/countries`, `/v1/airports` API가 최신 데이터를 참조하며, 여정 생성 시 국가/공항 자동 매핑에 활용됩니다.

## 참고 문서

프로젝트의 상세 문서는 `docs/` 디렉토리에 있습니다:

- [`llm_risk_classifier_plan.md`](docs/llm_risk_classifier_plan.md) - LLM 기반 위험물 분류 시스템 설계
- [`regulation_implementation_guide.md`](docs/regulation_implementation_guide.md) - 규정 수집 구현 가이드
- [`regulation_sources.md`](docs/regulation_sources.md) - 규정 소스 목록
- [`regulation_json_schema.md`](docs/regulation_json_schema.md) - 규정 JSON 스키마
- [`regulation_conditions_guide.md`](docs/regulation_conditions_guide.md) - 규정 조건 필드 가이드
- [`regulation_scraping_methods.md`](docs/regulation_scraping_methods.md) - 스크래핑 방법
- [`packsafe.md`](docs/packsafe.md) - PackSafe 규정 참고