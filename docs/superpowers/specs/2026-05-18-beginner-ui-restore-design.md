# 초보 친화 정보량 복원 + 컴포넌트 분해 설계서

- 날짜: 2026-05-18
- 상태: 설계 승인 대기 → 사용자 검토
- 선행 작업: `2026-05-15-astro-migration-design.md`(Python→Astro), `2026-05-16-m3-theme-darklight-design.md`(M3 테마)

## 1. 문제 정의

Astro 마이그레이션(`dashboard.py` 1547줄 → `src/pages/index.astro` 263줄) 과정에서
초보 친화 정보가 대거 누락됐다. M3 테마 머지(a00181b)는 index.astro를 23줄만
변경했으므로 무관하다. 데이터 파이프라인(`latest.json`)·신호 로직(`signal.ts`)은
온전하며, **손실은 순수하게 표현(presentation) 계층**이다.

### 1.1 소실 항목 (구버전 `build_html` 대비)

1. 헤더 부제 "주식 초보자를 위한 투자 타이밍 신호등"
2. 섹션 분리: 🎯 타이밍 신호 vs 💰 밸류에이션·참고(장기 맥락용) + 💡 안내 박스
3. 공포·탐욕 반원 게이지 SVG (메인 뷰)
4. 매크로 카드 하단 한 줄 초보 힌트 + ⓘ + 한글 배지(긍정/주의/위험) + 영문 부제
5. 종합 신호 7개 컴포넌트 배지(클릭 가능) + 방법론 설명 줄
6. 초보자 용어 가이드 16개 접이식 글로사리 — 완전 삭제
7. 상세 모달: 현재 수치 / 이 지표가 뭔가요 / 어떻게 읽나요(임계값 표) / ⚠️ 주의 / 검증·원본 링크 → 한 문장으로 축소
8. ETF 카드 인라인 힌트(RSI 30↓매수·70↑주의, MA200 추세, 52주 저점/고점 바)
9. 푸터: 데이터 출처 + 투자 권유 아님 면책

### 1.2 모달 위치 버그

현재 네이티브 `<dialog>` + `showModal()`가 화면 중앙이 아닌 **좌상단에 고정**된다.
원인: Tailwind v4 preflight가 `<dialog>`의 UA 기본 중앙정렬(`margin:auto`)을
무력화함. 구버전은 `fixed inset-0 flex` 오버레이 div라 이 버그가 없었다.

## 2. 결정 사항 (브레인스토밍 합의)

- 복원 범위: **전체 완전 복원** — 위 9개 항목 정보량 100% 복귀
- 시각 톤: 현재 M3 다크/라이트 테마·디자인 톤 **유지** (직전 머지 작업 무손상)
- 파일 구조: **지금 컴포넌트 분해** (CLAUDE.md "단일 페이지 유지" 규약을 본 PR로 갱신)
- 설명문 정확성: 원문 복원하되 **현 TS 파이프라인과 불일치하는 caveat·source는 정정**
- 기술 스택: **순수 `.astro` 컴포넌트** — shadcn/ui(React 필수)·신규 토큰 시스템 미도입.
  shadcn 컴포넌트의 해부 구조(Card 하위 분해 등)만 패턴으로 차용

## 3. 아키텍처

```
src/
├─ components/
│  ├─ Header.astro          # 제목 + 부제 + 업데이트 시각(점) + 테마 토글
│  ├─ SectionHeading.astro  # 이모지 + 제목 + 부제 (재사용)
│  ├─ CompositeSignal.astro # 신호등 dot·label·comment·4카운트 + 7컴포넌트 배지 + 방법론 줄
│  ├─ GaugeFearGreed.astro  # 반원 공포·탐욕 게이지 SVG
│  ├─ MacroCard.astro       # 이모지·영문부제·한글배지·값·신호문구·하단 힌트+ⓘ
│  ├─ EtfCard.astro         # 가격·등락배지·52주바·RSI·MA200 추세 (행 클릭)
│  ├─ Glossary.astro        # <details>/<summary> 16개 용어
│  ├─ IndicatorModal.astro  # 네이티브 <dialog> 리치 레이아웃
│  └─ Footer.astro          # 데이터 출처 + 면책
├─ lib/
│  └─ indicator-info.ts     # 신규: INDICATOR_INFO 타입드 상수
└─ pages/index.astro        # 얇은 조립 레이어 (~80줄)
```

`index.astro`는 `signal.ts`·`computeComposite`로 데이터를 가공해 props로 내려주고
컴포넌트를 배치하는 역할만 한다.

## 4. 데이터/콘텐츠 계층 — `src/lib/indicator-info.ts`

구 `dashboard.py`의 `INDICATOR_INFO` 전 항목을 타입드 상수로 이식.

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

