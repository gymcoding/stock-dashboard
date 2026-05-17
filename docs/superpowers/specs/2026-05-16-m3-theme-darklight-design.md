# stock-dashboard: Material 3 테마 + 다크/라이트 모드 설계서

- 작성일: 2026-05-16
- 작성자: 짐코딩 + Claude
- 상태: 설계 확정, 구현 계획 작성 대기
- 브랜치: `feat/m3-theme-darklight`
- 선행: Astro 마이그레이션 (main 머지·techboost.dev 라이브, 2026-05-16)
- 후속 문서: `2026-05-16-m3-theme-darklight-plan.md` (writing-plans로 생성 예정)

---

## 1. 목적과 범위

### 1.1 목적

Astro 마이그레이션의 임시 Toss 다크 팔레트를 **Material 3 테마**로 교체하고, **다크/라이트 모드 토글**을 추가한다. 인프라는 그대로, 색 토큰 + 테마 전환만.

### 1.2 범위에 포함

- `src/styles/global.css`를 M3 토큰 + CSS 변수 간접 참조 구조로 교체
- 다크/라이트 2개 토큰 셋, 런타임 class 토글로 스왑
- no-FOUC 인라인 스크립트 (Base.astro `<head>`)
- 헤더 우측 테마 토글 버튼 + vanilla JS 핸들러 (index.astro)
- signal 색(good/warn/bad/neutral) 라이트/다크 2셋 손튜닝
- 브랜드/강조색을 M3 primary(그린)로 교체

### 1.3 범위에 포함하지 않음

- 컴포넌트 분해·M3 컴포넌트 패턴(elevation/FAB/ripple 등) 도입 — 단일 페이지 유지
- 차트·신규 시각화
- 시스템 `prefers-color-scheme` 자동 추종 (다크 기본 + 수동 토글만)
- 데이터 파이프라인·워크플로 변경 (선행 PR에서 완료)

### 1.4 잠긴 결정 (재논의 불필요)

1. signal 색은 트래픽 신호등 의미라 M3 롤 매핑 안 함 — 고정, 다크/라이트별 대비만 조정
2. 다크 기본 + 사용자 토글 + localStorage 기억 + no-FOUC
3. 토글: 헤더 우측 아이콘
4. 단일 페이지 유지 (과한 컴포넌트화 금지 — 대표 선호)
5. M3 토큰 → Tailwind @theme 매핑, 컴포넌트는 Astro 재작성 (M3 Web Component 복붙 아님)
6. 대비 변형: 기본 (light.css/dark.css), 중·고대비 미사용
7. 브랜드/강조색: M3 primary(그린)로 교체 (기존 Toss 블루 폐기)
8. 전환 메커니즘: CSS 변수 간접 참조 (A안)

### 1.5 자산

`material-theme-css/` (repo 루트, untracked — 본 PR에서 git 추적 안 함, 값만 참조). Material Theme Builder 웹앱 export, 그린 시드. light.css = `.light{--md-sys-color-*}`, dark.css = `.dark{--md-sys-color-*}`. 6개 파일 중 **기본 light.css/dark.css만 사용**.

---

## 2. 아키텍처 — CSS 변수 간접 참조 (A안)

Tailwind v4 `@theme`는 빌드 타임 정적. 런타임 테마 스왑을 위해 `@theme` 토큰이 런타임 CSS 변수(`var(--c-*)`)를 가리키고, `:root`/`.light`에서 그 변수 값을 오버라이드한다.

```
@theme { --color-bg: var(--c-bg) ... }   ← 빌드 정적, 유틸 생성(bg-bg 등)
:root, .dark { --c-bg: <다크값> ... }     ← 기본(다크) + no-FOUC 안전판
.light { --c-bg: <라이트값> ... }          ← 라이트 오버라이드
<html class="dark|light">                 ← no-FOUC 스크립트가 첫 페인트 전 확정
```

기존 유틸 클래스(`bg-bg`·`text-text`·`bg-surface/40`·`text-good`·signalBg/signalText)는 **전부 무수정**. Tailwind가 `--color-*`에서 생성한 유틸이 `var(--c-*)`를 가리켜 런타임 스왑.

