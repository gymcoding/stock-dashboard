export type MaCross =
  | 'strong_bull'
  | 'bull'
  | 'bear'
  | 'strong_bear'
  | null;

export type Snapshot = {
  generated_at: string;            // ISO 8601 UTC
  fear_greed: { score: number | null; rating: string } | null;
  cape: number | null;
  sp500_pe: number | null;
  buffett: number | null;
  vix: number | null;
  dxy: { value: number; above_ma200: boolean } | null;
  usdkrw: number | null;
  yield_spread: { spread: number; y10: number; y3m: number } | null;
  hy_spread: number | null;
  tickers: TickerAnalysis[];
  sp500_trend: boolean | null;
  sp500_trend_pct: number | null;
  sp500_ma_cross: MaCross;
};

export type TickerAnalysis = {
  ticker: string;
  name: string;
  price_str: string;
  change_pct: number | null;
  rsi: number | null;
  ma200_above: boolean | null;
  ma200_diff_pct: number | null;
  ma_cross: MaCross;
  pos_52w: number | null;
};

export type RatePoint = { date: string; value: number };

export type RateSeriesId =
  | 'dgs10'
  | 'dgs3mo'
  | 'yield_spread'
  | 'hy_spread'
  | 'usdkrw'
  | 'fedfunds';

export type RateHistory = Partial<Record<RateSeriesId, RatePoint[]>>;
