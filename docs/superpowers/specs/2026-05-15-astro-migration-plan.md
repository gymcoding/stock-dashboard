# Astro 마이그레이션 구현 계획서

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** stock-dashboard을 Python 단일 파일에서 Astro 5.x + TypeScript 정적 사이트로 마이그레이션. 데이터 소스 다변화(FRED + Yahoo + multpl + CNN), 카카오→Slack, GH Pages 제거 후 Cloudflare Pages + Wrangler 단일 배포로 통일.

**Architecture:** 빌드 타임에 `tsx scripts/fetch-data.ts`가 외부 17개 호출(FRED 6 + Yahoo 8 + multpl 2 + CNN 1)로 `src/data/latest.json` 생성 → `astro build`가 JSON을 정적 인라인하여 `dist/` 출력 → `wrangler pages deploy dist`로 Cloudflare Pages에 직접 업로드. cron/manual 성공 시 Slack Incoming Webhook으로 종합 신호 요약 발송.

**Tech Stack:** Astro 5.x · TypeScript · Node 22.12+ · `@tailwindcss/vite` v4 · `yahoo-finance2` v3.14+ · `cheerio` v1 · `tsx` v4 · `cloudflare/wrangler-action@v3`

**Spec Reference:** `docs/superpowers/specs/2026-05-15-astro-migration-design.md` (commit `a8710ce`)

---

## File Structure Map

이 plan으로 변경되는 모든 파일.

### 신규 생성

| 경로 | 책임 |
|---|---|
| `package.json` | Node 의존성·scripts |
| `tsconfig.json` | `{ "extends": "astro/tsconfigs/base" }` |
| `astro.config.mjs` | Astro 설정 (site URL, Tailwind Vite 플러그인) |
| `src/pages/index.astro` | 메인 페이지 (build_html 마크업 이식) |
| `src/layouts/Base.astro` | head·meta·OpenGraph·Pretendard·AdSense |
| `src/styles/global.css` | `@import "tailwindcss"` + Toss 다크 @theme |
| `src/lib/data.ts` | `Snapshot`·`TickerAnalysis`·`MaCross` 타입 |
| `src/lib/signal.ts` | `signalColor()`·`overallSignal()`·`computeComposite()` |
| `src/lib/gauge.ts` | `needleCoords()` 게이지 SVG 좌표 |
| `src/lib/format.ts` | 숫자·날짜 포맷 유틸 (KST 변환 포함) |
| `scripts/fetch-data.ts` | FRED·Yahoo·multpl·CNN 페치 → `src/data/latest.json` |
| `scripts/send-slack.ts` | Slack Incoming Webhook 발송 |
| `public/robots.txt` | Googlebot 허용 + AI 학습 봇 차단 |
| `src/data/.gitkeep` | gitignored 디렉토리 유지용 |

### 수정

| 경로 | 변경 |
|---|---|
| `.gitignore` | `src/data/latest.json`·`dist/`·`node_modules/` 추가 |
| `.github/workflows/daily.yml` | 전체 교체 (Python → Node + Wrangler) |
| `CLAUDE.md` | Composite 4→7 indicator, Tailwind CDN→빌드, GH Pages 제거 등 stale 정정 |
| `.env` | `FRED_API_KEY`·`SLACK_WEBHOOK_URL` 추가, 카카오 변수 제거 (사용자 수동) |

### 삭제

| 경로 | 비고 |
|---|---|
| `dashboard.py` | 1547줄 Python 단일 파일 |
| `dashboard.html` | Python 생성물 |
| `requirements.txt` | Python 의존성 |
| `scripts/send_kakao.py` | 카카오 알림 (Slack으로 대체) |
| `scripts/setup_kakao.py` | 카카오 OAuth 초기 설정 |
| `_site/` | Astro는 `dist/` 사용 |
| `tablet-768-fullpage.png` | 정체불명 자산 (Task 22에서 검증 후 삭제) |
| `.playwright-mcp/` | 마이그레이션과 무관한 캐시 (Task 22에서 검토) |

---

## Pre-flight: External Setup (Task 0)

이 작업은 코드 변경 전에 짐코딩님이 외부 시스템에서 직접 수행하셔야 합니다. 모든 항목이 완료되어야 Task 19(워크플로 교체) 이후 CI가 정상 동작합니다.

### Task 0: 외부 시스템 사전 준비 (사용자 작업)

**Files:** 없음 — 외부 대시보드·API 작업

- [ ] **Step 1: FRED API 키 발급** (이미 완료, 2026-05-15)
  - https://fred.stlouisfed.org/docs/api/api_key.html
  - "Request or View Your API Key" → 이메일·application 설명 입력
  - 받은 키를 로컬 `.env`의 `FRED_API_KEY=...`에 저장 (사용자 완료)

- [ ] **Step 2: Slack Incoming Webhook URL 발급**
  - https://api.slack.com/apps → Create New App → From scratch
  - App Name: `stock-dashboard`, Workspace 선택
  - Features → **Incoming Webhooks** → 토글 ON
  - "Add New Webhook to Workspace" → 발송할 채널 선택 (개인 DM 가능)
  - 생성된 `https://hooks.slack.com/services/T.../B.../...` URL 복사
  - 로컬 `.env`에 `SLACK_WEBHOOK_URL=<url>` 추가

- [ ] **Step 3: Cloudflare API Token 발급**
  - https://dash.cloudflare.com → 우측 상단 프로필 → **My Profile → API Tokens**
  - "Create Token" → **Custom token** 선택
  - 권한 설정:
    - `Account` → `Cloudflare Pages` → `Edit`
  - "Account Resources" → 본인 계정만 (또는 All accounts)
  - 토큰 생성 후 표시되는 값 복사 (이후 다시 볼 수 없음)

- [ ] **Step 4: Cloudflare Account ID 확보**
  - https://dash.cloudflare.com 메인 페이지 우측 사이드바에 표시된 16자리 hex 문자열 복사
  - (예: `abc123def456...`)

- [ ] **Step 5: Cloudflare Pages 프로젝트명 확인**
  - CF 대시보드 → **Workers & Pages** → 좌측 메뉴에서 techboost.dev에 연결된 프로젝트 클릭
  - URL `https://dash.cloudflare.com/.../pages/view/<프로젝트명>`에서 `<프로젝트명>` 복사

- [ ] **Step 6: Cloudflare Pages 자동 배포 비활성화**
  - 위 프로젝트 → **Settings → Builds & deployments → Branch deployments**
  - **Production branch** 섹션 → **"Disable Automatic Deployments"** 또는 **"Pause"** 토글 ON
  - 목적: Wrangler 업로드와 git push 자동 빌드의 경합 회피

- [ ] **Step 7: GitHub 저장소 Secrets·Variables 등록**
  - 저장소 → **Settings → Secrets and variables → Actions**
  - **Secrets 탭** → "New repository secret" 5개:
    - `FRED_API_KEY` = (Step 1의 키)
    - `SLACK_WEBHOOK_URL` = (Step 2의 URL)
    - `CLOUDFLARE_API_TOKEN` = (Step 3의 토큰)
    - `CLOUDFLARE_ACCOUNT_ID` = (Step 4의 ID)
  - **Variables 탭** → "New repository variable":
    - `CF_PAGES_PROJECT` = (Step 5의 프로젝트명, 평문)

- [ ] **Step 8: 사용자 검증 체크포인트 — Pre-flight 완료 보고**
  - 위 7단계 완료 시 다음 메시지로 보고: "Pre-flight 완료. FRED·Slack·CF 토큰·CF 자동배포 비활성화·GH Secrets 모두 완료."
  - 검증: Task 19 워크플로 교체 후 첫 manual workflow_dispatch가 정상 동작

---

## Phase 1: Astro 스캐폴딩

### Task 1: Astro 프로젝트 초기화

**Files:**
- Create: `package.json`, `tsconfig.json`, `astro.config.mjs`, `astro.config.mjs 외 Astro CLI 생성 파일들`
- Modify: `.gitignore`

이 task는 기존 dashboard.py·dashboard.html·scripts·public·.github·.env·.gitignore 그대로 두고, Astro 골격만 *겹쳐* 추가합니다. 기존 자산은 Task 21에서 일괄 제거.

- [ ] **Step 1: Node 22 LTS 확인**

Run:
```bash
node --version
```
Expected: `v22.12.0` 또는 그 이상.

`v20`이거나 더 낮으면 먼저 nvm으로 업그레이드:
```bash
nvm install 22 && nvm use 22 && nvm alias default 22
```

- [ ] **Step 2: Astro 프로젝트 생성 (현재 디렉토리에)**

Run:
```bash
cd /Users/gymcoding/Company/projects/stock-dashboard
npm create astro@latest -- --template minimal --no-git --no-install --skip-houston --typescript strict .
```

옵션 설명:
- `--template minimal`: 빈 Astro 프로젝트(샘플 페이지 없음)
- `--no-git`: git init 안 함 (이미 git repo)
- `--no-install`: npm install은 다음 step에서 수동으로
- `--skip-houston`: 환영 출력 생략
- `--typescript strict`: TypeScript strict 모드 자동 설정
- 마지막 `.`: 현재 디렉토리에 설치

생성 시 "Directory not empty" 경고가 나오면 "Continue anyway" 선택.

Expected output:
```
✔ Project initialized
- package.json, tsconfig.json, astro.config.mjs, src/pages/index.astro 생성됨
- 기존 dashboard.py·CLAUDE.md·.env 등은 그대로 유지됨
```

- [ ] **Step 3: 기본 의존성 설치**

Run:
```bash
npm install
```

Expected: `node_modules/`, `package-lock.json` 생성. Warning 일부 있을 수 있으나 error는 없어야 함.

- [ ] **Step 4: 추가 의존성 설치**

Run:
```bash
npm install yahoo-finance2 cheerio
npm install -D tsx
```

Expected: 4개 패키지 추가. `package.json` `dependencies`/`devDependencies`에 반영.

- [ ] **Step 5: Tailwind v4 통합 추가**

Run:
```bash
npx astro add tailwind --yes
```

Expected:
- `@tailwindcss/vite`, `tailwindcss` 설치
- `astro.config.mjs`에 Vite 플러그인 자동 추가
- `src/styles/global.css` 자동 생성 (`@import "tailwindcss";` 포함)

- [ ] **Step 6: `package.json` scripts 보강**

Open `package.json` and replace the `scripts` block with:

```json
"scripts": {
  "dev": "astro dev",
  "build": "astro build",
  "preview": "astro preview",
  "fetch:data": "tsx scripts/fetch-data.ts",
  "notify:slack": "tsx scripts/send-slack.ts"
}
```

Also add at top level:
```json
"engines": {
  "node": ">=22.12.0"
}
```

- [ ] **Step 7: `astro.config.mjs` site URL 설정**

`astro.config.mjs`를 다음으로 교체 (Tailwind plugin은 Step 5에서 자동 추가됨, 보존):

```js
// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: 'https://techboost.dev',
  vite: {
    plugins: [tailwindcss()],
  },
});
```

- [ ] **Step 8: `.gitignore`에 Astro·데이터 항목 추가**

`.gitignore` 끝에 다음 추가 (이미 있는 줄은 중복 추가하지 말 것):

```
# Astro
dist/
.astro/

# generated data snapshot
src/data/latest.json

# Node
node_modules/
```

- [ ] **Step 9: 빈 페이지 dev server 동작 확인**

Run:
```bash
npm run dev
```

Expected: `localhost:4321`에서 minimal Astro 스타터 페이지 로드. 브라우저로 직접 열어 확인.

확인 후 Ctrl+C로 중단.

- [ ] **Step 10: 커밋**

```bash
git add package.json package-lock.json tsconfig.json astro.config.mjs src/ public/favicon.svg .gitignore
git commit -m "Astro 스캐폴딩 + Tailwind v4 통합

npm create astro@latest --template minimal로 초기화 후
@tailwindcss/vite·yahoo-finance2·cheerio·tsx 추가. site URL
techboost.dev 설정, fetch:data·notify:slack 커스텀 스크립트
package.json에 추가. dist·node_modules·latest.json gitignore.
기존 dashboard.py 등 Python 자산은 Task 21까지 보존."
```

⚠️ `dashboard.html`이 staged에 들어가지 않도록 — Astro CLI가 src/pages/index.astro를 만들어도 기존 dashboard.html은 건드리지 않습니다. 확인하려면 `git status`로 staged 목록 점검.

---

### Task 2: 디렉토리 구조 + 빈 스텁

**Files:**
- Create: `src/lib/data.ts`, `src/lib/signal.ts`, `src/lib/gauge.ts`, `src/lib/format.ts`
- Create: `src/data/.gitkeep`
- Create: `scripts/.gitkeep`

- [ ] **Step 1: 디렉토리 생성**

