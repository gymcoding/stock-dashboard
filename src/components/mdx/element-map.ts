// <Content components={elementMap} /> 용 HTML 요소 치환 맵 (Astro 공식 문서 패턴).
// 표준 마크다운 링크/이미지/표를 M3 스타일 컴포넌트로 자동 치환 — 작성자 조치 불필요.
import Anchor from './prose/Anchor.astro';
import Image from './prose/Image.astro';
import Table from './prose/Table.astro';

export const elementMap = {
  a: Anchor,
  img: Image,
  table: Table,
};
