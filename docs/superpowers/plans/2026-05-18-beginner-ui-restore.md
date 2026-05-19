# 초보 친화 정보량 복원 + 컴포넌트 분해 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Astro 마이그레이션 시 소실된 초보 친화 콘텐츠 9개 항목을 순수 `.astro` 컴포넌트로 100% 복원하고, 네이티브 `<dialog>` 좌상단 버그를 수정한다.

**Architecture:** `src/pages/index.astro`(263줄 단일 파일)를 `src/components/*.astro` 9개 + `src/lib` 데이터/스타일 모듈 2개로 분해. 데이터·신호 로직(`latest.json`, `signal.ts`)은 무변경 — 표현 계층만 복원. React·신규 토큰 미도입, 기존 M3 다크/라이트 테마 유지.

**Tech Stack:** Astro 5.x 정적 사이트, TypeScript, Tailwind CSS v4(`@theme` + M3 `--c-*` 토큰), 네이티브 `<dialog>`/`<details>`.

**테스트 전략 주의:** 이 프로젝트엔 단위 테스트 러너가 없고(`package.json` scripts 확인), `CLAUDE.md`가 검증을 **`npm run build` + Playwright 실브라우저**로 규정한다. 단위 테스트 프레임워크 추가는 설계서 8절(out of scope)다. 따라서 각 태스크의 검증 게이트는 `npm run build` 통과(+ 순수 TS 파일은 `npx tsc --noEmit`)이며, 최종 Task 14에서 Playwright로 동작·시각 검증한다. 이는 기존 코드베이스 패턴을 따르는 의도적 적응이다.

**공유 타입 계약 (모든 태스크 공통):**
- `SignalKey = 'good' | 'neutral' | 'warn' | 'bad'` (`src/lib/signal.ts`에서 export, 기존)
- `signalColor(label, value): [SignalKey, string]` (기존)
- `computeComposite(data): { key, label, comment, good, warn, bad, neutral, signals: {name,key,text}[] }` — `signals` 순서 고정: `[공포·탐욕, VIX, 10Y-3M, S&P500 MA200, MA Cross, HY Spread, DXY Trend]` (기존)
- `IndicatorInfo` (Task 1에서 정의): `{ title, description, thresholds: {range,label,sig:SignalKey}[], caveat, sourceUrl, sourceLabel }`
- 공유 스타일 맵 (Task 2에서 정의): `signalBg`, `signalText`, `SIGNAL_KR` — 각 `Record<SignalKey,string>`

---

## File Structure

| 파일 | 책임 |
|------|------|
| `src/lib/indicator-info.ts` (생성) | 15개 지표 상세 콘텐츠 타입드 상수 (모달용) |
| `src/lib/signal-style.ts` (생성) | `signalBg`/`signalText`/`SIGNAL_KR` 공유 맵 (DRY) |
| `src/components/SectionHeading.astro` (생성) | 이모지+제목+부제 섹션 헤더 (재사용) |
| `src/components/MacroCard.astro` (생성) | 매크로 지표 카드 (클릭→모달) |
| `src/components/EtfCard.astro` (생성) | ETF 카드 (RSI/MA200/52주 행 클릭→모달) |
| `src/components/GaugeFearGreed.astro` (생성) | 반원 공포·탐욕 게이지 SVG |
| `src/components/CompositeSignal.astro` (생성) | 종합 신호등 + 7컴포넌트 배지 |
| `src/components/Glossary.astro` (생성) | 16개 용어 `<details>` 가이드 |
| `src/components/Header.astro` (생성) | 헤더(제목·부제·시각·테마 토글) |
| `src/components/Footer.astro` (생성) | 데이터 출처 + 면책 |
| `src/components/IndicatorModal.astro` (생성) | 네이티브 `<dialog>` 리치 모달 + 모듈 스크립트 |
| `src/styles/global.css` (수정) | `<dialog>` 중앙정렬 CSS 추가 |
| `src/pages/index.astro` (재작성) | 얇은 조립 레이어 |
| `CLAUDE.md` (수정) | 컴포넌트 맵 문서화, 단일 페이지 규약 갱신 |

---

## Task 1: indicator-info.ts 데이터 모듈

**Files:**
- Create: `src/lib/indicator-info.ts`

구 `dashboard.py`(`git show 6400f6b^:dashboard.py` 43–240행)의 `INDICATOR_INFO`를 타입드 TS 상수로 이식. 설계서 4.1절 정확성 정정 2건 반영: `yield_spread.caveat`, `buffett.caveat`.

- [ ] **Step 1: 파일 작성**