Run:
```bash
mkdir -p src/lib src/data
touch src/data/.gitkeep
```

`scripts/`는 이미 존재 (`send_kakao.py`·`setup_kakao.py`가 있음). 새 TS 스크립트는 같은 디렉토리에 공존하다가 Task 21에서 Python 파일만 제거.

- [ ] **Step 2: `src/lib/data.ts` 타입 정의**

Create `src/lib/data.ts`:

```ts
export type MaCross =
  | 'strong_bull'
  | 'bull'
  | 'bear'
  | 'strong_bear'
  | null;

export type Snapshot = {
  generated_at: string;            // ISO 8601 UTC
  fear_greed: { score: number | null; rating: string } | null;
  cape: number | null;
  sp500_pe: number | null;
  buffett: number | null;
  vix: number | null;
  dxy: { value: number; above_ma200: boolean } | null;
  usdkrw: number | null;
  yield_spread: { spread: number; y10: number; y3m: number } | null;
  hy_spread: number | null;
  tickers: TickerAnalysis[];
  sp500_trend: boolean | null;
  sp500_trend_pct: number | null;
  sp500_ma_cross: MaCross;
};

export type TickerAnalysis = {
  ticker: string;
  name: string;
  price_str: string;
  change_pct: number | null;
  rsi: number | null;
  ma200_above: boolean | null;
  ma200_diff_pct: number | null;
  ma_cross: MaCross;
  pos_52w: number | null;
};
```

- [ ] **Step 3: 나머지 lib 빈 스텁**

Create `src/lib/signal.ts`:
```ts
// Implemented in Task 3.
export {};
```

Create `src/lib/gauge.ts`:
```ts
// Implemented in Task 4.
export {};
```

Create `src/lib/format.ts`:
```ts
// Implemented in Task 5.
export {};
```

- [ ] **Step 4: TypeScript 컴파일 가능 확인**

Run:
```bash
npx tsc --noEmit
```

Expected: 에러 없음 (warnings는 무시). 만약 `src/lib/data.ts`에 syntax error면 수정 후 재실행.

- [ ] **Step 5: 커밋**

```bash
git add src/lib/ src/data/.gitkeep
git commit -m "src/lib 디렉토리·타입 정의 + 빈 스텁

Snapshot/TickerAnalysis/MaCross 타입을 dashboard.py 반환 구조와
1:1 일치하도록 정의. signal/gauge/format은 후속 Task에서 구현."
```

---

## Phase 2: 핵심 라이브러리 이식

### Task 3: `src/lib/signal.ts` — 신호 색상·종합 신호

**Files:**
- Modify: `src/lib/signal.ts`

dashboard.py 의 `signal_color()` (line 241-322), `SCORE_MAP`·`overall_signal()` (line 324-334), `overall_signal_from_data()` (line 337-372)을 1:1 이식.

- [ ] **Step 1: `src/lib/signal.ts` 전체 교체**

Replace `src/lib/signal.ts` with:

```ts
import type { Snapshot, MaCross } from './data';

export type SignalKey = 'good' | 'neutral' | 'warn' | 'bad';

export const SCORE_MAP: Record<SignalKey, number> = {
  good: 1,
  neutral: 0,
  warn: -1,
  bad: -2,
};

export type SignalLabel =
  | 'fear_greed' | 'rsi' | 'cape' | 'buffett' | 'vix'
  | 'dxy' | 'yield_spread' | 'ma200' | '52w' | 'usdkrw'
  | 'sp500pe' | 'hy_spread' | 'ma_cross' | 'dxy_trend';

export function signalColor(
  label: SignalLabel,
  value: number | boolean | string | null,
): [SignalKey, string] {
  if (value === null || value === undefined) return ['neutral', '데이터 없음'];

  switch (label) {
    case 'fear_greed': {
      const v = value as number;
      if (v <= 24) return ['good',    '극도의 공포 (역사적 매수 기회)'];
      if (v <= 44) return ['good',    '공포 구간 (매수 기회)'];
      if (v <= 55) return ['neutral', '중립'];
      if (v <= 74) return ['warn',    '탐욕 구간 (주의)'];
      return ['bad', '극도의 탐욕 (고점 경고)'];
    }
    case 'rsi': {
      const v = value as number;
      if (v <= 30) return ['good',    '과매도 — 반등 가능성'];
      if (v <= 45) return ['good',    '저점 근처'];
      if (v <= 60) return ['neutral', '중립'];
      if (v <= 70) return ['warn',    '과열 주의'];
      return ['bad', '과매수 — 조정 위험'];
    }
    case 'cape': {
      const v = value as number;
      if (v <= 20) return ['good',    '역사적 저평가'];
      if (v <= 28) return ['neutral', '보통 수준'];
      if (v <= 38) return ['warn',    '다소 고평가'];
      return ['bad', '역사적 고평가'];
    }
    case 'buffett': {
      const v = value as number;
      if (v <= 80)  return ['good',    '저평가'];
      if (v <= 100) return ['neutral', '적정 수준'];
      if (v <= 150) return ['warn',    '고평가 주의'];
      return ['bad', '매우 고평가'];
    }
    case 'vix': {
      const v = value as number;
      if (v < 15)  return ['warn',    '지나치게 조용함 (과신 주의)'];
      if (v <= 20) return ['neutral', '안정적인 시장'];
      if (v <= 30) return ['good',    '적당한 긴장 (기회 탐색)'];
      if (v <= 40) return ['good',    '공포 구간 (역발투자 기회)'];
      return ['warn', '극단적 공포 (장기 역발투자 기회, 단기 매우 위험)'];
    }
    case 'dxy': {
      const v = value as number;
      if (v < 100)  return ['good',    '달러 약세 (신흥국·상품 유리)'];
      if (v <= 103) return ['neutral', '보통'];
      if (v <= 107) return ['warn',    '달러 강세 (주의)'];
      return ['bad', '달러 매우 강세'];
    }
    case 'yield_spread': {
      const v = value as number;
      if (v > 0.5)   return ['neutral', '정상 (경기 양호)'];
      if (v >= 0)    return ['warn',    '금리차 축소 (주의)'];
      if (v >= -0.5) return ['warn',    '부분 역전 (침체 우려)'];
      return ['bad', '완전 역전 (침체 경고)'];
    }
    case 'ma200': {
      return value
        ? ['good', '200일선 위 (상승추세)']
        : ['bad', '200일선 아래 (하락추세)'];
    }
    case '52w': {
      const v = value as number;
      if (v <= 30) return ['good',    '52주 저점 근처 (저가)'];
      if (v <= 70) return ['neutral', '중간 구간'];
      if (v <= 85) return ['warn',    '고점 근처 (고가)'];
      return ['bad', '52주 고점 부근'];
    }
    case 'usdkrw': {
      const v = value as number;
      if (v <= 1280) return ['good',    '원화 강세 (안정)'];
      if (v <= 1350) return ['neutral', '보통'];
      if (v <= 1420) return ['warn',    '원화 약세 (주의)'];
      return ['bad', '원화 매우 약세'];
    }
    case 'sp500pe': {
      const v = value as number;
      if (v <= 17) return ['good',    '역사 평균 이하'];
      if (v <= 22) return ['neutral', '적정 수준'];
      if (v <= 28) return ['warn',    '다소 고평가'];
      return ['bad', '고평가'];
    }
    case 'hy_spread': {
      const v = value as number;
      if (v < 3)  return ['good',    '신용 위험 낮음 (시장 안정)'];
      if (v <= 5) return ['neutral', '정상 범위'];
      if (v <= 7) return ['warn',    '신용 스트레스 증가'];
      return ['bad', '신용 위기 (디폴트 위험 급등)'];
    }
    case 'ma_cross': {
      const v = value as MaCross;
      if (v === 'strong_bull') return ['good',    '강한 상승추세 (50선·200선 모두 위)'];
      if (v === 'bull')        return ['neutral', '상승추세 (단기 조정 가능)'];
      if (v === 'bear')        return ['warn',    '약세 신호 (전환 진행)'];
      if (v === 'strong_bear') return ['bad',     '강한 하락추세 (50선·200선 모두 아래)'];
      return ['neutral', '데이터 없음'];
    }
    case 'dxy_trend': {
      if (value === true)  return ['warn', '달러 강세 (위험자산 역풍)'];
      if (value === false) return ['good', '달러 약세 (위험자산 우호)'];
      return ['neutral', '데이터 없음'];
    }
  }
  return ['neutral', ''];
}

export function overallSignal(keys: SignalKey[]): {
  key: SignalKey;
  label: string;
  comment: string;
} {
  // 7개 컴포넌트 기준: 점수 범위 -14 ~ +7
  const score = keys.reduce((s, k) => s + (SCORE_MAP[k] ?? 0), 0);
  // 임계값: ≥+4/≥0/≥-5/<-5
  if (score >= 4) return {
    key: 'good',
    label: '매수 유리',
    comment: '전반적으로 긍정적인 신호예요. 장기 투자를 시작하기 좋은 환경이에요.',
  };
  if (score >= 0) return {
    key: 'neutral',
    label: '중립 — 관망 추천',
    comment: '긍정과 부정 신호가 섞여 있어요. 급하게 움직이지 않아도 돼요.',
  };
  if (score >= -5) return {
    key: 'warn',
    label: '주의 — 신중하게',
    comment: '부정적 지표가 늘고 있어요. 분할 매수나 관망을 추천해요.',
  };
  return {
    key: 'bad',
    label: '위험 — 방어적으로',
    comment: '전반적으로 위험 신호가 많아요. 현금 비중을 높이는 게 좋을 수 있어요.',
  };
}

export function computeComposite(data: Snapshot): {
  key: SignalKey;
  label: string;
  comment: string;
  good: number;
  warn: number;
  bad: number;
  neutral: number;
  signals: { name: string; key: SignalKey; text: string }[];
} {
  const fg = data.fear_greed?.score ?? null;
  const [fgKey, fgText] = signalColor('fear_greed', fg);

  const [vxKey, vxText] = signalColor('vix', data.vix);

  const ysVal = data.yield_spread?.spread ?? null;
  const [ysKey, ysText] = signalColor('yield_spread', ysVal);

  const [trKey, trText] = signalColor('ma200', data.sp500_trend);

  const [mcKey, mcText] = signalColor('ma_cross', data.sp500_ma_cross);

  const [hyKey, hyText] = signalColor('hy_spread', data.hy_spread);

  const dxyAbove = data.dxy?.above_ma200 ?? null;
  const [dxKey, dxText] = signalColor('dxy_trend', dxyAbove);

  const keys: SignalKey[] = [fgKey, vxKey, ysKey, trKey, mcKey, hyKey, dxKey];
  const ov = overallSignal(keys);

  return {
    ...ov,
    good: keys.filter(k => k === 'good').length,
    warn: keys.filter(k => k === 'warn').length,
    bad: keys.filter(k => k === 'bad').length,
    neutral: keys.filter(k => k === 'neutral').length,
    signals: [
      { name: '공포·탐욕',     key: fgKey, text: fgText },
      { name: 'VIX',           key: vxKey, text: vxText },
      { name: '10Y-3M',        key: ysKey, text: ysText },
      { name: 'S&P500 MA200',  key: trKey, text: trText },
      { name: 'MA Cross',      key: mcKey, text: mcText },
      { name: 'HY Spread',     key: hyKey, text: hyText },
      { name: 'DXY Trend',     key: dxKey, text: dxText },
    ],
  };
}
```

- [ ] **Step 2: 타입 체크 검증**

Run:
```bash
npx tsc --noEmit
```

Expected: 에러 없음. 만약 import 경로 등에서 에러 나면 수정.

- [ ] **Step 3: smoke test — 알려진 입력에서 dashboard.py와 동일 출력 확인**

임시 검증 스크립트 작성 (`scripts/smoke-signal.ts`):

