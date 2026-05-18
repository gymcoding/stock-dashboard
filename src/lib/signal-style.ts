import type { SignalKey } from './signal';

export const signalBg: Record<SignalKey, string> = {
  good: 'bg-good/15 border-good/30',
  neutral: 'bg-neutral/15 border-neutral/30',
  warn: 'bg-warn/15 border-warn/30',
  bad: 'bg-bad/15 border-bad/30',
};

export const signalText: Record<SignalKey, string> = {
  good: 'text-good',
  neutral: 'text-muted',
  warn: 'text-warn',
  bad: 'text-bad',
};

export const SIGNAL_KR: Record<SignalKey, string> = {
  good: '긍정',
  neutral: '중립',
  warn: '주의',
  bad: '위험',
};
