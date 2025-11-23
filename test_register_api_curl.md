# Device Register API curl 테스트 명령어

기본 URL: `http://localhost:8000` (필요시 변경)

## 1. 디바이스 등록 (Register)

### 기본 등록 (필수 필드만)
```bash
curl -X POST "http://localhost:8000/v1/devices/register" \
  -H "Content-Type: application/json" \
  -d '{
    "device_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "app_version": "1.0.0",
    "os": "iOS",
    "model": "iPhone 15 Pro"
  }'
```

### 전체 필드 포함 등록
```bash
curl -X POST "http://localhost:8000/v1/devices/register" \
  -H "Content-Type: application/json" \
  -H "Accept-Language: ko-KR" \
  -d '{
    "device_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "app_version": "1.0.0",
    "os": "iOS",
    "model": "iPhone 15 Pro",
    "locale": "ko-KR",
    "timezone": "Asia/Seoul"
  }'
```

### Android 디바이스 등록
```bash
curl -X POST "http://localhost:8000/v1/devices/register" \
  -H "Content-Type: application/json" \
  -H "Accept-Language: ko-KR" \
  -d '{
    "device_uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "app_version": "1.0.0",
    "os": "Android",
    "model": "Samsung Galaxy S24",
    "locale": "ko-KR",
    "timezone": "Asia/Seoul"
  }'
```

### 영어 로케일 등록
```bash
curl -X POST "http://localhost:8000/v1/devices/register" \
  -H "Content-Type: application/json" \
  -H "Accept-Language: en-US" \
  -d '{
    "device_uuid": "12345678-1234-1234-1234-123456789abc",
    "app_version": "1.0.0",
    "os": "iOS",
    "model": "iPhone 15 Pro",
    "locale": "en-US",
    "timezone": "America/New_York"
  }'
```

## 2. 디바이스 정보 갱신 (Refresh)

**주의**: refresh 엔드포인트는 인증이 필요합니다. `X-Device-Token` 헤더에 register에서 받은 `device_token`을 포함해야 합니다.

### 디바이스 정보 갱신 (전체 필드)
```bash
curl -X POST "http://localhost:8000/v1/devices/refresh" \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: YOUR_DEVICE_TOKEN_HERE" \
  -H "Accept-Language: ko-KR" \
  -d '{
    "app_version": "1.0.1",
    "os": "iOS",
    "model": "iPhone 15 Pro",
    "locale": "ko-KR",
    "timezone": "Asia/Seoul"
  }'
```

### 앱 버전만 갱신
```bash
curl -X POST "http://localhost:8000/v1/devices/refresh" \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: YOUR_DEVICE_TOKEN_HERE" \
  -d '{
    "app_version": "1.0.2"
  }'
```

### 로케일만 갱신
```bash
curl -X POST "http://localhost:8000/v1/devices/refresh" \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: YOUR_DEVICE_TOKEN_HERE" \
  -d '{
    "locale": "en-US",
    "timezone": "America/New_York"
  }'
```

## 응답 예시

### Register/Refresh 성공 응답
```json
{
  "device_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "feature_flags": {
    "safety_mode": true,
    "tips_enabled": true
  },
  "ab_test_bucket": "control",
  "expires_in": 2592000
}
```

## 필드 설명

### Register 요청 필드
- `device_uuid` (필수): 디바이스 고유 식별자 (4-64자)
- `app_version` (필수): 앱 버전 (1-32자)
- `os` (필수): 운영체제 (2-32자, 예: "iOS", "Android")
- `model` (필수): 디바이스 모델명 (2-64자)
- `locale` (선택): 로케일 (2-16자, 예: "ko-KR", "en-US")
- `timezone` (선택): 타임존 (2-64자, 예: "Asia/Seoul", "America/New_York")

### Refresh 요청 필드
- 모든 필드가 선택사항입니다. 변경하고 싶은 필드만 포함하면 됩니다.
- `device_uuid`는 자동으로 인증된 디바이스의 UUID가 사용됩니다.

### 헤더
- `Content-Type: application/json` (필수)
- `Accept-Language` (선택): 언어 설정 (예: "ko-KR", "en-US")
- `X-Device-Token` (Refresh만 필수): register에서 받은 device_token

## 사용 예시

### 1. 디바이스 등록
```bash
# 1단계: 디바이스 등록
RESPONSE=$(curl -s -X POST "http://localhost:8000/v1/devices/register" \
  -H "Content-Type: application/json" \
  -d '{
    "device_uuid": "550e8400-e29b-41d4-a716-446655440000",
    "app_version": "1.0.0",
    "os": "iOS",
    "model": "iPhone 15 Pro",
    "locale": "ko-KR",
    "timezone": "Asia/Seoul"
  }')

# 2단계: device_token 추출 (jq 사용)
DEVICE_TOKEN=$(echo $RESPONSE | jq -r '.device_token')
echo "Device Token: $DEVICE_TOKEN"

# 3단계: 추출한 토큰으로 refresh 테스트
curl -X POST "http://localhost:8000/v1/devices/refresh" \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: $DEVICE_TOKEN" \
  -d '{
    "app_version": "1.0.1"
  }'
```

### 2. JSON 포맷팅 없이 간단히 테스트
```bash
curl -X POST "http://localhost:8000/v1/devices/register" \
  -H "Content-Type: application/json" \
  -d '{"device_uuid":"test-uuid-123","app_version":"1.0.0","os":"iOS","model":"iPhone"}'
```

