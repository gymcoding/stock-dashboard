# stock-dashboard: Learn 섹션 + 금리 딥다이브 설계서

- 작성일: 2026-05-18
- 작성자: 짐코딩 + Claude
- 상태: 설계 확정, 구현 계획 작성 대기
- 후속 문서: `2026-05-18-learn-rates-deepdive-plan.md` (superpowers:writing-plans로 생성 예정)

---

## 1. 목적과 범위

### 1.1 배경 / 목적

대표가 "금리가 주가에 큰 영향을 준다"는 사실을 인지하고, 대시보드에 **금리를 깊게 다루는 교육 페이지**를 추가하고자 한다. 단순 숫자 나열이 아니라 **라이브 데이터 + 초보자가 이해할 수 있는 해설**을 결합한, 검색·재방문을 부르는 evergreen explainer/pillar 페이지다.

전략적 근거:

- 이미 `src/lib/indicator-info.ts`(모달 해설) + `Glossary` 컴포넌트라는 마이크로 교육 레이어가 존재 — 딥다이브 페이지는 그 다음 단계의 자연스러운 확장
- CLAUDE.md상 SEO·AdSense에 이미 투자 중 — 장문 evergreen 해설 페이지는 유기적 트래픽·광고 수익 양쪽에 가장 효율적인 콘텐츠 유형
- "숫자를 보는 곳" → "숫자를 이해하는 곳"으로 차별화해 재방문율 향상

### 1.2 범위에 포함 (v1)

- 확장 가능한 **Learn(지표 해설) 섹션** 구조 구축
- 그 첫 딥다이브로 **금리** 페이지 작성 (라이브 데이터 + 초보 해설 결합)
- 데이터 파이프라인 확장 → 금리 지표 **과거 시계열** 수집·저장
- 금리 지표 6종: 미국 10Y(`DGS10`), 미국 3M(`DGS3MO`), 10Y-3M 금리차(파생), HY 스프레드(`BAMLH0A0HYM2`), 원/달러(`DEXKOUS`), **미국 연준 기준금리(`FEDFUNDS`, 신규)**
- **D3 빌드타임 SVG** 추이 차트 (정적 출력, 클라이언트 JS 0, 다크/라이트 자동)
- Content Collection(Markdown) + MDX 기반 콘텐츠 저작
- 페이지별 canonical/OG 파라미터화 + Learn 페이지 JSON-LD + 사이트맵

### 1.3 범위에 포함하지 않음 (후속 확장)

- 차트 호버 툴팁·기간 토글(1Y/5Y/10Y) — 데이터·SVG 토대를 안 바꾸고 후속 island로 추가 가능
- 침체 구간 음영·금리 인상기 주석 밴드
- 한국은행 기준금리 (한국은행 ECOS API 신규 연동 필요 — 별도 작업)
- 금리 외 추가 딥다이브(VIX·환율·실업률 등) — Learn 토대 위에 단계적으로
- 단위 테스트 신규 도입, 수동 새로고침

### 1.4 비결정자가 알아야 할 핵심 제약

- 일 1회 cron 단순성 우선 — 히스토리 페치 실패는 **비치명적**, 빌드/배포를 깨지 않음
- AdSense 수익화 — 페이지는 공개+검색 크롤링 가능 필수 (인증 게이트 불가)
- 정적 사이트 철학 유지 — 차트는 빌드타임 SVG, 사용자 전송 JS 0
- 다크/라이트는 CSS 변수 런타임 스왑 — 차트 색은 `var(--c-*)`/signal 토큰만 사용

---

## 2. 데이터 파이프라인 확장

대상: `scripts/fetch-data.ts`

- 신규 함수 `fredSeries(seriesId, startDate)` — 기존 `fredLatest()` 옆에 추가. FRED observations API를 `sort_order=asc&observation_start=YYYY-MM-DD`로 호출 → `{ date, value }[]` 반환. 결측치(`'.'`) 제외. try/catch → `null` (기존 부분 실패 허용 패턴 그대로)
- 수집 시리즈: `DGS10`·`DGS3MO`·`BAMLH0A0HYM2`·`DEXKOUS`·`FEDFUNDS`(신규). 장단기 금리차는 `DGS10`·`DGS3MO`를 날짜 매칭·차감해 파생 시리즈 생성
- 히스토리 윈도우: **15년, 일별 원본** (2008·2020·2022 금리 사이클 학습 가치)
- 출력: **신규 파일** `src/data/history.json` — 스냅샷 `latest.json`과 분리. `.gitignore`에 `src/data/history.json` 추가
- `main()` 진입점에서 히스토리 페치를 추가 호출하되 **핵심 4개 실패 체크(`process.exit(1)`)·`latest.json` 로직은 건드리지 않음**. 히스토리 전체 실패해도 빌드 진행 (각 시리즈 null 허용)
- `.github/workflows/daily.yml` 변경 불필요 — `fetch:data`가 두 파일을 함께 생성, build/deploy가 자동 포함
- 선결: `package.json` `fetch:data` 스크립트가 `--env-file-if-exists=.env`로 `.env` 로딩 (2026-05-18 적용 완료)

## 3. 타입

대상: `src/lib/data.ts` (기존 `Snapshot` 옆에 신규, 기존 타입 불변)

```ts
export type RatePoint = { date: string; value: number };
export type RateSeriesId =
  | 'dgs10' | 'dgs3mo' | 'yield_spread' | 'hy_spread' | 'usdkrw' | 'fedfunds';
export type RateHistory = Partial<Record<RateSeriesId, RatePoint[]>>;
```

