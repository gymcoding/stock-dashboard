#!/usr/bin/env python3
"""Kakao "나에게 보내기" 최초 OAuth 셋업.

사용:
    python3 scripts/setup_kakao.py

필요 환경 (Kakao Developers 콘솔):
    1. 내 애플리케이션 > 앱 키 > REST API 키 → .env에 KAKAO_REST_API_KEY=...
    2. 카카오 로그인 > 활성화 ON
    3. 카카오 로그인 > Redirect URI: http://localhost:8765/callback (정확히)
    4. 동의항목 > 카카오톡 메시지 전송 (talk_message) ON, 선택 동의
    5. 플랫폼 > Web 플랫폼 등록: http://localhost:8765

결과:
    콘솔에 refresh_token 출력 → .env와 GitHub Secrets에 저장
"""

import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from threading import Event

REDIRECT_URI_DEFAULT = "http://localhost:8765/callback"
SCOPE = "talk_message"
AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"


def load_env(path):
    if not os.path.exists(path):
        return {}
    env = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'\"")
    return env


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    env_path = os.path.join(project_root, ".env")
    env = load_env(env_path)

    api_key = env.get("KAKAO_REST_API_KEY") or os.environ.get("KAKAO_REST_API_KEY")
    client_secret = (env.get("KAKAO_CLIENT_SECRET")
                     or os.environ.get("KAKAO_CLIENT_SECRET"))
    redirect_uri = (env.get("KAKAO_REDIRECT_URI")
                    or os.environ.get("KAKAO_REDIRECT_URI")
                    or REDIRECT_URI_DEFAULT)

    if not api_key:
        print("❌ KAKAO_REST_API_KEY가 .env에 없어요.", file=sys.stderr)
        print(f"   {env_path}에 다음 줄을 추가하세요:", file=sys.stderr)
        print("   KAKAO_REST_API_KEY=<발급받은_REST_API_키>", file=sys.stderr)
        sys.exit(1)

    print(f"✓ KAKAO_REST_API_KEY ({api_key[:6]}...) 확인")
    if client_secret:
        print(f"✓ KAKAO_CLIENT_SECRET ({client_secret[:6]}...) 확인")
    else:
        print("  KAKAO_CLIENT_SECRET 없음 — 콘솔에서 시크릿 활성화된 경우 KOE010 발생")
    print(f"  Redirect URI: {redirect_uri}")
    print(f"  ⚠️  이 값이 Kakao Developers 콘솔에 등록된 값과 완전 일치해야 합니다 (B4).")
    print()

    # 콜백 수신용 임시 서버
    parsed = urllib.parse.urlparse(redirect_uri)
    if parsed.hostname not in ("localhost", "127.0.0.1"):
        print(f"❌ Redirect URI는 localhost여야 합니다: {redirect_uri}", file=sys.stderr)
        sys.exit(1)
    port = parsed.port or 8765
    callback_path = parsed.path or "/callback"

    received = {"code": None, "error": None}
    done = Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args, **kwargs):
            pass

        def do_GET(self):
            url = urllib.parse.urlparse(self.path)
            if url.path != callback_path:
                self.send_response(404)
                self.end_headers()
                return
            qs = urllib.parse.parse_qs(url.query)
            if "code" in qs:
                received["code"] = qs["code"][0]
                msg = ("<!doctype html><meta charset='utf-8'>"
                       "<h2>✅ 인증 성공!</h2>"
                       "<p>이 창은 닫아도 됩니다. 터미널을 확인하세요.</p>")
            else:
                received["error"] = qs.get("error_description", ["unknown"])[0]
                msg = (f"<!doctype html><meta charset='utf-8'>"
                       f"<h2>❌ 인증 실패</h2><p>{received['error']}</p>")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(msg.encode("utf-8"))
            done.set()

    try:
        server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        print(f"❌ 포트 {port}을 열 수 없어요: {e}", file=sys.stderr)
        print("   다른 프로세스가 포트를 쓰고 있거나, Redirect URI 포트를 변경하세요.", file=sys.stderr)
        sys.exit(1)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    auth_params = {
        "client_id": api_key,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
    }
    auth_url = AUTHORIZE_URL + "?" + urllib.parse.urlencode(auth_params)

    print("브라우저에서 카카오 로그인 페이지를 엽니다...")
    print(f"  (안 열리면 이 URL을 직접 여세요)")
    print(f"  {auth_url}")
    print()
    webbrowser.open(auth_url)

    print("⏳ 로그인 + 동의 대기 중... (Ctrl+C로 취소)")
    try:
        done.wait()
    except KeyboardInterrupt:
        print("\n취소됨")
        server.shutdown()
        sys.exit(1)
    server.shutdown()

    if received["error"]:
        print(f"❌ 인증 실패: {received['error']}", file=sys.stderr)
        sys.exit(1)

    code = received["code"]
    print(f"✓ Authorization code 수신: {code[:8]}...")

    token_params = {
        "grant_type": "authorization_code",
        "client_id": api_key,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    if client_secret:
        token_params["client_secret"] = client_secret
    token_data = urllib.parse.urlencode(token_params).encode()

    req = urllib.request.Request(
        TOKEN_URL,
        data=token_data,
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"❌ Token 교환 실패: HTTP {e.code}", file=sys.stderr)
        print(f"   응답: {err_body}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Token 교환 실패: {e}", file=sys.stderr)
        sys.exit(1)

    refresh_token = body.get("refresh_token")
    if not refresh_token:
        print(f"❌ refresh_token 없음. 응답: {body}", file=sys.stderr)
        sys.exit(1)

    print()
    print("✅ 발급 완료!")
    print()
    print(f"  refresh_token: {refresh_token}")
    print()
    print("--- 다음 단계 ---")
    print("1. .env에 추가:")
    print(f"   KAKAO_REFRESH_TOKEN={refresh_token}")
    print()
    print("2. (나중에) GitHub Secrets 등록:")
    print(f"   gh secret set KAKAO_REFRESH_TOKEN -b '{refresh_token}'")
    print(f"   gh secret set KAKAO_REST_API_KEY -b '{api_key}'")
    print()
    print("3. dry-run 메시지 미리보기:")
    print("   python3 scripts/send_kakao.py --dry-run")


if __name__ == "__main__":
    main()
