#!/usr/bin/env python3
"""
JSON 규정 파일들을 DB에 로드하는 스크립트
"""
import sys
import logging
from pathlib import Path

from app.db.session import SessionLocal
from app.services.regulation_loader import RegulationLoader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """메인 함수"""
    # 데이터 디렉토리 경로
    data_dir = Path(__file__).parent / "data" / "regulations"
    
    if not data_dir.exists():
        logger.error(f"데이터 디렉토리가 존재하지 않습니다: {data_dir}")
        sys.exit(1)
    
    # DB 세션 생성
    db = SessionLocal()
    
    try:
        loader = RegulationLoader(db)
        
        # 디렉토리 내 모든 JSON 파일 로드
        logger.info(f"규정 파일 로드 시작: {data_dir}")
        results = loader.load_from_directory(data_dir)
        
        # 결과 출력
        logger.info("\n" + "="*60)
        logger.info("로드 결과 요약")
        logger.info("="*60)
        
        total_loaded = 0
        total_errors = 0
        
        for filename, result in results.items():
            loaded = result.get("loaded", 0)
            errors = result.get("errors", 0)
            total_loaded += loaded
            total_errors += errors
            
            status = "✅ 성공" if errors == 0 else "❌ 실패"
            logger.info(
                f"{status} {filename}: "
                f"저장={loaded}, 에러={errors}"
            )
            
            if "error" in result:
                logger.error(f"  에러: {result['error']}")
        
        logger.info("="*60)
        logger.info(f"전체: 저장={total_loaded}, 에러={total_errors}")
        logger.info("="*60)
        
        if total_errors > 0:
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"로드 실패: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()


