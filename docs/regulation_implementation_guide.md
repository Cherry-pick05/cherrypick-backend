# 규정 수집 구현 가이드

## 1. 필요한 라이브러리 설치

### 기본 스크래핑 (정적 HTML)
```bash
# pyproject.toml의 dependencies에 추가:
"requests (>=2.31,<3.0)",
"beautifulsoup4 (>=4.12,<5.0)",
"lxml (>=5.0,<6.0)",  # 빠른 파싱을 위해 (선택사항)

# 설치:
poetry add requests beautifulsoup4 lxml
```

### 동적 콘텐츠 스크래핑 (선택사항)
```bash
# Selenium 옵션
poetry add selenium

# 또는 Playwright 옵션 (더 현대적, 권장)
poetry add playwright
playwright install chromium  # 브라우저 설치
```

### 비동기 HTTP (선택사항)
```bash
poetry add httpx
```

## 2. 설정 추가

`app/core/config.py`에 스크래퍼 설정 추가:

```python
class Settings(BaseSettings):
    # ... 기존 설정 ...
    
    # 스크래퍼 설정
    scraper_user_agent: str = "Mozilla/5.0 (compatible; CherryPickBot/1.0)"
    scraper_timeout: int = 10
    scraper_delay_seconds: float = 1.0  # 요청 간 딜레이 (서버 부하 방지)
    
    # 규정 업데이트 스케줄
    regulation_update_interval_hours: int = 24
```

## 3. 사용 예시

### 3.1 수동으로 규정 저장

```python
from app.db.session import SessionLocal
from app.services.regulation_collector import RegulationCollector

db = SessionLocal()
collector = RegulationCollector(db)

# 항공사 규정 저장
collector.save_regulation(
    scope="airline",
    code="KE",  # 대한항공
    item_category="carry_on",
    constraints={
        "max_weight_kg": 7,
        "max_size_cm": "55x40x20",
        "max_pieces": 1,
        "allowed_items": ["laptop", "camera", "handbag"],
        "restricted_items": ["liquids_over_100ml"]
    },
    severity="warn",
    notes="기내 반입 가능한 소형 수하물"
)

# 국가 규정 저장
collector.save_regulation(
    scope="country",
    code="US",  # 미국
    item_category="prohibited",
    constraints={
        "prohibited_items": [
            "weapons",
            "explosives",
            "liquids_over_100ml",
            "certain_foods"
        ]
    },
    severity="block",
    notes="미국 입국 금지 물품"
)

db.close()
```

### 3.2 스크래핑으로 규정 수집

```python
from app.services.regulation_scraper import RegulationScraper
from app.services.regulation_collector import RegulationCollector
from app.db.session import SessionLocal

# 스크래퍼 구현 (각 항공사/국가별로 커스터마이징 필요)
class KoreanAirScraper(RegulationScraper):
    def scrape_airline_regulations(self, airline_code: str):
        import requests
        from bs4 import BeautifulSoup
        
        url = f"https://www.koreanair.com/baggage/{airline_code}"
        html = self._get_page(url)
        
        if not html:
            return []
        
        soup = BeautifulSoup(html, "lxml")
        regulations = []
        
        # 실제 파싱 로직 구현
        # ... (항공사별로 다름)
        
        return regulations

# 사용
scraper = KoreanAirScraper(base_url="https://www.koreanair.com")
regulations = scraper.scrape_airline_regulations("KE")

db = SessionLocal()
collector = RegulationCollector(db)

for reg in regulations:
    collector.save_regulation(
        scope="airline",
        code="KE",
        item_category=reg["category"],
        constraints=reg["constraints"],
        severity=reg.get("severity", "info")
    )

db.close()
```

### 3.3 규정 조회

```python
from app.db.session import SessionLocal
from app.services.regulation_collector import RegulationCollector

db = SessionLocal()
collector = RegulationCollector(db)

# 항공사별 규정 조회
ke_regulations = collector.get_regulations(
    scope="airline",
    code="KE"
)

# 국가별 규정 조회
us_regulations = collector.get_regulations(
    scope="country",
    code="US"
)

# 특정 카테고리만 조회
carry_on_rules = collector.get_regulations(
    scope="airline",
    code="KE",
    item_category="carry_on"
)

db.close()
```

