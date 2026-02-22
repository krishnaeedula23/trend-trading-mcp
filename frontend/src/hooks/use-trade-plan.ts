"use client";

import useSWR from 'swr';
import type { TradePlanResponse } from '@/lib/types';

const fetcher = (url: string, body: unknown) =>
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(res => {
    if (!res.ok) throw new Error('Failed to fetch trade plan');
    return res.json();
  });

export function useTradePlan(
  ticker: string | null,
  timeframe: string = '5m',
  direction: string = 'bullish'
) {
  // Use SWR with POST - key is null when no ticker
  const { data, error, isLoading, mutate } = useSWR<TradePlanResponse>(
    ticker ? ['/api/satyland/trade-plan', ticker, timeframe, direction] : null,
    ([url]) => fetcher(url as string, { ticker, timeframe, direction }),
    { refreshInterval: 60000 }
  );

  return { data, error, isLoading, refresh: mutate };
}
