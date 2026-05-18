import { readFileSync } from 'node:fs';
import type { RateHistory } from './data';

export function loadHistory(): RateHistory {
  try {
    return JSON.parse(readFileSync('src/data/history.json', 'utf-8')) as RateHistory;
  } catch {
    return {};
  }
}
