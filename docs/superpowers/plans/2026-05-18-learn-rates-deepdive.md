# Learn 섹션 + 금리 딥다이브 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 확장형 Learn 섹션과 그 첫 딥다이브인 금리 페이지를, 파이프라인이 수집한 15년 시계열을 빌드타임 SVG 차트로 보여주며 초보 해설과 결합해 출시한다.

**Architecture:** `fetch-data.ts`가 FRED 시계열 5종(+파생 금리차)을 `src/data/history.json`(비치명적)에 저장 → `d3-scale`/`d3-shape`로 빌드타임에 정적 SVG 라인차트 생성 → Astro Content Collection(MDX) 글 안에 `<RateChart>`로 삽입 → `/learn` 인덱스 + `/learn/[slug]` 라우트로 정적 출력. 클라이언트 차트 JS 0, 색은 기존 `--c-*` 테마 변수.

**Tech Stack:** Astro 6, TypeScript, `d3-scale`·`d3-shape`(빌드타임), `@astrojs/mdx`, `@astrojs/sitemap`, Tailwind v4(`@theme`/`--c-*`).

**설계서:** `docs/superpowers/specs/2026-05-18-learn-rates-deepdive-design.md`

**검증 방식 주의:** 이 프로젝트는 설계서 §1.3에 따라 **단위 테스트 프레임워크를 신규 도입하지 않는다**(기존에도 없음). 검증은 프로젝트 관행대로 `npm run build`/`npm run fetch:data` 실행 결과, `grep`/파일 점검, `npm run dev` 수동 확인, 그리고 순수 함수는 **커밋하지 않는 일회성 `tsx` 검증 스크립트**로 한다. 각 Task의 "검증" 스텝이 곧 그 Task의 테스트다 — 통과 전까지 다음 Task로 가지 않는다.

**선행 사실(확인됨):** 테마 변수 `--c-bg/-surface/-surface-hi/-border/-text/-muted/-subtle/-brand/-brand-hi/-good/-warn/-bad/-neutral`(`src/styles/global.css`). 페이지 셸 패턴: `<Base><main class="mx-auto max-w-screen-lg px-4 py-6 sm:py-10">…</main>…</Base>`(`src/pages/index.astro`). 테마 토글 핸들러는 현재 `index.astro`의 `<script is:inline>`. `package.json` `fetch:data`는 `--env-file-if-exists=.env` 적용 완료(커밋 `081ff48`).

---

## File Structure

| 파일 | 책임 |
|------|------|
| `scripts/fetch-data.ts` (수정) | `fredSeries()`/`deriveYieldSpread()` 추가, `history.json` 생성(비치명적) |
| `src/lib/data.ts` (수정) | `RatePoint`/`RateSeriesId`/`RateHistory` 타입 |
| `src/lib/line-chart.ts` (신규) | 시계열→SVG 좌표 순수 계산 (`gauge.ts` 패턴) |
| `src/lib/history.ts` (신규) | `history.json` 안전 로더 |
| `src/components/LineChart.astro` (신규) | 좌표→정적 `<svg>` (테마 변수 색) |
| `src/components/RateChart.astro` (신규) | MDX 임베드용 — 시리즈 id→LineChart |
| `src/components/ThemeToggleScript.astro` (신규) | 테마 토글 핸들러 단일 출처 |
| `src/layouts/Learn.astro` (신규) | Learn 페이지 셸(탑바·토글·Footer) |
| `src/content.config.ts` (신규) | `learn` 컬렉션 정의(glob+zod) |
| `src/content/learn/interest-rates.mdx` (신규) | 금리 딥다이브 본문 |
| `src/pages/learn/index.astro` (신규) | Learn 인덱스 |
| `src/pages/learn/[...slug].astro` (신규) | 딥다이브 라우트 |
| `src/layouts/Base.astro` (수정) | canonical/OG/JSON-LD 파라미터화 |
| `src/components/Header.astro` (수정) | `/learn` 링크 추가 |
| `src/components/IndicatorModal.astro` (수정) | "자세히 →" 딥링크 |
| `src/lib/indicator-info.ts` (수정) | `learnHref?` 필드 |
| `src/pages/index.astro` (수정) | 토글 스크립트를 공용 컴포넌트로 교체 |
| `astro.config.mjs`·`package.json`·`.gitignore` (수정) | 통합/의존성/무시 |

---

## Task 1: 의존성 + Astro 통합

**Files:**
- Modify: `package.json`
- Modify: `astro.config.mjs`

- [ ] **Step 1: 의존성 설치**

Run:
```bash
npm install d3-scale@^4 d3-shape@^3 @astrojs/mdx@^4 @astrojs/sitemap@^3 && npm install -D @types/d3-scale@^4 @types/d3-shape@^3
```
Expected: 설치 성공, `package.json` `dependencies`에 `d3-scale`·`d3-shape`·`@astrojs/mdx`·`@astrojs/sitemap`, `devDependencies`에 `@types/d3-scale`·`@types/d3-shape` 추가됨.

- [ ] **Step 2: astro.config.mjs에 통합 추가**

