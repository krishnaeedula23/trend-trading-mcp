import { NextRequest, NextResponse } from 'next/server';
import { railwayFetch } from '@/lib/railway';
import { RailwayError } from '@/lib/errors';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const response = await railwayFetch('/api/screener/golden-gate-scan', body);
    const data = await response.json();

    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    if (error instanceof RailwayError) {
      return NextResponse.json(
        { error: error.detail, code: error.code },
        { status: error.status }
      );
    }
    console.error('Screener golden-gate-scan error:', error);
    return NextResponse.json(
      { error: 'Backend unavailable', code: 'NETWORK_ERROR' },
      { status: 502 }
    );
  }
}
