import type { Snapshot, MaCross } from './data';

export type SignalKey = 'good' | 'neutral' | 'warn' | 'bad';

export const SCORE_MAP: Record<SignalKey, number> = {
  good: 1,
  neutral: 0,
  warn: -1,
  bad: -2,
};

export type SignalLabel =
  | 'fear_greed' | 'rsi' | 'cape' | 'buffett' | 'vix'
  | 'dxy' | 'yield_spread' | 'ma200' | '52w' | 'usdkrw'
  | 'sp500pe' | 'hy_spread' | 'ma_cross' | 'dxy_trend';

export function signalColor(
  label: SignalLabel,
  value: number | boolean | string | null,
): [SignalKey, string] {
  if (value === null || value === undefined) return ['neutral', '데이터 없음'];

  switch (label) {
    case 'fear_greed': {
      const v = value as number;
      if (v <= 24) return ['good',    '극도의 공포 (역사적 매수 기회)'];
      if (v <= 44) return ['good',    '공포 구간 (매수 기회)'];
      if (v <= 55) return ['neutral', '중립'];
      if (v <= 74) return ['warn',    '탐욕 구간 (주의)'];
      return ['bad', '극도의 탐욕 (고점 경고)'];
    }
    case 'rsi': {
      const v = value as number;
      if (v <= 30) return ['good',    '과매도 — 반등 가능성'];
      if (v <= 45) return ['good',    '저점 근처'];
      if (v <= 60) return ['neutral', '중립'];
      if (v <= 70) return ['warn',    '과열 주의'];
      return ['bad', '과매수 — 조정 위험'];
    }
    case 'cape': {
      const v = value as number;
      if (v <= 20) return ['good',    '역사적 저평가'];
      if (v <= 28) return ['neutral', '보통 수준'];
      if (v <= 38) return ['warn',    '다소 고평가'];
      return ['bad', '역사적 고평가'];
    }
    case 'buffett': {
      const v = value as number;
      if (v <= 80)  return ['good',    '저평가'];
      if (v <= 100) return ['neutral', '적정 수준'];
      if (v <= 150) return ['warn',    '고평가 주의'];
      return ['bad', '매우 고평가'];
    }
    case 'vix': {
      const v = value as number;
      if (v < 15)  return ['warn',    '지나치게 조용함 (과신 주의)'];
      if (v <= 20) return ['neutral', '안정적인 시장'];
      if (v <= 30) return ['good',    '적당한 긴장 (기회 탐색)'];
      if (v <= 40) return ['good',    '공포 구간 (역발투자 기회)'];
      return ['warn', '극단적 공포 (장기 역발투자 기회, 단기 매우 위험)'];
    }
    case 'dxy': {
      const v = value as number;
      if (v < 100)  return ['good',    '달러 약세 (신흥국·상품 유리)'];
      if (v <= 103) return ['neutral', '보통'];
      if (v <= 107) return ['warn',    '달러 강세 (주의)'];
      return ['bad', '달러 매우 강세'];
    }
    case 'yield_spread': {
      const v = value as number;
      if (v > 0.5)   return ['neutral', '정상 (경기 양호)'];
      if (v >= 0)    return ['warn',    '금리차 축소 (주의)'];
      if (v >= -0.5) return ['warn',    '부분 역전 (침체 우려)'];
      return ['bad', '완전 역전 (침체 경고)'];
    }
    case 'ma200': {
      return value
        ? ['good', '200일선 위 (상승추세)']
        : ['bad', '200일선 아래 (하락추세)'];
    }
    case '52w': {
      const v = value as number;
      if (v <= 30) return ['good',    '52주 저점 근처 (저가)'];
      if (v <= 70) return ['neutral', '중간 구간'];
      if (v <= 85) return ['warn',    '고점 근처 (고가)'];
      return ['bad', '52주 고점 부근'];
    }
    case 'usdkrw': {
      const v = value as number;
      if (v <= 1280) return ['good',    '원화 강세 (안정)'];
      if (v <= 1350) return ['neutral', '보통'];
      if (v <= 1420) return ['warn',    '원화 약세 (주의)'];
      return ['bad', '원화 매우 약세'];
    }
    case 'sp500pe': {
      const v = value as number;
      if (v <= 17) return ['good',    '역사 평균 이하'];
      if (v <= 22) return ['neutral', '적정 수준'];
      if (v <= 28) return ['warn',    '다소 고평가'];
      return ['bad', '고평가'];
    }
    case 'hy_spread': {
      const v = value as number;
      if (v < 3)  return ['good',    '신용 위험 낮음 (시장 안정)'];
      if (v <= 5) return ['neutral', '정상 범위'];
      if (v <= 7) return ['warn',    '신용 스트레스 증가'];
      return ['bad', '신용 위기 (디폴트 위험 급등)'];
    }
    case 'ma_cross': {
      const v = value as MaCross;
      if (v === 'strong_bull') return ['good',    '강한 상승추세 (50선·200선 모두 위)'];
      if (v === 'bull')        return ['neutral', '상승추세 (단기 조정 가능)'];
      if (v === 'bear')        return ['warn',    '약세 신호 (전환 진행)'];
      if (v === 'strong_bear') return ['bad',     '강한 하락추세 (50선·200선 모두 아래)'];
      return ['neutral', '데이터 없음'];
    }
    case 'dxy_trend': {
      if (value === true)  return ['warn', '달러 강세 (위험자산 역풍)'];
      if (value === false) return ['good', '달러 약세 (위험자산 우호)'];
      return ['neutral', '데이터 없음'];
    }
  }
  return ['neutral', ''];
}

