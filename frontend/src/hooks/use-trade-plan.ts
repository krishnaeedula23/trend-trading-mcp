"use client";

import useSWR from 'swr';
import type { TradePlanResponse } from '@/lib/types';
import { ApiError, type ErrorCode } from '@/lib/errors';

const fetcher = async (url: string, body: unknown) => {
  let res: Response;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Network error — check your connection');
  }

  if (!res.ok) {
    let code: ErrorCode = 'UNKNOWN';
    let detail = 'Failed to fetch trade plan';
    try {
      const err = await res.json();
      code = err.code ?? (res.status >= 500 ? 'UPSTREAM_ERROR' : 'BAD_REQUEST');
      detail = err.error ?? detail;
    } catch { /* use defaults */ }
    throw new ApiError(res.status, code, detail);
  }

  return res.json();
};

export function useTradePlan(
  ticker: string | null,
  timeframe: string = '1d',
  direction: string = 'bullish',
  useCurrentClose?: boolean | null
) {
  const { data, error, isLoading, mutate } = useSWR<TradePlanResponse>(
    ticker ? ['/api/satyland/trade-plan', ticker, timeframe, direction, useCurrentClose ?? 'auto'] : null,
    ([url]) => fetcher(url as string, {
      ticker,
      timeframe,
      direction,
      use_current_close: useCurrentClose ?? undefined,
    }),
    { refreshInterval: 60000 }
  );

  return { data, error: error as ApiError | undefined, isLoading, refresh: mutate };
}
