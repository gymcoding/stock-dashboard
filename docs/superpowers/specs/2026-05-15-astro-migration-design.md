# stock-dashboard: Astro 마이그레이션 설계서

- 작성일: 2026-05-15
- 작성자: 짐코딩 + Claude
- 상태: 설계 확정, 구현 계획 작성 대기
- 후속 문서: `2026-05-15-astro-migration-plan.md` (superpowers:writing-plans로 생성 예정)

---

## 1. 목적과 범위

### 1.1 목적

현재 단일 Python 파일(`dashboard.py`, 1547줄)이 매일 외부 데이터를 페치하여 정적 HTML 한 장(`dashboard.html`)을 만들고 Cloudflare Pages·GitHub Pages에 배포하는 구조를, **Astro 기반 정적 사이트 + TypeScript 데이터 파이프라인** 으로 이전한다.

### 1.2 범위에 포함

- `dashboard.py`(1547줄)의 모든 데이터 페칭·신호 계산·HTML 생성 로직을 TypeScript로 이전
- 단일 HTML 생성기 → Astro 정적 사이트 빌드 체계로 전환
- 외부 데이터 소스 다양화: Yahoo Finance 단일 의존 → FRED(매크로) + Yahoo(주가·VIX) + multpl(밸류에이션) + CNN(F&G) + FRED(HY)
- 카카오 일일 리포트 → Slack Incoming Webhook 알림으로 교체
- 토스 다크 테마 적용(컬러·타이포만, UI 구조는 그대로)
- AdSense 스니펫 + `ads.txt` 통합 (수동 광고 슬롯 배치는 후속)
- AI 학습 봇 차단용 `robots.txt`
- 배포 단일화: GH Pages 제거, Cloudflare Pages 단일 + Wrangler 직접 업로드
- 7-indicator 종합 신호 보존 (`fear_greed` + `vix` + `yield_spread` + `ma200` + `ma_cross` + `hy_spread` + `dxy_trend`)
- `CLAUDE.md` 갱신 (Composite 4 → 7 indicator, Tailwind CDN → 빌드 타임, deploy 단일화 등 stale 부분)

### 1.3 범위에 포함하지 않음

- **UI 전면 개편** — 마이그레이션 직후 별도 PR로 진행. 본 작업은 기존 카드 구조·게이지·모달을 그대로 옮기는 데 한정
- **접근 제어(auth gate)** — AdSense 수익화와 양립 불가하여 제외
- **AdSense 광고 슬롯 수동 배치** — 자동 광고만 활성화, 수동 슬롯은 UI 개편 단계에서
- **수동 새로고침 기능, 단위 테스트 신규 도입** — 후속
- **현재 워크플로의 push 트리거·cron 시각·동시성 정책** — 그대로 보존

### 1.4 비결정자가 알아야 할 핵심 제약

- AdSense 수익화 예정 → 페이지는 **공개+검색 크롤링 가능** 필수. 인증 게이트 불가
- 일 1회 cron이라 단순성이 최우선 — 재시도·다중 fallback 등 복잡한 안정화 회피
- 사용자(짐코딩) 1인 운영 — 운영 부담 최소화

---

## 2. 검증된 사실 (구현 시 참조)

### 2.1 Astro 공식 권장 (Astro 5.x 기준, 공식 docs 인용)

- Astro에서 reserved 디렉토리는 `src/pages/`만 — 그 외 `src/lib`, `src/data` 등 자유 구성 가능
- Node.js **v22.12.0 이상** 필수, v23 같은 홀수 버전 미지원
- `tsconfig.json`: `{ "extends": "astro/tsconfigs/base" }` 권장
- Tailwind 통합은 **Astro ≥5.2.0에서 `@tailwindcss/vite` Vite 플러그인**이 공식 권장. `npx astro add tailwind` 실행 시:
  - `@tailwindcss/vite` 자동 설치
  - `astro.config.mjs`에 플러그인 자동 추가
  - `src/styles/global.css` 자동 생성(`@import "tailwindcss";` 포함)
