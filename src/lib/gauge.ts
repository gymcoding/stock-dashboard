/**
 * 반원형 게이지의 needle 좌표 계산.
 *
 * 0% = 좌측 (180° from x-axis, 공포)
 * 100% = 우측 (0° from x-axis, 탐욕)
 *
 * 인버트하면(`pct/100 * 180` 사용) needle이 잘못된 방향을 가리킴.
 * CLAUDE.md 의 경고 참조.
 */
export function needleCoords(pct: number): { nx: number; ny: number } {
  const clamped = Math.max(0, Math.min(100, pct));
  const rad = Math.PI * (1 - clamped / 100);
  return {
    nx: 80 + 55 * Math.cos(rad),
    ny: 85 - 55 * Math.sin(rad),
  };
}
