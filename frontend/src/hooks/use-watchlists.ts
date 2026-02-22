"use client";

import useSWR from 'swr';
import type { Watchlist } from '@/lib/types';

const fetcher = (url: string) => fetch(url).then(res => res.json());

export function useWatchlists() {
  const { data, error, isLoading, mutate } = useSWR<Watchlist[]>(
    '/api/watchlists',
    fetcher
  );

  return { watchlists: data ?? [], error, isLoading, refresh: mutate };
}

export async function createWatchlist(name: string, tickers: string[]): Promise<Watchlist> {
  const res = await fetch('/api/watchlists', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, tickers }),
  });
  if (!res.ok) throw new Error('Failed to create watchlist');
  return res.json();
}