```ts
import type { SignalKey } from './signal';

export type IndicatorInfo = {
  title: string;
  description: string;
  thresholds: { range: string; label: string; sig: SignalKey }[];
  caveat: string;
  sourceUrl: string;
  sourceLabel: string;
};

export const INDICATOR_INFO: Record<string, IndicatorInfo> = {
  overall: {
    title: '종합 투자 신호 (7개 컴포넌트)',
    description:
      '이 대시보드의 종합 신호는 CNN Fear & Greed Index(7-component composite)와 Goldman Sachs Bull/Bear Indicator(6-component) 방법론을 참고해 7개 지표를 종합한 결과예요. 각 지표를 매수(+1)·중립(0)·주의(-1)·위험(-2) 4단계로 분류하고 합산해서 최종 점수(범위: -14 ~ +7)를 산출해요. 점수 구간에 따라 4가지 행동 권고를 보여줘요.',
    thresholds: [
      { range: '≥ +4점', label: '매수 유리 — 장기 투자 시작 좋은 환경', sig: 'good' },
      { range: '0 ~ +3점', label: '중립 — 관망 추천', sig: 'neutral' },
      { range: '-1 ~ -5점', label: '주의 — 신중하게 (분할 매수/관망)', sig: 'warn' },
      { range: '≤ -6점', label: '위험 — 방어적으로 (현금 비중 ↑)', sig: 'bad' },
    ],
    caveat:
      '이 신호는 학술적 백테스트가 아닌 휴리스틱(experience-based heuristic)이에요. 카드를 클릭해 각 컴포넌트의 현재값·임계값·검증 출처를 직접 확인하세요. 매매 결정은 본인 책임이며 다른 지표·뉴스와 함께 종합 판단해야 해요.',
    sourceUrl: 'https://github.com/gymcoding/stock-dashboard',
    sourceLabel: '방법론·코드 (GitHub)',
  },
  fear_greed: {
    title: 'CNN 공포 & 탐욕 지수',
    description:
      'CNN이 매일 발표하는 미국 주식시장 투자자 심리 지표예요. S&P500 모멘텀, 주식 가격 강도, 풋콜 비율 등 7개 하위 지표를 0~100 점수로 종합해요. 0에 가까울수록 투자자가 겁먹어 매도세가 강하고, 100에 가까울수록 욕심을 부리며 매수세가 강한 상태예요.',
    thresholds: [
      { range: '0~24', label: '극도의 공포 (역사적 매수 기회)', sig: 'good' },
      { range: '25~44', label: '공포 (매수 기회)', sig: 'good' },
      { range: '45~55', label: '중립', sig: 'neutral' },
      { range: '56~74', label: '탐욕 (주의)', sig: 'warn' },
      { range: '75~100', label: '극도의 탐욕 (고점 경고)', sig: 'bad' },
    ],
    caveat:
      '단기 심리 지표라 추세 전환 시점을 정확히 짚지 못해요. 극단값(25 이하·75 이상)일수록 역사적 신뢰도가 높아요.',
    sourceUrl: 'https://edition.cnn.com/markets/fear-and-greed',
    sourceLabel: 'CNN — Fear & Greed Index',
  },
  vix: {
    title: 'VIX 공포 지수',
    description:
      "S&P500 옵션 가격으로 산출한 향후 30일 변동성 기대치예요. 시장이 평온하면 낮고, 불확실성·공포가 커지면 급등해요. '월스트리트의 공포 지표'라고도 불려요.",
    thresholds: [
      { range: '< 15', label: '지나치게 조용 (과신 주의)', sig: 'warn' },
      { range: '15~20', label: '안정적인 시장', sig: 'neutral' },
      { range: '20~30', label: '적당한 긴장 (기회 탐색)', sig: 'good' },
      { range: '30~40', label: '공포 구간 (역발투자 기회)', sig: 'good' },
      { range: '> 40', label: '극단적 공포 (단기 위험·장기 기회)', sig: 'warn' },
    ],
    caveat: 'VIX 40 이상은 단기 추가 하락 위험과 장기 매수 기회가 동시에 존재하는 양면 구간이에요.',
    sourceUrl: 'https://finance.yahoo.com/quote/%5EVIX',
    sourceLabel: 'Yahoo Finance — ^VIX',
  },
  yield_spread: {
    title: '10Y-3M 금리차 (장단기 금리차)',
    description:
      '미국 10년물 국채 금리에서 3개월물 금리를 뺀 값이에요. 0% 아래로 역전되면 1~2년 안에 경기 침체 가능성이 높다고 봐요. 역사적으로 8번 역전 중 7번 경기침체가 뒤따랐어요.',
    thresholds: [
      { range: '> 0.5%', label: '정상 (경기 양호)', sig: 'neutral' },
      { range: '0~0.5%', label: '금리차 축소 (주의)', sig: 'warn' },
      { range: '-0.5~0%', label: '부분 역전 (침체 우려)', sig: 'warn' },
      { range: '< -0.5%', label: '완전 역전 (침체 경고)', sig: 'bad' },
    ],
    caveat:
      '본 대시보드는 FRED DGS10−DGS3MO(둘 다 Constant Maturity)를 사용해요. 기존 yfinance ^IRX(Bank Discount 방식) 근사보다 정확해요.',
    sourceUrl: 'https://fred.stlouisfed.org/series/T10Y3M',
    sourceLabel: 'FRED — 10-Year minus 3-Month Treasury Spread',
  },
  ma200: {
    title: 'S&P500 200일 이동평균 추세',
    description:
      'SPY(S&P500 ETF) 현재가가 최근 200거래일 평균보다 위인지 아래인지로 큰 흐름을 판단해요. 위면 상승추세(강세장), 아래면 하락추세(약세장)로 봐요.',
    thresholds: [
      { range: 'MA200 위', label: '상승추세 (강세장)', sig: 'good' },
      { range: 'MA200 아래', label: '하락추세 (약세장)', sig: 'bad' },
    ],
    caveat:
      '후행 지표라 추세 전환이 어느 정도 진행된 뒤에야 신호가 바뀌어요. 단독으로 매매하기보다 다른 지표와 함께 보세요.',
    sourceUrl: 'https://finance.yahoo.com/quote/SPY/chart',
    sourceLabel: 'Yahoo Finance — SPY 차트',
  },
  cape: {
    title: 'CAPE (Shiller P/E)',
    description:
      '노벨상 수상자 Robert Shiller가 만든 지표예요. 인플레이션 조정한 10년 평균 EPS로 주가 배수를 계산해서, 단기 이익 변동을 평활화해요. 장기 밸류에이션 측정에 사용해요.',
    thresholds: [
      { range: '≤ 20', label: '역사적 저평가', sig: 'good' },
      { range: '20~28', label: '보통 수준', sig: 'neutral' },
      { range: '28~38', label: '다소 고평가', sig: 'warn' },
      { range: '> 38', label: '역사적 고평가', sig: 'bad' },
    ],
    caveat:
      'AQR·IMF 연구에 따르면 단기 타이밍 신호가 아니라 10~20년 장기 수익률 예측 지표예요. 그래서 본 대시보드의 종합 신호 계산에는 포함하지 않아요.',
    sourceUrl: 'https://www.multpl.com/shiller-pe',
    sourceLabel: 'multpl.com — Shiller PE Ratio',
  },
  sp500pe: {
    title: 'S&P500 PER (TTM)',
    description:
      '최근 12개월 실제 EPS 기준으로 계산한 주가 배수예요. CAPE보다 더 빠르게 반응하지만, 단기 이익 변동성에 민감해서 위기 직후엔 왜곡될 수 있어요.',
    thresholds: [
      { range: '≤ 17', label: '역사 평균 이하', sig: 'good' },
      { range: '17~22', label: '적정 수준', sig: 'neutral' },
      { range: '22~28', label: '다소 고평가', sig: 'warn' },
      { range: '> 28', label: '고평가', sig: 'bad' },
    ],
    caveat:
      '코로나·금융위기처럼 일시 이익 충격이 있으면 PER이 비정상적으로 튀어요. 그럴 땐 CAPE를 함께 참고하세요.',
    sourceUrl: 'https://www.multpl.com/s-p-500-pe-ratio',
    sourceLabel: 'multpl.com — S&P 500 P/E Ratio',
  },
  buffett: {
    title: '버핏 지수 (Market Cap / GDP)',
    description:
      '미국 주식 시가총액 합을 명목 GDP로 나눈 값이에요. 워렌 버핏이 시장 거품을 판단할 때 즐겨 쓴 지표라서 그의 이름이 붙었어요.',
    thresholds: [
      { range: '≤ 80%', label: '저평가', sig: 'good' },
      { range: '80~100%', label: '적정 수준', sig: 'neutral' },
      { range: '100~150%', label: '고평가 주의', sig: 'warn' },
      { range: '> 150%', label: '매우 고평가 (버블 경고)', sig: 'bad' },
    ],
    caveat:
      '본 대시보드는 Yahoo ^W5000 ÷ FRED GDP × 100 근사값이에요. GDP는 FRED에서 분기별 자동 반영돼요. (FRED WILL5000PRFC는 2026-05 단종되어 Yahoo ^W5000을 사용)',
    sourceUrl: 'https://www.longtermtrends.net/market-cap-to-gdp-the-buffett-indicator/',
    sourceLabel: 'longtermtrends.net — Buffett Indicator',
  },
  dxy: {
    title: '달러 강세 지수 (DXY)',
    description:
      '유로·엔·파운드·캐나다달러·스웨덴크로나·스위스프랑 6개 주요 통화 대비 미국 달러의 상대 강도예요. 1973년 100을 기준점으로 시작했어요.',
    thresholds: [
      { range: '< 100', label: '달러 약세 (신흥국·상품 유리)', sig: 'good' },
      { range: '100~103', label: '보통', sig: 'neutral' },
      { range: '103~107', label: '달러 강세 (주의)', sig: 'warn' },
      { range: '> 107', label: '달러 매우 강세', sig: 'bad' },
    ],
    caveat:
      '달러 강세는 신흥국 주식·금·원자재에 역풍이 되고, 미국 수출기업 실적에도 부담이 돼요.',
    sourceUrl: 'https://finance.yahoo.com/quote/DX-Y.NYB',
    sourceLabel: 'Yahoo Finance — DX-Y.NYB',
  },
  usdkrw: {
    title: '원달러 환율',
    description:
      '1달러를 사는 데 필요한 원화 금액이에요. 환율이 오르면 원화 가치가 떨어진 것이고, 내리면 원화가 강해진 거예요.',
    thresholds: [
      { range: '≤ 1,280', label: '원화 강세 (안정)', sig: 'good' },
      { range: '1,280~1,350', label: '보통', sig: 'neutral' },
      { range: '1,350~1,420', label: '원화 약세 (주의)', sig: 'warn' },
      { range: '> 1,420', label: '원화 매우 약세', sig: 'bad' },
    ],
    caveat:
      '환율 상승은 외국인 자금 유출 우려가 있지만, 한국 수출기업 실적엔 유리할 수 있어요. 단방향 해석은 위험해요.',
    sourceUrl: 'https://finance.yahoo.com/quote/USDKRW=X',
    sourceLabel: 'Yahoo Finance — USDKRW=X',
  },
  rsi: {
    title: 'RSI (14일 상대강도지수)',
    description:
      "최근 14거래일 동안 상승폭과 하락폭의 비율을 0~100으로 표현해요. Wilder's EMA 방식으로 계산해요. 단기 과열·과매도를 판단하는 가장 유명한 지표예요.",
    thresholds: [
      { range: '≤ 30', label: '과매도 — 반등 가능성', sig: 'good' },
      { range: '30~45', label: '저점 근처', sig: 'good' },
      { range: '45~60', label: '중립', sig: 'neutral' },
      { range: '60~70', label: '과열 주의', sig: 'warn' },
      { range: '> 70', label: '과매수 — 조정 위험', sig: 'bad' },
    ],
    caveat:
      '강한 추세장에서는 RSI가 70 이상이나 30 이하에 오래 머물 수 있어요. RSI만 보고 매매하는 건 위험해요.',
    sourceUrl: 'https://www.investopedia.com/terms/r/rsi.asp',
    sourceLabel: 'Investopedia — Relative Strength Index',
  },
  hy_spread: {
    title: 'HY 회사채 스프레드 (신용 위험)',
    description:
      '투자등급 미만 회사채(정크본드)와 미국채의 금리 차이예요. 회사채 디폴트 위험을 가격으로 반영해서, 신용 위기 가능성을 측정해요. ICE BofA US High Yield Index Option-Adjusted Spread (FRED 코드 BAMLH0A0HYM2) 기준이에요. 10Y-3M 금리차(12~24개월 전 침체 신호)보다 더 빠른 3~6개월 전 신호로 작동해요.',
    thresholds: [
      { range: '< 3%', label: '신용 위험 낮음 (시장 안정)', sig: 'good' },
      { range: '3~5%', label: '정상 범위', sig: 'neutral' },
      { range: '5~7%', label: '신용 스트레스 증가', sig: 'warn' },
      { range: '> 7%', label: '신용 위기 (디폴트 위험 급등)', sig: 'bad' },
    ],
    caveat:
      '역사상 5% 이상 = 시장 우려, 7%+ = 침체/위기 (2008년 21.8%, 2020년 3월 11%까지 급등). S&P500과 강한 역상관 관계.',
    sourceUrl: 'https://fred.stlouisfed.org/series/BAMLH0A0HYM2',
    sourceLabel: 'FRED — ICE BofA US HY OAS',
  },
  ma_cross: {
    title: 'S&P500 추세 강도 (50/200일선)',
    description:
      "SPY의 50일선과 200일선의 위치 관계로 추세의 강도를 판정해요. 50일선이 200일선을 돌파해 위로 가면 '골든 크로스'(강세), 아래로 내려가면 '데드 크로스'(약세)예요. 가격까지 함께 봐서 4단계로 분류해요.",
    thresholds: [
      { range: '가격 > 50선 > 200선', label: '강한 상승추세 (모든 신호 강세)', sig: 'good' },
      { range: '가격 > 200선, 50선 위', label: '상승추세 (단기 조정 가능)', sig: 'neutral' },
      { range: '가격 < 50선 또는 전환 중', label: '약세 신호 (전환 진행)', sig: 'warn' },
      { range: '가격 < 50선 < 200선', label: '강한 하락추세 (모든 신호 약세)', sig: 'bad' },
    ],
    caveat:
      '200일선과 같이 후행 지표예요. 추세 전환의 확정 신호로 좋지만, 전환 직후엔 진입이 늦을 수 있어요.',
    sourceUrl: 'https://finance.yahoo.com/quote/SPY/chart',
    sourceLabel: 'Yahoo Finance — SPY 차트',
  },
  dxy_trend: {
    title: '달러 트렌드 (DXY MA200)',
    description:
      "달러 지수(DXY)가 200일 이동평균보다 위인지 아래인지로 'risk-on/risk-off' 환경을 판정해요. 약달러(MA200 아래)는 신흥국·원자재·주식에 우호적이고, 강달러(MA200 위)는 글로벌 유동성 긴축 신호예요.",
    thresholds: [
      { range: 'DXY < MA200', label: '달러 약세 (위험자산 우호)', sig: 'good' },
      { range: 'DXY > MA200', label: '달러 강세 (위험자산 역풍)', sig: 'warn' },
    ],
    caveat:
      '달러 절대값(100 기준)과 함께 보면 더 정확해요. 강달러 + 상승추세 = 매우 강한 위험자산 역풍.',
    sourceUrl: 'https://finance.yahoo.com/quote/DX-Y.NYB',
    sourceLabel: 'Yahoo Finance — DX-Y.NYB',
  },
  '52w': {
    title: '52주 고저 위치',
    description:
      '지난 1년 최저가(0%)와 최고가(100%) 사이에서 현재가의 위치를 보여줘요. 저점 근처면 싸게 살 가능성, 고점 근처면 추격 매수 위험을 나타내요.',
    thresholds: [
      { range: '≤ 30%', label: '저점 근처 (저가)', sig: 'good' },
      { range: '30~70%', label: '중간 구간', sig: 'neutral' },
      { range: '70~85%', label: '고점 근처 (고가)', sig: 'warn' },
      { range: '> 85%', label: '52주 고점 부근', sig: 'bad' },
    ],
    caveat:
      '추세가 살아있는 종목은 52주 고점을 계속 갱신해요. 단순 진입 회피 기준으로만 쓰면 좋은 기회를 놓칠 수 있어요.',
    sourceUrl: 'https://finance.yahoo.com/',
    sourceLabel: 'Yahoo Finance — 종목별 차트',
  },
};
```