export function overallSignal(keys: SignalKey[]): {
  key: SignalKey;
  label: string;
  comment: string;
} {
  // 7개 컴포넌트 기준: 점수 범위 -14 ~ +7
  const score = keys.reduce((s, k) => s + (SCORE_MAP[k] ?? 0), 0);
  // 임계값: ≥+4/≥0/≥-5/<-5
  if (score >= 4) return {
    key: 'good',
    label: '매수 유리',
    comment: '전반적으로 긍정적인 신호예요. 장기 투자를 시작하기 좋은 환경이에요.',
  };
  if (score >= 0) return {
    key: 'neutral',
    label: '중립 — 관망 추천',
    comment: '긍정과 부정 신호가 섞여 있어요. 급하게 움직이지 않아도 돼요.',
  };
  if (score >= -5) return {
    key: 'warn',
    label: '주의 — 신중하게',
    comment: '부정적 지표가 늘고 있어요. 분할 매수나 관망을 추천해요.',
  };
  return {
    key: 'bad',
    label: '위험 — 방어적으로',
    comment: '전반적으로 위험 신호가 많아요. 현금 비중을 높이는 게 좋을 수 있어요.',
  };
}

export function computeComposite(data: Snapshot): {
  key: SignalKey;
  label: string;
  comment: string;
  good: number;
  warn: number;
  bad: number;
  neutral: number;
  signals: { name: string; key: SignalKey; text: string }[];
} {
  const fg = data.fear_greed?.score ?? null;
  const [fgKey, fgText] = signalColor('fear_greed', fg);

  const [vxKey, vxText] = signalColor('vix', data.vix);

  const ysVal = data.yield_spread?.spread ?? null;
  const [ysKey, ysText] = signalColor('yield_spread', ysVal);

  const [trKey, trText] = signalColor('ma200', data.sp500_trend);

  const [mcKey, mcText] = signalColor('ma_cross', data.sp500_ma_cross);

  const [hyKey, hyText] = signalColor('hy_spread', data.hy_spread);

  const dxyAbove = data.dxy?.above_ma200 ?? null;
  const [dxKey, dxText] = signalColor('dxy_trend', dxyAbove);

  const keys: SignalKey[] = [fgKey, vxKey, ysKey, trKey, mcKey, hyKey, dxKey];
  const ov = overallSignal(keys);

  return {
    ...ov,
    good: keys.filter(k => k === 'good').length,
    warn: keys.filter(k => k === 'warn').length,
    bad: keys.filter(k => k === 'bad').length,
    neutral: keys.filter(k => k === 'neutral').length,
    signals: [
      { name: '공포·탐욕',     key: fgKey, text: fgText },
      { name: 'VIX',           key: vxKey, text: vxText },
      { name: '10Y-3M',        key: ysKey, text: ysText },
      { name: 'S&P500 MA200',  key: trKey, text: trText },
      { name: 'MA Cross',      key: mcKey, text: mcText },
      { name: 'HY Spread',     key: hyKey, text: hyText },
      { name: 'DXY Trend',     key: dxKey, text: dxText },
    ],
  };
}
