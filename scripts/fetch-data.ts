import { writeFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';
import type { Snapshot, TickerAnalysis } from '../src/lib/data';

const FRED_KEY = process.env.FRED_API_KEY;
if (!FRED_KEY) {
  console.error('FRED_API_KEY 환경변수가 비어있습니다. .env 또는 GH Secrets 확인.');
  process.exit(2);
}

// ────────────────────────────────────────────────────────────
// FRED: 최신 관측치 단일 값
// ────────────────────────────────────────────────────────────
async function fredLatest(seriesId: string): Promise<number | null> {
  try {
    const url = `https://api.stlouisfed.org/fred/series/observations?series_id=${seriesId}&api_key=${FRED_KEY}&file_type=json&sort_order=desc&limit=20`;
    const r = await fetch(url, { signal: AbortSignal.timeout(10_000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json() as { observations: Array<{ value: string; date: string }> };
    const valid = data.observations.find(o => o.value !== '.' && o.value);
    return valid ? Number(valid.value) : null;
  } catch (e) {
    console.error(`  ⚠️  FRED ${seriesId} 실패:`, e instanceof Error ? e.message : e);
    return null;
  }
}

// ────────────────────────────────────────────────────────────
// CNN Fear & Greed
// ────────────────────────────────────────────────────────────
async function fetchFearGreed(): Promise<Snapshot['fear_greed']> {
  try {
    const r = await fetch(
      'https://production.dataviz.cnn.io/index/fearandgreed/graphdata',
      {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0',
          'Referer': 'https://money.cnn.com/',
          'Origin': 'https://money.cnn.com',
        },
        signal: AbortSignal.timeout(10_000),
      },
    );
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json() as { fear_and_greed: { score: number; rating: string } };
    return {
      score: Math.round(data.fear_and_greed.score),
      rating: data.fear_and_greed.rating,
    };
  } catch (e) {
    console.error('  ⚠️  Fear & Greed 실패:', e instanceof Error ? e.message : e);
    return null;
  }
}

// ────────────────────────────────────────────────────────────
// 진입점
// ────────────────────────────────────────────────────────────
async function main() {
  console.log('▶ fetch-data 시작');

  const [
    fearGreed,
    dgs10, dgs3mo, dexkous, will5000, gdp, hySpread,
  ] = await Promise.all([
    fetchFearGreed(),
    fredLatest('DGS10'),
    fredLatest('DGS3MO'),
    fredLatest('DEXKOUS'),
    fredLatest('WILL5000PRFC'),
    fredLatest('GDP'),
    fredLatest('BAMLH0A0HYM2'),
  ]);

  // yield_spread = DGS10 - DGS3MO
  const yieldSpread = (dgs10 !== null && dgs3mo !== null)
    ? { spread: Number((dgs10 - dgs3mo).toFixed(2)), y10: dgs10, y3m: dgs3mo }
    : null;

  // buffett = WILL5000 / GDP(billions) * 100
  const buffett = (will5000 !== null && gdp !== null)
    ? Number(((will5000 / gdp) * 100).toFixed(1))
    : null;

  // TODO: Yahoo (Task 7), multpl (Task 7), ticker analysis (Task 8)
  const snapshot: Snapshot = {
    generated_at: new Date().toISOString(),
    fear_greed: fearGreed,
    cape: null,
    sp500_pe: null,
    buffett,
    vix: null,
    dxy: null,
    usdkrw: dexkous,
    yield_spread: yieldSpread,
    hy_spread: hySpread,
    tickers: [],
    sp500_trend: null,
    sp500_trend_pct: null,
    sp500_ma_cross: null,
  };

  const out = 'src/data/latest.json';
  await mkdir(dirname(out), { recursive: true });
  await writeFile(out, JSON.stringify(snapshot, null, 2));
  console.log(`✓ ${out} 작성 완료`);
  console.log(`  fear_greed=${fearGreed?.score ?? 'null'} | y10-y3m=${yieldSpread?.spread ?? 'null'} | hy=${hySpread ?? 'null'} | buffett=${buffett ?? 'null'} | usdkrw=${dexkous ?? 'null'}`);
}

main().catch(e => {
  console.error('fatal:', e);
  process.exit(1);
});
