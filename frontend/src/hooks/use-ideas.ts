"use client";

import useSWR from 'swr';
import type { Idea } from '@/lib/types';

const fetcher = (url: string) => fetch(url).then(res => res.json());

export function useIdeas(status?: string) {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  const key = `/api/ideas${params.toString() ? '?' + params.toString() : ''}`;

  const { data, error, isLoading, mutate } = useSWR<Idea[]>(
    key,
    fetcher,
    { refreshInterval: 30000 }
  );

  return { ideas: data ?? [], error, isLoading, refresh: mutate };
}

export async function createIdea(idea: Partial<Idea>): Promise<Idea> {
  const res = await fetch('/api/ideas', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(idea),
  });
  if (!res.ok) throw new Error('Failed to create idea');
  return res.json();
}

export async function updateIdea(id: string, updates: Partial<Idea>): Promise<Idea> {
  const res = await fetch(`/api/ideas/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error('Failed to update idea');
  return res.json();
}

export async function deleteIdea(id: string): Promise<void> {
  const res = await fetch(`/api/ideas/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete idea');
}