- [ ] **Step 2: 타입체크**

Run: `npx tsc --noEmit`
Expected: 에러 없이 종료 (exit 0)

- [ ] **Step 3: 커밋**

```bash
git add src/lib/indicator-info.ts
git commit -m "indicator-info.ts — 15개 지표 상세 콘텐츠 타입드 상수 (정확성 정정 반영)"
```

---

## Task 2: signal-style.ts 공유 스타일 맵

**Files:**
- Create: `src/lib/signal-style.ts`

현 `index.astro`에 인라인된 `signalBg`/`signalText`를 공유 모듈로 추출 + 한글 배지 라벨 추가 (DRY — 여러 컴포넌트가 사용).

- [ ] **Step 1: 파일 작성**

```ts
import type { SignalKey } from './signal';

export const signalBg: Record<SignalKey, string> = {
  good: 'bg-good/15 border-good/30',
  neutral: 'bg-neutral/15 border-neutral/30',
  warn: 'bg-warn/15 border-warn/30',
  bad: 'bg-bad/15 border-bad/30',
};

export const signalText: Record<SignalKey, string> = {
  good: 'text-good',
  neutral: 'text-muted',
  warn: 'text-warn',
  bad: 'text-bad',
};

export const SIGNAL_KR: Record<SignalKey, string> = {
  good: '긍정',
  neutral: '중립',
  warn: '주의',
  bad: '위험',
};
```

- [ ] **Step 2: 타입체크**

Run: `npx tsc --noEmit`
Expected: exit 0

- [ ] **Step 3: 커밋**

```bash
git add src/lib/signal-style.ts
git commit -m "signal-style.ts — signalBg/signalText/SIGNAL_KR 공유 맵 추출"
```

---

## Task 3: SectionHeading.astro

**Files:**
- Create: `src/components/SectionHeading.astro`

- [ ] **Step 1: 파일 작성**

```astro
---
interface Props {
  emoji: string;
  title: string;
  subtitle?: string;
}
const { emoji, title, subtitle } = Astro.props;
---
<h2 class="text-xs font-semibold text-muted uppercase tracking-widest mb-3">
  <span aria-hidden="true">{emoji}</span> {title}
  {subtitle && (
    <span class="normal-case font-normal opacity-60">({subtitle})</span>
  )}
</h2>
```

- [ ] **Step 2: 빌드 검증**

Run: `npm run build`
Expected: 빌드 성공 (`dist/` 생성, 에러 0). 컴포넌트 미사용 상태라 출력엔 영향 없음.

- [ ] **Step 3: 커밋**

```bash
git add src/components/SectionHeading.astro
git commit -m "SectionHeading.astro — 재사용 섹션 헤더 컴포넌트"
```

---

## Task 4: MacroCard.astro

**Files:**
- Create: `src/components/MacroCard.astro`

구 `_macro_card`의 정보량 복원: 영문 부제·이모지·한글 배지·큰 값·신호 문구·하단 한 줄 힌트+ⓘ. 클릭 시 모달용 `data-*` 속성.

- [ ] **Step 1: 파일 작성**

```astro
---
import type { SignalKey } from '../lib/signal';
import { signalBg, signalText, SIGNAL_KR } from '../lib/signal-style';

interface Props {
  emoji: string;
  en: string;
  title: string;
  value: string;
  signal: SignalKey;
  detail: string;
  hint: string;
  indicatorKey: string;
  current: string;
}
const { emoji, en, title, value, signal, detail, hint, indicatorKey, current } =
  Astro.props;
---
<article
  class={`border rounded-2xl p-4 sm:p-5 flex flex-col gap-3 cursor-pointer hover:bg-surface-hi transition ${signalBg[signal]}`}
  data-indicator={indicatorKey}
  data-current={current}
  data-sig={signal}
  role="button"
  tabindex="0"
  aria-label={`${title} 상세 보기`}
>
  <div class="flex items-start justify-between gap-2">
    <div class="min-w-0">
      <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-0.5 truncate">{en}</div>
      <div class="font-semibold text-text text-sm sm:text-base">
        <span aria-hidden="true">{emoji}</span> {title}
      </div>
    </div>
    <span class={`inline-flex whitespace-nowrap ${signalBg[signal]} ${signalText[signal]} border rounded-full px-2.5 py-0.5 text-xs font-bold`}>
      {SIGNAL_KR[signal]}
    </span>
  </div>
  <div class={`text-2xl sm:text-3xl font-bold ${signalText[signal]}`}>{value}</div>
  <div class={`text-xs sm:text-sm ${signalText[signal]}`}>{detail}</div>
  <div class="mt-auto text-xs text-muted border-t border-border pt-2 flex justify-between items-center gap-2">
    <span class="leading-relaxed">{hint}</span>
    <span class="text-text/40 text-xs shrink-0" aria-hidden="true">ⓘ</span>
  </div>
</article>
```

- [ ] **Step 2: 빌드 검증**

Run: `npm run build`
Expected: 빌드 성공, 에러 0.

- [ ] **Step 3: 커밋**

```bash
git add src/components/MacroCard.astro
git commit -m "MacroCard.astro — 영문부제·배지·힌트·ⓘ 복원 + 모달 data-* 속성"
```

---

## Task 5: EtfCard.astro

**Files:**
- Create: `src/components/EtfCard.astro`

구 `_index_card` 정보량 복원: 가격·등락 배지·52주 게이지 SVG(저점/고점 라벨)·RSI(인라인 힌트)·MA200 추세. RSI/MA200/52주 행이 각각 클릭 가능(모달).

- [ ] **Step 1: 파일 작성**

