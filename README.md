# cherrypick-backend

## API 문서 공유하기

프론트엔드 팀과 API를 공유하는 방법:

### 방법 1: OpenAPI JSON 파일 (권장)

```bash
poetry run python export_openapi.py
```

생성된 `openapi.json` 파일을 프론트엔드 팀에게 공유하세요. 이 파일은:
- Postman, Insomnia 등 API 클라이언트에서 바로 import 가능
- TypeScript/JavaScript 타입 생성 도구에서 사용 가능
- API 문서 자동 생성 도구와 호환

### 방법 2: Swagger UI 직접 공유

서버가 실행 중일 때:

- **Swagger UI**: `http://localhost:8000/docs` (또는 배포된 서버 URL)
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

로컬 환경이라면 [ngrok](https://ngrok.com/) 등을 사용해 임시 public URL을 만들 수 있습니다:

#### ngrok 설정 (최초 1회만)

1. **ngrok 계정 생성**: https://dashboard.ngrok.com/signup
2. **authtoken 확인**: https://dashboard.ngrok.com/get-started/your-authtoken
   - 대시보드에서 긴 문자열로 된 authtoken을 복사하세요
3. **토큰 설정** (실제 토큰으로 교체하세요!):
   ```bash
   ngrok config add-authtoken <여기에_실제_토큰_입력>
   ```
   
   ⚠️ **주의**: `YOUR_AUTHTOKEN`은 예시입니다! 대시보드에서 복사한 실제 토큰을 사용하세요.
   
   예시:
   ```bash
   ngrok config add-authtoken 2abc123def456ghi789jkl0mn1op2qr3st4uv5wx6yz
   ```

#### 터널링 시작

```bash
# 방법 1: 스크립트 사용 (권장)
./start_ngrok.sh

# 방법 2: 직접 실행
ngrok http 8000
```

터널링이 시작되면:
1. `http://127.0.0.1:4040` 으로 접속하여 public URL 확인
2. 생성된 URL 예시: `https://abc123.ngrok-free.app/v1/docs`
3. 이 URL을 프론트엔드 팀에게 공유

### 방법 3: 배포된 환경

스테이징/프로덕션 서버가 있다면 해당 서버의 `/docs` URL을 직접 공유하세요.

## Device Bootstrap API 요약

- 공통 헤더: `X-Device-UUID`, `X-Device-Token`, `Accept-Language`
- 최초 실행 시 플로우:
  1. `POST /v1/devices/register` 로 기기 프로필 업서트 및 토큰 발급
  2. `GET /v1/config` 로 안전모드, 단위계, UI 플래그 조회
  3. 온보딩 중 `POST /v1/consent` 로 필수/선택 동의를 기록
  4. 필요 시 `POST /v1/devices/link` 로 복구 코드를 생성/입력

### 엔드포인트 요약

| Method | Path | 설명 |
| --- | --- | --- |
| POST | `/v1/devices/register` | `{device_uuid, app_version, os, model, locale, timezone}` 업서트 후 `{device_token, feature_flags, ab_test_bucket}` 반환 |
| POST | `/v1/devices/refresh` | 기존 토큰 검증 후 재발급 및 프로필 갱신 |
| GET | `/v1/config` | `safe_mode`, `units`, `ui_flags`, 룰/사전 버전 정보 제공 |
| POST | `/v1/consent` | 필수/선택 동의 플래그 저장 (`terms_required`, `privacy_required`, `marketing_opt_in`, `crash_opt_in`) |
| POST | `/v1/devices/link` | `action=generate` 시 복구코드 발급, `action=redeem` 시 새 기기로 계정 이전 후 토큰 반환 |

### 예시

```http
POST /v1/devices/register
Headers:
  X-Device-UUID: 123e4567-e89b-12d3-a456-426614174000
  Accept-Language: ko-KR
Body:
{
  "device_uuid": "123e4567-e89b-12d3-a456-426614174000",
  "app_version": "1.0.0",
  "os": "iOS",
  "model": "iPhone 16",
  "locale": "ko-KR",
  "timezone": "Asia/Seoul"
}

Response 200:
{
  "device_token": "<opaque>",
  "feature_flags": {"safety_mode": true, "tips_enabled": true},
  "ab_test_bucket": "control",
  "expires_in": 2592000
}

GET /v1/config → 200
{
  "safe_mode": true,
  "supported_locales": ["ko-KR", "en-US"],
  "units": {"weight": "kg", "length": "cm"},
  "ui_flags": {"show_reco_tab": true, "max_payload_kb": 256},
  "rule_manifest_version": "2024-11-01",
  "taxonomy_manifest_version": "2024-11-01"
}
```
