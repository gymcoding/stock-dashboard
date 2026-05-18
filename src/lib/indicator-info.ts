import type { SignalKey } from './signal';

export type IndicatorInfo = {
  title: string;
  description: string;
  thresholds: { range: string; label: string; sig: SignalKey }[];
  caveat: string;
  sourceUrl: string;
  sourceLabel: string;
};

export const INDICATOR_INFO: Record<string, IndicatorInfo> = {
  overall: {
    title: '종합 투자 신호 (7개 컴포넌트)',
    description:
      '이 대시보드의 종합 신호는 CNN Fear & Greed Index(7-component composite)와 Goldman Sachs Bull/Bear Indicator(6-component) 방법론을 참고해 7개 지표를 종합한 결과예요. 각 지표를 매수(+1)·중립(0)·주의(-1)·위험(-2) 4단계로 분류하고 합산해서 최종 점수(범위: -14 ~ +7)를 산출해요. 점수 구간에 따라 4가지 행동 권고를 보여줘요.',
    thresholds: [
      { range: '≥ +4점', label: '매수 유리 — 장기 투자 시작 좋은 환경', sig: 'good' },
      { range: '0 ~ +3점', label: '중립 — 관망 추천', sig: 'neutral' },
      { range: '-1 ~ -5점', label: '주의 — 신중하게 (분할 매수/관망)', sig: 'warn' },
      { range: '≤ -6점', label: '위험 — 방어적으로 (현금 비중 ↑)', sig: 'bad' },
    ],
    caveat:
      '이 신호는 학술적 백테스트가 아닌 휴리스틱(experience-based heuristic)이에요. 카드를 클릭해 각 컴포넌트의 현재값·임계값·검증 출처를 직접 확인하세요. 매매 결정은 본인 책임이며 다른 지표·뉴스와 함께 종합 판단해야 해요.',
    sourceUrl: 'https://github.com/gymcoding/stock-dashboard',
    sourceLabel: '방법론·코드 (GitHub)',
  },
  fear_greed: {
    title: 'CNN 공포 & 탐욕 지수',
    description:
      'CNN이 매일 발표하는 미국 주식시장 투자자 심리 지표예요. S&P500 모멘텀, 주식 가격 강도, 풋콜 비율 등 7개 하위 지표를 0~100 점수로 종합해요. 0에 가까울수록 투자자가 겁먹어 매도세가 강하고, 100에 가까울수록 욕심을 부리며 매수세가 강한 상태예요.',
    thresholds: [
      { range: '0~24', label: '극도의 공포 (역사적 매수 기회)', sig: 'good' },
      { range: '25~44', label: '공포 (매수 기회)', sig: 'good' },
      { range: '45~55', label: '중립', sig: 'neutral' },
      { range: '56~74', label: '탐욕 (주의)', sig: 'warn' },
      { range: '75~100', label: '극도의 탐욕 (고점 경고)', sig: 'bad' },
    ],
    caveat:
      '단기 심리 지표라 추세 전환 시점을 정확히 짚지 못해요. 극단값(25 이하·75 이상)일수록 역사적 신뢰도가 높아요.',
    sourceUrl: 'https://edition.cnn.com/markets/fear-and-greed',
    sourceLabel: 'CNN — Fear & Greed Index',
  },
  vix: {
    title: 'VIX 공포 지수',
    description:
      "S&P500 옵션 가격으로 산출한 향후 30일 변동성 기대치예요. 시장이 평온하면 낮고, 불확실성·공포가 커지면 급등해요. '월스트리트의 공포 지표'라고도 불려요.",
    thresholds: [
      { range: '< 15', label: '지나치게 조용 (과신 주의)', sig: 'warn' },
      { range: '15~20', label: '안정적인 시장', sig: 'neutral' },
      { range: '20~30', label: '적당한 긴장 (기회 탐색)', sig: 'good' },
      { range: '30~40', label: '공포 구간 (역발투자 기회)', sig: 'good' },
      { range: '> 40', label: '극단적 공포 (단기 위험·장기 기회)', sig: 'warn' },
    ],
    caveat: 'VIX 40 이상은 단기 추가 하락 위험과 장기 매수 기회가 동시에 존재하는 양면 구간이에요.',
    sourceUrl: 'https://finance.yahoo.com/quote/%5EVIX',
    sourceLabel: 'Yahoo Finance — ^VIX',
  },
  yield_spread: {
    title: '10Y-3M 금리차 (장단기 금리차)',
    description:
      '미국 10년물 국채 금리에서 3개월물 금리를 뺀 값이에요. 0% 아래로 역전되면 1~2년 안에 경기 침체 가능성이 높다고 봐요. 역사적으로 8번 역전 중 7번 경기침체가 뒤따랐어요.',
    thresholds: [
      { range: '> 0.5%', label: '정상 (경기 양호)', sig: 'neutral' },
      { range: '0~0.5%', label: '금리차 축소 (주의)', sig: 'warn' },
      { range: '-0.5~0%', label: '부분 역전 (침체 우려)', sig: 'warn' },
      { range: '< -0.5%', label: '완전 역전 (침체 경고)', sig: 'bad' },
    ],
    caveat:
      '본 대시보드는 FRED DGS10−DGS3MO(둘 다 Constant Maturity)를 사용해요. 기존 yfinance ^IRX(Bank Discount 방식) 근사보다 정확해요.',
    sourceUrl: 'https://fred.stlouisfed.org/series/T10Y3M',
    sourceLabel: 'FRED — 10-Year minus 3-Month Treasury Spread',
  },
  ma200: {
    title: 'S&P500 200일 이동평균 추세',
    description:
      'SPY(S&P500 ETF) 현재가가 최근 200거래일 평균보다 위인지 아래인지로 큰 흐름을 판단해요. 위면 상승추세(강세장), 아래면 하락추세(약세장)로 봐요.',
    thresholds: [
      { range: 'MA200 위', label: '상승추세 (강세장)', sig: 'good' },
      { range: 'MA200 아래', label: '하락추세 (약세장)', sig: 'bad' },
    ],
    caveat:
      '후행 지표라 추세 전환이 어느 정도 진행된 뒤에야 신호가 바뀌어요. 단독으로 매매하기보다 다른 지표와 함께 보세요.',
    sourceUrl: 'https://finance.yahoo.com/quote/SPY/chart',
    sourceLabel: 'Yahoo Finance — SPY 차트',
  },
  cape: {
    title: 'CAPE (Shiller P/E)',
    description:
      '노벨상 수상자 Robert Shiller가 만든 지표예요. 인플레이션 조정한 10년 평균 EPS로 주가 배수를 계산해서, 단기 이익 변동을 평활화해요. 장기 밸류에이션 측정에 사용해요.',
    thresholds: [
      { range: '≤ 20', label: '역사적 저평가', sig: 'good' },
      { range: '20~28', label: '보통 수준', sig: 'neutral' },
      { range: '28~38', label: '다소 고평가', sig: 'warn' },
      { range: '> 38', label: '역사적 고평가', sig: 'bad' },
    ],
    caveat:
      'AQR·IMF 연구에 따르면 단기 타이밍 신호가 아니라 10~20년 장기 수익률 예측 지표예요. 그래서 본 대시보드의 종합 신호 계산에는 포함하지 않아요.',
    sourceUrl: 'https://www.multpl.com/shiller-pe',
    sourceLabel: 'multpl.com — Shiller PE Ratio',
  },
  sp500pe: {
    title: 'S&P500 PER (TTM)',
    description:
      '최근 12개월 실제 EPS 기준으로 계산한 주가 배수예요. CAPE보다 더 빠르게 반응하지만, 단기 이익 변동성에 민감해서 위기 직후엔 왜곡될 수 있어요.',
    thresholds: [
      { range: '≤ 17', label: '역사 평균 이하', sig: 'good' },
      { range: '17~22', label: '적정 수준', sig: 'neutral' },
      { range: '22~28', label: '다소 고평가', sig: 'warn' },
      { range: '> 28', label: '고평가', sig: 'bad' },
    ],
    caveat:
      '코로나·금융위기처럼 일시 이익 충격이 있으면 PER이 비정상적으로 튀어요. 그럴 땐 CAPE를 함께 참고하세요.',
    sourceUrl: 'https://www.multpl.com/s-p-500-pe-ratio',
    sourceLabel: 'multpl.com — S&P 500 P/E Ratio',
  },
  buffett: {
    title: '버핏 지수 (Market Cap / GDP)',
    description:
      '미국 주식 시가총액 합을 명목 GDP로 나눈 값이에요. 워렌 버핏이 시장 거품을 판단할 때 즐겨 쓴 지표라서 그의 이름이 붙었어요.',
    thresholds: [
      { range: '≤ 80%', label: '저평가', sig: 'good' },
      { range: '80~100%', label: '적정 수준', sig: 'neutral' },
      { range: '100~150%', label: '고평가 주의', sig: 'warn' },
      { range: '> 150%', label: '매우 고평가 (버블 경고)', sig: 'bad' },
    ],
    caveat:
      '본 대시보드는 Yahoo ^W5000 ÷ FRED GDP × 100 근사값이에요. GDP는 FRED에서 분기별 자동 반영돼요. (FRED WILL5000PRFC는 2026-05 단종되어 Yahoo ^W5000을 사용)',
    sourceUrl: 'https://www.longtermtrends.net/market-cap-to-gdp-the-buffett-indicator/',
    sourceLabel: 'longtermtrends.net — Buffett Indicator',
  },
  dxy: {
    title: '달러 강세 지수 (DXY)',
    description:
      '유로·엔·파운드·캐나다달러·스웨덴크로나·스위스프랑 6개 주요 통화 대비 미국 달러의 상대 강도예요. 1973년 100을 기준점으로 시작했어요.',
    thresholds: [
      { range: '< 100', label: '달러 약세 (신흥국·상품 유리)', sig: 'good' },
      { range: '100~103', label: '보통', sig: 'neutral' },
      { range: '103~107', label: '달러 강세 (주의)', sig: 'warn' },
      { range: '> 107', label: '달러 매우 강세', sig: 'bad' },
    ],
    caveat:
      '달러 강세는 신흥국 주식·금·원자재에 역풍이 되고, 미국 수출기업 실적에도 부담이 돼요.',
    sourceUrl: 'https://finance.yahoo.com/quote/DX-Y.NYB',
    sourceLabel: 'Yahoo Finance — DX-Y.NYB',
  },
  usdkrw: {
    title: '원달러 환율',
    description:
      '1달러를 사는 데 필요한 원화 금액이에요. 환율이 오르면 원화 가치가 떨어진 것이고, 내리면 원화가 강해진 거예요.',
    thresholds: [
      { range: '≤ 1,280', label: '원화 강세 (안정)', sig: 'good' },
      { range: '1,280~1,350', label: '보통', sig: 'neutral' },
      { range: '1,350~1,420', label: '원화 약세 (주의)', sig: 'warn' },
      { range: '> 1,420', label: '원화 매우 약세', sig: 'bad' },
    ],
    caveat:
      '환율 상승은 외국인 자금 유출 우려가 있지만, 한국 수출기업 실적엔 유리할 수 있어요. 단방향 해석은 위험해요.',
    sourceUrl: 'https://finance.yahoo.com/quote/USDKRW=X',
    sourceLabel: 'Yahoo Finance — USDKRW=X',
  },
  rsi: {
    title: 'RSI (14일 상대강도지수)',
    description:
      "최근 14거래일 동안 상승폭과 하락폭의 비율을 0~100으로 표현해요. Wilder's EMA 방식으로 계산해요. 단기 과열·과매도를 판단하는 가장 유명한 지표예요.",
    thresholds: [
      { range: '≤ 30', label: '과매도 — 반등 가능성', sig: 'good' },
      { range: '30~45', label: '저점 근처', sig: 'good' },
      { range: '45~60', label: '중립', sig: 'neutral' },
      { range: '60~70', label: '과열 주의', sig: 'warn' },
      { range: '> 70', label: '과매수 — 조정 위험', sig: 'bad' },
    ],
    caveat:
      '강한 추세장에서는 RSI가 70 이상이나 30 이하에 오래 머물 수 있어요. RSI만 보고 매매하는 건 위험해요.',
    sourceUrl: 'https://www.investopedia.com/terms/r/rsi.asp',
    sourceLabel: 'Investopedia — Relative Strength Index',
  },
  hy_spread: {
    title: 'HY 회사채 스프레드 (신용 위험)',
    description:
      '투자등급 미만 회사채(정크본드)와 미국채의 금리 차이예요. 회사채 디폴트 위험을 가격으로 반영해서, 신용 위기 가능성을 측정해요. ICE BofA US High Yield Index Option-Adjusted Spread (FRED 코드 BAMLH0A0HYM2) 기준이에요. 10Y-3M 금리차(12~24개월 전 침체 신호)보다 더 빠른 3~6개월 전 신호로 작동해요.',
    thresholds: [
      { range: '< 3%', label: '신용 위험 낮음 (시장 안정)', sig: 'good' },
      { range: '3~5%', label: '정상 범위', sig: 'neutral' },
      { range: '5~7%', label: '신용 스트레스 증가', sig: 'warn' },
      { range: '> 7%', label: '신용 위기 (디폴트 위험 급등)', sig: 'bad' },
    ],
    caveat:
      '역사상 5% 이상 = 시장 우려, 7%+ = 침체/위기 (2008년 21.8%, 2020년 3월 11%까지 급등). S&P500과 강한 역상관 관계.',
    sourceUrl: 'https://fred.stlouisfed.org/series/BAMLH0A0HYM2',
    sourceLabel: 'FRED — ICE BofA US HY OAS',
  },
  ma_cross: {
    title: 'S&P500 추세 강도 (50/200일선)',
    description:
      "SPY의 50일선과 200일선의 위치 관계로 추세의 강도를 판정해요. 50일선이 200일선을 돌파해 위로 가면 '골든 크로스'(강세), 아래로 내려가면 '데드 크로스'(약세)예요. 가격까지 함께 봐서 4단계로 분류해요.",
    thresholds: [
      { range: '가격 > 50선 > 200선', label: '강한 상승추세 (모든 신호 강세)', sig: 'good' },
      { range: '가격 > 200선, 50선 위', label: '상승추세 (단기 조정 가능)', sig: 'neutral' },
      { range: '가격 < 50선 또는 전환 중', label: '약세 신호 (전환 진행)', sig: 'warn' },
      { range: '가격 < 50선 < 200선', label: '강한 하락추세 (모든 신호 약세)', sig: 'bad' },
    ],
    caveat:
      '200일선과 같이 후행 지표예요. 추세 전환의 확정 신호로 좋지만, 전환 직후엔 진입이 늦을 수 있어요.',
    sourceUrl: 'https://finance.yahoo.com/quote/SPY/chart',
    sourceLabel: 'Yahoo Finance — SPY 차트',
  },
  dxy_trend: {
    title: '달러 트렌드 (DXY MA200)',
    description:
      "달러 지수(DXY)가 200일 이동평균보다 위인지 아래인지로 'risk-on/risk-off' 환경을 판정해요. 약달러(MA200 아래)는 신흥국·원자재·주식에 우호적이고, 강달러(MA200 위)는 글로벌 유동성 긴축 신호예요.",
    thresholds: [
      { range: 'DXY < MA200', label: '달러 약세 (위험자산 우호)', sig: 'good' },
      { range: 'DXY > MA200', label: '달러 강세 (위험자산 역풍)', sig: 'warn' },
    ],
    caveat:
      '달러 절대값(100 기준)과 함께 보면 더 정확해요. 강달러 + 상승추세 = 매우 강한 위험자산 역풍.',
    sourceUrl: 'https://finance.yahoo.com/quote/DX-Y.NYB',
    sourceLabel: 'Yahoo Finance — DX-Y.NYB',
  },
  '52w': {
    title: '52주 고저 위치',
    description:
      '지난 1년 최저가(0%)와 최고가(100%) 사이에서 현재가의 위치를 보여줘요. 저점 근처면 싸게 살 가능성, 고점 근처면 추격 매수 위험을 나타내요.',
    thresholds: [
      { range: '≤ 30%', label: '저점 근처 (저가)', sig: 'good' },
      { range: '30~70%', label: '중간 구간', sig: 'neutral' },
      { range: '70~85%', label: '고점 근처 (고가)', sig: 'warn' },
      { range: '> 85%', label: '52주 고점 부근', sig: 'bad' },
    ],
    caveat:
      '추세가 살아있는 종목은 52주 고점을 계속 갱신해요. 단순 진입 회피 기준으로만 쓰면 좋은 기회를 놓칠 수 있어요.',
    sourceUrl: 'https://finance.yahoo.com/',
    sourceLabel: 'Yahoo Finance — 종목별 차트',
  },
};