```astro
---
import type { SignalKey } from '../lib/signal';
import { signalText } from '../lib/signal-style';

interface Props {
  ticker: string;
  name: string;
  priceStr: string;
  changePct: number | null;
  rsi: number | null;
  rsiSignal: SignalKey;
  rsiText: string;
  ma200Above: boolean | null;
  maDiffPct: number | null;
  pos52w: number | null;
  needleX: number;
  needleY: number;
}
const {
  ticker, name, priceStr, changePct, rsi, rsiSignal, rsiText,
  ma200Above, maDiffPct, pos52w, needleX, needleY,
} = Astro.props;

const chg = changePct ?? 0;
const chgStr = `${chg >= 0 ? '▲' : '▼'} ${Math.abs(chg).toFixed(2)}%`;
const maArrow = (maDiffPct ?? 0) >= 0 ? '↑' : '↓';
const maText =
  ma200Above === null ? 'MA200 데이터 부족 (1년 미만)'
  : ma200Above ? '상승추세' : '하락추세';
const maSig: SignalKey =
  ma200Above === null ? 'neutral' : ma200Above ? 'good' : 'bad';
const rsiCurrent = `${name} · RSI ${rsi ?? '—'} · ${rsiText}`;
const maCurrent =
  ma200Above === null
    ? `${name} · MA200 데이터 부족 (1년 미만)`
    : `${name} · ${ma200Above ? '200일선 위' : '200일선 아래'} ${maArrow}${Math.abs(maDiffPct ?? 0).toFixed(1)}% · ${maText}`;
const posCurrent = `${name} · 52주 저점에서 ${(pos52w ?? 50).toFixed(0)}% 위치`;
---
<article class="border border-border bg-surface rounded-2xl p-4 sm:p-5 flex flex-col gap-3">
  <div class="flex items-start justify-between gap-2">
    <div class="min-w-0">
      <div class="font-semibold text-text truncate">{name}</div>
      <div class="text-xs text-muted">{ticker}</div>
    </div>
    {changePct !== null && (
      <span class={`text-xs rounded-full px-2 py-0.5 font-bold whitespace-nowrap shrink-0 ${chg >= 0 ? 'text-good bg-good/15' : 'text-bad bg-bad/15'}`}>
        {chgStr}
      </span>
    )}
  </div>
  <div class="text-2xl font-bold text-text">{priceStr}</div>

  <div class="border-t border-border pt-3 flex flex-col gap-2">
    <div
      class="flex items-center justify-between gap-2 text-xs cursor-pointer hover:bg-surface-hi rounded px-1 -mx-1 py-1 transition"
      data-indicator="rsi" data-current={rsiCurrent} data-sig={rsiSignal}
      role="button" tabindex="0" aria-label="RSI 설명"
    >
      <span class="text-muted min-w-0">
        RSI <span class="font-mono font-bold">{rsi ?? '—'}</span>
        <span class="text-muted/60 hidden sm:inline">(30↓매수·70↑주의)</span>
      </span>
      <span class={`${signalText[rsiSignal]} font-semibold whitespace-nowrap shrink-0`}>{rsiText}</span>
    </div>

    <div
      class="flex items-center justify-between gap-2 text-xs cursor-pointer hover:bg-surface-hi rounded px-1 -mx-1 py-1 transition"
      data-indicator="ma200" data-current={maCurrent} data-sig={maSig}
      role="button" tabindex="0" aria-label="MA200 설명"
    >
      <span class="text-muted min-w-0">
        MA200
        {ma200Above !== null && (
          <span class="font-mono">({maArrow}{Math.abs(maDiffPct ?? 0).toFixed(1)}%)</span>
        )}
      </span>
      <span class={`${signalText[maSig]} font-semibold whitespace-nowrap shrink-0`}>{maText}</span>
    </div>

    {pos52w !== null && (
      <div
        class="mt-0.5 cursor-pointer hover:bg-surface-hi rounded px-1 -mx-1 py-1 transition"
        data-indicator="52w" data-current={posCurrent} data-sig="neutral"
        role="button" tabindex="0" aria-label="52주 위치 설명"
      >
        <svg viewBox="0 0 160 100" class="w-full">
          <path d="M 25 85 A 55 55 0 0 1 135 85" fill="none" stroke="var(--color-border)" stroke-width="10" />
          <line x1="80" y1="85" x2={needleX} y2={needleY} stroke="var(--color-brand)" stroke-width="3" stroke-linecap="round" />
          <circle cx="80" cy="85" r="4" fill="var(--color-brand)" />
          <text x="22" y="98" text-anchor="middle" font-size="9" fill="var(--color-muted)">저점</text>
          <text x="80" y="98" text-anchor="middle" font-size="9" fill="var(--color-muted)">52주 {pos52w}%</text>
          <text x="138" y="98" text-anchor="middle" font-size="9" fill="var(--color-muted)">고점</text>
        </svg>
      </div>
    )}
  </div>
</article>
```

- [ ] **Step 2: 빌드 검증**

Run: `npm run build`
Expected: 빌드 성공, 에러 0.

- [ ] **Step 3: 커밋**

```bash
git add src/components/EtfCard.astro
git commit -m "EtfCard.astro — RSI 인라인힌트·MA200 추세·52주 저점/고점 게이지 복원"
```

---

## Task 6: GaugeFearGreed.astro

**Files:**
- Create: `src/components/GaugeFearGreed.astro`

구 `_gauge` 반원 게이지 복원. 기존 `src/lib/gauge.ts:needleCoords`(NaN-safe, 검증됨) 재사용 — viewBox/좌표계는 `EtfCard`와 동일(중심 80,85 / r 55).

- [ ] **Step 1: 파일 작성**

```astro
---
import { needleCoords } from '../lib/gauge';

interface Props {
  score: number | null;
}
const { score } = Astro.props;
const { nx, ny } = needleCoords(score ?? 50);
---
<div class="border border-border bg-surface rounded-2xl p-4 sm:p-5 flex flex-col items-center justify-center gap-2">
  <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest">공포 & 탐욕 게이지</div>
  {score === null ? (
    <div class="h-20 flex items-center justify-center text-muted text-sm">데이터 없음</div>
  ) : (
    <svg viewBox="0 0 160 110" class="w-full max-w-[240px]" role="img" aria-label={`공포탐욕지수 게이지: 현재 ${score}점`}>
      <defs>
        <linearGradient id="fg-grad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="var(--color-bad)" />
          <stop offset="50%" stop-color="var(--color-warn)" />
          <stop offset="100%" stop-color="var(--color-good)" />
        </linearGradient>
      </defs>
      <path d="M 25 85 A 55 55 0 0 1 135 85" fill="none" stroke="url(#fg-grad)" stroke-width="10" stroke-linecap="round" />
      <line x1="80" y1="85" x2={nx} y2={ny} stroke="var(--color-text)" stroke-width="3" stroke-linecap="round" />
      <circle cx="80" cy="85" r="4" fill="var(--color-text)" />
      <text x="25" y="100" text-anchor="middle" font-size="9" fill="var(--color-muted)">공포</text>
      <text x="80" y="105" text-anchor="middle" font-size="13" font-weight="bold" fill="var(--color-text)">{score}</text>
      <text x="135" y="100" text-anchor="middle" font-size="9" fill="var(--color-muted)">탐욕</text>
    </svg>
  )}
</div>
```

- [ ] **Step 2: 빌드 검증**

Run: `npm run build`
Expected: 빌드 성공, 에러 0.

- [ ] **Step 3: 커밋**

```bash
git add src/components/GaugeFearGreed.astro
git commit -m "GaugeFearGreed.astro — 반원 공포·탐욕 게이지 SVG 복원"
```

---

## Task 7: CompositeSignal.astro

**Files:**
- Create: `src/components/CompositeSignal.astro`

종합 신호등 dot + 라벨 + 코멘트 + 4카운트 + **7개 컴포넌트 배지(각 클릭→해당 지표 모달)** + 방법론 줄. 카드 본체 클릭 시 `overall` 모달.

`composite.signals` 순서는 고정(`[공포·탐욕, VIX, 10Y-3M, S&P500 MA200, MA Cross, HY Spread, DXY Trend]`). 각 배지의 `data-indicator` 키 매핑은 props로 받는다(index.astro가 책임).

- [ ] **Step 1: 파일 작성**

```astro
---
import type { SignalKey } from '../lib/signal';
import { signalBg, signalText } from '../lib/signal-style';

interface BadgeItem {
  name: string;
  key: SignalKey;
  text: string;
  indicatorKey: string;
}
interface Props {
  signalKey: SignalKey;
  label: string;
  comment: string;
  good: number;
  neutral: number;
  warn: number;
  bad: number;
  badges: BadgeItem[];
}
const { signalKey, label, comment, good, neutral, warn, bad, badges } =
  Astro.props;
const overallCurrent = `긍정 ${good} · 중립 ${neutral} · 주의 ${warn} · 위험 ${bad} → ${label}`;
---
<section
  class={`mb-8 border rounded-2xl p-6 cursor-pointer hover:bg-surface-hi transition ${signalBg[signalKey]}`}
  data-indicator="overall"
  data-current={overallCurrent}
  data-sig={signalKey}
  role="button"
  tabindex="0"
  aria-label="종합 신호 판단 근거 보기"
>
  <div class="flex items-center justify-between flex-wrap gap-3">
    <div class="flex items-center gap-4 min-w-0">
      <div class={`w-12 h-12 rounded-full shrink-0 border-2 flex items-center justify-center ${signalBg[signalKey]}`}>
        <div class={`w-5 h-5 rounded-full ${signalText[signalKey]}`} style="background:currentColor"></div>
      </div>
      <div class="min-w-0">
        <h2 class={`text-2xl font-bold ${signalText[signalKey]}`}>📊 {label}</h2>
        <p class="text-text/90 mt-1 text-sm leading-relaxed">{comment}</p>
      </div>
    </div>
    <div class="grid grid-cols-4 gap-3 text-center shrink-0">
      <div><div class="text-good font-bold text-lg">{good}</div><div class="text-muted text-[10px] mt-0.5">긍정</div></div>
      <div><div class="text-muted font-bold text-lg">{neutral}</div><div class="text-muted text-[10px] mt-0.5">중립</div></div>
      <div><div class="text-warn font-bold text-lg">{warn}</div><div class="text-muted text-[10px] mt-0.5">주의</div></div>
      <div><div class="text-bad font-bold text-lg">{bad}</div><div class="text-muted text-[10px] mt-0.5">위험</div></div>
    </div>
  </div>

  <div class="mt-5 pt-5 border-t border-border">
    <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-3">판단 근거 — 7개 컴포넌트</div>
    <div class="flex flex-wrap gap-2">
      {badges.map(b => (
        <button
          type="button"
          class={`text-xs border rounded-full px-3 py-1 ${signalBg[b.key]} ${signalText[b.key]} font-semibold`}
          data-indicator={b.indicatorKey}
          data-current={`${b.name} · ${b.text}`}
          data-sig={b.key}
          aria-label={`${b.name} 상세 보기`}
        >
          {b.name}: {b.text}
        </button>
      ))}
    </div>
    <p class="text-[11px] sm:text-xs text-muted mt-3 leading-relaxed">
      계산: 각 매수 +1·중립 0·주의 -1·위험 -2 합산 → 임계값 비교. 카드 빈 공간 클릭 시 방법론 상세.
    </p>
  </div>
</section>
```