```ts
import { signalColor, overallSignal, computeComposite } from '../src/lib/signal';

// dashboard.py와 동일 입력에서 동일 출력이 나오는지 확인
const cases: [string, any, string, string][] = [
  ['fear_greed', 20, 'good', '극도의 공포 (역사적 매수 기회)'],
  ['fear_greed', 50, 'neutral', '중립'],
  ['fear_greed', 80, 'bad', '극도의 탐욕 (고점 경고)'],
  ['vix', 12, 'warn', '지나치게 조용함 (과신 주의)'],
  ['vix', 18, 'neutral', '안정적인 시장'],
  ['ma200', true, 'good', '200일선 위 (상승추세)'],
  ['ma200', false, 'bad', '200일선 아래 (하락추세)'],
  ['ma_cross', 'strong_bull', 'good', '강한 상승추세 (50선·200선 모두 위)'],
  ['hy_spread', 2.5, 'good', '신용 위험 낮음 (시장 안정)'],
  ['yield_spread', -0.3, 'warn', '부분 역전 (침체 우려)'],
];

let failed = 0;
for (const [label, val, expectedKey, expectedText] of cases) {
  const [k, t] = signalColor(label as any, val);
  if (k !== expectedKey || t !== expectedText) {
    console.error(`FAIL ${label}(${val}): got [${k}, "${t}"], expected [${expectedKey}, "${expectedText}"]`);
    failed++;
  }
}

// overallSignal 임계값 확인
const ov1 = overallSignal(['good', 'good', 'good', 'good', 'neutral', 'neutral', 'neutral']); // score=4
if (ov1.key !== 'good') { console.error(`FAIL overallSignal score=4: ${ov1.key}`); failed++; }
const ov2 = overallSignal(['bad', 'bad', 'bad', 'warn', 'neutral', 'neutral', 'neutral']); // score=-5
if (ov2.key !== 'warn') { console.error(`FAIL overallSignal score=-5: ${ov2.key}`); failed++; }
const ov3 = overallSignal(['bad', 'bad', 'bad', 'bad', 'warn', 'neutral', 'neutral']); // score=-9
if (ov3.key !== 'bad') { console.error(`FAIL overallSignal score=-9: ${ov3.key}`); failed++; }

if (failed === 0) console.log('signal.ts smoke OK — 모든 케이스 통과');
else { console.error(`signal.ts smoke FAILED: ${failed}건`); process.exit(1); }
```

Run:
```bash
npx tsx scripts/smoke-signal.ts
```

Expected output: `signal.ts smoke OK — 모든 케이스 통과`

만약 실패하면 signal.ts에서 분기 오타·임계값 오류 수정 후 재실행.

- [ ] **Step 4: 임시 smoke 스크립트 제거**

Run:
```bash
rm scripts/smoke-signal.ts
```

- [ ] **Step 5: 커밋**

```bash
git add src/lib/signal.ts
git commit -m "signal.ts — 신호 색상·종합 신호 로직 이식

dashboard.py:241-372 (signal_color, SCORE_MAP, overall_signal,
overall_signal_from_data)를 1:1 TypeScript 이식. 14개 label 분기,
7-indicator 합산, 임계값 ≥+4/≥0/≥-5/<-5. computeComposite()는
Snapshot을 받아 종합 신호 + 7개 개별 신호 + 카운트 반환.
smoke-test 10건 통과 (커밋 전 임시 스크립트로 검증, 후 삭제)."
```

---

### Task 4: `src/lib/gauge.ts` — 게이지 SVG 좌표

**Files:**
- Modify: `src/lib/gauge.ts`

dashboard.py의 `_gauge()` 헬퍼 중 needle 좌표 계산 부분(현 build_html 내부)을 분리하여 이식.

- [ ] **Step 1: `src/lib/gauge.ts` 작성**

Replace `src/lib/gauge.ts` with:

```ts
/**
 * 반원형 게이지의 needle 좌표 계산.
 *
 * 0% = 좌측 (180° from x-axis, 공포)
 * 100% = 우측 (0° from x-axis, 탐욕)
 *
 * 인버트하면(`pct/100 * 180` 사용) needle이 잘못된 방향을 가리킴.
 * CLAUDE.md 의 경고 참조.
 */
export function needleCoords(pct: number): { nx: number; ny: number } {
  const clamped = Math.max(0, Math.min(100, pct));
  const rad = Math.PI * (1 - clamped / 100);
  return {
    nx: 80 + 55 * Math.cos(rad),
    ny: 85 - 55 * Math.sin(rad),
  };
}
```

- [ ] **Step 2: smoke test로 경계 확인**

임시 검증 (`scripts/smoke-gauge.ts`):

```ts
import { needleCoords } from '../src/lib/gauge';

// 0% → 좌측: x = 80 + 55*cos(π) = 80 - 55 = 25, y = 85 - 55*sin(π) = 85 - 0 = 85
// 50% → 정중앙: x = 80 + 55*cos(π/2) = 80, y = 85 - 55*sin(π/2) = 30
// 100% → 우측: x = 80 + 55*cos(0) = 135, y = 85 - 0 = 85
const cases: [number, number, number][] = [
  [0, 25, 85],
  [50, 80, 30],
  [100, 135, 85],
];

let failed = 0;
for (const [pct, ex, ey] of cases) {
  const { nx, ny } = needleCoords(pct);
  if (Math.abs(nx - ex) > 0.01 || Math.abs(ny - ey) > 0.01) {
    console.error(`FAIL ${pct}%: got (${nx}, ${ny}), expected (${ex}, ${ey})`);
    failed++;
  }
}
if (failed === 0) console.log('gauge.ts smoke OK');
else process.exit(1);
```

Run:
```bash
npx tsx scripts/smoke-gauge.ts
```

Expected: `gauge.ts smoke OK`

- [ ] **Step 3: 임시 스크립트 제거 + 커밋**

```bash
rm scripts/smoke-gauge.ts
git add src/lib/gauge.ts
git commit -m "gauge.ts — 반원 게이지 needle 좌표

dashboard.py의 _gauge() 각도 공식을 분리 이식. 0% 좌측 / 100% 우측.
인버트 금지 경고 주석 유지 (CLAUDE.md 참조)."
```

---

### Task 5: `src/lib/format.ts` — 숫자·날짜 포맷

**Files:**
- Modify: `src/lib/format.ts`

- [ ] **Step 1: `src/lib/format.ts` 작성**

Replace `src/lib/format.ts` with:

```ts
/** ISO UTC 문자열을 KST 표시 문자열(예: "2026-05-15 16:37")로 변환 */
export function fmtKST(isoUtc: string): string {
  const d = new Date(isoUtc);
  // KST는 UTC+9
  const kst = new Date(d.getTime() + 9 * 3600_000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${kst.getUTCFullYear()}-${pad(kst.getUTCMonth() + 1)}-${pad(kst.getUTCDate())} ${pad(kst.getUTCHours())}:${pad(kst.getUTCMinutes())}`;
}

