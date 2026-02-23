import { NextRequest, NextResponse } from 'next/server';
import { railwayFetch } from '@/lib/railway';
import { RailwayError } from '@/lib/errors';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { ticker, timeframe, use_current_close } = body;

    if (!ticker) {
      return NextResponse.json(
        { error: 'ticker is required', code: 'BAD_REQUEST' },
        { status: 400 }
      );
    }

    const response = await railwayFetch('/api/satyland/calculate', {
      ticker,
      timeframe: timeframe || '5m',
      use_current_close: use_current_close ?? undefined,
    });

    const data = await response.json();

    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 's-maxage=60, stale-while-revalidate=300',
      },
    });
  } catch (error) {
    if (error instanceof RailwayError) {
      return NextResponse.json(
        { error: error.detail, code: error.code },
        { status: error.status }
      );
    }
    console.error('Satyland calculate error:', error);
    return NextResponse.json(
      { error: 'Backend unavailable', code: 'NETWORK_ERROR' },
      { status: 502 }
    );
  }
}
