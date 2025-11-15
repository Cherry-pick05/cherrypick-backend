"""
JSON 파일에서 규정을 로드하여 DB에 저장하는 서비스 (새 정규화 스키마)
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.regulation_collector import RegulationCollector

logger = logging.getLogger(__name__)


class RegulationLoader:
    """JSON 파일에서 규정을 로드하는 서비스"""
    
    def __init__(self, db: Session):
        self.db = db
        self.collector = RegulationCollector(db)
    
    def load_from_file(self, file_path: str | Path) -> Dict[str, int]:
        """
        JSON 파일에서 규정을 로드하여 DB에 저장
        
        Args:
            file_path: JSON 파일 경로
            
        Returns:
            {"loaded": 저장된 규정 수, "updated": 업데이트된 규정 수, "errors": 에러 수}
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 파싱 실패: {e}")
        
        # 유효성 검사
        self._validate_data(data)
        
        # 규정 저장
        loaded = 0
        updated = 0
        errors = 0
        
        scope = data["scope"]
        code = data["code"]
        name = data.get("name", code)
        source_url = data.get("source_url")
        source_etag = data.get("source_etag")
        
        # 1. RuleSet 생성/업데이트
        try:
            rule_set = self.collector.save_regulation_file(
                scope=scope,
                code=code,
                name=name,
                source_url=source_url,
                source_etag=source_etag,
            )
            self.db.commit()
            logger.info(f"RuleSet 저장 완료: {scope}/{code}")
        except Exception as e:
            logger.error(f"RuleSet 저장 실패: {scope}/{code}, 에러: {e}")
            self.db.rollback()
            return {
                "loaded": 0,
                "updated": 0,
                "errors": 1,
                "scope": scope,
                "code": code,
                "error": str(e),
            }
        
        # 2. 각 규정 저장
        for rule in data["rules"]:
            try:
                # constraints 참조 (save_complete_rule 내부에서 복사됨)
                constraints = rule["constraints"]
                
                # 완전한 규정 저장
                item_rule, applicability, constraint = self.collector.save_complete_rule(
                    rule_set_id=rule_set.id,
                    item_name=rule.get("item_name"),
                    item_category=rule["item_category"],
                    severity=rule["severity"],
                    notes=rule.get("notes"),
                    constraints=constraints,
                )
                
                # constraint_extras 처리 (allowed_items, additional_items 등)
                # 원본 constraints 사용 (extras는 ext에 저장되지 않으므로)
                self._process_extras(constraint.id, rule["constraints"])
                
                loaded += 1
                
            except Exception as e:
                logger.error(
                    f"규정 저장 실패: {rule.get('item_category')}, "
                    f"item_name={rule.get('item_name')}, 에러: {e}",
                    exc_info=True
                )
                errors += 1
                self.db.rollback()
                continue
        
        # 최종 커밋
        try:
            self.db.commit()
            logger.info(
                f"규정 로드 완료: {file_path.name} - "
                f"저장: {loaded}, 에러: {errors}"
            )
        except Exception as e:
            logger.error(f"커밋 실패: {e}")
            self.db.rollback()
            errors += loaded
            loaded = 0
        
        return {
            "loaded": loaded,
            "updated": 0,  # 새 스키마에서는 updated 개념이 다름
            "errors": errors,
            "scope": scope,
            "code": code
        }
    
    def _process_extras(self, constraints_id: int, constraints: Dict) -> None:
        """
        constraint_extras 처리 (allowed_items, additional_items 등)
        """
        # allowed_items 처리
        if "allowed_items" in constraints and isinstance(constraints["allowed_items"], list):
            for item in constraints["allowed_items"]:
                self.collector.save_extra(
                    constraints_id=constraints_id,
                    extra_type="allowed_item",
                    label=str(item),
                    details={"item": item},
                )
        
        # additional_items 처리 (예: personal_item, stroller 등)
        if "additional_items" in constraints and isinstance(constraints["additional_items"], list):
            for item in constraints["additional_items"]:
                if isinstance(item, dict):
                    label = item.get("type", item.get("label", "unknown"))
                    details = item
                else:
                    label = str(item)
                    details = {"type": item}
                
                self.collector.save_extra(
                    constraints_id=constraints_id,
                    extra_type="additional_item",
                    label=label,
                    details=details,
                )
        
        # exceptions 처리
        if "exceptions" in constraints and isinstance(constraints["exceptions"], list):
            for exc in constraints["exceptions"]:
                if isinstance(exc, dict):
                    label = exc.get("type", exc.get("label", "exception"))
                    details = exc
                else:
                    label = str(exc)
                    details = {"description": exc}
                
                self.collector.save_extra(
                    constraints_id=constraints_id,
                    extra_type="exception",
                    label=label,
                    details=details,
                )
    
    def load_from_directory(self, directory: str | Path) -> Dict[str, Dict]:
        """
        디렉토리 내의 모든 JSON 파일을 로드
        
        Args:
            directory: JSON 파일들이 있는 디렉토리 경로
            
        Returns:
            각 파일별 로드 결과
        """
        directory = Path(directory)
        
        if not directory.exists() or not directory.is_dir():
            raise ValueError(f"디렉토리가 존재하지 않습니다: {directory}")
        
        results = {}
        
        # JSON 파일만 찾기
        json_files = list(directory.glob("*.json"))
        
        if not json_files:
            logger.warning(f"JSON 파일을 찾을 수 없습니다: {directory}")
            return results
        
        for json_file in json_files:
            try:
                logger.info(f"로드 시작: {json_file.name}")
                result = self.load_from_file(json_file)
                results[json_file.name] = result
            except Exception as e:
                logger.error(f"파일 로드 실패: {json_file.name}, 에러: {e}", exc_info=True)
                results[json_file.name] = {
                    "error": str(e),
                    "loaded": 0,
                    "updated": 0,
                    "errors": 1
                }
        
        return results
    
    def _validate_data(self, data: Dict) -> None:
        """
        JSON 데이터 유효성 검사
        
        Args:
            data: 검사할 JSON 데이터
            
        Raises:
            ValueError: 유효성 검사 실패시
        """
        # 최상위 필드 검사
        if "scope" not in data:
            raise ValueError("'scope' 필드가 필요합니다")
        
        valid_scopes = ["international", "country", "airline"]
        if data["scope"] not in valid_scopes:
            raise ValueError(
                f"잘못된 scope 값: {data['scope']} "
                f"(예상: {', '.join(valid_scopes)})"
            )
        
        if "code" not in data or not data["code"]:
            raise ValueError("'code' 필드가 필요합니다 (비어있을 수 없음)")
        
        if "rules" not in data:
            raise ValueError("'rules' 필드가 필요합니다")
        
        if not isinstance(data["rules"], list):
            raise ValueError("'rules'는 배열이어야 합니다")
        
        if len(data["rules"]) == 0:
            raise ValueError("'rules' 배열이 비어있습니다 (최소 1개 규정 필요)")
        
        # 각 규정 검사
        valid_severities = ["info", "warn", "block"]
        
        for i, rule in enumerate(data["rules"]):
            if not isinstance(rule, dict):
                raise ValueError(f"rules[{i}]는 객체여야 합니다")
            
            if "item_category" not in rule or not rule["item_category"]:
                raise ValueError(f"rules[{i}].item_category가 필요합니다")
            
            if "constraints" not in rule:
                raise ValueError(f"rules[{i}].constraints가 필요합니다")
            
            if not isinstance(rule["constraints"], dict):
                raise ValueError(f"rules[{i}].constraints는 객체여야 합니다")
            
            if "severity" not in rule:
                raise ValueError(f"rules[{i}].severity가 필요합니다")
            
            if rule["severity"] not in valid_severities:
                raise ValueError(
                    f"rules[{i}].severity는 다음 중 하나여야 합니다: {valid_severities}"
                )
