# MDX 컴포넌트 작성 가이드 (학습 글용)

`src/content/learn/*.mdx` 작성 시 사용하는 컴포넌트 레퍼런스. **시각 확인은 `npm run dev` → `/kitchen-sink`** (개발 전용, 프로덕션 미생성)이 source of truth.

## 핵심 규칙

- **named 블록은 명시적 import 필수** (Astro 공식 모범사례 — 업그레이드 안전). 글 상단 한 줄:
  ```
  import { Callout, KeyTakeaways, Figure } from '../../components/mdx';
  ```
  필요한 것만 골라 import. 경로는 항상 `../../components/mdx` (= `src/content/learn/*.mdx` 기준).
- **표준 마크다운 링크/이미지/표는 자동 스타일** — 별도 조치 불필요. `[...slug].astro`의 element-map이 `a`/`img`/`table`을 M3 스타일 컴포넌트로 치환:
  - `[텍스트](https://외부)` → 새 탭 + `rel="noopener noreferrer"` + 스크린리더 안내 자동
  - `![alt](src)` → `loading=lazy` 반응형 둥근 이미지. **캡션이 필요하면 `<Figure>`** 사용
  - 표 → 모바일 가로 스크롤 래퍼 자동 (prose 표 스타일 유지)
- v1 클라이언트 JS 없음. `set:html` 금지.
- 컴포넌트 사이의 일반 문단/제목/리스트는 그대로 마크다운으로 — prose 타이포그래피 자동 적용.

## named 블록

| 컴포넌트 | 용도 | Props |
|---|---|---|
| `Callout` | 강조 박스 | `type?`: `note`(기본)·`tip`·`warn`·`danger`, `title?` |
| `Lead` | 도입 문단 강조 | (없음, slot — **인라인 콘텐츠 전용**, 블록 넣으면 invalid HTML) |
| `KeyTakeaways` | 핵심 요약 카드 | `title?`(기본 "핵심 요약"), `items?: string[]` (없으면 slot) |
| `Figure` | 이미지/차트 + 캡션 | `src?`, `alt?`, `caption?` (`src` 없으면 slot 래핑) |
| `Stat` | 숫자 강조 | `label`, `value`, `signal?`(`good`·`neutral`·`warn`·`bad`), `sub?` |
| `StatGrid` | Stat 그리드 | `cols?`: `2`·`3`(기본)·`4` |
| `Steps` / `Step` | 순서 단계 | `Steps`: `title?` / `Step`: `title`(필수) |
| `Compare` | 2단 비교 | `mode?`: `split`(기본)·`proscons`, `leftTitle?`, `rightTitle?`, slot `left`/`right` |
| `Term` | 인라인 용어+툴팁 | `def`(필수), `label?` (없으면 slot). `title` 속성 기반 → 터치/키보드 한계(v1 트레이드오프) |
| `RateChart` | 대시보드 추이 차트 | `id`: `dgs10`·`dgs3mo`·`yield_spread`·`hy_spread`·`usdkrw`·`fedfunds` |

## 최소 예시

```mdx
---
title: "예시 글"
description: "..."
summary: "..."
order: 2
updated: "2026-05-19"
---
import { Lead, Callout, KeyTakeaways, Stat, StatGrid } from '../../components/mdx';

<Lead>한 줄 도입부.</Lead>

## 본문 제목

일반 문단은 그대로 마크다운. [외부 링크](https://example.com)도 자동 스타일.

<Callout type="warn" title="주의">리스크를 강조.</Callout>

<StatGrid cols={2}>
  <Stat label="10Y" value="4.21%" signal="warn" />
  <Stat label="VIX" value="13.2" signal="good" />
</StatGrid>

<KeyTakeaways items={["핵심 1", "핵심 2"]} />
```

## 트러블슈팅

- 컴포넌트가 `undefined`로 렌더되면 → import 줄 확인 (`../../components/mdx`), 컴포넌트명 철자.
- 배럴 import가 동작 안 하면(드묾) fallback: 개별 경로 직접 import — `import Callout from '../../components/mdx/Callout.astro';`
- Kitchen Sink는 `/kitchen-sink`만 의도 URL. dev에서 하위 경로(`/kitchen-sink/foo`)는 미지원.
- 표/이미지/링크가 안 꾸며지면 → `src/pages/learn/[...slug].astro`에 `<Content components={elementMap} />` 유지 확인.
