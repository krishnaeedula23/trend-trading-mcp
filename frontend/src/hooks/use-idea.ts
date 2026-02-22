"use client";

import useSWR from 'swr';
import type { Idea } from '@/lib/types';
import { ApiError } from '@/lib/errors';

async function fetcher(url: string): Promise<Idea> {
  const res = await fetch(url);
  if (!res.ok) {
    let detail = 'Failed to load idea';
    try {
      const err = await res.json();
      detail = err.error ?? detail;
    } catch { /* use default */ }
    throw new ApiError(res.status, res.status === 404 ? 'NOT_FOUND' : 'UPSTREAM_ERROR', detail);
  }
  return res.json();
}

export function useIdea(id: string | null) {
  const { data, error, isLoading, mutate } = useSWR<Idea>(
    id ? `/api/ideas/${id}` : null,
    fetcher
  );

  return { idea: data, error, isLoading, refresh: mutate };
}