`astro.config.mjs` 전체를 아래로 교체:
```js
// @ts-check
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://techboost.dev',
  integrations: [mdx(), sitemap()],
  vite: {
    plugins: [tailwindcss()],
  },
});
```

- [ ] **Step 3: 빌드가 깨지지 않는지 검증**

Run: `npm run build`
Expected: 빌드 성공. `dist/sitemap-index.xml` 생성됨.
Run: `ls dist/sitemap-index.xml`
Expected: 파일 존재.

- [ ] **Step 4: Commit**

```bash
git add package.json package-lock.json astro.config.mjs
git commit -m "build: d3-scale·d3-shape + @astrojs/mdx·sitemap 통합 추가"
```

---

## Task 2: 금리 히스토리 타입

**Files:**
- Modify: `src/lib/data.ts` (파일 끝에 추가, 기존 타입 불변)

- [ ] **Step 1: 타입 추가**

`src/lib/data.ts` 맨 끝에 추가:
```ts

export type RatePoint = { date: string; value: number };

export type RateSeriesId =
  | 'dgs10'
  | 'dgs3mo'
  | 'yield_spread'
  | 'hy_spread'
  | 'usdkrw'
  | 'fedfunds';

export type RateHistory = Partial<Record<RateSeriesId, RatePoint[]>>;
```

- [ ] **Step 2: 타입 컴파일 검증**

Run: `npm run build`
Expected: 빌드 성공(타입 에러 없음).

- [ ] **Step 3: Commit**

```bash
git add src/lib/data.ts
git commit -m "feat: RatePoint/RateSeriesId/RateHistory 타입 추가"
```

---

## Task 3: 파이프라인 — fredSeries + history.json

**Files:**
- Modify: `scripts/fetch-data.ts`
- Modify: `.gitignore`

- [ ] **Step 1: import에 타입 추가**

`scripts/fetch-data.ts` 5번째 줄을 교체:
```ts
import type { Snapshot, TickerAnalysis, MaCross, RateHistory, RatePoint } from '../src/lib/data';
```

- [ ] **Step 2: fredSeries / deriveYieldSpread 함수 추가**

