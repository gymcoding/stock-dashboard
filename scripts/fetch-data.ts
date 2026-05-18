import { writeFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';
import YahooFinance from 'yahoo-finance2';
import * as cheerio from 'cheerio';
import type { Snapshot, TickerAnalysis, MaCross, RateHistory, RatePoint } from '../src/lib/data';

const FRED_KEY = process.env.FRED_API_KEY;
if (!FRED_KEY) {
  console.error('FRED_API_KEY 환경변수가 설정되지 않았습니다.');
  process.exit(2);
}

const WATCHLIST: [string, string][] = [
  ['SPY',   'S&P 500 ETF'],
  ['QQQ',   '나스닥 100 ETF'],
  ['^KS11', 'KOSPI'],
  ['^KQ11', 'KOSDAQ'],
  ['TLT',   '미국 장기채 ETF'],
  ['GLD',   '금 ETF'],
];

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
// FRED: 과거 시계열 전체 (sort_order=asc, observation_start)
// ────────────────────────────────────────────────────────────
async function fredSeries(seriesId: string, start: string): Promise<RatePoint[] | null> {
  try {
    const url = `https://api.stlouisfed.org/fred/series/observations?series_id=${seriesId}&api_key=${FRED_KEY}&file_type=json&sort_order=asc&observation_start=${start}`;
    const r = await fetch(url, { signal: AbortSignal.timeout(15_000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json() as { observations: Array<{ date: string; value: string }> };
    const points: RatePoint[] = data.observations
      .filter(o => o.value !== '.' && o.value !== '')
      .map(o => ({ date: o.date, value: Number(o.value) }))
      .filter(p => Number.isFinite(p.value));
    return points.length ? points : null;
  } catch (e) {
    console.error(`  ⚠️  FRED series ${seriesId} 실패:`, e instanceof Error ? e.message : e);
    return null;
  }
}

// DGS10 − DGS3MO 를 같은 날짜끼리 매칭해 장단기 금리차 시계열 생성
function deriveYieldSpread(
  y10: RatePoint[] | null,
  y3m: RatePoint[] | null,
): RatePoint[] | null {
  if (!y10 || !y3m) return null;
  const m = new Map(y3m.map(p => [p.date, p.value]));
  const out: RatePoint[] = [];
  for (const p of y10) {
    const v3 = m.get(p.date);
    if (v3 !== undefined) out.push({ date: p.date, value: Number((p.value - v3).toFixed(2)) });
  }
  return out.length ? out : null;
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
    const RATINGS = ['extreme fear', 'fear', 'neutral', 'greed', 'extreme greed'] as const;
    const rawRating = String(data.fear_and_greed.rating ?? '').toLowerCase().trim();
    const rating = (RATINGS as readonly string[]).includes(rawRating) ? rawRating : 'neutral';
    return {
      score: Math.round(data.fear_and_greed.score),
      rating,
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

/**
 * Wilder EMA 14일 RSI. dashboard.py:580-585 이식.
 *
 *   delta = close.diff()
 *   gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
 *   loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
 *   rsi = 100 - 100/(1 + gain/loss)
 */
function rsi14(closes: number[]): number | null {
  if (closes.length < 15) return null;
  const alpha = 1 / 14;
  let gainEma = 0;
  let lossEma = 0;
  for (let i = 1; i < closes.length; i++) {
    const delta = closes[i] - closes[i - 1];
    const gain = delta > 0 ? delta : 0;
    const loss = delta < 0 ? -delta : 0;
    if (i === 1) {
      gainEma = gain;
      lossEma = loss;
    } else {
      gainEma = alpha * gain + (1 - alpha) * gainEma;
      lossEma = alpha * loss + (1 - alpha) * lossEma;
    }
  }
  if (lossEma === 0) return 100;
  const rs = gainEma / lossEma;
  return Number((100 - 100 / (1 + rs)).toFixed(1));
}

function mean(arr: number[]): number {
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

async function analyzeTicker(ticker: string, name: string): Promise<TickerAnalysis> {
  const closes = await yfCloses(ticker);
  if (!closes || closes.length < 5) {
    return {
      ticker, name, price_str: 'N/A',
      change_pct: null, rsi: null,
      ma200_above: null, ma200_diff_pct: null,
      ma_cross: null, pos_52w: null,
    };
  }

  const price = closes[closes.length - 1];
  const prev = closes[closes.length - 2];
  const change_pct = Number((((price - prev) / prev) * 100).toFixed(2));

  const rsi = rsi14(closes);

  let ma200_above: boolean | null = null;
  let ma200_diff_pct: number | null = null;
  let ma200Val: number | null = null;
  if (closes.length >= 200) {
    ma200Val = mean(closes.slice(-200));
    ma200_above = price > ma200Val;
    ma200_diff_pct = Number((((price - ma200Val) / ma200Val) * 100).toFixed(1));
  }

  // MA50 + Golden/Death cross — dashboard.py:597-613 이식
  let ma_cross: MaCross = null;
  if (closes.length >= 200 && ma200Val !== null) {
    const ma50 = mean(closes.slice(-50));
    const above50 = price > ma50;
    const above200 = price > ma200Val;
    const goldenCross = ma50 > ma200Val;
    if (above50 && above200 && goldenCross) ma_cross = 'strong_bull';
    else if (above200 && goldenCross) ma_cross = 'bull';
    else if (!above50 && !above200 && !goldenCross) ma_cross = 'strong_bear';
    else ma_cross = 'bear';
  }

  // 52주 위치 (0~100%) — dashboard.py:615-617
  const high = Math.max(...closes);
  const low = Math.min(...closes);
  const pos_52w = high !== low
    ? Number((((price - low) / (high - low)) * 100).toFixed(1))
    : 50;

  const isKr = ticker === '^KS11' || ticker === '^KQ11';
  const price_str = isKr
    ? price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : `$${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return { ticker, name, price_str, change_pct, rsi, ma200_above, ma200_diff_pct, ma_cross, pos_52w };
}

async function fetchVix(): Promise<number | null> {
  const closes = await yfCloses('^VIX');
  return closes ? Number(closes[closes.length - 1].toFixed(2)) : null;
}

async function fetchDxy(): Promise<Snapshot['dxy']> {
  const closes = await yfCloses('DX-Y.NYB');
  if (!closes) return null;
  const value = Number(closes[closes.length - 1].toFixed(2));
  if (closes.length < 200) {
    console.warn(`  ⚠️  DXY MA200 계산 불가 (${closes.length}일 < 200) — above_ma200=false 강제`);
    return { value, above_ma200: false };
  }
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

  const tickers = await Promise.all(
    WATCHLIST.map(([t, n]) => analyzeTicker(t, n)),
  );

  const spy = tickers.find(t => t.ticker === 'SPY');
  const sp500_trend = spy?.ma200_above ?? null;
  const sp500_trend_pct = spy?.ma200_diff_pct ?? null;
  const sp500_ma_cross = spy?.ma_cross ?? null;

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
    tickers,
    sp500_trend,
    sp500_trend_pct,
    sp500_ma_cross,
  };

  const out = 'src/data/latest.json';
  await mkdir(dirname(out), { recursive: true });
  await writeFile(out, JSON.stringify(snapshot, null, 2));
  console.log(`✓ ${out} 작성 완료`);

  // ── 금리 히스토리 (비치명적: 실패해도 빌드 진행) ──
  try {
    const start = `${new Date().getFullYear() - 15}-01-01`;
    const [h10, h3m, hHy, hKrw, hFf] = await Promise.all([
      fredSeries('DGS10', start),
      fredSeries('DGS3MO', start),
      fredSeries('BAMLH0A0HYM2', start),
      fredSeries('DEXKOUS', start),
      fredSeries('FEDFUNDS', start),
    ]);
    const history: RateHistory = {};
    if (h10) history.dgs10 = h10;
    if (h3m) history.dgs3mo = h3m;
    if (hHy) history.hy_spread = hHy;
    if (hKrw) history.usdkrw = hKrw;
    if (hFf) history.fedfunds = hFf;
    const ys = deriveYieldSpread(h10, h3m);
    if (ys) history.yield_spread = ys;
    const hOut = 'src/data/history.json';
    await writeFile(hOut, JSON.stringify(history));
    console.log(`✓ ${hOut} 작성 완료 (${Object.keys(history).length}/6 시리즈)`);
  } catch (e) {
    console.error('  ⚠️  history.json 생성 실패 (빌드는 계속):', e instanceof Error ? e.message : e);
  }

  // 핵심 4개 지표 점검: 2개 이상 null이면 빌드 실패 (spec §4.5)
  const core = {
    fear_greed: fearGreed?.score,
    vix,
    yield_spread: yieldSpread?.spread,
    sp500_trend,
  };
  const nullCount = Object.values(core).filter(v => v === null || v === undefined).length;
  if (nullCount >= 2) {
    console.error(`✗ 핵심 지표 ${nullCount}개 누락 — 빌드 중단`);
    console.error('  null 필드:', Object.entries(core).filter(([_, v]) => v === null || v === undefined).map(([k]) => k));
    process.exit(1);
  }

  console.log(`  fear_greed=${fearGreed?.score ?? 'null'} | y10-y3m=${yieldSpread?.spread ?? 'null'} | hy=${hySpread ?? 'null'} | buffett=${buffett ?? 'null'} | usdkrw=${dexkous ?? 'null'}`);
  console.log(`  vix=${vix ?? 'null'} | dxy=${dxy?.value ?? 'null'}${dxy ? `(${dxy.above_ma200 ? '↑MA200' : '↓MA200'})` : ''} | cape=${cape ?? 'null'} | sp500pe=${sp500Pe ?? 'null'} | wilshire=${wilshire ?? 'null'}`);

  for (const t of tickers) {
    console.log(`  ${t.ticker.padEnd(6)} ${t.price_str.padStart(12)} | rsi=${t.rsi ?? 'null'} | MA200 ${t.ma200_above === null ? '?' : t.ma200_above ? '↑' : '↓'} (${t.ma200_diff_pct ?? '?'}%) | cross=${t.ma_cross ?? 'null'} | 52w=${t.pos_52w ?? 'null'}%`);
  }
}

main().catch(e => {
  console.error('fatal:', e instanceof Error ? e.message : e);
  process.exit(1);
});
