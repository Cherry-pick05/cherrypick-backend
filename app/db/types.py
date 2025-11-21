from sqlalchemy import BigInteger, Integer

# SQLite는 INTEGER PRIMARY KEY일 때만 AUTOINCREMENT를 지원하므로
# BigInteger 컬럼은 SQLite에서 Integer로 치환해 테스트 환경을 지원한다.
BIGINT = BigInteger().with_variant(Integer, "sqlite")