## 4. 주기적 업데이트 작업

### 4.1 스케줄러 스크립트 생성

`app/tasks/update_regulations.py`:

```python
"""
규정 업데이트 스케줄러
"""
import logging
from app.db.session import SessionLocal
from app.services.regulation_scraper import RegulationScraper
from app.services.regulation_collector import RegulationCollector

logger = logging.getLogger(__name__)

def update_airline_regulations():
    """항공사 규정 업데이트"""
    db = SessionLocal()
    try:
        collector = RegulationCollector(db)
        
        # 주요 항공사 코드 리스트
        airlines = ["KE", "OZ", "DL", "AA", "UA", "LH", "AF"]
        
        for airline_code in airlines:
            try:
                # 스크래퍼 인스턴스 생성 (각 항공사별로 다름)
                scraper = RegulationScraper(base_url=f"https://{airline_code}.com")
                regulations = scraper.scrape_airline_regulations(airline_code)
                
                for reg in regulations:
                    collector.save_regulation(
                        scope="airline",
                        code=airline_code,
                        item_category=reg["category"],
                        constraints=reg["constraints"],
                        severity=reg.get("severity", "info")
                    )
                
                logger.info(f"{airline_code} 규정 업데이트 완료")
            except Exception as e:
                logger.error(f"{airline_code} 규정 업데이트 실패: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    update_airline_regulations()
```

### 4.2 Cron Job 설정

```bash
# 매일 새벽 3시에 실행
0 3 * * * cd /path/to/cherrypick-backend && poetry run python app/tasks/update_regulations.py
```

또는 Python 스케줄러 사용:

```bash
poetry add schedule
```

## 5. API 엔드포인트 예시

`app/api/admin/regulations.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.db.session import get_db
from app.services.regulation_collector import RegulationCollector
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/regulations", tags=["admin"])

class RegulationCreate(BaseModel):
    scope: str  # "country" or "airline"
    code: str
    item_category: str
    constraints: dict
    severity: str = "info"
    notes: Optional[str] = None

@router.post("/")
def create_regulation(
    data: RegulationCreate,
    db: Session = Depends(get_db)
):
    collector = RegulationCollector(db)
    rule = collector.save_regulation(
        scope=data.scope,
        code=data.code,
        item_category=data.item_category,
        constraints=data.constraints,
        severity=data.severity,
        notes=data.notes
    )
    return {"rule_id": rule.rule_id, "message": "규정 저장 완료"}

@router.get("/")
def get_regulations(
    scope: Optional[str] = None,
    code: Optional[str] = None,
    item_category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    collector = RegulationCollector(db)
    rules = collector.get_regulations(
        scope=scope,
        code=code,
        item_category=item_category
    )
    return {"rules": rules}
```

## 6. 주의사항 및 모범 사례

### 6.1 법적 고려사항
- **robots.txt 확인**: 스크래핑 전 반드시 확인
- **이용약관 확인**: 각 사이트의 이용약관 준수
- **Rate Limiting**: 과도한 요청 방지
- **개인정보**: 수집하지 않기

### 6.2 기술적 고려사항
- **에러 처리**: 네트워크 오류, 파싱 오류 등 처리
- **재시도 로직**: 실패시 재시도 (exponential backoff)
- **캐싱**: Redis를 활용한 캐싱으로 부하 감소
- **로깅**: 모든 작업 로깅

### 6.3 데이터 품질
- **검증**: 수집한 데이터 검증
- **수동 확인**: 중요한 변경사항은 수동 확인
- **버전 관리**: 규정 변경 이력 관리

## 7. 다음 단계

1. **프로토타입 구현**: 한 두 개 항공사로 시작
2. **테스트**: 다양한 케이스 테스트
3. **확장**: 점진적으로 항공사/국가 추가
4. **모니터링**: 수집 성공률, 오류율 모니터링
5. **자동화**: 완전 자동화까지 단계적 진행