> **참고:** 배지는 `<button>`이며 카드 본체(`<section>`)도 클릭 가능하다. Task 13의 모달 스크립트는 클릭된 요소에서 가장 가까운 `[data-indicator]`를 `event.target.closest('[data-indicator]')`로 찾으므로, 배지 클릭 시 배지의 키가, 빈 공간 클릭 시 `overall`이 열린다(이벤트 버블링 + closest 우선순위).

- [ ] **Step 2: 빌드 검증**

Run: `npm run build`
Expected: 빌드 성공, 에러 0.

- [ ] **Step 3: 커밋**

```bash
git add src/components/CompositeSignal.astro
git commit -m "CompositeSignal.astro — 신호등 dot·4카운트·7컴포넌트 배지·방법론 복원"
```

---

## Task 8: Glossary.astro

**Files:**
- Create: `src/components/Glossary.astro`

구 `_guide` 16개 용어 가이드 복원. `<details>`/`<summary>` 네이티브 접이식 (JS 0). 16개 항목 데이터는 컴포넌트 내부 상수.

- [ ] **Step 1: 파일 작성**

```astro
---
const GUIDE: { emoji: string; term: string; short: string; detail: string }[] = [
  { emoji: '🎯', term: '타이밍 신호란?', short: '종합 신호를 구성하는 7개 지표 소개',
    detail: '이 대시보드의 종합 신호는 CNN Fear & Greed(7-component composite)와 Goldman Sachs Bull/Bear Indicator(6-component) 방법론을 참고해 7개 지표로 구성했어요: ① 심리(CNN F&G) ② 변동성(VIX) ③ 경기(10Y-3M 금리차) ④ 시장 추세(S&P500 MA200) ⑤ 추세 강도(50/200 cross) ⑥ 신용(HY 회사채 스프레드) ⑦ 통화(DXY 트렌드). 각 지표를 매수/중립/주의/위험 4단계로 분류하고 합산해서 종합 신호를 만들어요. 학술 연구(AQR, IMF)에 따라 CAPE 같은 밸류에이션 지표는 10~20년 장기 예측에 적합해서 종합 신호에서 제외하고 참고 지표로만 표시해요.' },
  { emoji: '😨', term: '공포 & 탐욕 지수', short: '투자자 심리를 0~100으로 표시',
    detail: "0에 가까울수록 사람들이 무서워서 내다 팔고, 100에 가까우면 욕심을 부리며 사고 있는 상태예요. 워렌 버핏은 '남들이 탐욕스러울 때 두려워하고, 두려울 때 탐욕스러워져라'라고 했어요. 25 이하 극도의 공포 구간은 역사적으로 이후 수익률이 높게 나타나는 경향이 있어요." },
  { emoji: '🌊', term: 'VIX (공포 지수)', short: '시장이 얼마나 출렁일지 예측',
    detail: '다음 30일간 주가 변동을 옵션 시장에서 예측해요. 15 이하면 너무 조용한 시장(과신 주의), 20~30이면 적당한 긴장, 30~40이면 공포 구간이에요. 역설적으로 VIX 30~40 구간은 역발투자 관점에서 좋은 매수 기회인 경우가 많아요.' },
  { emoji: '📉', term: '금리차 (10Y-3M)', short: '경기침체 조기 경보',
    detail: '미국 10년 국채금리에서 3개월 국채금리를 뺀 값이에요. 이게 0 아래로 뒤집어지면(역전) 1~2년 안에 경기침체가 올 수 있어요. 과거에 8번 역전 중 7번 경기침체가 왔어요.' },
  { emoji: '📏', term: 'S&P500 추세 (MA200)', short: '지금 강세장인지 약세장인지',
    detail: 'S&P 500 ETF(SPY)가 200일 이동평균선보다 높으면 상승추세(강세장), 낮으면 하락추세(약세장)예요. 단기 등락이 아닌 큰 흐름을 보여주는 지표로, CNN·OECD 등 주요 복합 지수가 공통으로 포함하는 모멘텀 카테고리예요.' },
  { emoji: '⚡', term: '추세 강도 (50/200 cross)', short: '추세가 얼마나 강하고 가속 중인지',
    detail: "200일선만 보면 강세장·약세장 이진 판단만 가능해요. 50일선까지 함께 보면 강한 상승(가격>50선>200선) / 상승(50선 위·200선 아래 또는 그 반대) / 약세 / 강한 하락 4단계로 더 세밀하게 판정할 수 있어요. 50선이 200선을 위로 돌파하는 'Golden Cross'는 강한 상승 전환 신호로 유명해요." },
  { emoji: '🏦', term: 'HY 회사채 스프레드', short: '신용 위기 조기 경보 (가장 빠른 침체 신호)',
    detail: '투자등급 미만 회사채(정크본드)와 미국채의 금리 차이예요. 회사들이 디폴트 위험을 시장에서 어떻게 평가하는지 보여줘요. 10Y-3M 금리차가 12~24개월 전 침체 신호라면, HY 스프레드는 3~6개월 전 신호로 더 빠르고 정확해요. 역사상 2008년 21.8%, 2020년 3월 11%까지 급등했어요. S&P500과 강한 역상관 관계예요.' },
  { emoji: '🌍', term: '달러 트렌드 (DXY MA200)', short: '위험자산 환경 판정',
    detail: '달러 지수(DXY)가 200일선 아래면 약달러 추세 = 위험자산(주식·신흥국·원자재) 우호적 환경이에요. 위면 강달러 = 글로벌 유동성 긴축 신호로, 미국 외 주식·금·원자재에 역풍이에요. 달러 절대값이 아닌 추세 방향이 중요해요.' },
  { emoji: '📊', term: 'CAPE (Shiller PE)', short: '주식이 역사적으로 비싼지 확인 (장기 맥락용)',
    detail: '10년 평균 이익 기준으로 주가 수준을 봐요. 역사 평균이 약 17이에요. 38을 넘으면 역사적으로 매우 비싼 수준이에요. 단, 현대 시장은 저금리 시대를 거쳐 구조적으로 높아졌어요. 이 지표는 10~20년 장기 수익률 예측에 유용하지만, 단기 타이밍 신호로는 적합하지 않아요.' },
  { emoji: '📈', term: 'S&P500 PER', short: '지금 당장의 실적 대비 주가 수준 (장기 맥락용)',
    detail: '최근 12개월 실제 이익 기준으로 주가가 얼마나 비싼지 봐요. CAPE보다 더 빠르게 반응해요. 역사 평균은 약 16~17이고, 25 이상이면 고평가 신호예요.' },
  { emoji: '🏦', term: '버핏 지수', short: '전체 시장의 거품 확인 (장기 맥락용)',
    detail: '시장 시가총액을 GDP로 나눈 값이에요. 워렌 버핏이 즐겨 쓰는 지표예요. 100%가 적정 수준, 150%를 넘으면 고평가 주의, 200%를 넘으면 버블 경고예요. ※ 이 대시보드는 Wilshire 5000 지수 기반 근사값이에요.' },
  { emoji: '💵', term: '달러 강세 지수 (DXY)', short: '달러 강도가 투자에 미치는 영향',
    detail: '달러가 강하면 원화가 약해지고 외국인이 한국 주식을 팔기도 해요. 금·원유 가격도 달러와 반대로 움직이는 경우가 많아요. 100이 기준선이에요.' },
  { emoji: '🇰🇷', term: '원달러 환율', short: '원화 가치와 한국 시장 영향',
    detail: '환율이 오르면 원화 가치가 떨어진 거예요. 1,350원 이상이면 외국인 자금 이탈 우려가 커져요. 해외 주식 투자 시 환율이 오르면 달러 자산 가치가 원화 기준으로 올라가 유리하기도 해요.' },
  { emoji: '📈', term: 'RSI', short: '지금 너무 오른 건지 너무 떨어진 건지',
    detail: '최근 14일간 오른 폭과 떨어진 폭을 비교해요. 30 이하면 너무 많이 떨어진 상태(반등 가능성), 70 이상이면 너무 오른 상태(조정 가능성)예요. 단, RSI만 보고 바로 매매하는 건 위험해요.' },
  { emoji: '📏', term: 'MA200 (200일 이동평균)', short: '개별 종목의 추세 확인',
    detail: '최근 200일 평균 주가예요. 현재가가 이 선 위면 상승추세, 아래면 하락추세로 봐요. 후행 지표라 하락이 많이 진행된 뒤에야 신호가 나와요. 다른 지표와 함께 참고하세요.' },
  { emoji: '📍', term: '52주 고저 위치', short: '1년 기준으로 지금 가격이 저렴한지',
    detail: '지난 1년 최저가(0%)와 최고가(100%) 사이에서 현재가 위치예요. 30% 이하면 저점 근처(싸게 살 가능성), 80% 이상이면 고점 근처(비싸게 사는 위험)예요.' },
];
---
<div class="flex flex-col gap-2">
  {GUIDE.map(g => (
    <details class="border border-border rounded-xl overflow-hidden">
      <summary class="flex items-center gap-3 p-3 sm:p-4 hover:bg-surface-hi transition-colors min-h-[48px] cursor-pointer">
        <span class="font-semibold text-text text-sm shrink-0">
          <span aria-hidden="true">{g.emoji}</span> {g.term}
        </span>
        <span class="text-muted text-xs flex-1 hidden sm:inline truncate">{g.short}</span>
      </summary>
      <div class="px-3 sm:px-4 pb-3 sm:pb-4 pt-3 text-sm text-muted leading-relaxed border-t border-border">
        {g.detail}
      </div>
    </details>
  ))}
</div>
```

