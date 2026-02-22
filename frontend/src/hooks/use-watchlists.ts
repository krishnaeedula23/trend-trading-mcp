"use client";

import useSWR from 'swr';
import type { Watchlist } from '@/lib/types';
import { ApiError } from '@/lib/errors';

async function fetcher(url: string): Promise<Watchlist[]> {
  const res = await fetch(url);
  if (!res.ok) {
    let detail = 'Failed to load watchlists';
    try {
      const err = await res.json();
      detail = err.error ?? detail;
    } catch { /* use default */ }
    throw new ApiError(res.status, 'UPSTREAM_ERROR', detail);
  }
  return res.json();
}

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
  if (!res.ok) {
    let detail = 'Failed to create watchlist';
    try {
      const err = await res.json();
      detail = err.error ?? detail;
    } catch { /* use default */ }
    throw new ApiError(res.status, 'UPSTREAM_ERROR', detail);
  }
  return res.json();
}

export async function updateWatchlist(
  id: string,
  data: { name?: string; tickers?: string[] }
): Promise<Watchlist> {
  const res = await fetch(`/api/watchlists/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    let detail = 'Failed to update watchlist';
    try {
      const err = await res.json();
      detail = err.error ?? detail;
    } catch { /* use default */ }
    throw new ApiError(res.status, 'UPSTREAM_ERROR', detail);
  }
  return res.json();
}

export async function deleteWatchlist(id: string): Promise<void> {
  const res = await fetch(`/api/watchlists/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    let detail = 'Failed to delete watchlist';
    try {
      const err = await res.json();
      detail = err.error ?? detail;
    } catch { /* use default */ }
    throw new ApiError(res.status, 'UPSTREAM_ERROR', detail);
  }
}
