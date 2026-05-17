# M3 테마 + 다크/라이트 모드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** stock-dashboard의 임시 Toss 다크 팔레트를 Material 3 토큰으로 교체하고 다크/라이트 모드 토글을 추가한다.

**Architecture:** Tailwind v4 `@theme` 토큰이 런타임 CSS 변수(`var(--c-*)`)를 가리키고, `:root`/`.dark`(기본)와 `.light`에서 변수 값을 오버라이드. `<html>` class를 no-FOUC 인라인 스크립트로 첫 페인트 전 확정, 헤더 토글 버튼이 class·localStorage 전환. 기존 유틸 클래스 전부 무수정.

**Tech Stack:** Astro 5.x · Tailwind v4 (`@tailwindcss/vite`) · vanilla JS · 변경 파일 3개 (global.css, Base.astro, index.astro)

**Spec:** `docs/superpowers/specs/2026-05-16-m3-theme-darklight-design.md` (commit `469aea1`)

---

## File Structure

| 파일 | 책임 | 변경 |
|---|---|---|
| `src/styles/global.css` | @theme indirection + 다크/라이트 변수 2셋 + 아이콘 토글 CSS | 전체 교체 (34→~70줄) |
| `src/layouts/Base.astro` | `<head>` no-FOUC 인라인 스크립트 | head에 1블록 추가 |
| `src/pages/index.astro` | `<header>` flex+토글 버튼, 하단 토글 핸들러 스크립트 | 헤더+스크립트 (카드/그리드/모달/게이지 무수정) |

테스트 프레임워크 없음(선행 PR과 동일 — 범위 밖). 검증은 build + dev 시각 확인 + WCAG 대비 실측.

---

### Task 1: global.css — M3 토큰 indirection + opacity-slash 검증

이 task가 아키텍처 핵심. opacity-slash(`bg-surface/40` 등)가 `var()` 기반 @theme 색에서 동작하는지 **여기서 결판**.

**Files:**
- Modify: `src/styles/global.css` (전체 교체)

- [ ] **Step 1: global.css 전체 교체**

`src/styles/global.css`를 다음으로 완전 교체:

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

.dark .light-icon, .light .dark-icon { display: none; }

