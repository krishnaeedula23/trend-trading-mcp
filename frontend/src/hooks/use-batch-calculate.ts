"use client";

import useSWR from 'swr';
import type { BatchCalculateResponse } from '@/lib/types';

const fetcher = async (url: string, body: unknown) => {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) return { results: [] };
  return res.json();
};

export function useBatchCalculate(
  tickers: string[],
  timeframe: string = '5m',
  direction: string = 'bullish'
) {
  const key = tickers.length > 0
    ? ['/api/satyland/batch-calculate', ...tickers.sort(), timeframe, direction]
    : null;

  const { data, error, isLoading } = useSWR<BatchCalculateResponse>(
    key,
    ([url]) => fetcher(url as string, { tickers, timeframe, direction }),
    { refreshInterval: 120000 }
  );

  return { results: data?.results ?? [], error, isLoading };
}