/** 소수점 자리 지정 숫자 포맷 ("1,234.56" 형태) */
export function fmtNumber(value: number | null, decimals = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** 퍼센트 포맷 (소수점 자리 지정, 부호 포함 옵션) */
export function fmtPercent(value: number | null, decimals = 1, withSign = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const sign = withSign && value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}
```

- [ ] **Step 2: smoke test**

임시 (`scripts/smoke-format.ts`):
```ts
import { fmtKST, fmtNumber, fmtPercent } from '../src/lib/format';

console.assert(fmtKST('2026-05-15T07:37:00Z') === '2026-05-15 16:37', 'KST 변환');
console.assert(fmtNumber(1234.567, 2) === '1,234.57', 'fmtNumber');
console.assert(fmtNumber(null) === '—', 'fmtNumber null');
console.assert(fmtPercent(2.345, 1, true) === '+2.3%', 'fmtPercent positive');
console.assert(fmtPercent(-1.5, 1, true) === '-1.5%', 'fmtPercent negative');
console.log('format.ts smoke OK');
```

Run:
```bash
npx tsx scripts/smoke-format.ts
```

Expected: `format.ts smoke OK` (assert 실패 시 메시지 출력됨)

- [ ] **Step 3: 임시 스크립트 제거 + 커밋**

```bash
rm scripts/smoke-format.ts
git add src/lib/format.ts
git commit -m "format.ts — KST 시각·숫자·퍼센트 포맷 유틸"
```

---

## Phase 3: 데이터 페치 스크립트

### Task 6: `scripts/fetch-data.ts` — 골격 + FRED·CNN 페치

**Files:**
- Create: `scripts/fetch-data.ts`
- Modify: `.env` (이미 FRED_API_KEY 등록됨)

이 task는 외부 호출 일부만 구현. Yahoo·multpl·ticker 분석은 Task 7-8에서 추가.

- [ ] **Step 1: `scripts/fetch-data.ts` 골격 작성**

Create `scripts/fetch-data.ts`:

```ts
import { writeFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';
import type { Snapshot, TickerAnalysis } from '../src/lib/data';

const FRED_KEY = process.env.FRED_API_KEY;
if (!FRED_KEY) {
  console.error('FRED_API_KEY 환경변수가 비어있습니다. .env 또는 GH Secrets 확인.');
  process.exit(2);
}

// ────────────────────────────────────────────────────────────
// FRED: 최신 관측치 단일 값
// ────────────────────────────────────────────────────────────
async function fredLatest(seriesId: string): Promise<number | null> {
  try {
    const url = `https://api.stlouisfed.org/fred/series/observations?series_id=${seriesId}&api_key=${FRED_KEY}&file_type=json&sort_order=desc&limit=20`;
    const r = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json() as { observations: Array<{ value: string; date: string }> };
    const valid = data.observations.find(o => o.value !== '.' && o.value);
    return valid ? Number(valid.value) : null;
  } catch (e) {
    console.error(`  ⚠️  FRED ${seriesId} 실패:`, e instanceof Error ? e.message : e);
    return null;
  }
}

// ────────────────────────────────────────────────────────────
// CNN Fear & Greed
// ────────────────────────────────────────────────────────────
async function fetchFearGreed(): Promise<Snapshot['fear_greed']> {
  try {
    const r = await fetch(
      'https://production.dataviz.cnn.io/index/fearandgreed/graphdata',
      {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0',
          'Referer': 'https://money.cnn.com/',
          'Origin': 'https://money.cnn.com',
        },
      },
    );
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json() as { fear_and_greed: { score: number; rating: string } };
    return {
      score: Math.round(data.fear_and_greed.score),
      rating: data.fear_and_greed.rating,
    };
  } catch (e) {
    console.error('  ⚠️  Fear & Greed 실패:', e instanceof Error ? e.message : e);
    return { score: null, rating: 'N/A' };
  }
}

// ────────────────────────────────────────────────────────────
// 진입점
// ────────────────────────────────────────────────────────────
async function main() {
  console.log('▶ fetch-data 시작');

  const [
    fearGreed,
    dgs10, dgs3mo, dexkous, will5000, gdp, hySpread,
  ] = await Promise.all([
    fetchFearGreed(),
    fredLatest('DGS10'),
    fredLatest('DGS3MO'),
    fredLatest('DEXKOUS'),
    fredLatest('WILL5000PRFC'),
    fredLatest('GDP'),
    fredLatest('BAMLH0A0HYM2'),
  ]);

  // yield_spread = DGS10 - DGS3MO
  const yieldSpread = (dgs10 !== null && dgs3mo !== null)
    ? { spread: Number((dgs10 - dgs3mo).toFixed(2)), y10: dgs10, y3m: dgs3mo }
    : null;

  // buffett = WILL5000 / GDP(billions) * 100
  // GDP는 billions of dollars, WILL5000은 지수 포인트 — 기존 단위 보존(dashboard.py:478)
  const buffett = (will5000 !== null && gdp !== null)
    ? Number(((will5000 / gdp) * 100).toFixed(1))
    : null;

  // TODO: Yahoo (Task 7), multpl (Task 7), ticker analysis (Task 8)
  const snapshot: Snapshot = {
    generated_at: new Date().toISOString(),
    fear_greed: fearGreed,
    cape: null,
    sp500_pe: null,
    buffett,
    vix: null,
    dxy: null,
    usdkrw: dexkous,
    yield_spread: yieldSpread,
    hy_spread: hySpread,
    tickers: [],
    sp500_trend: null,
    sp500_trend_pct: null,
    sp500_ma_cross: null,
  };

  const out = 'src/data/latest.json';
  await mkdir(dirname(out), { recursive: true });
  await writeFile(out, JSON.stringify(snapshot, null, 2));
  console.log(`✓ ${out} 작성 완료`);
  console.log(`  fear_greed=${fearGreed?.score ?? 'null'} | y10-y3m=${yieldSpread?.spread ?? 'null'} | hy=${hySpread ?? 'null'} | buffett=${buffett ?? 'null'} | usdkrw=${dexkous ?? 'null'}`);
}

main().catch(e => {
  console.error('fatal:', e);
  process.exit(1);
});
```

- [ ] **Step 2: `.env` 로드 환경 검증**

Run (현재 디렉토리에서 .env가 로드되도록):
```bash
set -a; source .env; set +a
echo "FRED key length: ${#FRED_API_KEY}"
```

Expected: `FRED key length: 32` (FRED API 키는 32자 hex)

- [ ] **Step 3: 실행하여 latest.json 확인**

Run:
```bash
npx tsx scripts/fetch-data.ts
```

Expected:
```
▶ fetch-data 시작
✓ src/data/latest.json 작성 완료
  fear_greed=<숫자> | y10-y3m=<숫자> | hy=<숫자> | buffett=<숫자> | usdkrw=<숫자>
```

`fear_greed`, `yield_spread`, `hy_spread`, `usdkrw`가 `null`이 **아닌** 숫자여야 함. 만약 모두 null이면 인터넷·키 문제 — 추적 후 수정.

- [ ] **Step 4: latest.json 내용 검증**

Run:
```bash
cat src/data/latest.json | head -30
```

기대: 위 5개 필드는 값이 채워져 있고, `cape`·`sp500_pe`·`vix`·`dxy`·`tickers`·`sp500_*`는 `null` 또는 빈 배열 (다음 Task에서 채움).

- [ ] **Step 5: 커밋**

```bash
git add scripts/fetch-data.ts
git commit -m "fetch-data.ts 골격 + FRED·CNN 페치

FRED 6 시리즈(DGS10/DGS3MO/DEXKOUS/WILL5000PRFC/GDP/BAMLH0A0HYM2)
와 CNN F&G 구현. yield_spread = DGS10-DGS3MO, buffett = WILL5000/GDP*100
계산. Yahoo·multpl·ticker는 후속 Task에서 추가.
환경변수 FRED_API_KEY 누락 시 exit(2)로 즉시 실패."
```

---

### Task 7: `scripts/fetch-data.ts` — Yahoo Finance + multpl 페치 추가

**Files:**
- Modify: `scripts/fetch-data.ts`

- [ ] **Step 1: import 및 yahoo-finance2 인스턴스 추가**

`scripts/fetch-data.ts` 최상단 import 블록 아래에 추가:

```ts
import YahooFinance from 'yahoo-finance2';
import * as cheerio from 'cheerio';

const yf = new YahooFinance();

const ONE_YEAR_MS = 366 * 24 * 60 * 60 * 1000;
const yfRange = () => {
  const end = new Date();
  const start = new Date(end.getTime() - ONE_YEAR_MS);
  return { period1: start, period2: end, interval: '1d' as const };
};
```

- [ ] **Step 2: Yahoo 차트 헬퍼 추가**

`fredLatest` 위 또는 아래에 추가:

```ts
async function yfCloses(symbol: string): Promise<number[] | null> {
  try {
    const result = await yf.chart(symbol, yfRange());
    if (!result.quotes || result.quotes.length === 0) throw new Error('빈 응답');
    const closes = result.quotes
      .map(q => q.close)
      .filter((c): c is number => typeof c === 'number' && !Number.isNaN(c));
    if (closes.length < 5) throw new Error(`데이터 부족 (${closes.length}일)`);
    return closes;
  } catch (e) {
    console.error(`  ⚠️  Yahoo ${symbol} 실패:`, e instanceof Error ? e.message : e);
    return null;
  }
}

async function fetchVix(): Promise<number | null> {
  const closes = await yfCloses('^VIX');
  return closes ? Number(closes[closes.length - 1].toFixed(2)) : null;
}

async function fetchDxy(): Promise<Snapshot['dxy']> {
  const closes = await yfCloses('DX-Y.NYB');
  if (!closes) return null;
  const value = Number(closes[closes.length - 1].toFixed(2));
  if (closes.length < 200) return { value, above_ma200: false };
  const ma200 = closes.slice(-200).reduce((a, b) => a + b, 0) / 200;
  return { value, above_ma200: value > ma200 };
}
```

- [ ] **Step 3: multpl 페치 헬퍼**

추가:

```ts
async function fetchMultpl(slug: 'shiller-pe' | 's-p-500-pe-ratio'): Promise<number | null> {
  try {
    const r = await fetch(`https://www.multpl.com/${slug}/table/by-month`, {
      headers: { 'User-Agent': 'Mozilla/5.0' },
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const html = await r.text();
    const $ = cheerio.load(html);
    // 첫 번째 테이블의 첫 번째 데이터 행, 두 번째 td를 추출
    const raw = $('table#datatable tr').eq(1).find('td').eq(1).text();
    const cleaned = raw.replace(/\*/g, '').replace(/†/g, '').trim();
    const val = Number(cleaned);
    if (Number.isNaN(val)) throw new Error(`파싱 실패: "${raw}"`);
    const range: [number, number] = slug === 'shiller-pe' ? [5, 100] : [5, 200];
    return (val > range[0] && val < range[1]) ? Number(val.toFixed(1)) : null;
  } catch (e) {
    console.error(`  ⚠️  multpl ${slug} 실패:`, e instanceof Error ? e.message : e);
    return null;
  }
}
```

- [ ] **Step 4: `main()`에 새 페치 추가**

`main()` 내 `Promise.all` 호출 블록을 다음으로 교체:

```ts
const [
  fearGreed,
  dgs10, dgs3mo, dexkous, will5000, gdp, hySpread,
  vix, dxy,
  cape, sp500Pe,
] = await Promise.all([
  fetchFearGreed(),
  fredLatest('DGS10'),
  fredLatest('DGS3MO'),
  fredLatest('DEXKOUS'),
  fredLatest('WILL5000PRFC'),
  fredLatest('GDP'),
  fredLatest('BAMLH0A0HYM2'),
  fetchVix(),
  fetchDxy(),
  fetchMultpl('shiller-pe'),
  fetchMultpl('s-p-500-pe-ratio'),
]);
```

그리고 `snapshot` 객체의 해당 필드들을 업데이트:

```ts
const snapshot: Snapshot = {
  generated_at: new Date().toISOString(),
  fear_greed: fearGreed,
  cape,
  sp500_pe: sp500Pe,
  buffett,
  vix,
  dxy,
  usdkrw: dexkous,
  yield_spread: yieldSpread,
  hy_spread: hySpread,
  tickers: [],
  sp500_trend: null,
  sp500_trend_pct: null,
  sp500_ma_cross: null,
};
```

로그 라인도 보강:
```ts
console.log(`  vix=${vix ?? 'null'} | dxy=${dxy?.value ?? 'null'}(${dxy?.above_ma200 ? '↑MA200' : '↓MA200'}) | cape=${cape ?? 'null'} | sp500pe=${sp500Pe ?? 'null'}`);
```

- [ ] **Step 5: 실행하여 새 필드 확인**

Run:
```bash
npx tsx scripts/fetch-data.ts
cat src/data/latest.json
```

Expected: `vix`·`dxy`·`cape`·`sp500_pe` 모두 숫자(또는 dxy는 객체). null이면 해당 소스 실패.

⚠️ Yahoo 첫 호출에서 crumb/cookie 획득 과정 때문에 5초 정도 지연될 수 있음.

- [ ] **Step 6: 커밋**

```bash
git add scripts/fetch-data.ts
git commit -m "fetch-data: Yahoo VIX·DXY + multpl CAPE·PER 추가

yahoo-finance2 chart() 모듈로 ^VIX·DX-Y.NYB 1년 일봉 수집,
DXY는 200일 MA 비교로 above_ma200 boolean 산출. multpl.com은
cheerio로 datatable 첫 행 두 번째 셀(별표·단검 제거 후) 파싱."
```

---

### Task 8: `scripts/fetch-data.ts` — Ticker 분석 (RSI·MA200·52w·MA cross)

**Files:**
- Modify: `scripts/fetch-data.ts`

`analyze_ticker()` 로직을 dashboard.py:568-630에서 1:1 이식.

- [ ] **Step 1: watchlist + analyzeTicker 추가**

`scripts/fetch-data.ts` 상수 영역에 추가:

```ts
const WATCHLIST: [string, string][] = [
  ['SPY',   'S&P 500 ETF'],
  ['QQQ',   '나스닥 100 ETF'],
  ['^KS11', 'KOSPI'],
  ['^KQ11', 'KOSDAQ'],
  ['TLT',   '미국 장기채 ETF'],
  ['GLD',   '금 ETF'],
];
```

`yfCloses` 정의 아래에 `analyzeTicker` 추가:

```ts
import type { MaCross } from '../src/lib/data';

/**
 * Wilder EMA 14일 RSI. dashboard.py:580-585 이식.
 *
 *   delta = close.diff()
 *   gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
 *   loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
 *   rsi = 100 - 100/(1 + gain/loss)
 */
function rsi14(closes: number[]): number | null {
  if (closes.length < 15) return null;
  const alpha = 1 / 14;
  let gainEma = 0;
  let lossEma = 0;
  for (let i = 1; i < closes.length; i++) {
    const delta = closes[i] - closes[i - 1];
    const gain = delta > 0 ? delta : 0;
    const loss = delta < 0 ? -delta : 0;
    if (i === 1) {
      gainEma = gain;
      lossEma = loss;
    } else {
      gainEma = alpha * gain + (1 - alpha) * gainEma;
      lossEma = alpha * loss + (1 - alpha) * lossEma;
    }
  }
  if (lossEma === 0) return 100;
  const rs = gainEma / lossEma;
  return Number((100 - 100 / (1 + rs)).toFixed(1));
}

function mean(arr: number[]): number {
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

async function analyzeTicker(ticker: string, name: string): Promise<TickerAnalysis> {
  const closes = await yfCloses(ticker);
  if (!closes || closes.length < 5) {
    return {
      ticker, name, price_str: 'N/A',
      change_pct: null, rsi: null,
      ma200_above: null, ma200_diff_pct: null,
      ma_cross: null, pos_52w: null,
    };
  }

  const price = closes[closes.length - 1];
  const prev = closes[closes.length - 2];
  const change_pct = Number((((price - prev) / prev) * 100).toFixed(2));

  const rsi = rsi14(closes);

  let ma200_above: boolean | null = null;
  let ma200_diff_pct: number | null = null;
  let ma200Val: number | null = null;
  if (closes.length >= 200) {
    ma200Val = mean(closes.slice(-200));
    ma200_above = price > ma200Val;
    ma200_diff_pct = Number((((price - ma200Val) / ma200Val) * 100).toFixed(1));
  }

  // MA50 + Golden/Death cross
  let ma_cross: MaCross = null;
  if (closes.length >= 200 && ma200Val !== null) {
    const ma50 = mean(closes.slice(-50));
    const above50 = price > ma50;
    const above200 = price > ma200Val;
    const goldenCross = ma50 > ma200Val;
    if (above50 && above200 && goldenCross) ma_cross = 'strong_bull';
    else if (above200 && goldenCross) ma_cross = 'bull';
    else if (!above50 && !above200 && !goldenCross) ma_cross = 'strong_bear';
    else ma_cross = 'bear';
  }

  // 52주 위치 (0~100%)
  const high = Math.max(...closes);
  const low = Math.min(...closes);
  const pos_52w = high !== low
    ? Number((((price - low) / (high - low)) * 100).toFixed(1))
    : 50;

  const isKr = ticker === '^KS11' || ticker === '^KQ11';
  const price_str = isKr
    ? price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : `$${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return { ticker, name, price_str, change_pct, rsi, ma200_above, ma200_diff_pct, ma_cross, pos_52w };
}
```

- [ ] **Step 2: `main()`에 ticker 분석 추가**

`main()`에 fredLatest·Yahoo 페치 직후 추가:

```ts
const tickers = await Promise.all(
  WATCHLIST.map(([t, n]) => analyzeTicker(t, n)),
);

const spy = tickers.find(t => t.ticker === 'SPY');
const sp500_trend = spy?.ma200_above ?? null;
const sp500_trend_pct = spy?.ma200_diff_pct ?? null;
const sp500_ma_cross = spy?.ma_cross ?? null;
```

snapshot 객체 업데이트:

```ts
const snapshot: Snapshot = {
  generated_at: new Date().toISOString(),
  fear_greed: fearGreed,
  cape, sp500_pe: sp500Pe, buffett, vix, dxy,
  usdkrw: dexkous, yield_spread: yieldSpread, hy_spread: hySpread,
  tickers,
  sp500_trend, sp500_trend_pct, sp500_ma_cross,
};
```

로그에 ticker 결과도 추가:
```ts
for (const t of tickers) {
  console.log(`  ${t.ticker.padEnd(6)} ${t.price_str.padStart(12)} | rsi=${t.rsi ?? 'null'} | MA200 ${t.ma200_above === null ? '?' : t.ma200_above ? '↑' : '↓'} (${t.ma200_diff_pct ?? '?'}%) | cross=${t.ma_cross ?? 'null'} | 52w=${t.pos_52w ?? 'null'}%`);
}
```

- [ ] **Step 3: CI 실패 정책 추가**

`writeFile` 호출 후 다음 블록 추가:

```ts
// 핵심 4개 지표 점검: 2개 이상 null이면 빌드 실패
const core = {
  fear_greed: fearGreed?.score,
  vix,
  yield_spread: yieldSpread?.spread,
  sp500_trend,
};
const nullCount = Object.values(core).filter(v => v === null || v === undefined).length;
if (nullCount >= 2) {
  console.error(`✗ 핵심 지표 ${nullCount}개 누락 — 빌드 중단`);
  console.error('  null 필드:', Object.entries(core).filter(([_, v]) => v === null || v === undefined).map(([k]) => k));
  process.exit(1);
}
```

- [ ] **Step 4: 실행하여 ticker 확인**

Run:
```bash
npx tsx scripts/fetch-data.ts
```

Expected: 6개 ticker 모두 가격·rsi·ma200·cross 출력. `^KS11`·`^KQ11`은 데이터가 적으면 일부 null 가능.

```bash
cat src/data/latest.json | python3 -m json.tool | grep -E "ticker|price_str|rsi" | head -20
```

- [ ] **Step 5: 커밋**

```bash
git add scripts/fetch-data.ts
git commit -m "fetch-data: ticker 분석 + CI 실패 정책

analyze_ticker(dashboard.py:568-630) 이식 — RSI(Wilder EMA 14일),
MA200·MA200_diff, 50/200 cross, 52주 위치, KR/US 가격 포맷.
SPY 결과에서 sp500_trend·sp500_trend_pct·sp500_ma_cross 추출.
핵심 4개 지표(fear_greed/vix/yield_spread/sp500_trend) 중 2개 이상
null이면 process.exit(1)."
```

---

### Task 9: 사용자 검증 체크포인트 — fetch-data 전체 동작 확인

**Files:** 없음 — 검증만

- [ ] **Step 1: 깨끗한 환경에서 풀 실행**

Run:
```bash
rm -f src/data/latest.json
npx tsx scripts/fetch-data.ts > /tmp/fetch.log 2>&1
echo "exit: $?"
```

Expected: `exit: 0`

- [ ] **Step 2: 모든 필드가 채워졌는지 확인**

Run:
```bash
node -e "
const d = require('./src/data/latest.json');
const required = ['fear_greed','cape','sp500_pe','buffett','vix','dxy','usdkrw','yield_spread','hy_spread','sp500_trend','sp500_trend_pct','sp500_ma_cross'];
const missing = required.filter(k => d[k] === null);
console.log('null 필드:', missing.length ? missing : '(없음)');
console.log('tickers 개수:', d.tickers.length);
console.log('SPY ma_cross:', d.sp500_ma_cross);
console.log('generated_at:', d.generated_at);
"
```

Expected: `null 필드: (없음)` 또는 1-2개 미만. tickers 6개. ma_cross는 strong_bull/bull/bear/strong_bear 중 하나.

- [ ] **Step 3: 사용자 검증 — fetch-data 보고**

이 시점에서 다음 메시지로 짐코딩님께 보고:

> "fetch-data 전체 동작 확인. 17개 외부 호출 모두 응답, latest.json 모든 핵심 필드 채워짐. 다음은 렌더링 레이어 작성."

(이슈가 있을 경우: 어느 필드가 null이고 원인이 무엇인지 보고)

---

## Phase 4: 렌더링 레이어

### Task 10: `src/styles/global.css` — Toss 다크 팔레트

**Files:**
- Modify: `src/styles/global.css`

- [ ] **Step 1: global.css 전체 교체**

Replace `src/styles/global.css` with:

```css
@import "tailwindcss";

@theme {
  /* ─── 배경 계조 ─── */
  --color-bg:         #191F28;
  --color-surface:    #20262F;
  --color-surface-hi: #2A323D;
  --color-border:     #333D4B;

  /* ─── 텍스트 ─── */
  --color-text:    #F2F4F6;
  --color-muted:   #8B95A1;
  --color-subtle:  #6B7684;

  /* ─── 신호 색상 ─── */
  --color-good:    #00C896;
  --color-warn:    #FF9500;
  --color-bad:     #F04452;
  --color-neutral: #4E5968;

  /* ─── 브랜드 ─── */
  --color-brand:    #3182F6;
  --color-brand-hi: #4F8BF7;

  /* ─── 타이포 ─── */
  --font-sans: 'Pretendard Variable', Pretendard, system-ui, sans-serif;
}

html, body {
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
}
```

- [ ] **Step 2: Tailwind 빌드 통과 확인**

Run:
```bash
npm run build
```

Expected: 빌드 성공. `dist/`에 빈 페이지 (아직 index.astro가 minimal 상태)가 생성됨.

- [ ] **Step 3: 커밋**

```bash
git add src/styles/global.css
git commit -m "global.css — Toss 다크 팔레트 @theme

배경/텍스트/신호/브랜드 토큰 정의. 기존 코드의 text-danger를
text-bad로 통일하기 위해 --color-danger 별칭은 두지 않음.
색상값도 #f85149→#F04452로 함께 변경 (디자인 §5.4)."
```

---

### Task 11: `src/layouts/Base.astro`

**Files:**
- Create: `src/layouts/Base.astro`

- [ ] **Step 1: Base.astro 작성**

Create `src/layouts/Base.astro`:

```astro
---
import "../styles/global.css";

export interface Props {
  title?: string;
  description?: string;
}

const {
  title = "투자 지표 대시보드 | techboost.dev",
  description = "S&P500·VIX·금리·환율 등 매크로 지표 일일 스냅샷. 매일 07:37 KST 자동 갱신.",
} = Astro.props;

const SITE_URL = 'https://techboost.dev';
const ADSENSE_CLIENT = import.meta.env.PUBLIC_ADSENSE_CLIENT;  // 승인 후 .env에 설정
const buildTime = new Date().toISOString();
---
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <meta name="description" content={description} />
  <link rel="canonical" href={SITE_URL} />

  <!-- OpenGraph (Slack/SNS 미리보기) -->
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={SITE_URL} />
  <meta property="og:locale" content="ko_KR" />

  <!-- 검색 허용 (AdSense 필수), AI 학습은 robots.txt로 차단 -->
  <meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large" />

  <!-- Pretendard 가변 폰트 -->
  <link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin />
  <link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.css"
  />

  {/* AdSense 자동 광고 — PUBLIC_ADSENSE_CLIENT가 설정된 경우에만 출력 */}
  {ADSENSE_CLIENT && (
    <script
      async
      src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${ADSENSE_CLIENT}`}
      crossorigin="anonymous"
    />
  )}

  <meta name="generator" content="Astro" />
  <meta name="build-time" content={buildTime} />
</head>
<body class="bg-bg text-text">
  <slot />
</body>
</html>
```

- [ ] **Step 2: 커밋**

```bash
git add src/layouts/Base.astro
git commit -m "Base.astro 레이아웃 — head 메타·Pretendard·AdSense

robots는 검색·광고 허용 (AdSense 필수), AI 차단은 robots.txt로.
AdSense 스니펫은 PUBLIC_ADSENSE_CLIENT env가 있을 때만 출력 →
승인 전에는 .env에서 비워두면 자동 비활성화."
```

---

### Task 12: `src/pages/index.astro` — 헤더·종합 신호 카드

**Files:**
- Modify: `src/pages/index.astro` (Astro CLI가 minimal 페이지 생성한 상태)

build_html의 마크업을 4 task에 걸쳐 옮긴다: 종합신호(12) → 매크로(13) → ETF(14) → 모달(15).

- [ ] **Step 1: index.astro 전체 교체 (헤더 + 종합 신호)**

Replace `src/pages/index.astro` with:

```astro
---
import Base from '../layouts/Base.astro';
import { computeComposite } from '../src/lib/signal';
import { fmtKST } from '../src/lib/format';
import data from '../data/latest.json';

const composite = computeComposite(data);
const generatedKst = fmtKST(data.generated_at);

const signalBg: Record<string, string> = {
  good:    'bg-good/15 border-good/30',
  neutral: 'bg-neutral/15 border-neutral/30',
  warn:    'bg-warn/15 border-warn/30',
  bad:     'bg-bad/15 border-bad/30',
};
const signalText: Record<string, string> = {
  good: 'text-good', neutral: 'text-muted', warn: 'text-warn', bad: 'text-bad',
};
---
<Base>
  <main class="mx-auto max-w-screen-lg px-4 py-6 sm:py-10">

    <!-- ━━━━━━ 헤더 ━━━━━━ -->
    <header class="mb-8">
      <h1 class="text-2xl sm:text-3xl font-bold tracking-tight">투자 지표 대시보드</h1>
      <p class="text-sm text-muted mt-2">최종 업데이트: {generatedKst} KST</p>
    </header>

    <!-- ━━━━━━ 종합 신호 ━━━━━━ -->
    <section class={`mb-8 border rounded-2xl p-6 ${signalBg[composite.key]}`}>
      <div class="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 class={`text-2xl font-bold ${signalText[composite.key]}`}>📊 {composite.label}</h2>
          <p class="text-text/90 mt-2">{composite.comment}</p>
        </div>
        <div class="flex gap-2 text-xs">
          <span class="bg-good/20 text-good px-2 py-1 rounded-md">good {composite.good}</span>
          <span class="bg-neutral/20 text-muted px-2 py-1 rounded-md">neutral {composite.neutral}</span>
          <span class="bg-warn/20 text-warn px-2 py-1 rounded-md">warn {composite.warn}</span>
          <span class="bg-bad/20 text-bad px-2 py-1 rounded-md">bad {composite.bad}</span>
        </div>
      </div>

      <!-- 7개 개별 지표 행 -->
      <ul class="mt-5 grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
        {composite.signals.map(s => (
          <li class="flex items-center justify-between bg-surface/40 px-3 py-2 rounded-lg">
            <span class="text-muted">{s.name}</span>
            <span class={signalText[s.key]}>{s.text}</span>
          </li>
        ))}
      </ul>
    </section>

    <!-- 매크로 카드 그리드는 Task 13에서 추가 -->
    <!-- ETF 카드 그리드는 Task 14에서 추가 -->
    <!-- 모달은 Task 15에서 추가 -->

  </main>
</Base>
```

- [ ] **Step 2: 빌드 + 페이지 렌더 확인**

Run:
```bash
npm run dev
```

브라우저로 `http://localhost:4321` 열기. 다음을 시각적으로 확인:
- 다크 배경 (#191F28)
- 헤더에 "투자 지표 대시보드" 출력
- 종합 신호 카드가 신호 색상으로 표시 (예: warn이면 주황 배경)
- 7개 개별 지표 행이 표시됨

확인 후 Ctrl+C로 중단.

- [ ] **Step 3: 커밋**

```bash
git add src/pages/index.astro
git commit -m "index.astro — 헤더 + 종합 신호 카드

build_html의 composite 영역을 Astro 마크업으로 이식. 7개 개별
지표 한 줄 텍스트, good/neutral/warn/bad 카운트 chip 표시.
신호 색상은 Tailwind v4 @theme 토큰 통해 동적 클래스 매핑."
```

---

### Task 13: 매크로 카드 그리드 추가

**Files:**
- Modify: `src/pages/index.astro`

- [ ] **Step 1: index.astro frontmatter에 매크로 카드용 import·계산 추가**

`---` 블록 안 `const generatedKst = ...` 아래에 추가:

```ts
import { signalColor } from '../src/lib/signal';
import { fmtNumber, fmtPercent } from '../src/lib/format';

type MacroCard = {
  title: string;
  value: string;        // 표시용 문자열
  signal: 'good' | 'neutral' | 'warn' | 'bad';
  detail: string;       // signal_color의 한국어 설명
};

const macros: MacroCard[] = [];

// Fear & Greed
{
  const v = data.fear_greed?.score ?? null;
  const [k, t] = signalColor('fear_greed', v);
  macros.push({
    title: '공포·탐욕 지수',
    value: v !== null ? `${v} · ${data.fear_greed?.rating ?? ''}` : '—',
    signal: k, detail: t,
  });
}
// VIX
{
  const [k, t] = signalColor('vix', data.vix);
  macros.push({ title: 'VIX', value: fmtNumber(data.vix, 2), signal: k, detail: t });
}
// CAPE
{
  const [k, t] = signalColor('cape', data.cape);
  macros.push({ title: 'CAPE (Shiller P/E)', value: fmtNumber(data.cape, 1), signal: k, detail: t });
}
// S&P500 PER
{
  const [k, t] = signalColor('sp500pe', data.sp500_pe);
  macros.push({ title: 'S&P500 PER', value: fmtNumber(data.sp500_pe, 1), signal: k, detail: t });
}
// Buffett Indicator
{
  const [k, t] = signalColor('buffett', data.buffett);
  macros.push({ title: '버핏 지수', value: fmtPercent(data.buffett, 1), signal: k, detail: t });
}
// Yield Spread
{
  const v = data.yield_spread?.spread ?? null;
  const [k, t] = signalColor('yield_spread', v);
  macros.push({
    title: '10Y-3M 금리차',
    value: v !== null ? `${v >= 0 ? '+' : ''}${v.toFixed(2)}` : '—',
    signal: k, detail: t,
  });
}
// HY Spread
{
  const [k, t] = signalColor('hy_spread', data.hy_spread);
  macros.push({ title: 'HY 회사채 스프레드', value: fmtPercent(data.hy_spread, 2), signal: k, detail: t });
}
// DXY
{
  const v = data.dxy?.value ?? null;
  const [k, t] = signalColor('dxy', v);
  macros.push({ title: '달러 인덱스 (DXY)', value: fmtNumber(v, 2), signal: k, detail: t });
}
// USDKRW
{
  const [k, t] = signalColor('usdkrw', data.usdkrw);
  macros.push({ title: '원달러 환율', value: fmtNumber(data.usdkrw, 2), signal: k, detail: t });
}
```

- [ ] **Step 2: `</section>` 다음 줄에 매크로 그리드 마크업 삽입**

`<!-- 매크로 카드 그리드는 Task 13에서 추가 -->` 주석을 다음으로 교체:

```astro
<!-- ━━━━━━ 매크로 카드 ━━━━━━ -->
<section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
  {macros.map(c => (
    <article class={`border rounded-xl p-4 ${signalBg[c.signal]}`}>
      <h3 class="text-sm text-muted">{c.title}</h3>
      <p class={`text-2xl font-semibold mt-1 ${signalText[c.signal]}`}>{c.value}</p>
      <p class="text-xs text-muted mt-2">{c.detail}</p>
    </article>
  ))}
</section>
```

- [ ] **Step 3: 빌드·시각 확인**

Run:
```bash
npm run dev
```

브라우저: 9개 매크로 카드가 3-column 그리드 (lg 기준)로 표시되어야 함. 값과 한국어 설명이 카드별로 정확히 매칭되는지 확인. Ctrl+C 종료.

- [ ] **Step 4: 커밋**

```bash
git add src/pages/index.astro
git commit -m "index.astro — 매크로 카드 9개 그리드

F&G·VIX·CAPE·S&P500 PER·버핏·10Y-3M·HY·DXY·USDKRW. 각 카드는
signal_color 결과로 배경·텍스트 색상 결정, 한국어 detail 표시."
```

---

### Task 14: ETF 카드 그리드 + 게이지 SVG

**Files:**
- Modify: `src/pages/index.astro`

- [ ] **Step 1: frontmatter에 게이지·52w 계산 추가**

`---` 블록 끝에 추가:

```ts
import { needleCoords } from '../src/lib/gauge';

type EtfCard = {
  ticker: string;
  name: string;
  price_str: string;
  change_pct: number | null;
  rsi: number | null;
  rsiSignal: 'good' | 'neutral' | 'warn' | 'bad';
  rsiText: string;
  pos_52w: number | null;
  needleX: number;
  needleY: number;
  ma200Above: boolean | null;
  maDiffPct: number | null;
};

const etfs: EtfCard[] = data.tickers.map(t => {
  const [rk, rt] = signalColor('rsi', t.rsi);
  const { nx, ny } = needleCoords(t.pos_52w ?? 50);
  return {
    ticker: t.ticker,
    name: t.name,
    price_str: t.price_str,
    change_pct: t.change_pct,
    rsi: t.rsi,
    rsiSignal: rk, rsiText: rt,
    pos_52w: t.pos_52w,
    needleX: nx, needleY: ny,
    ma200Above: t.ma200_above,
    maDiffPct: t.ma200_diff_pct,
  };
});
```

- [ ] **Step 2: ETF 그리드 마크업 추가**

`<!-- ETF 카드 그리드는 Task 14에서 추가 -->` 주석을 다음으로 교체:

```astro
<!-- ━━━━━━ ETF 카드 ━━━━━━ -->
<section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
  {etfs.map(e => (
    <article class="border border-border bg-surface rounded-xl p-4">
      <div class="flex items-baseline justify-between gap-2">
        <h3 class="text-sm text-muted">{e.name}</h3>
        <span class="text-xs text-muted">{e.ticker}</span>
      </div>
      <p class="text-2xl font-semibold mt-1">{e.price_str}</p>
      {e.change_pct !== null && (
        <p class={`text-sm mt-1 ${e.change_pct >= 0 ? 'text-good' : 'text-bad'}`}>
          {e.change_pct >= 0 ? '+' : ''}{e.change_pct.toFixed(2)}% (전일대비)
        </p>
      )}

      {/* 게이지 SVG — 52주 위치 */}
      {e.pos_52w !== null && (
        <div class="mt-3">
          <svg viewBox="0 0 160 100" class="w-full">
            {/* 반원 배경 */}
            <path d="M 25 85 A 55 55 0 0 1 135 85" fill="none" stroke="var(--color-border)" stroke-width="10" />
            {/* needle */}
            <line x1="80" y1="85" x2={e.needleX} y2={e.needleY} stroke="var(--color-brand)" stroke-width="3" stroke-linecap="round" />
            <circle cx="80" cy="85" r="4" fill="var(--color-brand)" />
            <text x="80" y="98" text-anchor="middle" font-size="9" fill="var(--color-muted)">52주 위치 {e.pos_52w}%</text>
          </svg>
        </div>
      )}

      <dl class="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div class="bg-surface-hi rounded-md px-2 py-1.5">
          <dt class="text-muted">RSI</dt>
          <dd class={e.rsi !== null ? signalText[e.rsiSignal] : 'text-muted'}>
            {e.rsi !== null ? `${e.rsi} · ${e.rsiText}` : '—'}
          </dd>
        </div>
        <div class="bg-surface-hi rounded-md px-2 py-1.5">
          <dt class="text-muted">MA200</dt>
          <dd class={e.ma200Above === null ? 'text-muted' : e.ma200Above ? 'text-good' : 'text-bad'}>
            {e.ma200Above === null ? '—' : e.ma200Above ? `↑ ${e.maDiffPct}%` : `↓ ${e.maDiffPct}%`}
          </dd>
        </div>
      </dl>
    </article>
  ))}
</section>
```

- [ ] **Step 3: 시각 확인**

Run `npm run dev` → 브라우저에서:
- ETF 카드 6개가 그리드로 표시
- 각 카드에 가격·전일 변동·52주 위치 게이지(반원·needle)·RSI·MA200 정보 표시
- 게이지 needle이 좌측(0%)/우측(100%)/중앙(50%) 방향이 의도대로

Ctrl+C 종료.

- [ ] **Step 4: 커밋**

```bash
git add src/pages/index.astro
git commit -m "index.astro — ETF 카드 6개 + 52주 게이지 SVG

watchlist 6종(SPY/QQQ/^KS11/^KQ11/TLT/GLD) 카드. 가격, 전일 변동,
RSI(signal_color 색상), MA200 above/below, 52주 위치 반원 게이지.
needleCoords(gauge.ts) 사용 — 0% 좌측/100% 우측 보존."
```

---

### Task 15: 모달 + 인터랙티브 JS

**Files:**
- Modify: `src/pages/index.astro`

`dashboard.html`의 모달 동작(?` 아이콘 클릭 → 지표 설명 출력)을 vanilla JS로 이식. 단 본 마이그레이션은 **UI 그대로 옮기는 게 목표**이므로 모달 콘텐츠 자체는 단순화하여 "임계값 표 + 출처 링크"만 표시. 풍부한 설명(현재 dashboard.py:90-240 `INDICATOR_DICT`)은 UI 개편 PR에서 다시 가져옴.

이 task에서는 우선 **모달 인프라만** 추가하고 콘텐츠는 후속.

- [ ] **Step 1: 모달 DOM 추가**

`</main>` 직전에 추가:

```astro
<dialog id="indicator-modal" class="bg-surface text-text border border-border rounded-2xl p-6 max-w-md w-[92vw] backdrop:bg-black/50">
  <button id="modal-close" class="text-muted text-sm float-right cursor-pointer" aria-label="닫기">×</button>
  <h3 id="modal-title" class="text-lg font-semibold mb-2"></h3>
  <p id="modal-body" class="text-sm text-text/90 leading-relaxed"></p>
  <a id="modal-source" class="block mt-4 text-brand text-sm" target="_blank" rel="noopener noreferrer">출처 ↗</a>
</dialog>

<script is:inline>
  (function () {
    const dlg = document.getElementById('indicator-modal');
    const title = document.getElementById('modal-title');
    const body = document.getElementById('modal-body');
    const source = document.getElementById('modal-source');
    const closeBtn = document.getElementById('modal-close');
    if (!dlg || !title || !body || !source || !closeBtn) return;

    document.querySelectorAll('[data-indicator]').forEach((el) => {
      el.addEventListener('click', () => {
        title.textContent = el.getAttribute('data-title') || '';
        body.textContent = el.getAttribute('data-desc') || '';
        source.href = el.getAttribute('data-source') || '#';
        source.textContent = (el.getAttribute('data-source-label') || '출처') + ' ↗';
        dlg.showModal();
      });
    });

    closeBtn.addEventListener('click', () => dlg.close());
    dlg.addEventListener('click', (e) => {
      if (e.target === dlg) dlg.close();  // 백드롭 클릭으로 닫기
    });
  })();
</script>
```

- [ ] **Step 2: 매크로 카드에 클릭 가능 표시 추가**

Task 13의 매크로 그리드 `<article>` 태그를 다음으로 교체 (이미 매크로 카드가 있는 위치):

```astro
<article
  class={`border rounded-xl p-4 cursor-pointer hover:bg-surface-hi transition ${signalBg[c.signal]}`}
  data-indicator="true"
  data-title={c.title}
  data-desc={`${c.detail} — 현재 값: ${c.value}`}
  data-source="https://example.com"
  data-source-label="기준 출처"
>
  <h3 class="text-sm text-muted flex items-center justify-between">
    {c.title}
    <span class="text-xs text-muted">?</span>
  </h3>
  <p class={`text-2xl font-semibold mt-1 ${signalText[c.signal]}`}>{c.value}</p>
  <p class="text-xs text-muted mt-2">{c.detail}</p>
</article>
```

- [ ] **Step 3: 시각·동작 확인**

`npm run dev` → 브라우저에서:
- 매크로 카드 hover 시 배경 약간 변화 + cursor pointer
- 카드 클릭 시 모달 열림, 제목·설명·출처 링크 표시
- "×" 또는 백드롭 클릭 시 모달 닫힘
- ESC 키로도 닫히는지 확인 (`<dialog>` 기본 동작)

Ctrl+C 종료.

- [ ] **Step 4: 커밋**

```bash
git add src/pages/index.astro
git commit -m "index.astro — <dialog> 모달 + 인터랙티브 JS

vanilla JS로 카드 클릭 시 지표 설명 표시. 본 PR에서는 모달 인프라만,
풍부한 INDICATOR_DICT 콘텐츠는 UI 개편 PR에서 재이식.
ESC·백드롭·X 버튼 모두 닫기 가능."
```

---

### Task 16: `public/robots.txt`

**Files:**
- Create: `public/robots.txt`

- [ ] **Step 1: robots.txt 작성**

Create `public/robots.txt`:

```
# 검색·광고 봇 허용 (AdSense 필수)
User-agent: Googlebot
Allow: /

User-agent: Googlebot-Image
Allow: /

User-agent: Bingbot
Allow: /

# AI 학습 봇 차단
User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: Claude-Web
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: PerplexityBot
Disallow: /

User-agent: Bytespider
Disallow: /

User-agent: anthropic-ai
Disallow: /

Sitemap: https://techboost.dev/sitemap.xml
```

- [ ] **Step 2: 빌드 후 dist에 복사되는지 확인**

Run:
```bash
npm run build
ls dist/robots.txt && cat dist/robots.txt | head -3
```

Expected: 파일 존재, 첫 줄 `# 검색·광고 봇 허용 (AdSense 필수)`.

- [ ] **Step 3: 커밋**

```bash
git add public/robots.txt
git commit -m "robots.txt — AI 학습 봇 8종 차단, 검색·광고 봇 허용

Googlebot·Bingbot 허용 (AdSense 수익화·SEO 필수).
GPTBot/ClaudeBot/Claude-Web/Google-Extended/CCBot/PerplexityBot/
Bytespider/anthropic-ai 차단."
```

---

## Phase 5: Slack 알림 + CI

### Task 17: `scripts/send-slack.ts`

**Files:**
- Create: `scripts/send-slack.ts`

- [ ] **Step 1: send-slack.ts 작성**

Create `scripts/send-slack.ts`:

```ts
import { readFileSync } from 'node:fs';
import { computeComposite, signalColor } from '../src/lib/signal';
import type { Snapshot } from '../src/lib/data';

const WEBHOOK = process.env.SLACK_WEBHOOK_URL;
const SITE_URL = process.env.SITE_URL || 'https://techboost.dev';

if (!WEBHOOK) {
  console.error('SLACK_WEBHOOK_URL 환경변수 비어있음.');
  process.exit(2);
}

const snap = JSON.parse(readFileSync('src/data/latest.json', 'utf-8')) as Snapshot;
const composite = computeComposite(snap);

const COLOR: Record<string, string> = {
  good:    '#00C896',
  neutral: '#8B95A1',
  warn:    '#FF9500',
  bad:     '#F04452',
};

const EMOJI: Record<string, string> = {
  good: '🟢', neutral: '⚪', warn: '🟡', bad: '🔴',
};

// 7개 지표 한 줄 포맷 (format_kakao_summary 기준)
function fmtLine(label: string, value: string | number | null, sigKey: string, sigText: string): string {
  const v = value === null || value === undefined ? '—' : value;
  return `${EMOJI[sigKey]} *${label}* ${v} (${sigText})`;
}

// 7개 지표 한 줄씩 만들기
const fg = snap.fear_greed?.score ?? null;
const [fgK, fgT] = signalColor('fear_greed', fg);
const [vxK, vxT] = signalColor('vix', snap.vix);
const ysVal = snap.yield_spread?.spread ?? null;
const [ysK, ysT] = signalColor('yield_spread', ysVal);
const [trK, trT] = signalColor('ma200', snap.sp500_trend);
const [mcK, mcT] = signalColor('ma_cross', snap.sp500_ma_cross);
const [hyK, hyT] = signalColor('hy_spread', snap.hy_spread);
const dxyAbove = snap.dxy?.above_ma200 ?? null;
const [dxK, dxT] = signalColor('dxy_trend', dxyAbove);

const lines = [
  fmtLine('공포·탐욕', fg !== null ? `${fg} (${snap.fear_greed?.rating})` : null, fgK, fgT),
  fmtLine('VIX', snap.vix !== null ? snap.vix.toFixed(2) : null, vxK, vxT),
  fmtLine('10Y-3M', ysVal !== null ? `${ysVal >= 0 ? '+' : ''}${ysVal.toFixed(2)}` : null, ysK, ysT),
  fmtLine('S&P500 MA200',
    snap.sp500_trend === null ? null :
    `${snap.sp500_trend ? '위' : '아래'} (${snap.sp500_trend_pct !== null ? (snap.sp500_trend_pct >= 0 ? '↑' : '↓') + Math.abs(snap.sp500_trend_pct).toFixed(1) + '%' : ''})`,
    trK, trT,
  ),
  fmtLine('MA Cross', snap.sp500_ma_cross, mcK, mcT),
  fmtLine('HY Spread', snap.hy_spread !== null ? snap.hy_spread.toFixed(2) + '%' : null, hyK, hyT),
  fmtLine('DXY', dxyAbove === null ? null : (dxyAbove ? '200일선 위' : '200일선 아래'), dxK, dxT),
];

// 실패 데이터 감지
const failed: string[] = [];
if (fg === null) failed.push('Fear & Greed');
if (snap.vix === null) failed.push('VIX');
if (ysVal === null) failed.push('Yield Spread');
if (snap.sp500_trend === null) failed.push('SPY MA200');

const body = {
  attachments: [{
    color: COLOR[composite.key],
    blocks: [
      {
        type: 'header',
        text: { type: 'plain_text', text: `📊 ${composite.label}` },
      },
      {
        type: 'section',
        text: { type: 'mrkdwn', text: composite.comment },
      },
      {
        type: 'section',
        text: { type: 'mrkdwn', text: lines.join('\n') },
      },
      {
        type: 'context',
        elements: [{
          type: 'mrkdwn',
          text: failed.length
            ? `⚠️ 일부 데이터 누락: ${failed.join(', ')}`
            : '✅ 모든 핵심 데이터 정상',
        }],
      },
      {
        type: 'actions',
        elements: [{
          type: 'button',
          text: { type: 'plain_text', text: '대시보드 열기' },
          url: SITE_URL,
        }],
      },
    ],
  }],
};

const r = await fetch(WEBHOOK, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
});

if (!r.ok) {
  console.error(`Slack 발송 실패: HTTP ${r.status} ${await r.text()}`);
  process.exit(1);
}
console.log('✓ Slack 발송 완료');
```

- [ ] **Step 2: 로컬에서 테스트 발송**

`.env`에 `SLACK_WEBHOOK_URL`이 등록되어 있다고 가정 (Task 0 Step 2 완료 상태).

Run:
```bash
set -a; source .env; set +a
npx tsx scripts/send-slack.ts
```

Expected: `✓ Slack 발송 완료`. 짐코딩님의 Slack 채널에 메시지가 표시됨:
- 컬러 사이드바 (종합 신호 색상)
- 헤더: 📊 종합 신호 라벨
- 7개 지표 한 줄씩
- 데이터 정상/실패 여부
- "대시보드 열기" 버튼

만약 실패하면 webhook URL 재확인, JSON payload 디버깅.

- [ ] **Step 3: 사용자 검증 체크포인트**

> "Slack 테스트 메시지가 정상 표시되는지 확인해주세요. 형식·색상·버튼이 의도대로 보이면 OK."

- [ ] **Step 4: 커밋**

```bash
git add scripts/send-slack.ts
git commit -m "send-slack.ts — Block Kit 종합 신호 알림

종합 신호 색상으로 사이드바 컬러링, 7개 지표 한 줄씩(format_kakao_summary
포맷 기반), 데이터 실패 컨텍스트, '대시보드 열기' 버튼. webhook URL은
SLACK_WEBHOOK_URL env에서. 실패 시 exit(1)."
```

---

### Task 18: `.github/workflows/daily.yml` 전체 교체

**Files:**
- Modify: `.github/workflows/daily.yml`

- [ ] **Step 1: 기존 워크플로 백업 (안전)**

Run:
```bash
cp .github/workflows/daily.yml .github/workflows/daily.yml.bak
```

(Task 21에서 .bak 파일도 삭제)

- [ ] **Step 2: daily.yml 전체 교체**

Replace `.github/workflows/daily.yml` with:

```yaml
name: daily-report

on:
  schedule:
    - cron: '37 22 * * *'   # 07:37 KST
  workflow_dispatch: {}
  push:
    branches: [main]
    paths:
      - 'src/**'
      - 'scripts/**'
      - 'astro.config.mjs'
      - 'package.json'
      - 'package-lock.json'
      - 'tsconfig.json'
      - 'public/**'
      - '.github/workflows/daily.yml'

permissions:
  contents: read

concurrency:
  group: deploy-cf-pages
  cancel-in-progress: false

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'

      - run: npm ci

      - name: Fetch external data → src/data/latest.json
        env:
          FRED_API_KEY: ${{ secrets.FRED_API_KEY }}
        run: npx tsx scripts/fetch-data.ts

      - name: Astro build → dist/
        run: npm run build

      - name: Deploy to Cloudflare Pages
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: pages deploy dist --project-name=${{ vars.CF_PAGES_PROJECT }} --branch=main

      - name: Slack notify
        if: github.event_name != 'push' && success()
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
          SITE_URL: https://techboost.dev
        run: npx tsx scripts/send-slack.ts
```

- [ ] **Step 3: yaml 문법 검증 (로컬)**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/daily.yml'))" && echo "yaml OK"
```

Expected: `yaml OK`

- [ ] **Step 4: 커밋**

```bash
git add .github/workflows/daily.yml .github/workflows/daily.yml.bak
git commit -m "workflows/daily.yml 전체 교체 — Node 22 + Wrangler

기존 Python 빌드·GH Pages 업로드·CF Deploy Hook·Kakao 발송 삭제.
새 흐름: setup-node@v4 22 → npm ci → tsx fetch-data → astro build →
cloudflare/wrangler-action@v3 → Slack(push 제외, success only).
백업: daily.yml.bak (Task 21에서 제거)."
```

---

### Task 19: 사용자 검증 체크포인트 — 첫 자동 배포

**Files:** 없음 — CI·CF 검증

이 task는 코드 변경이 없습니다. 모든 PR을 main에 push한 뒤 자동 배포가 끝까지 통과하는지 확인하는 단계입니다.

- [ ] **Step 1: main에 push**

Run:
```bash
git push origin main
```

이 push는 워크플로의 `paths` 필터(src/**·scripts/** 포함)에 매칭되어 워크플로를 트리거합니다.

- [ ] **Step 2: GH Actions 로그 모니터링**

브라우저: 저장소 → Actions 탭 → "daily-report" 워크플로의 가장 최근 실행 클릭.

각 step 통과 확인:
1. Checkout ✓
2. Setup Node ✓
3. npm ci ✓ (60-90초)
4. Fetch external data ✓ — 로그에서 `vix=`, `sp500_trend=` 등 모든 필드 값 확인
5. Astro build ✓
6. Deploy to Cloudflare Pages ✓ — Wrangler가 "Success" 로그 출력
7. Slack notify — push 트리거라 SKIPPED (정상)

총 소요: 약 2-3분.

- [ ] **Step 3: techboost.dev 라이브 확인**

브라우저: https://techboost.dev 열어서:
- Astro로 빌드된 새 페이지가 표시되는지 (다크 배경, Toss 톤)
- 종합 신호 카드·매크로 9개·ETF 6개 모두 데이터 채워졌는지
- 게이지 SVG 화살표가 의도대로 향하는지
- 카드 클릭 시 모달 열림

CF Pages 캐시 갱신 지연이 있을 수 있으니 30-60초 후 hard refresh (Ctrl+Shift+R).

- [ ] **Step 4: 수동 트리거로 Slack 발송 확인**

브라우저: Actions 탭 → "daily-report" → "Run workflow" 버튼 → main 선택 → Run.

워크플로 완료 후 Slack 채널에 알림 도착하는지 확인. 종합 신호 색상·7개 지표·"대시보드 열기" 버튼 모두 정상.

- [ ] **Step 5: 사용자 검증 보고**

> "첫 자동 배포 완료. techboost.dev에 새 Astro 페이지 라이브, 수동 트리거로 Slack 발송 정상 확인. 다음은 Python 자산 정리."

만약 어느 단계에서든 실패하면:
- Build/fetch 실패: 로그의 에러 메시지 보고 → 코드 수정 → 다시 push
- CF 배포 실패: API 토큰·account ID·project name 재확인
- Slack 발송 실패: webhook URL 재확인

---

## Phase 6: 정리

### Task 20: Python 자산 + 백업 제거

**Files:**
- Delete: 8개 파일·디렉토리

- [ ] **Step 1: 삭제 대상 확인**

Run:
```bash
ls -la dashboard.py dashboard.html requirements.txt scripts/send_kakao.py scripts/setup_kakao.py _site/ tablet-768-fullpage.png .github/workflows/daily.yml.bak 2>&1
```

각 파일·디렉토리 존재 확인. `.playwright-mcp/`는 Astro 빌드와 무관하지만 git 추적 대상인지 확인:
```bash
git ls-files .playwright-mcp/ | head -3
```

만약 추적 안 되고 단순 캐시면 .gitignore에 추가만 하고 삭제하지 않음.

- [ ] **Step 2: 핵심 Python·생성물 삭제**

Run:
```bash
rm -v dashboard.py dashboard.html requirements.txt
rm -v scripts/send_kakao.py scripts/setup_kakao.py
rm -rfv _site/
rm -v .github/workflows/daily.yml.bak
```

- [ ] **Step 3: 정체불명 자산 검토**

`tablet-768-fullpage.png` 확인:
```bash
file tablet-768-fullpage.png
```

스크린샷으로 보임 → 마이그레이션과 무관한 일회성 자산 → 삭제:
```bash
rm tablet-768-fullpage.png
```

- [ ] **Step 4: .env에서 카카오 변수 제거 (사용자 작업)**

`.env` 파일 직접 편집:
- `KAKAO_REST_API_KEY=...` 줄 삭제
- `KAKAO_REDIRECT_URI=...` 줄 삭제
- `KAKAO_CLIENT_SECRET=...` 줄 삭제
- `KAKAO_REFRESH_TOKEN=...` 줄 삭제

(GH Secrets의 카카오 4개도 본인이 Settings → Secrets에서 직접 Delete)

- [ ] **Step 5: 빌드 통과 재확인**

Run:
```bash
npm run build
```

Expected: 빌드 성공. `dist/index.html`이 정상 생성.

- [ ] **Step 6: 커밋**

```bash
git add -A
git commit -m "Python 자산·백업·정체불명 png 일괄 제거

삭제: dashboard.py(1547), dashboard.html, requirements.txt,
scripts/send_kakao.py, scripts/setup_kakao.py, _site/,
tablet-768-fullpage.png, daily.yml.bak. .env의 KAKAO_* 4개와
GH Secrets의 카카오 secrets도 사용자가 별도 정리."
```

---

### Task 21: `CLAUDE.md` 갱신 — stale 사실 정정

**Files:**
- Modify: `CLAUDE.md`

dashboard.py 기준으로 작성된 CLAUDE.md의 모든 stale 사실을 Astro·TypeScript 기준으로 정정.

- [ ] **Step 1: 현재 CLAUDE.md 통째 백업**

Run:
```bash
cp CLAUDE.md CLAUDE.md.before-migration
```

(나중에 비교용. Task 21 끝에서 삭제.)

- [ ] **Step 2: CLAUDE.md 전체 교체**

Replace `CLAUDE.md` (현재 디렉토리, 즉 `stock-dashboard/CLAUDE.md`) with:

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Dashboard

```bash
# 로컬 개발 서버 (npm run dev = astro dev, http://localhost:4321)
npm run dev

# 프로덕션 빌드 (CI와 동일 흐름)
npm run fetch:data   # 외부 17개 호출 → src/data/latest.json
npm run build        # → dist/

# Slack 알림 발송 (로컬 테스트)
SLACK_WEBHOOK_URL=... npm run notify:slack
```

`npm run dev`는 빌드 시점 fetch 없이 직전 `latest.json`을 그대로 사용. 데이터 갱신 보고 싶으면 `npm run fetch:data` 먼저.

**Node 22.12+ 필수**. v23 같은 홀수 버전 미지원.

**환경 변수** (.env):
- `FRED_API_KEY` — FRED API 키 (필수)
- `SLACK_WEBHOOK_URL` — Slack Incoming Webhook URL (notify 시 필수)
- `PUBLIC_ADSENSE_CLIENT` — AdSense 클라이언트 ID (선택, 비어있으면 스니펫 미출력)

## Architecture

전체가 Astro 정적 사이트 + TypeScript 데이터 파이프라인.

### Data Flow

```
scripts/fetch-data.ts
  ├─ FRED 6 시리즈    → DGS10, DGS3MO, DEXKOUS, WILL5000PRFC, GDP, BAMLH0A0HYM2
  ├─ Yahoo 8 심볼     → ^VIX, DX-Y.NYB, SPY, QQQ, ^KS11, ^KQ11, TLT, GLD
  ├─ multpl 2 페이지  → CAPE, S&P500 PER
  └─ CNN 1 endpoint   → Fear & Greed
                        ↓
                  src/data/latest.json (Snapshot 타입)
                        ↓
                  src/pages/index.astro
                  └─ computeComposite(data) — 7-indicator 합산
                  └─ build_html 마크업 이식 (카드·게이지·모달)
                        ↓
                       dist/
                        ↓
                  wrangler pages deploy → Cloudflare Pages → techboost.dev
```

### Composite Signal

종합 신호는 **7개 타이밍 지표**로 계산 (`src/lib/signal.ts:computeComposite`):
- `fear_greed` — CNN 심리
- `vix` — 변동성
- `yield_spread` — 10Y-3M 경기·신용
- `ma200` — SPY가 200일선 위/아래
- `ma_cross` — SPY 50/200일 MA 교차 상태 (strong_bull/bull/bear/strong_bear)
- `hy_spread` — HY 회사채 스프레드 (신용 시그널)
- `dxy_trend` — DXY가 200일선 위/아래 (통화)

SCORE_MAP: `good=+1, neutral=0, warn=-1, bad=-2`.
임계값: `≥+4 good · ≥0 neutral · ≥-5 warn · <-5 bad` (점수 범위 -14~+7).

CAPE·S&P500 PER·Buffett 지표·CAPE 등 **밸류에이션** 지표는 카드로는 표시하나 종합 신호 합산에서는 제외 — AQR/IMF 연구에 따르면 밸류에이션은 10-20년 수익 예측에 강한 반면 단기 타이밍에는 노이즈로 작용.

### Data Sources & Quirks

| 지표 | 소스 | 비고 |
|------|------|------|
| Fear & Greed | `production.dataviz.cnn.io` | `Referer: https://money.cnn.com/` 헤더 필수 — 누락 시 418 |
| CAPE, S&P500 PER | multpl.com (cheerio) | `*`·`†` 기호 strip 후 float |
| Buffett Indicator | FRED `WILL5000PRFC` ÷ FRED `GDP` × 100 | GDP는 분기 발표 후 자동 반영 |
| Yield Spread | FRED `DGS10` − FRED `DGS3MO` | 둘 다 Constant Maturity — 기존 yfinance `^IRX`(Bank Discount) 근사보다 정확 |
| 매크로 (10Y/3M/원달러/W5000/GDP/HY) | FRED API | 무료 키 필수, 분당 120 요청 |
| VIX·DXY·ETF·KR 지수 | yahoo-finance2 `.chart()` v3 | `new YahooFinance()` 인스턴스 패턴, 내장 동시성 4 |

### Tailwind CSS v4 Notes

빌드 타임 Tailwind v4 통합 (`@tailwindcss/vite`). 기존 `@tailwindcss/browser@4` CDN 방식은 제거됨.

- 커스텀 컬러는 `src/styles/global.css`의 `@theme {}`에 정의 → 자동으로 `bg-good`·`text-bad`·`bg-surface` 등 유틸로 노출
- v4 breaking: `flex-shrink-0` → `shrink-0`, `bg-opacity-50` → `bg-black/50` 슬래시 문법
- Content paths 명시 불필요 (v4 자동 감지)
- `text-muted = #8B95A1` — WCAG AA 5.0:1 on `#191F28` 배경 (Toss 다크 시그니처)
- `text-danger` 토큰은 `text-bad`로 통일 (`#F04452`). 색상은 #f85149에서 변경됨.

### Gauge SVG

반원 게이지 needle 좌표 공식 (`src/lib/gauge.ts:needleCoords`):

```ts
const rad = Math.PI * (1 - pct / 100);
const nx = 80 + 55 * Math.cos(rad);
const ny = 85 - 55 * Math.sin(rad);
```

0% = 좌측 (공포), 100% = 우측 (탐욕). 인버트(`pct/100 * 180` 사용) 금지 — 방향 반대로 가리킴.

### RSI

Wilder EMA(alpha=1/14), `src/lib/data.ts`·`scripts/fetch-data.ts:rsi14`. 단순 rolling mean 아님. 데이터 15일 미만이면 null.

MA200은 200일 미만이면 null 반환 (`scripts/fetch-data.ts:analyzeTicker`).

## Deployment

**Cloudflare Pages 단일 배포 (Wrangler)**:
- GH Actions가 `astro build` → `dist/`
- `cloudflare/wrangler-action@v3` 가 `wrangler pages deploy dist`로 직접 업로드
- CF Pages 측 자체 빌드는 **Disable Automatic Deployments**로 비활성화 (대시보드 설정)
- 따라서 `FRED_API_KEY`를 CF 환경변수에 등록할 필요 없음 — GH Secrets에만

**Workflows**:
- cron 07:37 KST → fetch + build + deploy + Slack 발송
- workflow_dispatch (수동) → 동일
- push to main (`src/**`·`scripts/**` 등) → fetch + build + deploy, Slack은 발송 안 함

**GH Secrets**: `FRED_API_KEY`, `SLACK_WEBHOOK_URL`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.
**GH Variables**: `CF_PAGES_PROJECT`.

## SEO & AdSense

- `<meta name="robots" content="index,follow,...">` — 검색·광고 봇 허용
- `public/robots.txt` — Googlebot/Bingbot 허용, GPTBot/ClaudeBot 등 AI 학습 봇 차단
- `public/ads.txt` — AdSense 사이트 인증
- AdSense 자동 광고 스니펫은 `src/layouts/Base.astro`에서 `PUBLIC_ADSENSE_CLIENT` env가 있을 때만 출력
```

- [ ] **Step 3: 백업 파일 제거**

Run:
```bash
rm CLAUDE.md.before-migration
```

- [ ] **Step 4: 커밋**

```bash
git add CLAUDE.md
git commit -m "CLAUDE.md 갱신 — Astro·TypeScript·7-indicator 기준으로 정정

기존 dashboard.py 기준 stale 사실 일괄 정리:
- 실행 명령 npm run dev/build/fetch:data/notify:slack
- 7-indicator 합산 + 임계값 ≥+4/≥0/≥-5/<-5 명시
- 데이터 소스 매핑 표 갱신 (FRED 6 + Yahoo 8 + multpl 2 + CNN 1)
- Tailwind v4 빌드 타임 통합 (CDN 폐기)
- text-danger → text-bad 토큰 통일
- Cloudflare Pages 단일 + Wrangler 배포 흐름
- robots.txt·AdSense 스니펫 환경변수 가이드"
```

---

### Task 22: 최종 검증 (사용자 체크포인트)

**Files:** 없음 — 다음 cron 또는 manual 트리거 후 검증

- [ ] **Step 1: 최종 push로 모든 변경 합본 푸시**

Run:
```bash
git push origin main
```

워크플로가 한 번 더 실행되어 깨끗한 상태에서 전 과정 통과 확인.

- [ ] **Step 2: 모든 항목 통과 체크리스트**

브라우저에서 다음 모두 확인:

- [ ] https://techboost.dev 정상 표시 (Astro 빌드 결과)
- [ ] 종합 신호 카드 색상·라벨·comment·7개 지표 한 줄 모두 정상
- [ ] 매크로 카드 9개 모두 값 채워짐 (`—` 표시 없음)
- [ ] ETF 카드 6개 모두 가격·RSI·MA200·52w 게이지 정상
- [ ] 게이지 SVG needle 방향 — 0% 좌측 / 50% 정중앙 / 100% 우측
- [ ] 매크로 카드 클릭 시 모달 열림, ESC·X·백드롭으로 닫힘
- [ ] https://techboost.dev/robots.txt 응답 — Googlebot Allow, GPTBot Disallow 확인
- [ ] https://techboost.dev/ads.txt 응답 (기존 그대로 유지)
- [ ] 브라우저 콘솔에 JS 에러 없음
- [ ] 모바일 viewport(≤640px)에서도 그리드가 1-column으로 정상 표시
- [ ] Slack 채널에 manual trigger 발송 메시지 도착 + 형식 정상
- [ ] GH Actions의 daily-report 워크플로 마지막 실행이 green

- [ ] **Step 3: 다음 cron 발동 후 자동 갱신 확인**

다음 날 07:37 KST 이후:
- GH Actions 로그: 자동 실행됨 (event: schedule)
- 사이트의 "최종 업데이트" 시각이 갱신됨
- Slack에 cron 트리거 메시지 도착

- [ ] **Step 4: 사용자 검증 최종 보고**

> "마이그레이션 전체 완료. 자동 배포·Slack·CF Pages 단일 흐름 안정 동작 확인. 후속 작업은 UI 전면 개편 별도 PR."

---

## 사용자 작업 일정 인터리브 요약

이 plan에서 짐코딩님이 외부 시스템에서 직접 수행하셔야 하는 작업의 시점:

| Task | 어디서 | 무엇 |
|---|---|---|
| **Task 0 (전체)** | FRED/Slack/CF/GH 대시보드 | 토큰 발급·CF 자동배포 비활성화·GH Secrets 등록 (코드 변경 시작 전 일괄) |
| Task 17 Step 3 | Slack 채널 | 테스트 메시지 형식 확인 |
| Task 19 Step 2-3 | GH Actions 로그·CF Pages 사이트 | 첫 자동 배포 통과 확인 |
| Task 19 Step 4 | Slack | manual trigger 발송 확인 |
| Task 20 Step 4 | `.env` 편집기 + GH Secrets UI | 카카오 4개 변수·secrets 수동 삭제 |
| Task 22 Step 2 | 브라우저 + Slack + GH Actions | 최종 체크리스트 12항목 |
| Task 22 Step 3 | 다음 cron 시각 후 | 자동 갱신 확인 |

---

## 후속 PR 후보 (이 plan에서 의도적 제외)

- UI 전면 개편 (카드 컴포넌트화, 차트 시각화, 모바일 전용 레이아웃)
- 모달의 풍부한 INDICATOR_DICT 콘텐츠 재이식 (현재는 minimal)
- 단위 테스트 프레임워크 도입 (`vitest` 등)
- AdSense 수동 광고 슬롯 배치
- Astro Content Collections + Zod 스키마
- 사이트맵 자동 생성 (`@astrojs/sitemap`)
- Telegram·이메일 등 알림 채널 확장
- 다국어 (i18n)

---

## 알려진 제약 (구현 중 만날 가능성)

- `^KS11`·`^KQ11` 한국 지수는 거래일 차이로 200일 데이터가 부족하면 `ma_cross`·`ma200_above` null 가능
- yahoo-finance2 첫 호출 시 cookie/crumb 획득에 3-7초 지연 — GH Actions 타임아웃은 충분
- multpl.com 페이지 구조 변경 시 cheerio 셀렉터(`table#datatable tr eq(1) td eq(1)`) 깨질 수 있음 → 그때 한 번 수정
- CNN F&G 비공식 endpoint — 1년+ 안정적이나 갑자기 차단되면 `fear_greed`만 null 처리되어 빌드는 계속됨 (단 2개 이상 null 정책에 걸리면 빌드 실패 가능)
