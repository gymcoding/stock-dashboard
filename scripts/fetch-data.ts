import { writeFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';
import YahooFinance from 'yahoo-finance2';
import * as cheerio from 'cheerio';
import type { Snapshot, TickerAnalysis } from '../src/lib/data';

const FRED_KEY = process.env.FRED_API_KEY;
if (!FRED_KEY) {
  console.error('FRED_API_KEY 환경변수가 비어있습니다. .env 또는 GH Secrets 확인.');
  process.exit(2);
}

const yf = new YahooFinance();

const ONE_YEAR_MS = 366 * 24 * 60 * 60 * 1000;
const yfRange = () => {
  const end = new Date();
  const start = new Date(end.getTime() - ONE_YEAR_MS);
  return { period1: start, period2: end, interval: '1d' as const };
};

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
// Yahoo Finance: 차트 close 배열
// ────────────────────────────────────────────────────────────
async function yfCloses(symbol: string): Promise<number[] | null> {
  try {
    const result = await yf.chart(symbol, yfRange());
    if (!result.quotes || result.quotes.length === 0) throw new Error('빈 응답');
    const closes = result.quotes
      .map(q => q.close)
      .filter((c): c is number => typeof c === 'number' && !Number.isNaN(c));
    if (closes.length < 5) throw new Error(`데이터 부족 (${closes.length}일)`);
    return closes;
  } catch (e) {
    console.error(`  ⚠️  Yahoo ${symbol} 실패:`, e instanceof Error ? e.message : e);
    return null;
  }
}

async function fetchVix(): Promise<number | null> {
  const closes = await yfCloses('^VIX');
  return closes ? Number(closes[closes.length - 1].toFixed(2)) : null;
}

async function fetchDxy(): Promise<Snapshot['dxy']> {
  const closes = await yfCloses('DX-Y.NYB');
  if (!closes) return null;
  const value = Number(closes[closes.length - 1].toFixed(2));
  if (closes.length < 200) return { value, above_ma200: false };
  const ma200 = closes.slice(-200).reduce((a, b) => a + b, 0) / 200;
  return { value, above_ma200: value > ma200 };
}

// Wilshire 5000 — Yahoo로 fetch (FRED WILL5000PRFC가 단종됨)
async function fetchWilshire5000(): Promise<number | null> {
  const closes = await yfCloses('^W5000');
  return closes ? closes[closes.length - 1] : null;
}

// ────────────────────────────────────────────────────────────
// multpl.com: CAPE / S&P500 PER 페치
// ────────────────────────────────────────────────────────────
async function fetchMultpl(slug: 'shiller-pe' | 's-p-500-pe-ratio'): Promise<number | null> {
  try {
    const r = await fetch(`https://www.multpl.com/${slug}/table/by-month`, {
      headers: { 'User-Agent': 'Mozilla/5.0' },
      signal: AbortSignal.timeout(10_000),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const html = await r.text();
    const $ = cheerio.load(html);
    // 첫 번째 테이블의 첫 번째 데이터 행, 두 번째 td를 추출
    const raw = $('table#datatable tr').eq(1).find('td').eq(1).text();
    const cleaned = raw.replace(/\*/g, '').replace(/†/g, '').trim();
    const val = Number(cleaned);
    if (Number.isNaN(val)) throw new Error(`파싱 실패: "${raw}"`);
    const range: [number, number] = slug === 'shiller-pe' ? [5, 100] : [5, 200];
    return (val > range[0] && val < range[1]) ? Number(val.toFixed(1)) : null;
  } catch (e) {
    console.error(`  ⚠️  multpl ${slug} 실패:`, e instanceof Error ? e.message : e);
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
    dgs10, dgs3mo, dexkous, gdp, hySpread,
    vix, dxy, wilshire,
    cape, sp500Pe,
  ] = await Promise.all([
    fetchFearGreed(),
    fredLatest('DGS10'),
    fredLatest('DGS3MO'),
    fredLatest('DEXKOUS'),
    fredLatest('GDP'),
    fredLatest('BAMLH0A0HYM2'),
    fetchVix(),
    fetchDxy(),
    fetchWilshire5000(),
    fetchMultpl('shiller-pe'),
    fetchMultpl('s-p-500-pe-ratio'),
  ]);

  // yield_spread = DGS10 - DGS3MO
  const yieldSpread = (dgs10 !== null && dgs3mo !== null)
    ? { spread: Number((dgs10 - dgs3mo).toFixed(2)), y10: dgs10, y3m: dgs3mo }
    : null;

  // buffett = Wilshire5000(Yahoo ^W5000) / FRED GDP(billions) * 100
  const buffett = (wilshire !== null && gdp !== null)
    ? Number(((wilshire / gdp) * 100).toFixed(1))
    : null;

  // TODO: ticker analysis (Task 8)
  const snapshot: Snapshot = {
    generated_at: new Date().toISOString(),
    fear_greed: fearGreed,
    cape,
    sp500_pe: sp500Pe,
    buffett,
    vix,
    dxy,
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
  console.log(`  vix=${vix ?? 'null'} | dxy=${dxy?.value ?? 'null'}(${dxy?.above_ma200 ? '↑MA200' : '↓MA200'}) | cape=${cape ?? 'null'} | sp500pe=${sp500Pe ?? 'null'} | wilshire=${wilshire ?? 'null'}`);
}

main().catch(e => {
  console.error('fatal:', e);
  process.exit(1);
});