### 2.1 컴포넌트 책임

| 파일 | 책임 | 변경 |
|---|---|---|
| `src/styles/global.css` | @theme 토큰 indirection + 다크/라이트 변수 2셋 + 아이콘 토글 CSS | 전체 교체 (34줄 → ~70줄) |
| `src/layouts/Base.astro` | `<head>` no-FOUC 인라인 스크립트 추가 | head에 스크립트 1블록 추가 |
| `src/pages/index.astro` | `<header>` flex + 토글 버튼, 하단 토글 핸들러 스크립트 | 헤더 영역 + 스크립트 1블록 (카드/그리드/모달/게이지 무수정) |

---

## 3. 토큰 매핑

### 3.1 시맨틱 토큰 → M3 롤 (다크/라이트)

| 우리 토큰 | 다크 (dark.css) | 라이트 (light.css) | M3 롤 |
|---|---|---|---|
| `--c-bg` | `rgb(18 20 14)` | `rgb(249 250 239)` | surface |
| `--c-surface` | `rgb(30 32 26)` | `rgb(238 239 227)` | surface-container |
| `--c-surface-hi` | `rgb(40 43 36)` | `rgb(232 233 222)` | surface-container-high |
| `--c-border` | `rgb(68 72 61)` | `rgb(197 200 186)` | outline-variant |
| `--c-text` | `rgb(226 227 216)` | `rgb(26 28 22)` | on-surface |
| `--c-muted` | `rgb(197 200 186)` | `rgb(68 72 61)` | on-surface-variant |
| `--c-subtle` | `rgb(143 146 133)` | `rgb(117 121 108)` | outline |
| `--c-brand` | `rgb(177 209 138)` | `rgb(76 102 43)` | primary |
| `--c-brand-hi` | `rgb(205 237 163)` | `rgb(53 78 22)` | primary-fixed / on-primary-container |

### 3.2 Signal 색 (고정 2셋, M3 무관)

| signal | 다크 (배경 rgb18,20,14) | 라이트 (배경 rgb249,250,239) |
|---|---|---|
| `--c-good` | `#00C896` | `#00875A` |
| `--c-warn` | `#FF9500` | `#B26A00` |
| `--c-bad` | `#F04452` | `#C5283D` |
| `--c-neutral` | `#8B95A1` | `#5A6470` |

라이트 값은 제안 — 구현 시 WCAG AA 4.5:1 실측 후 미세조정. 다크는 기존 검증값 유지.

---

## 4. global.css 최종 구조

```css
@import "tailwindcss";

@theme {
  --color-bg:         var(--c-bg);
  --color-surface:    var(--c-surface);
  --color-surface-hi: var(--c-surface-hi);
  --color-border:     var(--c-border);
  --color-text:       var(--c-text);
  --color-muted:      var(--c-muted);
  --color-subtle:     var(--c-subtle);
  --color-brand:      var(--c-brand);
  --color-brand-hi:   var(--c-brand-hi);
  --color-good:       var(--c-good);
  --color-warn:       var(--c-warn);
  --color-bad:        var(--c-bad);
  --color-neutral:    var(--c-neutral);
  --font-sans: 'Pretendard Variable', Pretendard, system-ui, sans-serif;
}

:root, .dark {
  --c-bg: rgb(18 20 14);
  --c-surface: rgb(30 32 26);
  --c-surface-hi: rgb(40 43 36);
  --c-border: rgb(68 72 61);
  --c-text: rgb(226 227 216);
  --c-muted: rgb(197 200 186);
  --c-subtle: rgb(143 146 133);
  --c-brand: rgb(177 209 138);
  --c-brand-hi: rgb(205 237 163);
  --c-good: #00C896;  --c-warn: #FF9500;
  --c-bad: #F04452;   --c-neutral: #8B95A1;
}

.light {
  --c-bg: rgb(249 250 239);
  --c-surface: rgb(238 239 227);
  --c-surface-hi: rgb(232 233 222);
  --c-border: rgb(197 200 186);
  --c-text: rgb(26 28 22);
  --c-muted: rgb(68 72 61);
  --c-subtle: rgb(117 121 108);
  --c-brand: rgb(76 102 43);
  --c-brand-hi: rgb(53 78 22);
  --c-good: #00875A;  --c-warn: #B26A00;
  --c-bad: #C5283D;   --c-neutral: #5A6470;
}

/* 아이콘 토글 */
.dark .light-icon, .light .dark-icon { display: none; }

html, body {
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
}
```