`fredLatest` 함수 정의(46번째 줄 `}` 다음) 바로 아래에 추가:
```ts

// ────────────────────────────────────────────────────────────
// FRED: 과거 시계열 전체 (sort_order=asc, observation_start)
// ────────────────────────────────────────────────────────────
async function fredSeries(seriesId: string, start: string): Promise<RatePoint[] | null> {
  try {
    const url = `https://api.stlouisfed.org/fred/series/observations?series_id=${seriesId}&api_key=${FRED_KEY}&file_type=json&sort_order=asc&observation_start=${start}`;
    const r = await fetch(url, { signal: AbortSignal.timeout(15_000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json() as { observations: Array<{ date: string; value: string }> };
    const points: RatePoint[] = data.observations
      .filter(o => o.value !== '.' && o.value !== '')
      .map(o => ({ date: o.date, value: Number(o.value) }))
      .filter(p => Number.isFinite(p.value));
    return points.length ? points : null;
  } catch (e) {
    console.error(`  ⚠️  FRED series ${seriesId} 실패:`, e instanceof Error ? e.message : e);
    return null;
  }
}

// DGS10 − DGS3MO 를 같은 날짜끼리 매칭해 장단기 금리차 시계열 생성
function deriveYieldSpread(
  y10: RatePoint[] | null,
  y3m: RatePoint[] | null,
): RatePoint[] | null {
  if (!y10 || !y3m) return null;
  const m = new Map(y3m.map(p => [p.date, p.value]));
  const out: RatePoint[] = [];
  for (const p of y10) {
    const v3 = m.get(p.date);
    if (v3 !== undefined) out.push({ date: p.date, value: Number((p.value - v3).toFixed(2)) });
  }
  return out.length ? out : null;
}
```

- [ ] **Step 3: main()에서 history.json 생성 (비치명적, latest.json 직후·핵심 체크 이전)**

`scripts/fetch-data.ts`에서 `console.log(\`✓ ${out} 작성 완료\`);` 줄 **바로 다음**에 아래 블록 삽입 (핵심 4개 체크 `const core = {...}` 위):
```ts

  // ── 금리 히스토리 (비치명적: 실패해도 빌드 진행) ──
  try {
    const start = `${new Date().getFullYear() - 15}-01-01`;
    const [h10, h3m, hHy, hKrw, hFf] = await Promise.all([
      fredSeries('DGS10', start),
      fredSeries('DGS3MO', start),
      fredSeries('BAMLH0A0HYM2', start),
      fredSeries('DEXKOUS', start),
      fredSeries('FEDFUNDS', start),
    ]);
    const history: RateHistory = {};
    if (h10) history.dgs10 = h10;
    if (h3m) history.dgs3mo = h3m;
    if (hHy) history.hy_spread = hHy;
    if (hKrw) history.usdkrw = hKrw;
    if (hFf) history.fedfunds = hFf;
    const ys = deriveYieldSpread(h10, h3m);
    if (ys) history.yield_spread = ys;
    const hOut = 'src/data/history.json';
    await writeFile(hOut, JSON.stringify(history));
    console.log(`✓ ${hOut} 작성 완료 (${Object.keys(history).length}/6 시리즈)`);
  } catch (e) {
    console.error('  ⚠️  history.json 생성 실패 (빌드는 계속):', e instanceof Error ? e.message : e);
  }
```

- [ ] **Step 4: .gitignore에 history.json 추가**

`.gitignore` 40번째 줄(`src/data/latest.json`) 바로 아래에 추가:
```
src/data/history.json
```

- [ ] **Step 5: 실행 검증 (history.json 6/6 생성)**

Run: `npm run fetch:data`
Expected: 출력에 `✓ src/data/history.json 작성 완료 (6/6 시리즈)` 포함, 기존 `✓ src/data/latest.json 작성 완료`도 그대로.
Run: `node -e "const h=require('./src/data/history.json');console.log(Object.keys(h).sort().join(','), h.dgs10.length)"`
Expected: `dgs10,dgs3mo,fedfunds,hy_spread,usdkrw,yield_spread` 와 dgs10 포인트 수(수천) 출력.

- [ ] **Step 6: gitignore 동작 검증**

Run: `git status --short src/data`
Expected: `src/data/history.json` 이 목록에 **나타나지 않음**(무시됨).

- [ ] **Step 7: Commit**

```bash
git add scripts/fetch-data.ts .gitignore
git commit -m "feat: fredSeries + history.json 생성 (15년 시계열, 비치명적)"
```

---

## Task 4: line-chart.ts 순수 모듈

**Files:**
- Create: `src/lib/line-chart.ts`
- Create(임시, 미커밋): `scripts/_verify-line-chart.ts`

- [ ] **Step 1: line-chart.ts 작성**

`src/lib/line-chart.ts` 생성:
```ts
import { scaleUtc, scaleLinear } from 'd3-scale';
import { line } from 'd3-shape';
import type { RatePoint } from './data';

export type ChartGeom = {
  width: number;
  height: number;
  pathD: string;
  xTicks: { x: number; label: string }[];
  yTicks: { y: number; label: string }[];
  last: { x: number; y: number; label: string } | null;
};

const W = 720;
const H = 280;
const PAD = { t: 16, r: 56, b: 28, l: 8 };

export function buildLineChart(
  points: RatePoint[],
  fmt: (v: number) => string = v => v.toFixed(2),
): ChartGeom | null {
  const clean = points.filter(p => !!p && Number.isFinite(p.value) && !!p.date);
  if (clean.length < 2) return null;

  const dates = clean.map(p => new Date(p.date + 'T00:00:00Z'));
  const values = clean.map(p => p.value);

  const x = scaleUtc()
    .domain([dates[0], dates[dates.length - 1]])
    .range([PAD.l, W - PAD.r]);

  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const pad = (maxV - minV) * 0.08 || 1;
  const y = scaleLinear()
    .domain([minV - pad, maxV + pad])
    .range([H - PAD.b, PAD.t]);

  const gen = line<{ d: Date; v: number }>()
    .x(p => x(p.d))
    .y(p => y(p.v));
  const pathD = gen(clean.map((p, i) => ({ d: dates[i], v: p.value }))) ?? '';
  if (!pathD.startsWith('M')) return null;

  const xTicks = x.ticks(5).map(t => ({ x: x(t), label: String(t.getUTCFullYear()) }));
  const yTicks = y.ticks(4).map(t => ({ y: y(t), label: fmt(t) }));

  const lp = clean[clean.length - 1];
  const last = { x: x(dates[dates.length - 1]), y: y(lp.value), label: fmt(lp.value) };

  return { width: W, height: H, pathD, xTicks, yTicks, last };
}
```

- [ ] **Step 2: 일회성 검증 스크립트 작성 (커밋 안 함)**

`scripts/_verify-line-chart.ts` 생성:
```ts
import { buildLineChart } from '../src/lib/line-chart';

const pts = Array.from({ length: 60 }, (_, i) => ({
  date: `${2010 + Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, '0')}-01`,
  value: Math.sin(i / 5) * 2 + 3,
}));

const g = buildLineChart(pts);
if (!g) throw new Error('FAIL: 정상 입력인데 null');
if (!g.pathD.startsWith('M')) throw new Error('FAIL: pathD 형식 오류');
if (g.xTicks.length < 2) throw new Error('FAIL: xTicks 부족');
if (g.yTicks.length < 2) throw new Error('FAIL: yTicks 부족');
if (!g.last) throw new Error('FAIL: last 없음');
if (buildLineChart([]) !== null) throw new Error('FAIL: 빈 배열은 null이어야');
if (buildLineChart([{ date: '2020-01-01', value: NaN }]) !== null) throw new Error('FAIL: NaN-only는 null이어야');
if (buildLineChart([{ date: '2020-01-01', value: 1 }]) !== null) throw new Error('FAIL: 1점은 null이어야');
console.log('PASS line-chart geom + edge cases');
```

- [ ] **Step 3: 검증 실행**

Run: `npx tsx scripts/_verify-line-chart.ts`
Expected: `PASS line-chart geom + edge cases`

- [ ] **Step 4: 임시 스크립트 삭제**

Run: `rm scripts/_verify-line-chart.ts`
Expected: 파일 삭제됨(커밋에 포함 안 됨).

- [ ] **Step 5: Commit**

```bash
git add src/lib/line-chart.ts
git commit -m "feat: line-chart 빌드타임 SVG 좌표 계산 (d3-scale/d3-shape)"
```

---

## Task 5: history 로더 + LineChart/RateChart 컴포넌트

**Files:**
- Create: `src/lib/history.ts`
- Create: `src/components/LineChart.astro`
- Create: `src/components/RateChart.astro`
- Create(임시, 미커밋): `src/pages/_chart-test.astro`

> 전제: Task 3 실행으로 `src/data/history.json` 이 이미 존재함. 없으면 먼저 `npm run fetch:data` 재실행.

- [ ] **Step 1: history.ts 로더 작성**

`src/lib/history.ts` 생성:
```ts
import { readFileSync } from 'node:fs';
import type { RateHistory } from './data';

export function loadHistory(): RateHistory {
  try {
    return JSON.parse(readFileSync('src/data/history.json', 'utf-8')) as RateHistory;
  } catch {
    return {};
  }
}
```

- [ ] **Step 2: LineChart.astro 작성 (색은 style의 CSS 변수 — 프리젠테이션 속성 var()는 미지원)**

`src/components/LineChart.astro` 생성:
```astro
---
import { buildLineChart } from '../lib/line-chart';
import type { RatePoint } from '../lib/data';

interface Props {
  points: RatePoint[];
  unit?: string;
  decimals?: number;
}
const { points, unit = '', decimals = 2 } = Astro.props;
const fmt = (v: number) => `${v.toFixed(decimals)}${unit}`;
const geom = buildLineChart(points, fmt);
---
{geom ? (
  <svg viewBox={`0 0 ${geom.width} ${geom.height}`} role="img"
       class="w-full h-auto" preserveAspectRatio="none">
    {geom.yTicks.map(t => (
      <>
        <line x1="8" x2={geom.width - 56} y1={t.y} y2={t.y}
              style="stroke: var(--c-border)" stroke-width="1" />
        <text x={geom.width - 50} y={t.y + 4} font-size="12"
              style="fill: var(--c-muted)">{t.label}</text>
      </>
    ))}
    {geom.xTicks.map(t => (
      <text x={t.x} y={geom.height - 8} font-size="12" text-anchor="middle"
            style="fill: var(--c-muted)">{t.label}</text>
    ))}
    <path d={geom.pathD} fill="none" stroke-width="2"
          stroke-linejoin="round" stroke-linecap="round"
          style="stroke: var(--c-good)" />
    {geom.last && (
      <>
        <circle cx={geom.last.x} cy={geom.last.y} r="3.5" style="fill: var(--c-good)" />
        <text x={geom.last.x - 6} y={geom.last.y - 8} font-size="12"
              text-anchor="end" font-weight="700" style="fill: var(--c-text)">
          {geom.last.label}
        </text>
      </>
    )}
  </svg>
) : (
  <p class="text-sm text-muted py-8 text-center">데이터를 일시적으로 불러올 수 없어요.</p>
)}
```

- [ ] **Step 3: RateChart.astro 작성**

`src/components/RateChart.astro` 생성:
```astro
---
import { loadHistory } from '../lib/history';
import LineChart from './LineChart.astro';
import type { RateSeriesId } from '../lib/data';

const META: Record<RateSeriesId, { unit: string; decimals: number }> = {
  dgs10:        { unit: '%',  decimals: 2 },
  dgs3mo:       { unit: '%',  decimals: 2 },
  yield_spread: { unit: '%p', decimals: 2 },
  hy_spread:    { unit: '%p', decimals: 2 },
  usdkrw:       { unit: '원', decimals: 2 },
  fedfunds:     { unit: '%',  decimals: 2 },
};

interface Props { id: RateSeriesId; }
const { id } = Astro.props;
const points = loadHistory()[id] ?? [];
const { unit, decimals } = META[id];
---
<figure class="my-6 bg-surface/60 border border-border rounded-xl p-3 sm:p-4">
  <LineChart points={points} unit={unit} decimals={decimals} />
</figure>
```

- [ ] **Step 4: 임시 테스트 페이지로 렌더 검증**

`src/pages/_chart-test.astro` 생성:
```astro
---
import RateChart from '../components/RateChart.astro';
---
<html><body>
  <RateChart id="fedfunds" />
  <RateChart id="yield_spread" />
</body></html>
```
Run: `npm run build`
Expected: 빌드 성공.
Run: `grep -c "<svg" dist/_chart-test/index.html`
Expected: `2` (시리즈 2개 모두 SVG로 렌더). 0이면 history.json 누락 → `npm run fetch:data` 후 재빌드.

- [ ] **Step 5: 임시 페이지 삭제**

Run: `rm src/pages/_chart-test.astro`

- [ ] **Step 6: Commit**

```bash
git add src/lib/history.ts src/components/LineChart.astro src/components/RateChart.astro
git commit -m "feat: history 로더 + LineChart/RateChart 컴포넌트 (정적 SVG)"
```

---

## Task 6: 콘텐츠 컬렉션 + 금리 MDX

**Files:**
- Create: `src/content.config.ts`
- Create: `src/content/learn/interest-rates.mdx`

- [ ] **Step 1: content.config.ts 작성**

`src/content.config.ts` 생성:
```ts
import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const learn = defineCollection({
  loader: glob({ pattern: '**/*.mdx', base: './src/content/learn' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    summary: z.string(),
    order: z.number().default(0),
    updated: z.string(),
  }),
});

export const collections = { learn };
```

- [ ] **Step 2: 금리 딥다이브 본문 작성**

`src/content/learn/interest-rates.mdx` 생성:
```mdx
---
title: "금리가 주가를 움직이는 이유"
description: "연준 기준금리·국채 금리·장단기 금리차·HY 스프레드·원달러를 초보 눈높이로, 15년 추이 차트와 함께 풀어봅니다."
summary: "금리 하나로 주가·환율·경기를 읽는 법 — 초보용 6개 지표 해설"
order: 1
updated: "2026-05-18"
---

import RateChart from '../../components/RateChart.astro';

## 왜 금리가 주가를 좌우할까?

주식의 가치는 **"이 회사가 미래에 벌 돈"을 지금 가치로 환산**한 거예요. 이때 나누는 값이 금리입니다. 금리가 오르면 같은 미래 이익도 현재 가치가 줄어, 특히 먼 미래 이익이 큰 성장주가 크게 흔들려요. 또 금리가 높으면 안전한 예금·채권 수익이 좋아져 위험한 주식에서 돈이 빠져나가고, 기업의 이자 비용도 늘어 이익이 깎입니다. 그래서 금리는 주식시장의 **중력**이라고 불려요.

## 1. 미국 연준 기준금리 (정책의 출발점)

미국 중앙은행(연준)이 정하는 금리예요. 모든 시장 금리의 기준점이라, 인상기엔 위험자산에 역풍·인하기엔 순풍이 부는 경향이 있어요.

<RateChart id="fedfunds" />

## 2. 미국 10년물 국채 금리 (시장의 장기 기대)

투자자들이 보는 장기 금리예요. 주식 밸류에이션의 할인율 역할을 해서, 10년물이 빠르게 오르면 성장주가 먼저 출렁입니다.

<RateChart id="dgs10" />

## 3. 장단기 금리차 (10Y − 3M) — 침체 신호등

장기 금리에서 단기 금리를 뺀 값이에요. **0 아래로 역전**되면 역사적으로 1~2년 안에 경기침체가 따라온 경우가 많았어요. 가장 유명한 선행 지표 중 하나입니다.

<RateChart id="yield_spread" />

## 4. HY(하이일드) 스프레드 — 신용 위험 체온계

신용등급이 낮은 회사채가 안전한 국채 대비 얼마나 더 높은 금리를 줘야 하는지예요. 급등하면 시장이 부도 위험을 크게 본다는 뜻으로, 신용 위기를 3~6개월 선행하는 신호로 봅니다.

<RateChart id="hy_spread" />

## 5. 원/달러 환율 — 한국 투자자의 추가 변수

미국 금리가 오르면 달러가 강해지고 원화가 약해지는 경향이 있어요. 환율이 오르면(원화 약세) 외국인 자금 이탈·수입물가 상승으로 국내 증시에 부담이 될 수 있습니다.

<RateChart id="usdkrw" />

## 정리 — 초보자가 기억할 3가지

1. **금리 ↑ → 주가에 역풍**(특히 성장주), 금리 ↓ → 순풍 (절대 법칙은 아님)
2. **장단기 금리차 역전**은 강력한 침체 경고, 단 시차가 길다
3. 금리는 단독이 아니라 **여러 지표·뉴스와 함께** 봐야 한다

> 이 글은 교육용이며 매매 권유가 아니에요. 데이터는 매일 자동 갱신됩니다.
```

- [ ] **Step 3: 컬렉션 로딩 검증**

Run: `npm run build`
Expected: 빌드 성공(zod 스키마·MDX 파싱 에러 없음). 아직 라우트가 없어 페이지 출력은 없음 — 에러 없이 통과하면 OK.

- [ ] **Step 4: Commit**

```bash
git add src/content.config.ts src/content/learn/interest-rates.mdx
git commit -m "feat: learn 컬렉션 + 금리 딥다이브 MDX 본문"
```

---

## Task 7: 테마 토글 공용화 + Learn 레이아웃 + 라우트

**Files:**
- Create: `src/components/ThemeToggleScript.astro`
- Create: `src/layouts/Learn.astro`
- Create: `src/pages/learn/index.astro`
- Create: `src/pages/learn/[...slug].astro`
- Modify: `src/pages/index.astro` (인라인 토글 스크립트 → 공용 컴포넌트)

- [ ] **Step 1: ThemeToggleScript.astro 작성 (index.astro의 핸들러를 그대로 단일화)**

`src/components/ThemeToggleScript.astro` 생성:
```astro
<script is:inline>
  document.getElementById('theme-toggle')?.addEventListener('click', function () {
    var html = document.documentElement;
    var toLight = !html.classList.contains('light');
    html.classList.toggle('light', toLight);
    html.classList.toggle('dark', !toLight);
    try { localStorage.setItem('theme', toLight ? 'light' : 'dark'); } catch (e) {}
  });
</script>
```

- [ ] **Step 2: index.astro에서 인라인 스크립트를 공용 컴포넌트로 교체**

`src/pages/index.astro` import 블록 마지막(`import IndicatorModal ...` 다음 줄)에 추가:
```ts
import ThemeToggleScript from '../components/ThemeToggleScript.astro';
```
그리고 143~151번째 줄의 `<script is:inline> … </script>` 블록 전체를 다음 한 줄로 교체:
```astro
  <ThemeToggleScript />
```

- [ ] **Step 3: index.astro 회귀 검증**

Run: `npm run build`
Expected: 빌드 성공.
Run: `grep -c "theme-toggle" dist/index.html`
Expected: `>=1` (토글 핸들러 여전히 존재).

- [ ] **Step 4: Learn 레이아웃 작성**

`src/layouts/Learn.astro` 생성:
```astro
---
import Base from './Base.astro';
import Footer from '../components/Footer.astro';
import ThemeToggleScript from '../components/ThemeToggleScript.astro';

interface Props {
  title: string;
  description: string;
  canonical: string;
  jsonLd?: Record<string, unknown>;
}
const { title, description, canonical, jsonLd } = Astro.props;
---
<Base title={title} description={description} canonical={canonical} jsonLd={jsonLd}>
  <main class="mx-auto max-w-screen-lg px-4 py-6 sm:py-10">
    <div class="mb-8 flex items-start justify-between gap-4">
      <a href="/" class="text-sm text-muted hover:text-text transition">← 대시보드</a>
      <button id="theme-toggle" type="button" aria-label="다크/라이트 모드 전환"
        class="shrink-0 rounded-full p-2 text-muted hover:text-text hover:bg-surface-hi transition">
        <span class="dark-icon">☀️</span>
        <span class="light-icon">🌙</span>
      </button>
    </div>
    <slot />
    <Footer />
  </main>
  <ThemeToggleScript />
</Base>
```

- [ ] **Step 5: Learn 인덱스 페이지 작성**

`src/pages/learn/index.astro` 생성:
```astro
---
import { getCollection } from 'astro:content';
import Learn from '../../layouts/Learn.astro';

const entries = (await getCollection('learn')).sort(
  (a, b) => a.data.order - b.data.order,
);
const canonical = new URL('/learn/', Astro.site).href;
---
<Learn
  title="투자 지표 학습 | techboost.dev"
  description="금리·변동성·환율 등 투자 지표를 초보 눈높이로 풀어주는 학습 글 모음."
  canonical={canonical}
>
  <h1 class="text-2xl sm:text-3xl font-bold tracking-tight mb-2">📖 투자 지표 학습</h1>
  <p class="text-sm text-muted mb-8">대시보드 숫자를 제대로 이해하고 싶을 때 — 초보 눈높이 딥다이브.</p>
  <ul class="grid gap-4">
    {entries.map(e => (
      <li>
        <a href={`/learn/${e.id}`}
           class="block bg-surface/60 border border-border rounded-xl p-4 sm:p-5 hover:bg-surface-hi transition">
          <h2 class="text-base sm:text-lg font-bold text-text">{e.data.title}</h2>
          <p class="text-sm text-muted mt-1">{e.data.summary}</p>
        </a>
      </li>
    ))}
  </ul>
</Learn>
```

- [ ] **Step 6: 딥다이브 라우트 작성**

`src/pages/learn/[...slug].astro` 생성:
```astro
---
import { getCollection, render } from 'astro:content';
import Learn from '../../layouts/Learn.astro';

export async function getStaticPaths() {
  const entries = await getCollection('learn');
  return entries.map(entry => ({ params: { slug: entry.id }, props: { entry } }));
}

const { entry } = Astro.props;
const { Content } = await render(entry);
const canonical = new URL(`/learn/${entry.id}/`, Astro.site).href;
const jsonLd = {
  '@context': 'https://schema.org',
  '@type': 'LearningResource',
  name: entry.data.title,
  description: entry.data.description,
  url: canonical,
  inLanguage: 'ko',
  dateModified: entry.data.updated,
  isAccessibleForFree: true,
};
---
<Learn
  title={`${entry.data.title} | techboost.dev`}
  description={entry.data.description}
  canonical={canonical}
  jsonLd={jsonLd}
>
  <article class="prose-learn">
    <h1 class="text-2xl sm:text-3xl font-bold tracking-tight mb-6">{entry.data.title}</h1>
    <Content />
  </article>
</Learn>
```

> 참고: 본문 타이포는 별도 prose 플러그인 없이 진행한다(설계 §1.3 YAGNI). `prose-learn` 클래스는 시각 hook으로만 두고 v1에서 추가 스타일은 강제하지 않는다.

- [ ] **Step 7: dev 렌더 수동 검증**

Run: `npm run dev` (백그라운드) 후 다른 셸에서:
```bash
curl -s localhost:4321/learn/ | grep -c "투자 지표 학습"
curl -s localhost:4321/learn/interest-rates/ | grep -c "<svg"
```
Expected: 첫째 `>=1`, 둘째 `>=5` (RateChart 6개 중 데이터 있는 시리즈가 SVG로). dev 서버 종료.
브라우저 `localhost:4321/learn/interest-rates/` 에서 차트 표시·테마 토글(우상단)·모바일 폭 확인.

- [ ] **Step 8: Commit**

```bash
git add src/components/ThemeToggleScript.astro src/layouts/Learn.astro src/pages/learn/index.astro src/pages/learn/'[...slug].astro' src/pages/index.astro
git commit -m "feat: /learn 인덱스·딥다이브 라우트 + 테마 토글 공용화"
```

---

## Task 8: Base.astro canonical/OG/JSON-LD 파라미터화

**Files:**
- Modify: `src/layouts/Base.astro`

- [ ] **Step 1: Props 확장**

`src/layouts/Base.astro`의 `export interface Props { … }` 와 구조분해를 교체:
```ts
export interface Props {
  title?: string;
  description?: string;
  canonical?: string;
  jsonLd?: Record<string, unknown>;
}

const {
  title = "투자 지표 대시보드 | techboost.dev",
  description = "S&P500·VIX·금리·환율 등 매크로 지표 일일 스냅샷. 매일 07:37 KST 자동 갱신.",
  canonical,
  jsonLd,
} = Astro.props;
```

- [ ] **Step 2: canonical/og:url 을 파라미터로, JSON-LD 주입**

`const SITE_URL = 'https://techboost.dev';` 는 유지. 그 아래에 추가:
```ts
const canonicalUrl = canonical ?? SITE_URL;
```
`<link rel="canonical" href={SITE_URL} />` → `<link rel="canonical" href={canonicalUrl} />`
`<meta property="og:url" content={SITE_URL} />` → `<meta property="og:url" content={canonicalUrl} />`
`</head>` 바로 위에 추가 (JSON-LD는 raw script body가 필수라 `set:html`을 쓰되, 데이터는 빌드타임 상수이며 `<` 를 이스케이프해 스크립트 탈출을 차단 — 프로젝트 보안 규칙의 유일한 정당 예외):
```astro
  {jsonLd && (
    <script
      type="application/ld+json"
      is:inline
      set:html={JSON.stringify(jsonLd).replace(/</g, '\\u003c')}
    />
  )}
```

- [ ] **Step 3: 검증**

Run: `npm run build`
Expected: 빌드 성공.
Run: `grep -o 'canonical[^>]*' dist/learn/interest-rates/index.html`
Expected: `href="https://techboost.dev/learn/interest-rates/"` 포함.
Run: `grep -c 'application/ld+json' dist/learn/interest-rates/index.html`
Expected: `1`.
Run: `grep -o 'canonical[^>]*' dist/index.html`
Expected: `href="https://techboost.dev"` (대시보드는 기존 동작 유지).

- [ ] **Step 4: Commit**

```bash
git add src/layouts/Base.astro
git commit -m "feat: Base canonical/OG 파라미터화 + Learn JSON-LD"
```

---

## Task 9: Header 링크 + IndicatorModal 딥링크

**Files:**
- Modify: `src/lib/indicator-info.ts`
- Modify: `src/components/IndicatorModal.astro`
- Modify: `src/components/Header.astro`

- [ ] **Step 1: IndicatorInfo 타입에 learnHref 추가**

`src/lib/indicator-info.ts`의 `export type IndicatorInfo = { … }` 안 `sourceLabel: string;` 다음 줄에 추가:
```ts
  learnHref?: string;
```

- [ ] **Step 2: 금리 관련 항목에 learnHref 부여**

`src/lib/indicator-info.ts`에서 `yield_spread` 객체의 `sourceLabel: '...'` 다음에 `,` 확인 후 추가:
```ts
    learnHref: '/learn/interest-rates',
```
동일하게 `hy_spread` 객체에도(존재 시) 같은 줄 추가. (`yield_spread`는 반드시, `hy_spread`는 키가 있으면.)

- [ ] **Step 3: IndicatorModal에 딥링크 요소 추가**

`src/components/IndicatorModal.astro`에서 `#modal-source` 를 감싼 `<div class="pt-3 border-t border-border"> … </div>` 블록 **다음**에 추가:
```astro
    <a id="modal-learn" class="hidden text-sm text-good hover:underline font-medium">
      📖 이 지표 자세히 알아보기 →
    </a>
```

- [ ] **Step 4: 모달 스크립트에서 learnHref 처리**

`src/components/IndicatorModal.astro` 스크립트에서:

(a) `const elClose = document.getElementById('modal-close');` 다음 줄에 추가:
```ts
  const elLearn = document.getElementById('modal-learn') as HTMLAnchorElement | null;
```
(b) 가드 조건 `if (dlg && elTitle && elCurrent && elDesc && elTbody && elCaveat && elSource && elClose) {` 을 교체:
```ts
  if (dlg && elTitle && elCurrent && elDesc && elTbody && elCaveat && elSource && elClose && elLearn) {
```
(c) `openFor` 안 `elSource.href = info.sourceUrl;` 다음에 추가:
```ts
      if (info.learnHref) {
        elLearn.href = info.learnHref;
        elLearn.classList.remove('hidden');
      } else {
        elLearn.removeAttribute('href');
        elLearn.classList.add('hidden');
      }
```

- [ ] **Step 5: Header에 /learn 링크 추가**

`src/components/Header.astro`에서 테마 토글 `<button id="theme-toggle" …>…</button>` 를 감싸도록, 그 버튼을 다음으로 교체:
```astro
  <div class="flex items-center gap-1 shrink-0">
    <a href="/learn"
      class="rounded-full px-3 py-2 text-sm text-muted hover:text-text hover:bg-surface-hi transition">
      📖 학습
    </a>
    <button id="theme-toggle" type="button" aria-label="다크/라이트 모드 전환"
      class="rounded-full p-2 text-muted hover:text-text hover:bg-surface-hi transition">
      <span class="dark-icon">☀️</span>
      <span class="light-icon">🌙</span>
    </button>
  </div>
```

- [ ] **Step 6: 검증**

Run: `npm run build`
Expected: 빌드 성공.
Run: `grep -c 'href="/learn"' dist/index.html`
Expected: `>=1` (대시보드 헤더에 학습 링크).
Run: `grep -c 'modal-learn' dist/index.html`
Expected: `>=1` (모달 딥링크 요소 존재).
`npm run dev` 후 브라우저에서 대시보드 → "10Y-3M 금리차" 카드 클릭 → 모달 하단 "📖 이 지표 자세히 알아보기 →" 표시·클릭 시 `/learn/interest-rates` 이동 확인. 금리와 무관한 카드(예: VIX)에선 링크 미표시 확인.

- [ ] **Step 7: Commit**

```bash
git add src/lib/indicator-info.ts src/components/IndicatorModal.astro src/components/Header.astro
git commit -m "feat: 대시보드→Learn 진입 (Header 링크 + 모달 딥링크)"
```

---

## Task 10: 엔드투엔드 검증

**Files:** (코드 변경 없음 — 통합 검증 게이트)

- [ ] **Step 1: 풀 파이프라인 + 빌드**

Run: `npm run fetch:data && npm run build`
Expected: `✓ src/data/history.json 작성 완료 (6/6 시리즈)` + 빌드 성공.

- [ ] **Step 2: 클라이언트 차트 JS 0 확인**

Run: `grep -rl "d3-shape\|d3-scale" dist/ || echo "NONE"`
Expected: `NONE` (d3가 클라이언트 번들에 없음 — 빌드타임 전용).
Run: `grep -o '<svg' dist/learn/interest-rates/index.html | wc -l`
Expected: `>=5` (정적 SVG 차트 인라인).

- [ ] **Step 3: SEO 산출물 확인**

Run: `ls dist/sitemap-index.xml && grep -c 'learn/interest-rates' dist/sitemap-0.xml`
Expected: sitemap 존재, 금리 페이지 URL 포함(`>=1`).
Run: `grep -c 'application/ld+json' dist/learn/interest-rates/index.html`
Expected: `1`.

- [ ] **Step 4: 상호 링크·테마 수동 확인**

`npm run dev` 후 브라우저:
- `/` → 우상단 "📖 학습" → `/learn` 인덱스 → 금리 카드 → 딥다이브
- 딥다이브에서 "← 대시보드" 동작
- 라이트/다크 토글 시 차트 선·축 색이 따라 바뀜
- 모바일 폭(375px)에서 차트 가로 스크롤 없이 맞음

- [ ] **Step 5: 최종 상태 확인**

Run: `git status --short`
Expected: 추적 대상 변경 없음(클린). `src/data/history.json` 은 gitignore라 미표시.

---

## Self-Review (작성자 체크 완료)

- **Spec coverage:** §2 파이프라인→Task3, §3 타입→Task2, §4 차트→Task1·4·5, §5 콘텐츠/라우팅→Task6·7, §6 SEO→Task1·8, 진입 네비→Task9, 검증→Task10. 누락 없음.
- **Placeholder scan:** TBD/TODO 없음, 모든 코드 스텝에 실제 코드 포함.
- **Type consistency:** `RatePoint`/`RateSeriesId`/`RateHistory`(Task2) ↔ `fredSeries`/`RateHistory`(Task3) ↔ `buildLineChart(points, fmt)`/`ChartGeom`(Task4) ↔ `loadHistory()`/`LineChart`/`RateChart`(Task5) ↔ `learnHref`(Task9) 일관. `entry.id` 슬러그 ↔ `[...slug]` params 일관.
- **검증 적응 사유:** 설계 §1.3이 신규 테스트 인프라를 범위에서 제외 → build/runtime/grep/일회성 tsx로 검증(프로젝트 관행 일치).
