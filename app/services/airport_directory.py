from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Dict, Iterable, Iterator, List, Sequence

import requests
import sqlalchemy as sa
from airportsdata import load as load_airportsdata
from redis.exceptions import RedisError
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.core.cache import cached_json, get_redis
from app.core.config import settings
from app.db.models.airport import Airport
from app.db.models.country import Country
from app.db.models.regulation import RuleSet


logger = logging.getLogger(__name__)

COUNTRY_CACHE_KEY = "ref:countries:v1"
AIRPORT_CACHE_KEY = "ref:airports:v1"
AIRPORT_INDEX_CACHE_KEY = "ref:airports:index:v1"
DIRECTORY_VERSION_KEY = "ref:directory:version"
CACHE_TTL_SECONDS = 60 * 60 * 6  # 6 hours


class AirportDirectoryError(RuntimeError):
    """Raised when the airport directory cannot be fetched or persisted."""


@dataclass(slots=True)
class NormalizedCountry:
    code: str
    name_en: str
    name_ko: str
    region_group: str | None = None
    iso3_code: str | None = None


@dataclass(slots=True)
class NormalizedAirport:
    iata_code: str
    icao_code: str | None
    name_en: str
    name_ko: str | None
    city_en: str | None
    city_ko: str | None
    region_group: str | None
    country_code: str


@dataclass(slots=True)
class SyncResult:
    country_count: int
    airport_count: int
    skipped_airports: int


