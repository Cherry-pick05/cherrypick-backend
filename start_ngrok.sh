#!/bin/bash
# ngrok 터널링 시작 스크립트

PORT=${1:-8000}

echo "🚀 ngrok 터널링 시작 중... (포트: $PORT)"
echo ""

# 인증 토큰 확인
if ! ngrok config check &>/dev/null; then
    echo "⚠️  ngrok 인증이 필요합니다!"
    echo ""
    echo "다음 단계를 따라주세요:"
    echo ""
    echo "1. ngrok 계정 생성: https://dashboard.ngrok.com/signup"
    echo "2. authtoken 확인: https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "3. 토큰 설정 (실제 토큰으로 교체하세요!):"
    echo "   ngrok config add-authtoken <실제_토큰을_여기에_입력>"
    echo ""
    echo "   ⚠️  예시: ngrok config add-authtoken 2abc123def456ghi789jkl0mn1op2qr3st4uv5wx6yz"
    echo ""
    exit 1
fi

echo "터널링이 시작되면 아래 URL들이 생성됩니다:"
echo "  - Swagger UI: https://YOUR_URL.ngrok-free.app/v1/docs"
echo "  - ReDoc: https://YOUR_URL.ngrok-free.app/v1/redoc"
echo ""
echo "⚠️  ngrok 웹 인터페이스: http://127.0.0.1:4040"
echo "   (여기서 실제 public URL을 확인할 수 있습니다)"
echo ""
echo "종료하려면 Ctrl+C를 누르세요."
echo ""

ngrok http $PORT

