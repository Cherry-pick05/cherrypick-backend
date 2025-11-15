"""
규정 수집 및 저장을 위한 서비스 (새 정규화 스키마)
"""
from datetime import datetime, date
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.models.regulation import (
    RuleSet,
    ItemRule,
    Applicability,
    ConstraintsQuant,
    ConstraintExtra,
)


class RegulationCollector:
    """규정 데이터를 새 정규화 스키마에 저장하는 서비스"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def save_regulation_file(
        self,
        scope: str,  # "international", "country", "airline"
        code: str,   # 규정 코드 (예: "IATA", "KE", "KR", "US_PACKSAFE")
        name: str,   # 규정 이름
        source_url: Optional[str] = None,
        source_etag: Optional[str] = None,
    ) -> RuleSet:
        """
        RuleSet 생성 또는 조회
        
        Returns:
            RuleSet 객체
        """
        # 기존 RuleSet 조회
        rule_set = self.db.query(RuleSet).filter(
            RuleSet.scope == scope,
            RuleSet.code == code
        ).first()
        
        if rule_set:
            # 업데이트
            rule_set.name = name
            if source_url:
                rule_set.source_url = source_url
            if source_etag:
                rule_set.source_etag = source_etag
            rule_set.imported_at = datetime.now()
        else:
            # 신규 생성
            rule_set = RuleSet(
                scope=scope,
                code=code,
                name=name,
                source_url=source_url,
                source_etag=source_etag,
            )
            self.db.add(rule_set)
            self.db.flush()  # ID를 얻기 위해 flush
        
        return rule_set
    
    def save_item_rule(
        self,
        rule_set_id: int,
        item_name: Optional[str],
        item_category: str,
        severity: str,
        notes: Optional[str] = None,
    ) -> ItemRule:
        """
        ItemRule 생성 또는 조회
        
        Returns:
            ItemRule 객체
        """
        # 기존 ItemRule 조회 (같은 rule_set_id, item_category, item_name 조합)
        query = self.db.query(ItemRule).filter(
            ItemRule.rule_set_id == rule_set_id,
            ItemRule.item_category == item_category,
        )
        
        if item_name:
            query = query.filter(ItemRule.item_name == item_name)
        else:
            query = query.filter(ItemRule.item_name.is_(None))
        
        item_rule = query.first()
        
        if item_rule:
            # 업데이트
            item_rule.severity = severity
            item_rule.notes = notes
        else:
            # 신규 생성
            item_rule = ItemRule(
                rule_set_id=rule_set_id,
                item_name=item_name,
                item_category=item_category,
                severity=severity,
                notes=notes,
            )
            self.db.add(item_rule)
            self.db.flush()  # ID를 얻기 위해 flush
        
        return item_rule
    
    def save_applicability(
        self,
        item_rule_id: int,
        route_type: Optional[str] = None,
        region: Optional[str] = None,
        cabin_class: Optional[str] = None,
        fare_class: Optional[str] = None,
        passenger_type: Optional[str] = None,
        effective_from: Optional[date] = None,
        effective_until: Optional[date] = None,
    ) -> Applicability:
        """
        Applicability 생성 또는 조회
        
        Returns:
            Applicability 객체
        """
        # 기존 Applicability 조회
        applicability = self.db.query(Applicability).filter(
            Applicability.item_rule_id == item_rule_id,
            Applicability.route_type == route_type,
            Applicability.region == region,
            Applicability.cabin_class == cabin_class,
            Applicability.fare_class == fare_class,
            Applicability.passenger_type == passenger_type,
            Applicability.effective_from == effective_from,
            Applicability.effective_until == effective_until,
        ).first()
        
        if not applicability:
            # 신규 생성
            applicability = Applicability(
                item_rule_id=item_rule_id,
                route_type=route_type,
                region=region,
                cabin_class=cabin_class,
                fare_class=fare_class,
                passenger_type=passenger_type,
                effective_from=effective_from,
                effective_until=effective_until,
            )
            self.db.add(applicability)
            self.db.flush()  # ID를 얻기 위해 flush
        
        return applicability
    
    def save_constraints(
        self,
        applicability_id: int,
        constraints: Dict[str, Any],
    ) -> ConstraintsQuant:
        """
        ConstraintsQuant 생성 또는 업데이트
        
        constraints에서 다음 필드들을 추출:
        - 수치 필드: max_weight_kg, per_piece_max_weight_kg, max_pieces, max_total_cm,
                     size_length_cm, size_width_cm, size_height_cm,
                     max_container_ml, max_total_bag_l,
                     lithium_ion_max_wh, lithium_metal_g, max_weight_per_person_kg
        - 불린 필드: carry_on_allowed, checked_allowed, on_person_allowed, operator_approval_required
        - 나머지는 ext JSON에 저장
        
        Returns:
            ConstraintsQuant 객체
        """
        # 기존 ConstraintsQuant 조회
        constraint = self.db.query(ConstraintsQuant).filter(
            ConstraintsQuant.applicability_id == applicability_id
        ).first()
        
        # 수치 필드 매핑
        numeric_fields = {
            "max_weight_kg": "max_weight_kg",
            "per_piece_max_weight_kg": "per_piece_max_weight_kg",
            "max_pieces": "max_pieces",
            "max_total_cm": "max_total_cm",
            "size_length_cm": "size_length_cm",
            "size_width_cm": "size_width_cm",
            "size_height_cm": "size_height_cm",
            "max_container_ml": "max_container_ml",
            "max_total_bag_l": "max_total_bag_l",
            "lithium_ion_max_wh": "lithium_ion_max_wh",
            "lithium_metal_g": "lithium_metal_g",
            "max_weight_per_person_kg": "max_weight_per_person_kg",
        }
        
        # 불린 필드 매핑
        boolean_fields = {
            "carry_on_allowed": "carry_on_allowed",
            "checked_allowed": "checked_allowed",
            "on_person_allowed": "on_person_allowed",
            "operator_approval_required": "operator_approval_required",
        }
        
        # size 관련 필드 처리 (max_size_cm 객체에서 추출)
        if "max_size_cm" in constraints and isinstance(constraints["max_size_cm"], dict):
            size_obj = constraints["max_size_cm"]
            if "length" in size_obj:
                constraints["size_length_cm"] = size_obj["length"]
            if "width" in size_obj:
                constraints["size_width_cm"] = size_obj["width"]
            if "height" in size_obj:
                constraints["size_height_cm"] = size_obj["height"]
        
        # ext JSON에 들어갈 필드들 (조건 필드 + 수치/불린 필드 제외)
        ext_data = {}
        condition_fields = {"route_type", "region", "cabin_class", "fare_class", "passenger_type", "effective_from", "effective_until"}
        
        for key, value in constraints.items():
            if key not in numeric_fields and key not in boolean_fields and key not in condition_fields and key != "max_size_cm":
                ext_data[key] = value
        
        # ConstraintsQuant 데이터 준비
        constraint_data = {}
        for json_key, db_key in numeric_fields.items():
            if json_key in constraints:
                val = constraints[json_key]
                if val is not None:
                    constraint_data[db_key] = float(val) if isinstance(val, (int, float, str)) else None
        
        for json_key, db_key in boolean_fields.items():
            if json_key in constraints:
                val = constraints[json_key]
                if val is not None:
                    # None, True, False를 1, 0, 0으로 변환
                    constraint_data[db_key] = 1 if val is True else (0 if val is False else None)
        
        if constraint:
            # 업데이트
            for key, value in constraint_data.items():
                setattr(constraint, key, value)
            constraint.ext = ext_data
        else:
            # 신규 생성
            constraint = ConstraintsQuant(
                applicability_id=applicability_id,
                **constraint_data,
                ext=ext_data,
            )
            self.db.add(constraint)
            self.db.flush()  # ID를 얻기 위해 flush
        
        return constraint
    
    def save_extra(
        self,
        constraints_id: int,
        extra_type: str,  # "additional_item", "allowed_item", "exception"
        label: str,
        details: Dict[str, Any],
    ) -> ConstraintExtra:
        """
        ConstraintExtra 생성 또는 조회
        
        Returns:
            ConstraintExtra 객체
        """
        # 기존 ConstraintExtra 조회
        extra = self.db.query(ConstraintExtra).filter(
            ConstraintExtra.constraints_id == constraints_id,
            ConstraintExtra.extra_type == extra_type,
            ConstraintExtra.label == label,
        ).first()
        
        if extra:
            # 업데이트
            extra.details = details
        else:
            # 신규 생성
            extra = ConstraintExtra(
                constraints_id=constraints_id,
                extra_type=extra_type,
                label=label,
                details=details,
            )
            self.db.add(extra)
            self.db.flush()
        
        return extra
    
    def save_complete_rule(
        self,
        rule_set_id: int,
        item_name: Optional[str],
        item_category: str,
        severity: str,
        notes: Optional[str],
        constraints: Dict[str, Any],
    ) -> tuple[ItemRule, Applicability, ConstraintsQuant]:
        """
        완전한 규정을 저장 (ItemRule + Applicability + ConstraintsQuant)
        
        Returns:
            (ItemRule, Applicability, ConstraintsQuant) 튜플
        """
        # constraints 복사 (원본 수정 방지)
        from copy import deepcopy
        constraints = deepcopy(constraints)
        
        # 1. ItemRule 저장
        item_rule = self.save_item_rule(
            rule_set_id=rule_set_id,
            item_name=item_name,
            item_category=item_category,
            severity=severity,
            notes=notes,
        )
        
        # 2. Applicability 조건 추출
        route_type = constraints.pop("route_type", None)
        region = constraints.pop("region", None)
        cabin_class = constraints.pop("cabin_class", None)
        fare_class = constraints.pop("fare_class", None)
        passenger_type = constraints.pop("passenger_type", None)
        effective_from = constraints.pop("effective_from", None)
        effective_until = constraints.pop("effective_until", None)
        
        # 날짜 문자열을 date 객체로 변환
        if isinstance(effective_from, str):
            effective_from = datetime.strptime(effective_from, "%Y-%m-%d").date()
        if isinstance(effective_until, str):
            effective_until = datetime.strptime(effective_until, "%Y-%m-%d").date()
        
        # 3. Applicability 저장
        applicability = self.save_applicability(
            item_rule_id=item_rule.id,
            route_type=route_type,
            region=region,
            cabin_class=cabin_class,
            fare_class=fare_class,
            passenger_type=passenger_type,
            effective_from=effective_from,
            effective_until=effective_until,
        )
        
        # 4. ConstraintsQuant 저장
        constraint = self.save_constraints(
            applicability_id=applicability.id,
            constraints=constraints,
        )
        
        return (item_rule, applicability, constraint)