class MolitAirportClient:
    """Thin wrapper around 국토교통부 공항 데이터 API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        dataset_id: str | None = None,
        timeout: float = 10.0,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key or settings.molit_service_key
        self.base_url = (base_url or settings.molit_airport_base_url).rstrip("/")
        self.dataset_id = dataset_id or settings.molit_airport_dataset_id
        self.timeout = timeout
        self.session = session or requests.Session()

        if not self.api_key:
            raise AirportDirectoryError("MOLIT service key is not configured.")
        if not self.dataset_id:
            raise AirportDirectoryError("MOLIT dataset id is not configured.")

    def iter_rows(self, per_page: int = 1000) -> Iterator[dict]:
        page = 1
        total = None
        while True:
            payload = self._fetch_page(page=page, per_page=per_page)
            data = payload.get("data") or []
            logger.debug("Fetched %s rows for page %s", len(data), page)
            if not data:
                break
            yield from data

            total = payload.get("totalCount") or total
            current = payload.get("currentCount") or len(data)
            if total is None:
                if len(data) < per_page:
                    break
            else:
                if page * per_page >= total or current == 0:
                    break
            page += 1

    def _fetch_page(self, page: int, per_page: int) -> dict:
        url = f"{self.base_url}/{self.dataset_id}"
        params = {
            "page": page,
            "perPage": per_page,
            "returnType": "JSON",
            "serviceKey": self.api_key,
        }
        response = self.session.get(url, params=params, timeout=self.timeout)
        if not response.ok:
            raise AirportDirectoryError(
                f"MOLIT API 호출 실패 (status={response.status_code}, body={response.text[:200]})"
            )
        return response.json()


class AirportDirectorySynchronizer:
    """Load MOLIT airport data and persist into MySQL."""

    def __init__(self, db: Session, client: MolitAirportClient | None = None) -> None:
        self.db = db
        self.client = client or MolitAirportClient()

    def run(self) -> SyncResult:
        rows = list(self.client.iter_rows())
        normalized = self._normalize(rows)
        self._replace_tables(normalized["countries"], normalized["airports"])
        invalidate_directory_cache()
        return SyncResult(
            country_count=len(normalized["countries"]),
            airport_count=len(normalized["airports"]),
            skipped_airports=normalized["skipped"],
        )

    def _normalize(self, rows: Sequence[dict]) -> dict:
        countries: Dict[str, NormalizedCountry] = {}
        airports: Dict[str, NormalizedAirport] = {}
        skipped = 0

        for raw in rows:
            iata = (raw.get("공항코드1(IATA)") or "").strip().upper()
            if len(iata) != 3:
                skipped += 1
                continue

            country_code = resolve_country_code(iata, raw.get("영문국가명"))
            if not country_code:
                skipped += 1
                continue

            english_name = (raw.get("영문공항명") or "").strip()
            if not english_name:
                english_name = iata
            hangul_name = _clean(raw.get("한글공항"))
            city_en = _clean(raw.get("영문도시명"))
            region = _clean(raw.get("지역"))
            korean_country = _clean(raw.get("한글국가명"))
            english_country = _clean(raw.get("영문국가명")) or country_code

            if country_code not in countries:
                countries[country_code] = NormalizedCountry(
                    code=country_code,
                    name_en=english_country,
                    name_ko=korean_country or english_country,
                    region_group=region,
                )
            else:
                existing = countries[country_code]
                if not existing.region_group and region:
                    existing.region_group = region
                if not existing.name_ko and korean_country:
                    existing.name_ko = korean_country

            airports[iata] = NormalizedAirport(
                iata_code=iata,
                icao_code=_clean(raw.get("공항코드2(ICAO)")) or None,
                name_en=english_name,
                name_ko=hangul_name or None,
                city_en=city_en or None,
                city_ko=None,
                region_group=region,
                country_code=country_code,
            )

        return {"countries": countries, "airports": airports, "skipped": skipped}

    def _replace_tables(
        self,
        countries: Dict[str, NormalizedCountry],
        airports: Dict[str, NormalizedAirport],
    ) -> None:
        logger.info("국가 %s개, 공항 %s개의 디렉터리를 재적재합니다.", len(countries), len(airports))
        self.db.execute(delete(Airport))
        self.db.execute(delete(Country))
        if countries:
            payload = [asdict(c) for c in countries.values()]
            self.db.execute(insert(Country), payload)
        if airports:
            payload = [asdict(a) for a in airports.values()]
            self.db.execute(insert(Airport), payload)
        self.db.commit()


class CountryDirectoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_active_country_codes(self) -> set[str]:
        """DB에 규정이 있는 서비스 중인 국가 코드 목록을 반환합니다."""
        rows = self.db.scalars(
            select(RuleSet.code).where(RuleSet.scope == "country")
        ).all()
        # code에서 국가 코드 부분만 추출 (예: "US_TSA" -> "US", "KR" -> "KR")
        db_codes = set()
        for code in rows:
            code_upper = code.upper()
            # 언더스코어로 분리하여 첫 번째 부분을 국가 코드로 사용
            country_code = code_upper.split("_")[0]
            db_codes.add(country_code)
        # 설정에 명시된 서비스 중인 국가만 필터링
        supported = {code.upper() for code in settings.supported_countries}
        return db_codes & supported

    def list(self, active_only: bool = True) -> List[dict]:
        def loader() -> List[dict]:
            query = select(Country).order_by(Country.name_en)
            if active_only:
                active_codes = self._get_active_country_codes()
                if active_codes:
                    query = query.where(Country.code.in_(active_codes))
            rows = self.db.scalars(query).all()
            return [
                {
                    "code": row.code,
                    "name_en": row.name_en,
                    "name_ko": row.name_ko,
                    "region_group": row.region_group,
                }
                for row in rows
            ]

        cache_key = f"{COUNTRY_CACHE_KEY}:active" if active_only else COUNTRY_CACHE_KEY
        return cached_json(cache_key, CACHE_TTL_SECONDS, loader)

    def search(self, q: str | None = None, region: str | None = None, active_only: bool = True) -> List[dict]:
        records = self.list(active_only=active_only)
        q_lower = q.lower().strip() if q else None
        region_lower = region.lower().strip() if region else None

        def match(record: dict) -> bool:
            if region_lower and (record.get("region_group") or "").lower() != region_lower:
                return False
            if not q_lower:
                return True
            return (
                q_lower in record["code"].lower()
                or q_lower in (record.get("name_en") or "").lower()
                or q_lower in (record.get("name_ko") or "").lower()
            )

        return [record for record in records if match(record)]


class AirportDirectoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_active_country_codes(self) -> set[str]:
        """DB에 규정이 있고 서비스 중인 국가 코드 목록을 반환합니다."""
        rows = self.db.scalars(
            select(RuleSet.code).where(RuleSet.scope == "country")
        ).all()
        # code에서 국가 코드 부분만 추출 (예: "US_TSA" -> "US", "KR" -> "KR")
        db_codes = set()
        for code in rows:
            code_upper = code.upper()
            # 언더스코어로 분리하여 첫 번째 부분을 국가 코드로 사용
            country_code = code_upper.split("_")[0]
            db_codes.add(country_code)
        # 설정에 명시된 서비스 중인 국가만 필터링
        supported = {code.upper() for code in settings.supported_countries}
        return db_codes & supported

    def list(self, active_only: bool = True) -> List[dict]:
        def loader() -> List[dict]:
            query = select(Airport).order_by(Airport.name_en)
            if active_only:
                active_codes = self._get_active_country_codes()
                if active_codes:
                    query = query.where(Airport.country_code.in_(active_codes))
            rows = self.db.scalars(query).all()
            return [
                {
                    "iata_code": row.iata_code,
                    "icao_code": row.icao_code,
                    "name_en": row.name_en,
                    "name_ko": row.name_ko,
                    "city_en": row.city_en,
                    "city_ko": row.city_ko,
                    "country_code": row.country_code,
                    "region_group": row.region_group,
                }
                for row in rows
            ]

        cache_key = f"{AIRPORT_CACHE_KEY}:active" if active_only else AIRPORT_CACHE_KEY
        return cached_json(cache_key, CACHE_TTL_SECONDS, loader)

    def as_index(self) -> Dict[str, dict]:
        def loader() -> Dict[str, dict]:
            items = self.list()
            return {item["iata_code"]: item for item in items}

        return cached_json(AIRPORT_INDEX_CACHE_KEY, CACHE_TTL_SECONDS, loader)

    def search(
        self,
        q: str | None = None,
        country_code: str | None = None,
        limit: int | None = None,
        active_only: bool = True,
    ) -> List[dict]:
        records = self.list(active_only=active_only)
        q_lower = q.lower().strip() if q else None
        country_lower = country_code.lower().strip() if country_code else None

        def match(record: dict) -> bool:
            if country_lower and record["country_code"].lower() != country_lower:
                return False
            if not q_lower:
                return True
            fields = (
                record["iata_code"],
                record.get("icao_code") or "",
                record.get("name_en") or "",
                record.get("name_ko") or "",
                record.get("city_en") or "",
                record.get("city_ko") or "",
            )
            return any(q_lower in (field or "").lower() for field in fields)

        filtered = [record for record in records if match(record)]
        if limit is not None:
            return filtered[: max(0, limit)]
        return filtered


def resolve_country_code(iata_code: str, english_country_name: str | None) -> str | None:
    info = _airportsdata_index().get(iata_code)
    if info:
        candidate = info.get("iso_country") or info.get("country")
        if candidate:
            return candidate.upper()
    if english_country_name:
        candidate = COUNTRY_NAME_OVERRIDES.get(english_country_name.strip().lower())
        if candidate:
            return candidate
    return None


def invalidate_directory_cache() -> None:
    r = get_redis()
    try:
        r.delete(COUNTRY_CACHE_KEY)
        r.delete(AIRPORT_CACHE_KEY)
        r.delete(AIRPORT_INDEX_CACHE_KEY)
        r.incr(DIRECTORY_VERSION_KEY)
    except RedisError:
        pass


@lru_cache(maxsize=1)
def _airportsdata_index() -> dict:
    return load_airportsdata("IATA")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


COUNTRY_NAME_OVERRIDES = {
    "greenland": "GL",
    "hong kong": "HK",
    "macau": "MO",
    "united states": "US",
    "united kingdom": "GB",
    "russia": "RU",
    "iran": "IR",
    "laos": "LA",
    "vietnam": "VN",
    "south korea": "KR",
    "north korea": "KP",
    "cote d'ivoire": "CI",
}


__all__ = [
    "AirportDirectorySynchronizer",
    "AirportDirectoryService",
    "CountryDirectoryService",
    "MolitAirportClient",
    "SyncResult",
    "resolve_country_code",
    "invalidate_directory_cache",
    "DIRECTORY_VERSION_KEY",
]


