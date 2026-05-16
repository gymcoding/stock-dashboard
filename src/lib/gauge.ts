/**
 * 반원형 게이지의 needle 좌표 계산.
 *
 * 0% = 좌측 (180° from x-axis, 공포)
 * 100% = 우측 (0° from x-axis, 탐욕)
 *
 * WARNING: `pct/100 * 180` 공식(인버트)을 사용하면 needle이 반대 방향을 가리킴.
 * 올바른 공식: Math.PI * (1 - clamped / 100)
 *
 * pct가 NaN·Infinity인 경우 중앙(50%) 좌표 반환.
 */
export function needleCoords(pct: number): { nx: number; ny: number } {
  if (!Number.isFinite(pct)) {
    return { nx: 80, ny: 30 };
  }
  const clamped = Math.max(0, Math.min(100, pct));
  const rad = Math.PI * (1 - clamped / 100);
  return {
    nx: 80 + 55 * Math.cos(rad),
    ny: 85 - 55 * Math.sin(rad),
  };
}