export const INDICATOR_INFO: Record<string, IndicatorInfo>;
```

키: `fear_greed`, `vix`, `yield_spread`, `ma200`, `ma_cross`, `hy_spread`,
`dxy_trend`, `cape`, `sp500pe`, `buffett`, `dxy`, `usdkrw`, `rsi`, `52w`,
`overall` (구버전 키 체계 유지).

### 4.1 정확성 정정 (CLAUDE.md 환각방지 규칙 준수)

원문 복원이 원칙이나, 현 TS 파이프라인과 사실이 어긋나는 문구만 정정한다:

- `yield_spread.caveat`: "yfinance ^IRX(Bank Discount) 사용" →
  **"FRED DGS10−DGS3MO Constant Maturity 사용 (Bank Discount 근사보다 정확)"**
- `buffett.caveat`: "Wilshire 5000 ÷ 하드코딩 GDP, GDP 상수 수동 갱신(~line 160)" →
  **"Yahoo ^W5000 ÷ FRED GDP × 100. GDP는 FRED에서 분기 자동 반영.
  FRED WILL5000PRFC는 2026-05 단종되어 Yahoo ^W5000 사용"**
- 나머지 항목 `sourceUrl`/`sourceLabel`은 현 소스(FRED·Yahoo·multpl·CNN)와
  대조해 일치 항목 유지, 불일치만 수정. 글로사리 본문(실측 16개)은 사실 정확성이
  유지되는 한 원문 그대로 복원(초보 친화 표현 보존)

## 5. 페이지 구조 (복원 순서)

1. `Header` — 제목 + 부제 복원 + 업데이트 시각 + 테마 토글(기존 유지)
2. `CompositeSignal` — 신호등 원형 dot, 라벨, 코멘트, 긍정/중립/주의/위험 4카운트,
   7개 컴포넌트 배지(클릭→해당 지표 모달), 방법론 줄
3. `SectionHeading` 🎯 타이밍 신호 + 부제 → `GaugeFearGreed` + `MacroCard` ×7
   (fear_greed·vix·yield_spread·ma200·ma_cross·hy_spread·dxy_trend)
4. 💡 안내 박스 + `SectionHeading` 💰 밸류에이션·참고 + `MacroCard` ×5
   (cape·sp500_pe·buffett·dxy·usdkrw)
5. `SectionHeading` 📈 지수 & ETF → `EtfCard` 그리드
6. `SectionHeading` 📖 초보자 용어 가이드 → `Glossary` (16개)
7. `Footer`

## 6. 모달 메커니즘 (버그 수정 + 리치 콘텐츠)

- 클릭 요소 공통 속성: `data-indicator="<key>"`, `data-current="<현재값 문자열>"`,
  `data-sig="<good|neutral|warn|bad>"` (MacroCard·EtfCard 행·컴포넌트 배지)
- `INDICATOR_INFO`를 `<script type="application/json" id="indicator-info">`로 임베드
  (Astro 자동 이스케이프) → 인라인 스크립트가 `JSON.parse`
- 클릭 시: 키 조회 → 모달 DOM에 **`textContent`로만** 주입.
  `innerHTML`/`set:html` 금지(CLAUDE.md 보안 규칙). 임계값 표 행은
  `createElement`+`textContent`로 생성
- **중앙정렬 버그 수정** — `src/styles/global.css`에 추가:
  ```css
  #indicator-modal[open]{ position: fixed; inset: 0; margin: auto; }
  ```
  네이티브 `<dialog>` 유지(포커스 트랩·ESC·top-layer·배경 inert 브라우저 제공)
- 모달 레이아웃: 현재 수치 / "이 지표가 뭔가요?" / "어떻게 읽나요?"(임계값 표) /
  ⚠️ 주의사항 / 검증·원본 링크(`target="_blank" rel="noopener noreferrer"`)
- 스크롤: `max-h-[90vh] overflow-y-auto`, sticky 헤더 + 닫기 버튼
- 닫기: × 버튼, ESC(네이티브), 배경(backdrop) 클릭

## 7. 테마·스타일

- 기존 M3 토큰·유틸(`bg-surface`·`text-muted`·`border-border`·`text-good/warn/bad`·
  opacity-slash) 그대로 사용 — **신규 토큰 0**
- 다크/라이트 토글·no-FOUC 스크립트·`color-scheme` 동기화·WCAG 신호색 2셋
  **무손상** (직전 머지 작업 보존)
- 시각 디테일 복원: `rounded-2xl` 카드, 한글 배지, ⓘ/▶ 아이콘, hover 상태
- CLAUDE.md 갱신: "컴포넌트 분해 의도적 안 함 — 후속 PR로 이연" → 분해 완료로
  수정 + 컴포넌트 맵 문서화

## 8. 비범위 (Out of Scope)

- 데이터 파이프라인(`scripts/fetch-data.ts`)·신호 임계값 로직 변경 없음
- 신규 지표 추가 없음 (구버전 정보량 복원에 한정)
- shadcn/ui·React·기타 프레임워크 도입 없음
- 새 색/디자인 시스템 도입 없음 (M3 테마 유지)
- 새로고침 버튼(`refresh_block`)은 구버전에서도 serve_mode 전용 →
  정적 사이트엔 비해당, 복원 제외

## 9. 검증

- `npm run build` (기존 `latest.json` 사용) → 타입/빌드 통과
- `npm run dev` + Playwright 실브라우저:
  - 모달이 **양 테마에서 화면 중앙** 표시 (좌상단 버그 해소)
  - 매크로 카드·컴포넌트 배지·ETF 행 클릭 → 올바른 지표 모달
  - 모달 닫기 3종(×·ESC·배경) 동작
  - 글로사리 16개 펼침/접힘
  - 다크↔라이트 토글·localStorage 기억·새로고침 FOUC 없음
  - 콘솔 에러 0
- 1.1의 9개 소실 항목 누락 0 체크리스트 대조
