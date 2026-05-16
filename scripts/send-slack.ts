import { readFileSync } from 'node:fs';
import { computeComposite, signalColor } from '../src/lib/signal';
import type { Snapshot } from '../src/lib/data';

const WEBHOOK = process.env.SLACK_WEBHOOK_URL;
const SITE_URL = process.env.SITE_URL || 'https://techboost.dev';

if (!WEBHOOK) {
  console.error('SLACK_WEBHOOK_URL 환경변수 비어있음.');
  process.exit(2);
}

const snap = JSON.parse(readFileSync('src/data/latest.json', 'utf-8')) as Snapshot;
const composite = computeComposite(snap);

const COLOR: Record<string, string> = {
  good:    '#00C896',
  neutral: '#8B95A1',
  warn:    '#FF9500',
  bad:     '#F04452',
};

const EMOJI: Record<string, string> = {
  good: '🟢', neutral: '⚪', warn: '🟡', bad: '🔴',
};

function fmtLine(label: string, value: string | number | null, sigKey: string, sigText: string): string {
  const v = value === null || value === undefined ? '—' : value;
  return `${EMOJI[sigKey]} *${label}* ${v} (${sigText})`;
}

const fg = snap.fear_greed?.score ?? null;
const [fgK, fgT] = signalColor('fear_greed', fg);
const [vxK, vxT] = signalColor('vix', snap.vix);
const ysVal = snap.yield_spread?.spread ?? null;
const [ysK, ysT] = signalColor('yield_spread', ysVal);
const [trK, trT] = signalColor('ma200', snap.sp500_trend);
const [mcK, mcT] = signalColor('ma_cross', snap.sp500_ma_cross);
const [hyK, hyT] = signalColor('hy_spread', snap.hy_spread);
const dxyAbove = snap.dxy?.above_ma200 ?? null;
const [dxK, dxT] = signalColor('dxy_trend', dxyAbove);

const lines = [
  fmtLine('공포·탐욕', fg !== null ? `${fg} (${snap.fear_greed?.rating})` : null, fgK, fgT),
  fmtLine('VIX', snap.vix !== null ? snap.vix.toFixed(2) : null, vxK, vxT),
  fmtLine('10Y-3M', ysVal !== null ? `${ysVal >= 0 ? '+' : ''}${ysVal.toFixed(2)}` : null, ysK, ysT),
  fmtLine('S&P500 MA200',
    snap.sp500_trend === null ? null :
    `${snap.sp500_trend ? '위' : '아래'} (${snap.sp500_trend_pct !== null ? (snap.sp500_trend_pct >= 0 ? '↑' : '↓') + Math.abs(snap.sp500_trend_pct).toFixed(1) + '%' : ''})`,
    trK, trT,
  ),
  fmtLine('MA Cross', snap.sp500_ma_cross, mcK, mcT),
  fmtLine('HY Spread', snap.hy_spread !== null ? snap.hy_spread.toFixed(2) + '%' : null, hyK, hyT),
  fmtLine('DXY', dxyAbove === null ? null : (dxyAbove ? '200일선 위' : '200일선 아래'), dxK, dxT),
];

const failed: string[] = [];
if (fg === null) failed.push('Fear & Greed');
if (snap.vix === null) failed.push('VIX');
if (ysVal === null) failed.push('Yield Spread');
if (snap.sp500_trend === null) failed.push('SPY MA200');

const body = {
  attachments: [{
    color: COLOR[composite.key],
    blocks: [
      {
        type: 'header',
        text: { type: 'plain_text', text: `📊 ${composite.label}` },
      },
      {
        type: 'section',
        text: { type: 'mrkdwn', text: composite.comment },
      },
      {
        type: 'section',
        text: { type: 'mrkdwn', text: lines.join('\n') },
      },
      {
        type: 'context',
        elements: [{
          type: 'mrkdwn',
          text: failed.length
            ? `⚠️ 일부 데이터 누락: ${failed.join(', ')}`
            : '✅ 모든 핵심 데이터 정상',
        }],
      },
      {
        type: 'actions',
        elements: [{
          type: 'button',
          text: { type: 'plain_text', text: '대시보드 열기' },
          url: SITE_URL,
        }],
      },
    ],
  }],
};

const r = await fetch(WEBHOOK, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
});

if (!r.ok) {
  console.error(`Slack 발송 실패: HTTP ${r.status} ${await r.text()}`);
  process.exit(1);
}
console.log('✓ Slack 발송 완료');
