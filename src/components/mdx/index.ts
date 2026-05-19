// 학습 글(MDX)에서 한 줄로 명시적 import 하는 배럴 (Astro 공식 모범사례).
//   import { Callout, KeyTakeaways, Figure } from '../../components/mdx';
// 표준 마크다운(링크/이미지/표)은 element-map.ts가 자동 스타일하므로 import 불필요.
export { default as Callout } from './Callout.astro';
export { default as Lead } from './Lead.astro';
export { default as KeyTakeaways } from './KeyTakeaways.astro';
export { default as Figure } from './Figure.astro';
export { default as Stat } from './Stat.astro';
export { default as StatGrid } from './StatGrid.astro';
export { default as Steps } from './Steps.astro';
export { default as Step } from './Step.astro';
export { default as Compare } from './Compare.astro';
export { default as Term } from './Term.astro';
export { default as RateChart } from '../RateChart.astro';
