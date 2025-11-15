# 국가별/항공사별 수하물 규정 수집 방법

## 개요
기내 수하물 및 위탁 수하물 규정을 인터넷에서 자동으로 수집하는 다양한 방법들을 정리합니다.

## 방법 1: 웹 스크래핑 (Web Scraping)

### 1.1 정적 HTML 스크래핑 (BeautifulSoup)
**적용 대상**: HTML로 직접 렌더링되는 사이트

**장점**:
- 빠르고 가벼움
- 리소스 사용량 적음
- 구현이 간단

**단점**:
- JavaScript로 동적 생성되는 콘텐츠는 못 가져옴
- 사이트 구조 변경 시 수정 필요

**필요 라이브러리**:
```bash
# pyproject.toml에 추가
"requests (>=2.31,<3.0)",
"beautifulsoup4 (>=4.12,<5.0)",
"lxml (>=5.0,<6.0)",
```

**예시 구조**:
```python
# app/services/regulation_scraper.py
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional

class StaticScraper:
    def scrape_airline_regulations(self, airline_code: str) -> List[Dict]:
        """항공사 규정 스크래핑"""
        url = f"https://example-airline.com/baggage/{airline_code}"
        response = requests.get(url, headers={"User-Agent": "..."})
        soup = BeautifulSoup(response.content, "lxml")
        # 파싱 로직
        return regulations
```

### 1.2 동적 콘텐츠 스크래핑 (Selenium/Playwright)
**적용 대상**: JavaScript로 동적 렌더링되는 사이트

**장점**:
- JavaScript 실행 가능
- 실제 브라우저처럼 동작

**단점**:
- 느리고 리소스 많이 사용
- 브라우저 드라이버 필요

**필요 라이브러리**:
```bash
# Selenium 옵션
"selenium (>=4.15,<5.0)"

# 또는 Playwright 옵션 (더 현대적)
"playwright (>=1.40,<2.0)"
```

**예시 구조**:
```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

class DynamicScraper:
    def scrape_with_selenium(self, url: str):
        driver = webdriver.Chrome()
        driver.get(url)
        # JavaScript 실행 대기 후 스크래핑
        return data
```

### 1.3 대규모 스크래핑 (Scrapy)
**적용 대상**: 여러 사이트를 체계적으로 수집

**장점**:
- 비동기 처리로 빠름
- 스케줄링, 중복 제거 등 내장 기능
- 확장 가능한 구조

**단점**:
- 학습 곡선 높음
- 오버엔지니어링 가능

## 방법 2: 공개 API 활용

### 2.1 항공사 공식 API
일부 항공사는 공식 API를 제공합니다:
- **IATA**: 국제 항공 운송 협회 데이터
- **Amadeus API**: 항공 데이터 제공
- **Sabre API**: 항공 예약 시스템 데이터

**장점**:
- 구조화된 데이터
- 공식 데이터라 신뢰성 높음
- 지속적 업데이트 가능

**단점**:
- API 키 필요 (유료 가능)
- 모든 항공사가 제공하지 않음
- Rate limiting 존재

**예시 구조**:
```python
import httpx
from app.core.config import settings

class AirlineAPIClient:
    def __init__(self):
        self.api_key = settings.airline_api_key
        self.base_url = "https://api.airline.com"
    
    async def get_baggage_rules(self, airline_code: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/baggage/{airline_code}",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            return response.json()
```

## 방법 3: 하이브리드 접근법 (권장)

### 3.1 수동 수집 + 자동 업데이트
1. **초기 데이터**: 수동으로 주요 항공사/국가 규정 수집
2. **자동 업데이트**: 주기적으로 스크래핑하여 변경사항 감지
3. **수동 검증**: 중요한 변경사항은 수동 확인

**구현 예시**:
```python
# app/services/regulation_collector.py
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models.regulation import RegulationRule

class RegulationCollector:
    def __init__(self, db: Session):
        self.db = db
    
    def save_regulation(
        self,
        scope: str,  # "country" or "airline"
        code: str,   # 국가 코드 또는 항공사 코드
        category: str,
        constraints: dict,
        severity: str = "info"
    ):
        # 중복 체크
        existing = self.db.query(RegulationRule).filter(
            RegulationRule.scope == scope,
            RegulationRule.code == code,
            RegulationRule.item_category == category
        ).first()
        
        if existing:
            # 업데이트
            existing.constraints = constraints
            existing.updated_at = datetime.now()
        else:
            # 신규 생성
            rule = RegulationRule(
                scope=scope,
                code=code,
                item_category=category,
                constraints=constraints,
                severity=severity
            )
            self.db.add(rule)
        
        self.db.commit()
```

### 3.2 다양한 소스 통합
- **웹 스크래핑**: 공식 사이트에서 최신 정보
- **API**: 가능한 경우 API 사용
- **수동 입력**: 스크래핑 불가능한 경우

## 방법 4: 구조화된 데이터 피드

### 4.1 RSS/XML 피드
일부 항공사는 RSS나 XML 형태로 규정 변경사항을 제공합니다.

### 4.2 JSON 피드
일부 사이트는 JSON API를 제공하지만 인증이 필요할 수 있습니다.

## 방법 5: 써드파티 서비스

### 5.1 항공 데이터 제공업체
- **Amadeus**: 항공 데이터 API
- **Sabre**: 항공 예약/운영 데이터
- **Travelport**: 항공 서비스 데이터

**장점**:
- 정확하고 최신 데이터
- 여러 항공사 통합 제공

**단점**:
- 비용 발생
- API 의존성

## 구현 전략 제안

### 단계별 접근

1. **1단계: 수동 수집 + DB 저장**
   - 주요 항공사/국가 규정을 수동으로 수집하여 DB에 저장
   - 관리자 API 엔드포인트 생성

2. **2단계: 간단한 스크래핑 자동화**
   - BeautifulSoup으로 정적 사이트 스크래핑
   - 주기적으로 실행하는 스크립트 생성

3. **3단계: 동적 사이트 지원**
   - Selenium/Playwright 추가
   - 필요시에만 사용하도록 조건부 실행

4. **4단계: 업데이트 감지 및 알림**
   - 규정 변경사항 감지
   - 관리자에게 알림

### 권장 아키텍처

```
app/
├── services/
│   ├── regulation_scraper.py      # 스크래핑 로직
│   ├── regulation_collector.py     # DB 저장 로직
│   └── regulation_updater.py       # 주기적 업데이트
├── api/
│   └── admin/
│       └── regulations.py          # 관리자 API
└── tasks/
    └── sync_regulations.py          # 스케줄링 작업
```

### 주의사항

1. **로봇 배제 표준 (robots.txt)**: 스크래핑 전 확인 필수
2. **Rate Limiting**: 과도한 요청 방지
3. **User-Agent**: 정중한 User-Agent 설정
4. **법적 고려사항**: 각 사이트의 이용약관 확인
5. **에러 처리**: 사이트 구조 변경 대응
6. **캐싱**: Redis를 활용한 캐싱으로 부하 감소

## 다음 단계

1. 어떤 방법으로 진행할지 결정
2. 필요한 라이브러리 추가
3. 프로토타입 구현
4. 테스트 및 검증
5. 프로덕션 배포