html, body {
  background: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
}
```

- [ ] **Step 2: 빌드**

Run:
```bash
cd /Users/gymcoding/Company/projects/stock-dashboard && npm run build
```
Expected: 빌드 성공 (1 page built).

- [ ] **Step 3: opacity-slash 동작 검증 (결정 게이트)**

기존 `index.astro`는 `bg-surface/40`·`bg-good/15`·`text-text/90`·`bg-neutral/20`·`border-good/30` 등을 이미 사용. dist CSS에서 이들이 유효한 color-mix로 생성됐는지 확인:

```bash
cd /Users/gymcoding/Company/projects/stock-dashboard
CSS=$(ls dist/_astro/*.css | head -1)
echo "=== /40 류 슬래시 생성 확인 ===" 
grep -o "color-mix([^)]*--color-surface[^)]*)" "$CSS" | head -2
grep -o "color-mix([^)]*--color-good[^)]*)" "$CSS" | head -2
echo "=== 빈/깨진 색 없는지 ==="
grep -c "color-mix(in oklab" "$CSS"
```
Expected: `color-mix(in oklab, var(--color-surface) 40%, transparent)` 형태가 출력됨 (count ≥ 1).

**결정 게이트:**
- ✅ color-mix가 `var(--color-surface)` 참조하며 정상 생성 → 그대로 진행 (Step 5)
- ❌ 빈 값/깨짐/슬래시 클래스 누락 → **Step 4 채널분리 폴백 적용**

- [ ] **Step 4: (조건부) 채널분리 RGB 폴백**

Step 3가 ❌일 때만 실행. `--c-*`를 `R G B` 채널로, `@theme`를 `rgb(var(--c-*))`로 변경:

```css
@theme {
  --color-bg:         rgb(var(--c-bg));
  --color-surface:    rgb(var(--c-surface));
  --color-surface-hi: rgb(var(--c-surface-hi));
  --color-border:     rgb(var(--c-border));
  --color-text:       rgb(var(--c-text));
  --color-muted:      rgb(var(--c-muted));
  --color-subtle:     rgb(var(--c-subtle));
  --color-brand:      rgb(var(--c-brand));
  --color-brand-hi:   rgb(var(--c-brand-hi));
  --color-good:       rgb(var(--c-good));
  --color-warn:       rgb(var(--c-warn));
  --color-bad:        rgb(var(--c-bad));
  --color-neutral:    rgb(var(--c-neutral));
  --font-sans: 'Pretendard Variable', Pretendard, system-ui, sans-serif;
}
:root, .dark {
  --c-bg: 18 20 14;       --c-surface: 30 32 26;
  --c-surface-hi: 40 43 36; --c-border: 68 72 61;
  --c-text: 226 227 216;  --c-muted: 197 200 186;
  --c-subtle: 143 146 133; --c-brand: 177 209 138;
  --c-brand-hi: 205 237 163;
  --c-good: 0 200 150;    --c-warn: 255 149 0;
  --c-bad: 240 68 82;     --c-neutral: 139 149 161;
}
.light {
  --c-bg: 249 250 239;    --c-surface: 238 239 227;
  --c-surface-hi: 232 233 222; --c-border: 197 200 186;
  --c-text: 26 28 22;     --c-muted: 68 72 61;
  --c-subtle: 117 121 108; --c-brand: 76 102 43;
  --c-brand-hi: 53 78 22;
  --c-good: 0 135 90;     --c-warn: 178 106 0;
  --c-bad: 197 40 61;     --c-neutral: 90 100 112;
}
```
(아이콘 토글 CSS·html/body 블록은 Step 1과 동일 유지). 재빌드 → Step 3 재검증 (이번엔 `rgb(var(--color-surface))` 기반 color-mix 확인). 채택 시 spec §8 리스크 항목을 "채널분리 폴백 적용됨"으로 본 plan 하단 메모.

- [ ] **Step 5: 다크 시각 회귀 확인**

Run:
```bash
cd /Users/gymcoding/Company/projects/stock-dashboard && timeout 12 npm run preview &
sleep 5 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:4321
```
브라우저 `http://localhost:4321` → 기본(다크) 화면이 M3 다크 톤(배경 rgb18,20,14 올리브블랙)으로 렌더, 카드·게이지·모달·signal 색 정상. (class 없어도 `:root` 다크라 정상)

- [ ] **Step 6: 커밋**

```bash
git add src/styles/global.css
git commit -m "global.css — M3 토큰 indirection + 다크/라이트 변수 2셋

@theme를 var(--c-*) 간접 참조로, :root/.dark 기본 + .light
오버라이드. M3 light/dark 토큰 매핑, signal 색 고정 2셋.
opacity-slash var() 호환 검증 통과(또는 채널분리 폴백 적용)."
```

---

### Task 2: Base.astro — no-FOUC 스크립트

**Files:**
- Modify: `src/layouts/Base.astro`

- [ ] **Step 1: 현재 head 구조 확인**

Run:
```bash
cd /Users/gymcoding/Company/projects/stock-dashboard && grep -n "<head>\|charset\|global.css\|<title>\|</head>" src/layouts/Base.astro
```
no-FOUC 스크립트는 `<meta charset>` 직후, `import "../styles/global.css"`(프론트매터)·`<title>`·기타 head 콘텐츠보다 **먼저** 들어가야 함. (global.css는 Astro 프론트매터 import라 빌드 시 head에 주입되지만, 인라인 스크립트는 `<head>` 마크업 최상단에 두면 파서가 먼저 실행)

- [ ] **Step 2: no-FOUC 인라인 스크립트 추가**

`src/layouts/Base.astro`의 `<head>` 여는 태그 바로 다음 줄(`<meta charset="utf-8" />` 직후)에 삽입:

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

다른 head 요소·body는 변경 없음.

- [ ] **Step 3: 빌드 + head 순서 검증**

Run:
```bash
cd /Users/gymcoding/Company/projects/stock-dashboard && npm run build
grep -o "classList.add\|<title>\|stylesheet" dist/index.html | head -5
```
Expected: `classList.add`가 `<title>`·`stylesheet`보다 **앞서** 출력 (head 최상단 위치 확인).

- [ ] **Step 4: 커밋**

```bash
git add src/layouts/Base.astro
git commit -m "Base.astro — no-FOUC 테마 스크립트

<head> 최상단(charset 직후) 인라인 스크립트가 첫 페인트 전
localStorage 기반 dark/light class 확정. 기본 다크, 예외 시
다크 fallback. :root 다크와 이중 방어."
```

---

### Task 3: index.astro — 헤더 토글 버튼 + 핸들러

**Files:**
- Modify: `src/pages/index.astro`

- [ ] **Step 1: 현재 헤더 확인**

Run:
```bash
cd /Users/gymcoding/Company/projects/stock-dashboard && sed -n '123,128p' src/pages/index.astro
```
현재 `<header class="mb-8">` + h1 + 업데이트 시각 `<p>` 구조 확인.

- [ ] **Step 2: 헤더를 flex + 토글 버튼으로 교체**

`src/pages/index.astro`의 `<header>` 블록(h1·업데이트 p 포함)을 다음으로 교체:

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
(h1·`{generatedKst}` 텍스트 동일 유지 — flex 래퍼만 추가)

- [ ] **Step 3: 토글 핸들러 스크립트 추가**

`index.astro` 하단의 기존 모달 `<script is:inline>` 블록 **다음**에 새 블록 추가 (모달 스크립트와 합치지 말 것 — 책임 분리):

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

- [ ] **Step 4: 빌드 + 동작 검증**

Run:
```bash
cd /Users/gymcoding/Company/projects/stock-dashboard && npm run build
grep -oc "theme-toggle\|dark-icon\|light-icon" dist/index.html
timeout 15 npm run preview & sleep 5 && curl -s http://localhost:4321 | grep -oc "theme-toggle"
```
Expected: `theme-toggle`·`dark-icon`·`light-icon` 마크업 dist에 존재.

브라우저 `http://localhost:4321` 수동 확인:
- 헤더 우측 ☀️ 보임(기본 다크)
- 클릭 → 라이트 모드(크림 배경 rgb249,250,239)로 전환, 아이콘 🌙로 바뀜
- 새로고침 → 라이트 유지(localStorage), 다크 깜빡임 없음(no-FOUC)
- 다시 클릭 → 다크 복귀
- 카드·게이지·모달 양 모드 정상

- [ ] **Step 5: 커밋**

```bash
git add src/pages/index.astro
git commit -m "index.astro — 헤더 우측 테마 토글 + vanilla JS 핸들러

헤더 flex 래퍼 + ☀️/🌙 토글 버튼(아이콘은 .dark/.light CSS로
전환). 클릭 시 html class·localStorage 갱신. 모달 스크립트와
분리된 별도 inline 스크립트. set:html 미사용."
```

---

### Task 4: signal 색 라이트 WCAG AA 실측·조정

라이트 배경 `rgb(249 250 239)` 대비 good/warn/bad/neutral이 WCAG AA(텍스트 4.5:1) 충족하는지 실측, 미달 시 조정.

**Files:**
- Modify: `src/styles/global.css` (`.light` signal 변수만, 미달 시)

- [ ] **Step 1: 대비비 측정 스크립트**

임시 `scripts/_contrast.mjs` 생성:

```js
// WCAG 상대휘도 + 대비비. 라이트 배경 rgb(249,250,239)
function lum(r, g, b) {
  const f = c => { c /= 255; return c <= 0.03928 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4); };
  return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b);
}
function ratio(fg, bg) {
  const L1 = lum(...fg) + 0.05, L2 = lum(...bg) + 0.05;
  return (Math.max(L1, L2) / Math.min(L1, L2)).toFixed(2);
}
const bg = [249, 250, 239];
const hex = h => [1,3,5].map(i => parseInt(h.slice(i, i+2), 16));
const cases = {
  good: '#00875A', warn: '#B26A00', bad: '#C5283D', neutral: '#5A6470',
};
for (const [k, v] of Object.entries(cases)) {
  const r = ratio(hex(v), bg);
  console.log(`${k} ${v}: ${r}:1 ${r >= 4.5 ? 'PASS' : 'FAIL(<4.5)'}`);
}
```

Run:
```bash
cd /Users/gymcoding/Company/projects/stock-dashboard && node scripts/_contrast.mjs
```

- [ ] **Step 2: 미달 색 조정**

FAIL 항목이 있으면 더 어둡게(채도 유지, 명도↓) 조정해 4.5:1 이상 만들기. 조정 후보(미달 시 사용):
- `good` 미달 → `#006B47`
- `warn` 미달 → `#8F5500`
- `bad` 미달 → `#B01E32`
- `neutral` 미달 → `#4A5560`

조정값을 `scripts/_contrast.mjs`의 `cases`에 넣어 재실행, 전부 PASS 확인. 그 최종값으로 `src/styles/global.css`의 `.light` signal 변수(`--c-good`/`--c-warn`/`--c-bad`/`--c-neutral`) 갱신. 전부 PASS면 변경 없음.

> 참고: `neutral`은 보조 텍스트/배경 용도라 4.5:1 엄격 적용이 과할 수 있으나, 본 plan은 일관성 위해 4.5:1 목표. 3:1만 충족해도 무방하다고 판단되면 그 근거를 커밋 메시지에 기록.

- [ ] **Step 3: 임시 스크립트 제거 + 커밋**

```bash
cd /Users/gymcoding/Company/projects/stock-dashboard
rm scripts/_contrast.mjs
git add src/styles/global.css 2>/dev/null
git diff --cached --quiet && echo "조정 불필요(전부 PASS) — 커밋 생략" || git commit -m "global.css — 라이트 signal 색 WCAG AA 4.5:1 충족 조정"
```
(전부 PASS여서 변경 없으면 커밋 생략 — 정상)

---

### Task 5: 양 모드 종합 검증 (사용자 체크포인트)

**Files:** 없음 — 검증만

- [ ] **Step 1: 빌드 + preview**

```bash
cd /Users/gymcoding/Company/projects/stock-dashboard && npm run build && (timeout 60 npm run preview &) && sleep 5 && curl -s -o /dev/null -w "%{http_code}\n" http://localhost:4321
```

- [ ] **Step 2: 체크리스트 (사용자 브라우저 확인)**

http://localhost:4321 에서:
- [ ] 기본 진입 = 다크(M3 올리브블랙), 깜빡임 없음
- [ ] 헤더 우측 ☀️ 클릭 → 라이트(크림) 전환, 아이콘 🌙
- [ ] 라이트에서: 종합신호 카드·매크로 9·ETF 6·게이지 SVG·모달 전부 가독·시인성 정상
- [ ] signal 색(good/warn/bad/neutral) 라이트에서 의미 구분 명확
- [ ] opacity 틴트 카드(`bg-good/15` 등) 양 모드 깨짐 없음
- [ ] 새로고침 → 마지막 선택 모드 유지(localStorage), no-FOUC
- [ ] 모달 양 모드 backdrop·텍스트 정상
- [ ] 모바일(창 좁힘) 양 모드 정상

- [ ] **Step 3: 사용자 보고**

> "M3 테마 + 다크/라이트 토글 양 모드 검증 완료. 머지 방식 결정해주세요." 로 보고하고 사용자 응답 대기 (HUMAN CHECKPOINT).

---

### Task 6: CLAUDE.md Tailwind 섹션 로컬 갱신

**Files:**
- Modify: `CLAUDE.md` (gitignored — 디스크 갱신만, 커밋 안 함)

- [ ] **Step 1: Tailwind 섹션 갱신**

`CLAUDE.md`의 "Tailwind CSS v4 Notes" 영역에서 "현재 Toss 다크 팔레트는 임시 베이스..." 문장을 다음으로 교체:

```
M3 토큰 기반 다크/라이트 테마. `@theme`가 `var(--c-*)` 간접 참조,
`:root`/`.dark`(기본) + `.light` 오버라이드, `<html>` class 토글.
no-FOUC 인라인 스크립트(Base.astro head 최상단), 헤더 우측 토글
(index.astro). signal 색은 트래픽 신호등 의미라 M3 무관 고정 2셋.
기본 다크, prefers-color-scheme 미추종(수동 토글만).
```

- [ ] **Step 2: 확인 (커밋 없음)**

```bash
cd /Users/gymcoding/Company/projects/stock-dashboard
git check-ignore CLAUDE.md && echo "gitignored 확인 — 커밋 불필요(디스크 갱신만)"
grep -c "var(--c-" CLAUDE.md
```
Expected: `gitignored 확인` 출력. CLAUDE.md는 커밋 대상 아님 — 디스크 갱신이 산출물.

---

## Self-Review

**Spec coverage:** §2 아키텍처→Task1, §3 토큰→Task1, §4 global.css→Task1, §5 no-FOUC→Task2, §6 헤더토글→Task3, §7 검증→Task5, §3.2 signal 대비→Task4, §9 CLAUDE.md→Task6. 전 항목 커버.

**Placeholder scan:** TBD/TODO 없음. signal 라이트값은 Task4에서 실측·확정(설계의 "제안"을 plan에서 측정 task로 구체화). 채널분리 폴백은 Task1 Step4에 완전 코드 제공(조건부, 추측 아님).

**Type/이름 일관성:** `--c-*` 변수명·`--color-*` @theme 토큰명·`theme-toggle` id·`dark-icon`/`light-icon` class·`localStorage 'theme'` 키가 Task 1·2·3 전반 동일.

---

## 실행 메모

- 머지: 선행 PR과 동일 — `feat/m3-theme-darklight` → main 머지 시 GH Actions 자동 배포. Task 5 사용자 체크포인트 후 사용자가 머지 방식 결정(직접/Claude 대행).
- 채널분리 폴백 채택 시: Task 1 Step 4 적용 + 이 줄 아래 기록.
  - [ ] 채널분리 폴백 적용됨 (Task 1에서 opacity-slash var() 비호환 확인 시 체크)
- `material-theme-css/`는 값 참조용 — git 추적 안 함(untracked 유지).