- [ ] **Step 2: 빌드 검증**

Run: `npm run build`
Expected: 빌드 성공, 에러 0.

- [ ] **Step 3: 커밋**

```bash
git add src/components/Glossary.astro
git commit -m "Glossary.astro — 16개 초보자 용어 가이드 <details> 복원"
```

---

## Task 9: Header.astro + Footer.astro

**Files:**
- Create: `src/components/Header.astro`
- Create: `src/components/Footer.astro`

헤더 부제 복원 + 기존 테마 토글 유지. 푸터(데이터 출처 + 면책) 신규 복원.

- [ ] **Step 1: Header.astro 작성**

```astro
---
interface Props {
  generatedKst: string;
}
const { generatedKst } = Astro.props;
---
<header class="mb-8 flex items-start justify-between gap-4">
  <div>
    <h1 class="text-2xl sm:text-3xl font-bold tracking-tight">
      <span aria-hidden="true">📊</span> 투자 지표 대시보드
    </h1>
    <p class="text-sm text-muted mt-1">주식 초보자를 위한 투자 타이밍 신호등</p>
    <p class="text-xs text-muted mt-2 inline-flex items-center gap-1.5">
      <span class="w-1.5 h-1.5 rounded-full bg-good shrink-0" aria-hidden="true"></span>
      최종 업데이트: {generatedKst} KST
    </p>
  </div>
  <button id="theme-toggle" type="button" aria-label="다크/라이트 모드 전환"
    class="shrink-0 rounded-full p-2 text-muted hover:text-text hover:bg-surface-hi transition">
    <span class="dark-icon">☀️</span>
    <span class="light-icon">🌙</span>
  </button>
</header>
```

- [ ] **Step 2: Footer.astro 작성**

```astro
---
---
<footer class="text-center text-xs text-muted border-t border-border pt-6 mt-10 leading-relaxed">
  <p>데이터 출처: CNN · multpl.com · Yahoo Finance · FRED (US Treasury/세인트루이스 연은)</p>
  <p class="mt-1">이 대시보드는 참고용이며 투자 권유가 아닙니다. 투자 판단은 본인 책임이에요.</p>
</footer>
```

- [ ] **Step 3: 빌드 검증**

Run: `npm run build`
Expected: 빌드 성공, 에러 0.

- [ ] **Step 4: 커밋**

```bash
git add src/components/Header.astro src/components/Footer.astro
git commit -m "Header.astro 부제 복원 + Footer.astro 출처·면책 복원"
```

---

## Task 10: IndicatorModal.astro + global.css 중앙정렬 수정

**Files:**
- Create: `src/components/IndicatorModal.astro`
- Modify: `src/styles/global.css` (html,body 블록 뒤에 추가)

리치 모달 마크업 + 중앙정렬 버그 수정. 모달 데이터/배선 스크립트는 **번들 모듈 `<script>`**(is:inline 아님)가 `INDICATOR_INFO`를 직접 import — JSON 임베드·`set:html`·`innerHTML` 미사용(CLAUDE.md 보안 규칙 준수). 주입은 전부 `textContent`.

- [ ] **Step 1: global.css에 중앙정렬 CSS 추가**

`src/styles/global.css` 맨 끝(현재 58행 `html, body { ... }` 블록 뒤)에 추가:

```css

#indicator-modal {
  background: var(--color-surface);
  color: var(--color-text);
}
#indicator-modal[open] {
  position: fixed;
  inset: 0;
  margin: auto;
}
#indicator-modal::backdrop {
  background: rgb(0 0 0 / 0.6);
}
```

> **버그 원인:** Tailwind v4 preflight가 `<dialog>`의 UA 기본 중앙정렬(`margin:auto`)을 무력화해 좌상단에 고정됨. 위 `#indicator-modal[open]{position:fixed;inset:0;margin:auto}`가 명시적으로 재중앙정렬한다.

- [ ] **Step 2: IndicatorModal.astro 작성**

```astro
---
---
<dialog id="indicator-modal" aria-labelledby="modal-title" class="border border-border rounded-2xl p-0 max-w-2xl w-[92vw] max-h-[90vh]">
  <div class="sticky top-0 bg-surface flex items-center justify-between p-4 sm:p-5 border-b border-border">
    <h2 id="modal-title" class="text-base sm:text-xl font-bold text-text pr-2 min-w-0"></h2>
    <button id="modal-close" type="button" aria-label="닫기"
      class="text-muted hover:text-text text-2xl leading-none w-10 h-10 flex items-center justify-center rounded-full hover:bg-surface-hi transition shrink-0">×</button>
  </div>
  <div class="p-4 sm:p-5 flex flex-col gap-4 overflow-y-auto">
    <div class="bg-surface-hi rounded-xl p-3 sm:p-4 border border-border">
      <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-1">현재 수치</div>
      <div id="modal-current" class="text-base sm:text-xl font-bold break-words text-text"></div>
    </div>
    <div>
      <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-2">이 지표가 뭔가요?</div>
      <p id="modal-description" class="text-sm text-text leading-relaxed"></p>
    </div>
    <div>
      <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-2">어떻게 읽나요?</div>
      <table class="w-full text-sm">
        <tbody id="modal-thresholds"></tbody>
      </table>
    </div>
    <div>
      <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-2">⚠️ 주의사항</div>
      <p id="modal-caveat" class="text-sm text-muted leading-relaxed"></p>
    </div>
    <div class="pt-3 border-t border-border">
      <div class="text-[10px] sm:text-xs text-muted uppercase tracking-widest mb-2">검증 / 원본 데이터</div>
      <a id="modal-source" target="_blank" rel="noopener noreferrer"
        class="inline-flex items-center gap-2 text-sm text-good hover:underline break-all min-h-[36px]"></a>
    </div>
  </div>
</dialog>

<script>
  import { INDICATOR_INFO } from '../lib/indicator-info';
  import { signalText } from '../lib/signal-style';

  const dlg = document.getElementById('indicator-modal') as HTMLDialogElement | null;
  const elTitle = document.getElementById('modal-title');
  const elCurrent = document.getElementById('modal-current');
  const elDesc = document.getElementById('modal-description');
  const elTbody = document.getElementById('modal-thresholds');
  const elCaveat = document.getElementById('modal-caveat');
  const elSource = document.getElementById('modal-source') as HTMLAnchorElement | null;
  const elClose = document.getElementById('modal-close');

  if (dlg && elTitle && elCurrent && elDesc && elTbody && elCaveat && elSource && elClose) {
    function openFor(trigger: Element) {
      const key = trigger.getAttribute('data-indicator') || '';
      const info = INDICATOR_INFO[key];
      if (!info) return;

      elTitle.textContent = info.title;
      elCurrent.textContent = trigger.getAttribute('data-current') || '—';
      elDesc.textContent = info.description;
      elCaveat.textContent = info.caveat;
      elSource.textContent = info.sourceLabel;
      elSource.href = info.sourceUrl;

      elTbody.textContent = '';
      for (const t of info.thresholds) {
        const tr = document.createElement('tr');
        tr.className = 'border-b border-border last:border-0';
        const tdR = document.createElement('td');
        tdR.className = 'py-2 pr-3 font-mono text-muted whitespace-nowrap align-top';
        tdR.textContent = t.range;
        const tdL = document.createElement('td');
        tdL.className = `py-2 ${signalText[t.sig]}`;
        tdL.textContent = t.label;
        tr.append(tdR, tdL);
        elTbody.appendChild(tr);
      }
      dlg.showModal();
    }

    document.addEventListener('click', e => {
      const trigger = (e.target as Element | null)?.closest('[data-indicator]');
      if (trigger) openFor(trigger);
    });
    // 키보드 접근성: role="button" 트리거(div/article/section)는 Space/Enter로 click이
    // 발생하지 않으므로 keydown을 직접 처리. 네이티브 <button> 배지는 click으로 충분.
    document.addEventListener('keydown', e => {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      const el = e.target as Element | null;
      if (!el || el.tagName === 'BUTTON' || el.tagName === 'A') return;
      const trigger = el.closest('[data-indicator]');
      if (trigger) {
        e.preventDefault();
        openFor(trigger);
      }
    });

    elClose.addEventListener('click', () => dlg.close());
    dlg.addEventListener('click', e => {
      if (e.target === dlg) dlg.close();
    });
  }
</script>
```