---

## 5. Base.astro — no-FOUC

`<head>` 최상단(charset 직후, global.css import·콘텐츠보다 먼저):

```astro
<script is:inline>
  (function () {
    try {
      var t = localStorage.getItem('theme');
      document.documentElement.classList.add(t === 'light' ? 'light' : 'dark');
    } catch (e) {
      document.documentElement.classList.add('dark');
    }
  })();
</script>
```

`:root`가 이미 다크라 스크립트 실패/지연 시에도 다크 (이중 방어). class 하나만 부여.

---

## 6. index.astro — 헤더 토글 + 핸들러

### 6.1 헤더 (현 `index.astro:124` 교체)

```astro
<header class="mb-8 flex items-start justify-between gap-4">
  <div>
    <h1 class="text-2xl sm:text-3xl font-bold tracking-tight">투자 지표 대시보드</h1>
    <p class="text-sm text-muted mt-2">최종 업데이트: {generatedKst} KST</p>
  </div>
  <button id="theme-toggle" type="button" aria-label="다크/라이트 모드 전환"
    class="shrink-0 rounded-full p-2 text-muted hover:text-text hover:bg-surface-hi transition">
    <span class="dark-icon">☀️</span>
    <span class="light-icon">🌙</span>
  </button>
</header>
```

### 6.2 토글 핸들러 (index.astro 하단, 모달 스크립트 부근 `<script is:inline>`)

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

vanilla JS (프레임워크 없음). `set:html` 미사용 (보안 기준 유지).

---

## 7. 검증 (구현 단계 체크리스트)

| 검증 | 방법 |
|---|---|
| 양 모드 토큰 스왑 | `npm run dev` → 토글, 13개 토큰 전환 확인 |
| opacity 슬래시 | `bg-surface/40`·`bg-good/15`·`text-text/90`·`bg-neutral/20` 라이트 정상 (color-mix + var) |
| signal 대비 | 라이트 배경 WCAG AA 4.5:1 실측 → 미달 시 §3.2 미세조정 |
| 게이지 SVG | 라이트에서 needle(brand)·호(border)·텍스트(muted) 시인성 |
| no-FOUC | 라이트 저장 상태 새로고침 → 다크 깜빡임 없음 |
| localStorage 차단 | 시크릿/차단 → 다크 fallback |
| 모달 | 양 모드 `<dialog>` 배경·텍스트·backdrop 정상 |
| 빌드·배포 | `npm run build` 통과, techboost.dev 양 모드 |

---

## 8. 리스크

| 리스크 | 영향 | 완화 |
|---|---|---|
| Tailwind v4 opacity-slash가 var() 기반 색에서 안 먹힘 | 카드 틴트 깨짐 | 구현 1단계에서 즉시 실측. 안 되면 `--c-*`를 채널 분리(`R G B`)해 `rgb(var(--c) / .15)` 패턴으로 폴백 |
| 라이트 모드 signal 대비 부족 | 신호 가독성·접근성 저하 | WCAG 실측 + 손튜닝 (§3.2 값은 제안) |
| M3 그린 brand가 게이지·링크에서 저시인성(라이트) | UX 저하 | 게이지 needle은 brand 유지하되 라이트에서 brand 채도/명도 실측 |
| no-FOUC 스크립트 위치 오류 | 다크→라이트 깜빡임 | charset 직후·CSS import 전 배치 강제, 빌드 산출 HTML로 순서 검증 |

## 9. 배포

선행 PR과 동일 — `feat/m3-theme-darklight` → main 머지 시 GH Actions(fetch→build→Wrangler) 자동 배포. 데이터·워크플로 변경 없음. CLAUDE.md(gitignored)의 Tailwind 섹션은 구현 후 로컬 갱신.