## 4. 차트 (D3 빌드타임 SVG)

- 신규 의존성: `d3-scale`, `d3-shape` (dependencies) + `@types/d3-scale`, `@types/d3-shape` (devDependencies). **빌드타임에만 실행**, 사용자 전송 0
- `src/lib/line-chart.ts` — 시계열 → SVG path/축 눈금 좌표 계산. 순수 함수가 좌표를 반환하는 기존 `src/lib/gauge.ts` 패턴 답습. 빈 배열·NaN/Inf → 안전 fallback
- `src/components/LineChart.astro` — 위 좌표로 정적 `<svg>` 마크업 출력. 선·축 색은 `stroke="var(--c-*)"`/signal 토큰 → 다크·라이트 자동 대응
- v1 렌더 범위: 라인 + 축 눈금 + 최신값 라벨. 인터랙션·주석 밴드 제외

## 5. 콘텐츠 / 라우팅

- `@astrojs/mdx` 통합 추가 — Markdown 본문 흐름 안에 `<RateChart id="dgs10" />`를 끼워 넣기 위함
- `src/content.config.ts` — `astro/loaders`의 `glob` 로더로 `learn` 컬렉션 정의. zod 스키마: `title`, `description`, `summary`, `order`, `updated`
- `src/content/learn/interest-rates.mdx` — 금리 첫 딥다이브. 영문 슬러그(깔끔한 URL), 한글 제목은 frontmatter
- 라우트:
  - `src/pages/learn/index.astro` — Learn 인덱스(딥다이브 목록 카드, `getCollection('learn')`로 생성)
  - `src/pages/learn/[...slug].astro` — 딥다이브 렌더. `render(entry)` + `history.json` 주입
- 네비게이션:
  - `src/components/Header.astro`에 `/learn` 링크 1개 추가, 대시보드 ↔ Learn 상호 링크
  - `src/components/IndicatorModal.astro` + `src/lib/indicator-info.ts`의 금리 관련 항목(예: `yield_spread`)에 "자세히 →" 딥링크

## 6. SEO / 레이아웃

대상: `src/layouts/Base.astro`

- 현재 `canonical`/`og:url`이 `SITE_URL` 루트 고정 → **페이지별 파라미터화** (Learn 각 페이지가 고유 canonical을 갖도록 Props 확장)
- Learn 페이지에 `LearningResource`/`Article` JSON-LD 주입 (SEO/GEO)
- `@astrojs/sitemap` 추가 — 콘텐츠 SEO 핵심. `robots.txt`는 이미 검색봇 허용
- AdSense 자동광고는 Base 경유 → Learn 페이지에 자동 적용 (추가 작업 0). 장문 교육 페이지 = 최적 광고 인벤토리

## 7. 데이터 흐름

```
scripts/fetch-data.ts
  ├─ (기존) → src/data/latest.json   [스냅샷, 불변]
  └─ fredSeries × 5 + 파생 금리차 → src/data/history.json   [신규, gitignored]
                        ↓ astro build
  src/content/learn/*.mdx ──(getCollection/render)──┐
  src/data/history.json ───(LineChart 빌드타임 SVG)─┤
                                                    ↓
  src/pages/learn/index.astro · src/pages/learn/[...slug].astro
                        ↓
                   dist/ → Cloudflare Pages → techboost.dev/learn/...
```

## 8. 에러 처리

- `fredSeries` 개별 실패 → 해당 시리즈 `null`, `RateHistory`에서 생략. 페이지는 가용 시리즈만 차트화, 누락 시리즈는 "데이터 일시 불가" 카피로 graceful degrade
- 히스토리 전체 실패해도 `latest.json`·핵심 4개 체크 무관 → 빌드/배포 정상
- `LineChart`: 빈/이상 데이터 → 차트 영역에 안전 placeholder, 페이지 크래시 없음

## 9. 검증

- `npm run fetch:data` → `history.json`에 6시리즈 생성 확인. 한 시리즈 강제 실패시켜도 빌드 안 깨짐 확인
- `npm run dev` → `/learn`, `/learn/interest-rates` 렌더, 차트 SVG·다크/라이트 토글·모바일 레이아웃 확인
- `npm run build` → 정적 출력에 클라이언트 차트 JS 0, 페이지별 canonical·JSON-LD·sitemap.xml 확인
- Lighthouse SEO/접근성 스팟 체크
- `IndicatorModal` "자세히 →" 딥링크 동작 확인

## 10. 영향 받는 파일 요약

| 구분 | 파일 |
|------|------|
| 수정 | `scripts/fetch-data.ts`, `src/lib/data.ts`, `src/layouts/Base.astro`, `src/components/Header.astro`, `src/components/IndicatorModal.astro`, `src/lib/indicator-info.ts`, `.gitignore`, `astro.config.mjs`, `package.json` |
| 신규 | `src/lib/line-chart.ts`, `src/components/LineChart.astro`, `src/content.config.ts`, `src/content/learn/interest-rates.mdx`, `src/pages/learn/index.astro`, `src/pages/learn/[...slug].astro`, `src/data/history.json`(생성물) |
| 재사용 | `src/lib/gauge.ts`(패턴), `src/lib/signal-style.ts`/signal 토큰(차트 색), 기존 `fredLatest()` 옆 `fredSeries()` |