> **보안 메모:** 모듈 `<script>`가 `INDICATOR_INFO`를 직접 import하므로 JSON 임베드/이스케이프 이슈가 없다. 모든 텍스트는 `textContent`, 표 행은 `createElement`로 생성 — `innerHTML`/`set:html` 미사용. 배경(backdrop) 클릭은 `e.target === dlg`로 감지(네이티브 dialog 패턴).

- [ ] **Step 3: 빌드 검증**

Run: `npm run build`
Expected: 빌드 성공, 에러 0. (모달은 아직 페이지에 미배치 — Task 11에서 배치)

- [ ] **Step 4: 커밋**

```bash
git add src/components/IndicatorModal.astro src/styles/global.css
git commit -m "IndicatorModal.astro 리치 모달 + global.css 중앙정렬 버그 수정"
```

---

## Task 11: index.astro 재작성 (조립)

**Files:**
- Modify: `src/pages/index.astro` (전체 재작성)

모든 컴포넌트를 조립. 데이터 가공은 `signalColor` + `computeComposite` 사용. 타이밍 7카드는 `composite.signals`(고정 순서)로 신호 일관성 보장, 밸류에이션 5카드는 `signalColor` 직접 호출.

- [ ] **Step 1: index.astro 전체 교체**

```astro
---
import Base from '../layouts/Base.astro';
import { computeComposite, signalColor } from '../lib/signal';
import { fmtKST, fmtNumber, fmtPercent } from '../lib/format';
import { needleCoords } from '../lib/gauge';
import data from '../data/latest.json';
import Header from '../components/Header.astro';
import SectionHeading from '../components/SectionHeading.astro';
import CompositeSignal from '../components/CompositeSignal.astro';
import GaugeFearGreed from '../components/GaugeFearGreed.astro';
import MacroCard from '../components/MacroCard.astro';
import EtfCard from '../components/EtfCard.astro';
import Glossary from '../components/Glossary.astro';
import Footer from '../components/Footer.astro';
import IndicatorModal from '../components/IndicatorModal.astro';

const composite = computeComposite(data);
const generatedKst = fmtKST(data.generated_at);

// 종합 신호 7개 컴포넌트 → 배지 (composite.signals 고정 순서와 1:1)
const badgeKeys = [
  'fear_greed', 'vix', 'yield_spread', 'ma200', 'ma_cross', 'hy_spread', 'dxy_trend',
];
const badges = composite.signals.map((s, i) => ({
  name: s.name,
  key: s.key,
  text: s.text,
  indicatorKey: badgeKeys[i],
}));

// ── 타이밍 카드 7개 (composite.signals 고정 순서) ──
const fgScore = data.fear_greed?.score ?? null;
const ysVal = data.yield_spread?.spread ?? null;
const dxyAbove = data.dxy?.above_ma200 ?? null;

const MA_CROSS_KR: Record<string, string> = {
  strong_bull: '강한 상승추세', bull: '상승추세', bear: '약세 전환', strong_bear: '강한 하락추세',
};

const timingValues = [
  fgScore !== null ? `${fgScore} · ${data.fear_greed?.rating ?? ''}` : '—',
  fmtNumber(data.vix, 2),
  ysVal !== null ? `${ysVal >= 0 ? '+' : ''}${ysVal.toFixed(2)}` : '—',
  data.sp500_trend === null ? '—'
    : `${data.sp500_trend ? '200일선 위' : '200일선 아래'}${data.sp500_trend_pct !== null ? ` ${data.sp500_trend_pct >= 0 ? '↑' : '↓'}${Math.abs(data.sp500_trend_pct).toFixed(1)}%` : ''}`,
  data.sp500_ma_cross ? (MA_CROSS_KR[data.sp500_ma_cross] ?? '—') : '—',
  fmtPercent(data.hy_spread, 2),
  dxyAbove === null ? '—' : dxyAbove ? '200일선 위 (강달러)' : '200일선 아래 (약달러)',
];
const timingMeta = [
  { emoji: '😨', en: 'FEAR & GREED', title: '공포·탐욕 지수', hint: '투자자 심리 0~100. 낮을수록 공포(매수 기회), 높을수록 탐욕(고점 경고)' },
  { emoji: '🌊', en: 'VIX', title: 'VIX 변동성', hint: '향후 30일 변동성 기대치. 낮으면 과신, 30~40은 역발투자 기회' },
  { emoji: '📉', en: 'YIELD SPREAD', title: '10Y-3M 금리차', hint: '10년−3개월 국채 금리차. 0 아래 역전 시 1~2년 내 침체 신호' },
  { emoji: '📏', en: 'S&P500 MA200', title: 'S&P500 추세', hint: 'SPY가 200일선 위면 강세장, 아래면 약세장' },
  { emoji: '⚡', en: 'MA CROSS', title: '추세 강도', hint: '50일·200일선 위치로 추세 강도 4단계 판정' },
  { emoji: '🏦', en: 'HY SPREAD', title: 'HY 회사채 스프레드', hint: '정크본드 가산금리. 신용 위기 3~6개월 선행 신호' },
  { emoji: '🌍', en: 'DXY TREND', title: '달러 트렌드', hint: '달러가 200일선 아래면 위험자산 우호, 위면 역풍' },
];
const timingCards = composite.signals.map((s, i) => ({
  ...timingMeta[i],
  value: timingValues[i],
  signal: s.key,
  detail: s.text,
  indicatorKey: badgeKeys[i],
  current: `${timingValues[i]} · ${s.text}`,
}));

// ── 밸류에이션 카드 5개 (signalColor 직접) ──
const dxyVal = data.dxy?.value ?? null;
const valuationDefs = [
  { emoji: '📊', en: 'SHILLER P/E', title: 'CAPE', key: 'cape' as const, value: fmtNumber(data.cape, 1), raw: data.cape, hint: '10년 평균 이익 기준 주가 배수. 장기 밸류에이션 (종합 신호 제외)' },
  { emoji: '📈', en: 'S&P500 PER', title: 'S&P500 PER', key: 'sp500pe' as const, value: fmtNumber(data.sp500_pe, 1), raw: data.sp500_pe, hint: '최근 12개월 이익 기준 주가 배수 (종합 신호 제외)' },
  { emoji: '🏦', en: 'BUFFETT', title: '버핏 지수', key: 'buffett' as const, value: fmtPercent(data.buffett, 1), raw: data.buffett, hint: '시가총액÷GDP. 시장 거품 판단 (종합 신호 제외)' },
  { emoji: '💵', en: 'DOLLAR INDEX', title: '달러 인덱스', key: 'dxy' as const, value: fmtNumber(dxyVal, 2), raw: dxyVal, hint: '주요 6개 통화 대비 달러 강도. 100 기준 (종합 신호 제외)' },
  { emoji: '🇰🇷', en: 'USD/KRW', title: '원달러 환율', key: 'usdkrw' as const, value: fmtNumber(data.usdkrw, 2), raw: data.usdkrw, hint: '원달러 환율. 상승 시 원화 약세 (종합 신호 제외)' },
];
const valuationCards = valuationDefs.map(d => {
  const [k, t] = signalColor(d.key, d.raw);
  return {
    emoji: d.emoji, en: d.en, title: d.title, value: d.value,
    signal: k, detail: t, hint: d.hint,
    indicatorKey: d.key, current: `${d.value} · ${t}`,
  };
});

// ── ETF 카드 ──
const etfs = data.tickers.map(tk => {
  const [rk, rt] = signalColor('rsi', tk.rsi);
  const { nx, ny } = needleCoords(tk.pos_52w ?? 50);
  return {
    ticker: tk.ticker, name: tk.name, priceStr: tk.price_str,
    changePct: tk.change_pct, rsi: tk.rsi, rsiSignal: rk, rsiText: rt,
    ma200Above: tk.ma200_above, maDiffPct: tk.ma200_diff_pct,
    pos52w: tk.pos_52w, needleX: nx, needleY: ny,
  };
});
---
<Base>
  <main class="mx-auto max-w-screen-lg px-4 py-6 sm:py-10">
    <Header generatedKst={generatedKst} />

    <CompositeSignal
      signalKey={composite.key}
      label={composite.label}
      comment={composite.comment}
      good={composite.good}
      neutral={composite.neutral}
      warn={composite.warn}
      bad={composite.bad}
      badges={badges}
    />

    <SectionHeading emoji="🎯" title="타이밍 신호" subtitle="종합 신호 구성 7개 지표 — CNN F&G·Goldman 모델 참고" />
    <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
      <GaugeFearGreed score={fgScore} />
      {timingCards.map(c => <MacroCard {...c} />)}
    </section>

    <div class="bg-surface/60 border border-border rounded-xl px-4 py-3 mb-3 flex items-start gap-2">
      <span class="text-sm shrink-0" aria-hidden="true">💡</span>
      <p class="text-xs text-muted leading-relaxed">
        아래 지표는 <strong class="text-text">장기 투자 맥락</strong>을 보여줘요. 주식이 역사적으로 비싼지 싼지 가늠하는 용도예요. 오늘 바로 사고팔 타이밍 신호가 아니라서 종합 신호 계산에는 포함하지 않아요.
      </p>
    </div>
    <SectionHeading emoji="💰" title="밸류에이션 & 참고 지표" subtitle="장기 맥락용" />
    <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
      {valuationCards.map(c => <MacroCard {...c} />)}
    </section>

    <SectionHeading emoji="📈" title="지수 & ETF 현황" />
    <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
      {etfs.map(e => <EtfCard {...e} />)}
    </section>

    <SectionHeading emoji="📖" title="초보자 용어 가이드" />
    <Glossary />

    <Footer />
  </main>

  <IndicatorModal />

  <script is:inline>
    document.getElementById('theme-toggle')?.addEventListener('click', function () {
      var html = document.documentElement;
      var toLight = !html.classList.contains('light');
      html.classList.toggle('light', toLight);
      html.classList.toggle('dark', !toLight);
      try { localStorage.setItem('theme', toLight ? 'light' : 'dark'); } catch (e) {}
    });
  </script>
</Base>
```

