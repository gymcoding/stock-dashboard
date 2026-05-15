/** ISO UTC 문자열을 KST 표시 문자열(예: "2026-05-15 16:37")로 변환 */
export function fmtKST(isoUtc: string): string {
  const d = new Date(isoUtc);
  // KST는 UTC+9
  const kst = new Date(d.getTime() + 9 * 3600_000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${kst.getUTCFullYear()}-${pad(kst.getUTCMonth() + 1)}-${pad(kst.getUTCDate())} ${pad(kst.getUTCHours())}:${pad(kst.getUTCMinutes())}`;
}

/** 소수점 자리 지정 숫자 포맷 ("1,234.56" 형태) */
export function fmtNumber(value: number | null, decimals = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** 퍼센트 포맷 (소수점 자리 지정, 부호 포함 옵션) */
export function fmtPercent(value: number | null, decimals = 1, withSign = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const sign = withSign && value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}
