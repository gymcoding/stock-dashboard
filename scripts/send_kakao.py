#!/usr/bin/env python3
"""카카오톡 "나에게 보내기" 데일리 리포트 발송.

사용:
    python3 scripts/send_kakao.py              # 실 발송
    python3 scripts/send_kakao.py --dry-run    # 콘솔에 미리보기만

필요 환경:
    KAKAO_REST_API_KEY        — Kakao Developers 콘솔 발급
    KAKAO_CLIENT_SECRET       — 콘솔 시크릿 활성화 시 필수 (없으면 KOE010)
    KAKAO_REFRESH_TOKEN       — setup_kakao.py로 발급
    SITE_URL                  — 카톡 메시지 안 링크 (default: https://techboost.dev)
    GH_PAT / GH_REPO          — refresh_token 회전 시 자동 GitHub Secret 갱신용 (선택, GHA 환경)

로컬 실행 시 .env에서 자동 로드.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

# 프로젝트 루트를 sys.path에 추가 — dashboard 모듈 import용
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
sys.path.insert(0, PROJECT_ROOT)

import dashboard  # noqa: E402

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


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


def get_env(env_dict, key, default=None):
    """env 파일 → 실행 환경 변수 순으로 fallback."""
    return env_dict.get(key) or os.environ.get(key) or default


def refresh_access_token(api_key, refresh_token, client_secret=None):
    """refresh_token으로 새 access_token 발급. 응답 dict 반환.

    응답에 새 refresh_token이 포함되면 (만료 1개월 미만 시 자동 회전):
      → 호출자가 GitHub Secret 갱신 처리해야 함 (M1).
    """
    params = {
        "grant_type": "refresh_token",
        "client_id": api_key,
        "refresh_token": refresh_token,
    }
    if client_secret:
        params["client_secret"] = client_secret
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise RuntimeError(f"Token refresh 실패 HTTP {e.code}: {err_body}")


def rotate_secret_if_needed(token_response, current_refresh_token):
    """카카오가 새 refresh_token을 응답에 포함시킨 경우 GitHub Secret 자동 갱신.

    조건:
        - 응답에 refresh_token이 있고
        - 기존 값과 다르고
        - GH_PAT + GH_REPO 환경변수가 모두 있으면 gh CLI로 갱신

    그 외엔 경고 출력만.
    """
    new_token = token_response.get("refresh_token")
    if not new_token or new_token == current_refresh_token:
        return  # 회전 없음

    print(f"⚠️  카카오가 refresh_token을 회전했습니다 (만료 1개월 미만).", file=sys.stderr)
    print(f"    새 토큰: {new_token[:20]}...", file=sys.stderr)

    gh_pat = os.environ.get("GH_PAT")
    gh_repo = os.environ.get("GH_REPO")
    if gh_pat and gh_repo:
        try:
            env = os.environ.copy()
            env["GH_TOKEN"] = gh_pat
            subprocess.run(
                ["gh", "secret", "set", "KAKAO_REFRESH_TOKEN", "-b", new_token,
                 "-R", gh_repo],
                check=True, env=env, capture_output=True, text=True,
            )
            print(f"✓ GitHub Secret KAKAO_REFRESH_TOKEN 자동 갱신 완료", file=sys.stderr)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"❌ Secret 자동 갱신 실패: {e}", file=sys.stderr)
            print(f"    수동 갱신 명령:", file=sys.stderr)
            print(f"    gh secret set KAKAO_REFRESH_TOKEN -b '{new_token}' -R {gh_repo}",
                  file=sys.stderr)
    else:
        print("    GH_PAT 또는 GH_REPO 환경변수 없음 — 수동 갱신 필요:", file=sys.stderr)
        print(f"    1. 로컬 .env 갱신: KAKAO_REFRESH_TOKEN={new_token}", file=sys.stderr)
        print(f"    2. GitHub Secret 갱신: gh secret set KAKAO_REFRESH_TOKEN -b '{new_token}'",
              file=sys.stderr)


def send_memo(access_token, text, site_url):
    """카카오톡 메모 API에 텍스트 메시지 + 링크 발송."""
    template_object = {
        "object_type": "text",
        "text": text,
        "link": {"web_url": site_url, "mobile_web_url": site_url},
    }
    # 메모 API는 application/x-www-form-urlencoded 요구 (JSON 아님)
    data = urllib.parse.urlencode({
        "template_object": json.dumps(template_object, ensure_ascii=False),
    }).encode("utf-8")
    req = urllib.request.Request(
        MEMO_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "Authorization": f"Bearer {access_token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise RuntimeError(f"메모 API HTTP {e.code}: {err_body}")

    # 응답 200이라도 result_code != 0이면 실패 (검토 에이전트 지적)
    if body.get("result_code") != 0:
        raise RuntimeError(f"메모 API result_code != 0: {body}")
    return body


def main():
    parser = argparse.ArgumentParser(description="카카오톡 데일리 리포트 발송")
    parser.add_argument("--dry-run", action="store_true",
                        help="실 발송 없이 메시지 + payload 미리보기만")
    parser.add_argument("--text-only", action="store_true",
                        help="메시지 텍스트만 출력 (다른 디버그 출력 없음)")
    args = parser.parse_args()

    env = load_env(os.path.join(PROJECT_ROOT, ".env"))
    api_key = get_env(env, "KAKAO_REST_API_KEY")
    client_secret = get_env(env, "KAKAO_CLIENT_SECRET")
    refresh_token = get_env(env, "KAKAO_REFRESH_TOKEN")
    site_url = get_env(env, "SITE_URL", "https://techboost.dev")

    if not (api_key and refresh_token):
        print("❌ KAKAO_REST_API_KEY 또는 KAKAO_REFRESH_TOKEN이 없어요.", file=sys.stderr)
        print("   .env 또는 환경변수에 설정 필요. setup_kakao.py로 발급받으세요.",
              file=sys.stderr)
        sys.exit(1)

    # 1. 데이터 수집 + 메시지 생성
    if not args.text_only:
        print("📡 데이터 수집 중...", file=sys.stderr)
    data = dashboard.collect_data()
    summary = dashboard.format_kakao_summary(data)

    if args.text_only:
        print(summary)
        return

    print()
    print("--- 메시지 미리보기 ---")
    print(summary)
    print("--- 끝 (길이: {} 자) ---".format(len(summary)))
    print()

    if args.dry_run:
        print("🔍 dry-run 모드 — 실제 발송 안 함")
        print(f"   site_url: {site_url}")
        return

    # 2. access_token 발급
    print("🔑 access_token 발급 중...")
    token_response = refresh_access_token(api_key, refresh_token, client_secret)
    access_token = token_response.get("access_token")
    if not access_token:
        print(f"❌ access_token 없음. 응답: {token_response}", file=sys.stderr)
        sys.exit(1)

    # 3. refresh_token 회전 처리 (M1)
    rotate_secret_if_needed(token_response, refresh_token)

    # 4. 메모 발송
    print("📤 카카오톡 메모 발송 중...")
    result = send_memo(access_token, summary, site_url)
    print(f"✅ 발송 완료 (result_code={result.get('result_code')})")


if __name__ == "__main__":
    main()