- Global CSS는 layout 컴포넌트에서 `import "../styles/global.css";` 형태로 import 권장
- Tailwind v4의 `@theme` directive는 그대로 사용 가능 (Tailwind 기능, Astro 무관)
- Content paths 명시 불필요 — Tailwind v4가 자동 감지
- Astro는 Vite 기반이라 `import data from "../data/latest.json"`이 빌드 타임 정적 인라인됨 (`with { type: "json" }` 불필요)

### 2.2 yahoo-finance2 검증

- 버전 v3.14.0 (2026-03-26), 주간 다운로드 15만, 활발한 유지보수
- 캐럿(`^VXAPL`)·등호(`EURGBP=X`) 심볼이 공식 테스트 케이스에 포함 → `^VIX`·`^TNX`·`^IRX`·`^DXY`·`^W5000`·`KRW=X`·`^KS11`·`^KQ11` 모두 동작 가능성 매우 높음
- `historical()`보다 **`chart()` 모듈이 v3 권장** (성능·기능 우위, JSDoc 인용)
- v3 진입점: `new YahooFinance()` 인스턴스 패턴
- 내장 동시성 제한 4 — 직접 throttle 불필요
- **리스크**: Yahoo cookie/crumb 깨짐 사고가 1~2년에 1회 정도 발생 (2025년 issue #784/#902/#977/#990). 라이브러리 측 대응은 빠르나 단일 의존은 위험 → 매크로는 FRED로 이관

### 2.3 FRED API

- 매크로 시계열 풍부: `DGS10`(10Y), `DGS3MO`(3M), `DEXKOUS`(원달러), `WILL5000PRFC`(Wilshire 5000), `GDP`(분기), `BAMLH0A0HYM2`(HY spread)
- 분당 120 요청 — 일 1회 cron엔 무제한 수준
- 무료 API 키 (이메일 등록만)
- 미 연준 공식 인프라 — 가장 안정적
- 라이선스: 미 정부 발표분 재게시, 상업 이용 가능

### 2.4 FRED가 대체할 수 없는 케이스

- **달러 인덱스(DXY)**: FRED `DTWEXBGS`는 23통화 광역 가중지수이고, ICE 6통화 DXY와 **다른 지수**. 현재 대시보드의 임계값·임계 문구는 6통화 DXY 기준이라 Yahoo `DX-Y.NYB` 유지가 정확

---

## 3. 아키텍처

### 3.1 파일 구조

```
stock-dashboard/
├── astro.config.mjs              # defineConfig({ site: 'https://techboost.dev', vite: { plugins: [tailwindcss()] } })
├── package.json                  # node >=22.12.0; scripts: dev/build/preview/fetch:data/notify:slack
├── tsconfig.json                 # { "extends": "astro/tsconfigs/base" }
├── public/
│   ├── ads.txt                   # 유지
│   ├── CNAME                     # 유지
│   └── robots.txt                # 신규 (AI 학습 봇 차단)
├── src/
│   ├── pages/index.astro         # 메인 페이지 (build_html 이식)
│   ├── layouts/Base.astro        # <head>·Pretendard·AdSense·global.css import
│   ├── styles/global.css         # @import "tailwindcss" + @theme { Toss 팔레트 }
│   ├── data/latest.json          # gitignored, CI 생성
│   └── lib/
│       ├── data.ts               # latest.json 타입
│       ├── signal.ts             # signal_color, overall_signal, computeComposite
│       ├── gauge.ts              # SVG 게이지 needle 좌표
│       └── format.ts             # 숫자·날짜 포맷
├── scripts/
│   ├── fetch-data.ts             # yahoo-finance2 + FRED + cheerio + CNN → latest.json
│   └── send-slack.ts             # Slack Incoming Webhook
└── .github/workflows/daily.yml   # cron + push → fetch → build → Wrangler deploy → Slack
```

### 3.2 삭제 대상

- `dashboard.py` (1547줄)
- `dashboard.html` (생성물)
- `requirements.txt`
- `scripts/send_kakao.py`, `scripts/setup_kakao.py`
- `_site/` (Astro는 `dist/` 사용)
- `tablet-768-fullpage.png` (정체불명 자산 — 마이그레이션 시 검토 후 정리)

### 3.3 빌드·배포 흐름

```
GH Actions (cron 07:37 KST | workflow_dispatch | push:main):
  1. checkout
  2. setup-node@v4 (node-version: 22, cache: npm)
  3. npm ci
  4. tsx scripts/fetch-data.ts   ─→  src/data/latest.json
       FRED API ─→ DGS10·DGS3MO·DEXKOUS·WILL5000PRFC·GDP·BAMLH0A0HYM2
       yahoo-finance2 ─→ ^VIX·DX-Y.NYB·SPY·QQQ·^KS11·^KQ11·TLT·GLD
       CNN ─→ Fear & Greed
       multpl(cheerio) ─→ CAPE·S&P500 PER
  5. npm run build  (astro build)  ─→  dist/
  6. cloudflare/wrangler-action@v3
       wrangler pages deploy dist --project-name=$CF_PAGES_PROJECT --branch=main
  7. (cron/manual && success)  npx tsx scripts/send-slack.ts
```

`push: main` 시에는 Slack 발송 안 함 (현재 카카오 정책 동일 유지).

---

## 4. 데이터 파이프라인 (§2)

### 4.1 데이터 소스 매핑 (최종)

| 지표 | 1차 소스 | 비고 |
|---|---|---|
| 10Y Treasury | FRED `DGS10` | |
| 3M Treasury | FRED `DGS3MO` | Constant Maturity — 기존 `^IRX` Bank Discount 근사보다 정확 |
| 원달러 환율 | FRED `DEXKOUS` | |
| Wilshire 5000 | FRED `WILL5000PRFC` | 주간 시리즈 |
| US GDP | FRED `GDP` | 하드코딩 제거 — 분기 발표 자동 반영 |
| HY Spread | FRED `BAMLH0A0HYM2` | 현 상태 유지 |
| Dollar Index | yahoo-finance2 `DX-Y.NYB` | 6통화 ICE 지수 — FRED 대체 불가 |
| VIX | yahoo-finance2 `^VIX` | |
| 미국 ETF | yahoo-finance2 `SPY`/`QQQ`/`TLT`/`GLD` | |
| 한국 지수 | yahoo-finance2 `^KS11`/`^KQ11` | |
| CNN F&G | `production.dataviz.cnn.io` 직접 호출 | `Referer: https://money.cnn.com/` 헤더 필수 |
| CAPE, S&P500 PER | multpl.com + cheerio | 기존 `pd.read_html` 로직 1:1 이식, `*`·`†` strip |

### 4.2 `latest.json` 스키마 (TypeScript 타입)

> 필드명은 dashboard.py의 반환 키와 **1:1 동일**하게 유지(snake_case). 임의 리네이밍은 본 PR에서 제외 — UI 개편 시 일괄 처리.

```ts
export type Snapshot = {
  generated_at: string;            // ISO 8601 UTC
  fear_greed: { score: number | null; rating: string } | null;
  cape: number | null;
  sp500_pe: number | null;
  buffett: number | null;          // dashboard.py:478 — Wilshire 5000 / GDP × 100 (단일 숫자)
  vix: number | null;
  dxy: { value: number; above_ma200: boolean } | null;
  usdkrw: number | null;
  yield_spread: { spread: number; y10: number; y3m: number } | null;
  hy_spread: number | null;
  tickers: TickerAnalysis[];
  sp500_trend: boolean | null;     // SPY가 MA200 위면 true, 아래면 false (dashboard.py:1400)
  sp500_trend_pct: number | null;  // MA200 대비 %, dashboard.py:1401에서 ma200_diff_pct 복사
  sp500_ma_cross: MaCross;         // SPY 기준 (dashboard.py:1402)
};

export type MaCross = 'strong_bull' | 'bull' | 'bear' | 'strong_bear' | null;

export type TickerAnalysis = {
  ticker: string;                  // SPY, QQQ, ^KS11, ^KQ11, TLT, GLD
  name: string;                    // 한글 표시명
  price_str: string;               // 이미 포맷된 문자열 ("$432.10" 또는 "2,650.32") — dashboard.py:618
  change_pct: number | null;       // 전일 대비 % (소수점 2)
  rsi: number | null;              // Wilder EMA 14일, 소수점 1
  ma200_above: boolean | null;     // 200일선 위/아래 (데이터 200일 미만이면 null)
  ma200_diff_pct: number | null;   // 200일선 대비 % (소수점 1)
  ma_cross: MaCross;               // 50/200 MA 교차 상태
  pos_52w: number | null;          // 52주 가격대 내 위치 0~100 (소수점 1)
};
```

`Snapshot.buffett`은 dashboard.py에서 단일 숫자 반환(`fetch_buffett_indicator():478`) — 객체 아님. FRED `GDP`로 분모 자동화하더라도 반환 형태는 동일하게 단일 percent 값 유지.

### 4.3 핵심 로직 보존

- **RSI**: Wilder EMA(alpha=1/14), `dashboard.py`의 공식 그대로 이식
- **MA200**: 200일 미만이면 `null` 반환 (현재 가드 보존)
- **게이지 SVG 각도**:
  ```ts
  const rad = Math.PI * (1 - pct / 100);
  const nx = 80 + 55 * Math.cos(rad);
  const ny = 85 - 55 * Math.sin(rad);
  ```
  좌(0°)=공포, 우(180°)=탐욕. 인버트 금지(`CLAUDE.md`의 경고 동일 적용)
- **신호 임계값·한글 문구**: `dashboard.py:241-336`의 `signal_color()` 분기를 1:1 이식. 새 작문 없음
- **7-indicator 합산**: `overall_signal_from_data()`를 `computeComposite()`로 이식. `SCORE_MAP = { good: 1, neutral: 0, warn: -1, bad: -2 }`. **임계값 `≥+4 good, ≥0 neutral, ≥-5 warn, <-5 bad`** (dashboard.py:325-332, 7-indicator 기준 점수 범위 −14~+7). 이전 4-indicator 임계값(`≥+2/≥0/≥-3/<-3`)은 stale 정보로 사용 금지 — CLAUDE.md에 잘못 기재된 부분도 본 PR에서 함께 정정

### 4.4 watchlist (현재 그대로 유지)

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

### 4.5 에러 처리

- 모든 fetcher: try/catch → `null` 반환 (현재 패턴 동일)
- 재시도 없음 — 일 1회 cron, 다음 빌드에서 자연 복구
- **7-indicator 부분 누락 정책**: 어느 한 지표가 null이면 `computeComposite()`에서 해당 항목을 **`neutral`(0점) 처리**하고 종합 신호 계산은 계속. 카드 UI는 "데이터 없음" 표시 (현재 dashboard.py 동작 동일)
- **CI 실패 기준**: 핵심 4개(`fear_greed`·`vix`·`yield_spread`·`sp500_trend`) 중 **2개 이상** null이면 `process.exit(1)`. 나머지 3개(`ma_cross`·`hy_spread`·`dxy_trend`)는 null이어도 빌드 통과 — 위 neutral 처리로 흡수
- 이 정책은 종합 신호의 코어 시그널이 유실되는 사고만 빌드 실패로 막고, 보조 지표 일시 누락은 그래도 사이트를 갱신해서 운영 단절을 방지

### 4.6 라이브러리·환경

```json
{
  "dependencies": {
    "astro": "^5",
    "@tailwindcss/vite": "^4",
    "tailwindcss": "^4",
    "yahoo-finance2": "^3.14",
    "cheerio": "^1"
  },
  "devDependencies": {
    "tsx": "^4",
    "typescript": "^5"
  },
  "engines": { "node": ">=22.12.0" },
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview",
    "fetch:data": "tsx scripts/fetch-data.ts",
    "notify:slack": "tsx scripts/send-slack.ts"
  }
}
```

---

## 5. 렌더링 레이어 (§3)

### 5.1 `Base.astro` 핵심

- `<html lang="ko">`
- `<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">` — 검색·AdSense 크롤링 허용
- OpenGraph 메타 (Slack 미리보기용)
- Pretendard CDN (preconnect + variable subset)
- AdSense `<script async ...>` (client ID는 `import.meta.env.PUBLIC_ADSENSE_CLIENT`로 환경변수화)
- `import "../styles/global.css";` 최상단
- `<meta name="generator" content="Astro">` + `build-time` 메타

### 5.2 `index.astro` 구조

`build_html(data)` 마크업을 그대로 이식, 카드·게이지·모달 구조 동일:
- 헤더 (타이틀 + 최종 업데이트 시각)
- 종합 신호 카드 (7-indicator 합산)
- 매크로 카드 그리드 (F&G·VIX·금리차·DXY·USDKRW·CAPE·PER·Buffett·HY)
- 종목 카드 그리드 (SPY·QQQ·KOSPI·KOSDAQ·TLT·GLD)
- 지표 설명 모달 (`<dialog>` 엘리먼트, `data-*` 속성으로 내용 주입)

페이지 frontmatter에서 `import data from "../data/latest.json"` 으로 빌드 타임 인라인.

### 5.3 인터랙티브 — 모달

UI 프레임워크 없이 vanilla JS `<script is:inline>`로 처리. 각 카드의 `data-modal-trigger` 클릭 → `<dialog>.showModal()` + `data-*` 속성에서 제목·설명·임계값표·근거 URL 채움. 현재 `dashboard.html`의 동작 그대로.

### 5.4 Toss 다크 팔레트 (확정 안)

> **토큰 리네이밍 작업 포함**: 현재 코드는 `text-danger`·`bg-danger/15`·`border-danger/30` 등 `danger` 키를 사용(`dashboard.py:34` `_CLS["bad"]` → `text-danger`). 본 PR에서 토큰을 **`danger` → `bad`로 일괄 치환**한다. 색상값도 `#f85149` → `#F04452`로 함께 변경. 호환성 별칭(`--color-danger`)은 두지 않음 — 단일 PR에서 완전 정리.

```css
@import "tailwindcss";

@theme {
  --color-bg:         #191F28;
  --color-surface:    #20262F;
  --color-surface-hi: #2A323D;
  --color-border:     #333D4B;

  --color-text:    #F2F4F6;
  --color-muted:   #8B95A1;
  --color-subtle:  #6B7684;

  --color-good:    #00C896;
  --color-warn:    #FF9500;
  --color-bad:     #F04452;
  --color-neutral: #4E5968;

  --color-brand:    #3182F6;
  --color-brand-hi: #4F8BF7;

  --font-sans: 'Pretendard Variable', Pretendard, system-ui, sans-serif;
}
```

기존 `bg-surface`·`text-good`·`text-muted` 등 클래스 그대로 동작 (Tailwind v4가 `--color-*` 토큰 자동 노출).

> 정확한 Toss 디자인 토큰은 비공개이므로 위 값은 일반에 알려진 키 컬러 기반의 안. 구현 시 시각 비교 후 미세조정 가능.

### 5.5 `public/robots.txt` (신규)

```
User-agent: Googlebot
Allow: /
User-agent: Googlebot-Image
Allow: /
User-agent: Bingbot
Allow: /

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

sitemap은 `@astrojs/sitemap` 인티그레이션으로 자동 생성. 단일 페이지지만 등록 시 search console 모니터링이 쉬워짐.

---

## 6. 알림·CI·배포 (§4)

### 6.1 Slack 알림 — `scripts/send-slack.ts`

- 메커니즘: Slack Incoming Webhook URL (Bot Token 불필요)
- 메시지: Block Kit attachment, 종합 신호 색상으로 컬러 사이드바
  - Header: `📊 {composite.label}` (예: `📊 매수 유리`)
  - Section: `{composite.comment}` (예: `전반적으로 긍정적인 신호예요. 장기 투자를 시작하기 좋은 환경이에요.`)
  - Section: 7개 지표 한 줄 요약
  - Context: 실패 데이터 있으면 알림, 없으면 ✅ 모든 데이터 정상
  - Actions: "대시보드 열기" 버튼 → techboost.dev

**7개 지표 한 줄 포맷 (`format_kakao_summary()` `dashboard.py:376-419` 기준)**:

```
😱 공포·탐욕 32 (공포)
📉 VIX 18.4 (정상)
📈 10Y-3M +0.42 (정상)
📏 S&P500 200일선 위 (↑2.1%)
🔀 MA Cross strong_bull (강세 신호)
💳 HY Spread 3.8 (정상)
💵 DXY 200일선 위 (달러 강세)
```

각 라인은 `이모지 + 지표명 + 값 + (해석 한국어)` 패턴. 해석 한국어는 `signal_color()` 두 번째 반환값을 그대로 사용. 임계값별 한국어 문구는 dashboard.py에서 가져옴 — 새 작문 없음.

- 발송 조건: `github.event_name != 'push' && success()` — cron/manual 성공 시에만, push 노이즈 제외

### 6.2 GitHub Actions 워크플로 (`.github/workflows/daily.yml`)

```yaml
name: daily-report
on:
  schedule:
    - cron: '37 22 * * *'
  workflow_dispatch: {}
  push:
    branches: [main]
    paths:
      - 'src/**'
      - 'scripts/**'
      - 'astro.config.mjs'
      - 'package.json'
      - 'package-lock.json'
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
        with: { node-version: '22', cache: 'npm' }
      - run: npm ci

      - name: Fetch external data
        env:
          FRED_API_KEY: ${{ secrets.FRED_API_KEY }}
        run: npx tsx scripts/fetch-data.ts

      - name: Astro build
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

### 6.3 GH Secrets·Variables 변경 매핑

| 종류 | 이름 | 동작 |
|---|---|---|
| Secret | `FRED_API_KEY` | 추가 |
| Secret | `CLOUDFLARE_API_TOKEN` | 추가 (Pages Edit 권한) |
| Secret | `CLOUDFLARE_ACCOUNT_ID` | 추가 |
| Secret | `SLACK_WEBHOOK_URL` | 추가 |
| Variable | `CF_PAGES_PROJECT` | 추가 (평문, 프로젝트 이름) |
| Secret | `KAKAO_REST_API_KEY`·`KAKAO_CLIENT_SECRET`·`KAKAO_REFRESH_TOKEN` | 삭제 |
| Secret | `CLOUDFLARE_PAGES_DEPLOY_HOOK` | 삭제 (Wrangler 사용 후 불필요) |
| Secret | `GH_PAT`·`GH_REPO` | 삭제 (kakao refresh token 자동 갱신용) |

### 6.4 CF Pages 대시보드 변경

- 현재: git 연결 + 자체 빌드 중
- **권장 변경 (배포 충돌 회피)**: CF Pages 대시보드 → 해당 프로젝트 → **Settings → Builds & deployments → Branch deployments → Production branch → "Disable Automatic Deployments"** 토글
- 이렇게 해두면 Wrangler 업로드만 유효하고 git push에 의한 CF 자체 빌드는 발생하지 않음 — **두 경로가 동시에 실행되어 어느 배포가 최종이 될지 모호해지는 사고 방지**
- 대안: git integration 자체를 제거해도 동일 효과(단 PR 미리보기를 나중에 다시 쓰려면 재연결 필요)
- "빌드 명령을 no-op으로" 방식은 **권장하지 않음** — 빌드는 안 돼도 자동 배포 자체는 매번 트리거되어 Wrangler 업로드와 경합

---

## 7. 이전 순서 (high-level)

자세한 단계는 후속 `2026-05-15-astro-migration-plan.md`에서 작성. 본 설계에서는 큰 그림만:

1. **사전 준비** — FRED/Slack/CF API 토큰 발급, GH Secrets 등록
2. **Astro 스캐폴딩** — `npm create astro@latest` + `npx astro add tailwind` + 디렉토리 생성
3. **신호·포맷 라이브러리 이식** — `signal.ts`·`gauge.ts`·`format.ts` (외부 의존 없음, 단위 동작 검증 쉬움)
4. **데이터 페치 스크립트** — FRED·yahoo-finance2·CNN·multpl 페치 함수 작성. smoke-test로 17개 외부 호출(FRED 6 시리즈 + Yahoo 8 심볼 + multpl 2 페이지 + CNN 1) 모두 응답 확인
5. **레이아웃·페이지** — Base.astro + index.astro로 build_html 마크업 이식 (Toss 팔레트 적용)
6. **Slack 스크립트** — webhook 발송 확인
7. **워크플로 교체** — daily.yml 새 워크플로로 덮어쓰기, 기존 secrets 정리
8. **첫 자동 배포 검증** — cron 한 차례 + push 한 차례 안정성 확인
9. **Python 자산 제거** — `dashboard.py`·`dashboard.html`·`requirements.txt`·`scripts/send_kakao.py`·`scripts/setup_kakao.py`·`_site/` 삭제
10. **CLAUDE.md 갱신** — Composite 4 → 7 indicator, Tailwind CDN → 빌드 타임, GH Pages 제거, 데이터 소스 매핑 등 stale 사실 모두 갱신

---

## 8. 알려진 리스크와 미해결 항목

### 8.1 리스크

| 리스크 | 영향 | 완화책 |
|---|---|---|
| yahoo-finance2 cookie/crumb 깨짐 | VIX·DXY·6 ETF 일시 null → 일부 카드 빈 값 | 매크로는 FRED로 이관해 단일 장애점 회피. 발생 시 라이브러리 패치 릴리스 대기 (1일 이내) |
| `^W5000` 인덱스 데이터 누락 | Buffett 지표 null | FRED `WILL5000PRFC`로 대체 — 이미 본 설계에 반영 |
| Toss 디자인 토큰 비공개 | 색상 미세 차이 | 일반 알려진 키 컬러로 초안, 시각 비교 후 미세조정 |
| `^IRX` Bank Discount vs Constant Maturity | yield spread 정확도 | FRED `DGS3MO` Constant Maturity로 대체 — 이미 반영 (정확도 개선) |
| AdSense 미승인 상태에서 스니펫 노출 | 영향 없음 (script만 무해) | client ID를 `PUBLIC_ADSENSE_CLIENT` env로 빼서 환경별 토글 |
| Wrangler 배포 실패 시 직전 dist 그대로 유지됨 | 사이트는 stale 이전 데이터 계속 노출 | Slack 실패 알림은 본 작업 범위 외 — GH Actions 이메일 알림으로 짐코딩님이 인지 |

### 8.2 구현 단계에서 smoke-test로 확인할 known unknown

- `yahoo-finance2`가 다음 심볼을 `chart()`로 정상 반환하는지: `^VIX`, `DX-Y.NYB`, `SPY`, `QQQ`, `^KS11`, `^KQ11`, `TLT`, `GLD`
- FRED API에서 모든 6개 시리즈가 같은 응답 스키마(observations[]) 반환하는지
- CNN F&G 엔드포인트가 GH Actions runner IP에서 차단되지 않는지
- multpl.com 페이지 구조 변경 없는지 (`tables[0].iloc[0,1]` 위치)

### 8.3 의도적 미포함

- 모달의 데이터 시각화 차트 신규 추가
- 단위 테스트 프레임워크 도입
- AdSense 수동 광고 슬롯 배치
- 모바일 전용 UI 재설계
- 접근 제어
- 알림 채널 확장 (Telegram·이메일 등)
- Astro Content Collections·Zod 스키마 도입 (단일 페이지·단일 스냅샷이라 오버스펙)
- 다국어

---

## 9. 사용자 작업 체크리스트 (구현 단계에서 안내됨)

본 설계 승인 후 구현 단계에서 짐코딩님이 직접 수행해야 할 외부 작업:

- [ ] FRED API 키 발급·`.env` 등록 (완료됨, 2026-05-15)
- [ ] Slack App 생성 → Incoming Webhook URL 발급 (채널 선택)
- [ ] Cloudflare API Token 발급 (Pages Edit 권한)
- [ ] Cloudflare Account ID 복사
- [ ] CF Pages 프로젝트명 확인
- [ ] GH 저장소 Secrets/Variables 등록 (`FRED_API_KEY`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `SLACK_WEBHOOK_URL`, `CF_PAGES_PROJECT`)
- [ ] CF Pages 대시보드 빌드 설정 변경 (no-op로)
- [ ] AdSense 승인 상태 확인 → 승인 시 `PUBLIC_ADSENSE_CLIENT` env 설정

---

## 10. 후속 — UI 전면 개편 (별도 PR)

본 마이그레이션 완료 후 UI 전면 개편을 별도 작업으로 진행 예정. 본 설계와 분리하는 이유:

- 인프라 전환 + 디자인 개편을 동시에 하면 회귀(regression) 원인 추적이 어려움
- Astro 환경에 적응한 뒤 디자인 결정을 내리는 편이 컴포넌트 분해를 더 적절하게 함
- 본 설계의 "단일 페이지 + 공용 유틸 수준" 구조는 후속 개편에서 자유롭게 재구성 가능

후속 개편에서 고려할 항목: 카드 단위 컴포넌트화, AdSense 수동 광고 슬롯 위치, 차트 시각화 추가, 모바일 전용 레이아웃 등.
