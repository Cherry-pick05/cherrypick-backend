from __future__ import annotations

CABIN_CLASSES_DEFAULT = [
    {
        "code": "Y",
        "name": "Economy",
        "description": "일반석 / Economy Class",
    },
    {
        "code": "W",
        "name": "Premium Economy",
        "description": "프리미엄 이코노미 / Premium Economy Class",
    },
    {
        "code": "J",
        "name": "Business",
        "description": "비즈니스석 / Business Class",
    },
    {
        "code": "F",
        "name": "First",
        "description": "일등석 / First Class",
    },
]

AIRLINE_CABIN_CLASSES = {
    "KE": [
        {"code": "Y", "name": "일반석", "description": "Economy"},
        {"code": "W", "name": "프리미엄석", "description": "Premium Economy"},
        {"code": "J", "name": "프레스티지석", "description": "Prestige / Business"},
        {"code": "F", "name": "일등석", "description": "First"},
    ],
    "TW": [
        {"code": "Y_STD", "name": "일반운임", "description": "스탠다드 요금"},
        {"code": "Y_SMART", "name": "스마트운임", "description": "할인 요금"},
        {"code": "Y_EVENT", "name": "이벤트운임", "description": "프로모션/이벤트 요금"},
        {"code": "J", "name": "비즈니스운임", "description": "Business"},
    ],
}


