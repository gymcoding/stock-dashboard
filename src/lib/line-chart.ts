import { scaleUtc, scaleLinear } from 'd3-scale';
import { line } from 'd3-shape';
import type { RatePoint } from './data';

export type ChartGeom = {
  width: number;
  height: number;
  pathD: string;
  xTicks: { x: number; label: string }[];
  yTicks: { y: number; label: string }[];
  last: { x: number; y: number; label: string } | null;
};

const W = 720;
const H = 280;
const PAD = { t: 16, r: 56, b: 28, l: 8 };

export function buildLineChart(
  points: RatePoint[],
  fmt: (v: number) => string = v => v.toFixed(2),
): ChartGeom | null {
  const clean = points.filter(p => !!p && Number.isFinite(p.value) && !!p.date);
  if (clean.length < 2) return null;

  const dates = clean.map(p => new Date(p.date + 'T00:00:00Z'));
  const values = clean.map(p => p.value);

  const x = scaleUtc()
    .domain([dates[0], dates[dates.length - 1]])
    .range([PAD.l, W - PAD.r]);

  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const pad = (maxV - minV) * 0.08 || 1;
  const y = scaleLinear()
    .domain([minV - pad, maxV + pad])
    .range([H - PAD.b, PAD.t]);

  const gen = line<{ d: Date; v: number }>()
    .x(p => x(p.d))
    .y(p => y(p.v));
  const pathD = gen(clean.map((p, i) => ({ d: dates[i], v: p.value }))) ?? '';
  if (!pathD.startsWith('M')) return null;

  const xTicks = x.ticks(5).map(t => ({ x: x(t), label: String(t.getUTCFullYear()) }));
  const yTicks = y.ticks(4).map(t => ({ y: y(t), label: fmt(t) }));

  const lp = clean[clean.length - 1];
  const last = { x: x(dates[dates.length - 1]), y: y(lp.value), label: fmt(lp.value) };

  return { width: W, height: H, pathD, xTicks, yTicks, last };
}