> **참고:** 테마 토글 인라인 스크립트는 기존 동작 보존(`Base.astro`의 no-FOUC 스크립트와 짝). 모달 스크립트는 `IndicatorModal.astro` 내부 모듈 스크립트가 `document`에 위임 리스너를 걸므로 index.astro에서 별도 배선 불필요.

- [ ] **Step 2: 빌드 검증**

Run: `npm run build`
Expected: 빌드 성공, 에러 0. `dist/index.html`에 모든 섹션 렌더.

- [ ] **Step 3: 타입체크**

Run: `npx tsc --noEmit`
Expected: exit 0 (props 타입 불일치 없음)

- [ ] **Step 4: 커밋**

```bash
git add src/pages/index.astro
git commit -m "index.astro — 컴포넌트 조립 레이어로 재작성, 정보량 100% 복원"
```

---

## Task 12: CLAUDE.md 갱신

**Files:**
- Modify: `src/pages/index.astro` 관련 서술이 있는 `projects/stock-dashboard/CLAUDE.md`

설계서 7절: "컴포넌트 분해 의도적 안 함 — 후속 PR로 이연" 서술을 분해 완료로 갱신.

- [ ] **Step 1: CLAUDE.md 해당 문장 수정**

`projects/stock-dashboard/CLAUDE.md`에서 다음 문장을 찾는다:

> `src/pages/index.astro`가 가장 큰 파일. `signalColor()`로 각 값의 신호 키(`good`/`neutral`/`warn`/`bad`)+한국어 설명을 얻어 카드 조립. 컴포넌트 분해는 의도적으로 안 함 — 후속 UI 개편 PR로 이연(단일 페이지 유지).

다음으로 교체:

> `src/pages/index.astro`는 데이터를 `signalColor()`/`computeComposite()`로 가공해 `src/components/*.astro`에 props로 내려주는 얇은 조립 레이어. 컴포넌트 맵: `Header`·`SectionHeading`·`CompositeSignal`·`GaugeFearGreed`·`MacroCard`·`EtfCard`·`Glossary`·`Footer`·`IndicatorModal`. 모달 콘텐츠는 `src/lib/indicator-info.ts`, 신호 스타일 맵은 `src/lib/signal-style.ts`. 모달은 네이티브 `<dialog>` + `global.css`의 `#indicator-modal[open]{margin:auto}` 중앙정렬 (Tailwind preflight가 UA 기본 중앙정렬을 무력화하므로 명시 필요).

- [ ] **Step 2: 빌드 검증 (회귀 없음 확인)**

Run: `npm run build`
Expected: 빌드 성공 (문서 변경이라 영향 없음, 안전 확인용)

- [ ] **Step 3: 커밋하지 않음 (수정 정정)**

`projects/stock-dashboard/CLAUDE.md`는 `.gitignore:32`에 의해 의도적으로 추적 제외됨
("개인 메모 / Claude Code 설정 — public repo 노출 방지"). 따라서 **커밋하지 않고
디스크 상의 내용만 갱신**한다. `git add -f`로 강제 추적 금지 (저장소 컨벤션 위반 +
public repo 노출). 이 태스크의 산출물은 로컬 CLAUDE.md 파일 갱신뿐 — git 변경 없음.

---

## Task 13: 최종 검증 (빌드 + Playwright 실브라우저)

**Files:** 없음 (검증 전용)

설계서 9절 검증 체크리스트 수행. Playwright는 `playwright-cli` 스킬 또는 playwright MCP 사용.

- [ ] **Step 1: 클린 빌드**

Run: `npm run build`
Expected: 빌드 성공, 에러·경고 0. `dist/index.html` 생성.

- [ ] **Step 2: 프리뷰 서버 기동**

Run: `npm run preview` (백그라운드, 기본 `http://localhost:4321`)
Expected: 서버 기동

- [ ] **Step 3: Playwright 검증 — 다음 항목을 순서대로 확인**

1. 페이지 로드 → 콘솔 에러 0 (`browser_console_messages`)
2. 헤더 부제 "주식 초보자를 위한 투자 타이밍 신호등" 표시
3. 종합 신호 카드: dot·라벨·코멘트·4카운트·7개 컴포넌트 배지 표시
4. 🎯 타이밍 섹션: 게이지 + 7카드, 💰 밸류에이션 섹션: 5카드, 💡 안내 박스 표시
5. 📈 ETF 섹션: 카드별 RSI(30↓매수·70↑주의 힌트)·MA200 추세·52주 게이지(저점/고점 라벨)
6. 📖 글로사리: `<details>` 16개, 클릭 시 펼침/접힘
7. **모달 중앙정렬 (핵심 버그)**: 매크로 카드 클릭 → 모달이 **화면 정중앙**에 표시(좌상단 아님). `browser_take_screenshot`으로 위치 육안 확인
8. 모달 내용: 제목·현재 수치·"이 지표가 뭔가요?"·"어떻게 읽나요?" 임계값 표·"⚠️ 주의사항"·원본 링크 모두 채워짐
9. 모달 닫기 3종: × 버튼 / ESC 키 / 배경 클릭 — 각각 닫힘
10. 컴포넌트 배지 클릭 → 해당 지표 모달 (overall 아님), 카드 빈 공간 클릭 → overall 모달
11. ETF 카드 RSI/MA200/52주 행 클릭 → 각 rsi/ma200/52w 모달
12. 테마 토글 클릭 → 라이트↔다크 전환, 모달도 양 테마에서 중앙·가독
13. 라이트 모드에서 새로고침 → FOUC(깜빡임) 없음, localStorage 'theme' 유지

- [ ] **Step 4: 소실 항목 0 체크리스트 대조**

설계서 1.1절 9개 항목이 모두 복원됐는지 육안 대조. 누락 발견 시 해당 컴포넌트 태스크로 돌아가 수정 후 재검증.

- [ ] **Step 5: 프리뷰 서버 종료 + 최종 커밋 (검증 통과 시)**

검증 전 항목 통과를 확인한 뒤에만:

```bash
git commit --allow-empty -m "검증 완료 — 정보량 복원·모달 중앙정렬·양 테마·콘솔 에러 0 확인"
```

---

## Self-Review

**1. Spec coverage** (설계서 ↔ 태스크 매핑):
- 1.1 소실 9항목: 부제(Task 9)·섹션분리(Task 3·11)·게이지(Task 6)·카드힌트/배지(Task 4)·7컴포넌트배지(Task 7)·글로사리(Task 8)·리치모달(Task 10)·ETF힌트(Task 5)·푸터(Task 9) → 전부 커버
- 1.2 모달 버그: Task 10 (global.css `#indicator-modal[open]{margin:auto}`) + Task 13 검증 → 커버
- 4.1 정확성 정정: Task 1 (yield_spread·buffett caveat) → 커버
- 3 아키텍처(컴포넌트 분해): Task 2~11 → 커버
- 7 CLAUDE.md 갱신: Task 12 → 커버
- 9 검증: Task 13 → 커버
- 8 out of scope(데이터 파이프라인·신규지표·React·새토큰·새로고침버튼): 어떤 태스크도 침범 안 함 → 준수

**2. Placeholder scan:** "TBD/TODO/적절히 처리" 없음. 모든 컴포넌트·데이터·스크립트 전체 코드 포함. Task 1 INDICATOR_INFO 15키 전수 기재. Task 8 글로사리 16항목 전수 기재.

**3. Type consistency:**
- `SignalKey` — signal.ts(기존) 단일 출처, 전 태스크 일관
- `signalBg`/`signalText`/`SIGNAL_KR` — Task 2 정의, Task 4·5·7·10에서 동일 시그니처 사용
- `IndicatorInfo` — Task 1 정의 `{title,description,thresholds:{range,label,sig}[],caveat,sourceUrl,sourceLabel}`, Task 10 스크립트에서 동일 필드명 접근 (`info.title/description/caveat/sourceLabel/sourceUrl`, `t.range/label/sig`)
- `composite.signals` 고정 순서 ↔ Task 11 `badgeKeys`/`timingMeta` 7원소 1:1 정렬 일치
- MacroCard Props(emoji,en,title,value,signal,detail,hint,indicatorKey,current) ↔ Task 11 `timingCards`/`valuationCards` 객체 키 일치
- EtfCard Props ↔ Task 11 `etfs` 매핑 키 일치 (priceStr/pos52w/needleX/needleY 등 camelCase 통일)

이슈 없음.
