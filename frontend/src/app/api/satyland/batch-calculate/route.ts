import { NextRequest, NextResponse } from 'next/server';
import { railwayFetch } from '@/lib/railway';
import { RailwayError } from '@/lib/errors';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { tickers, timeframe, direction, trading_mode } = body;

    if (!tickers || !Array.isArray(tickers) || tickers.length === 0) {
      return NextResponse.json(
        { error: 'tickers array is required', code: 'BAD_REQUEST' },
        { status: 400 }
      );
    }

    if (tickers.length > 20) {
      return NextResponse.json(
        { error: 'Maximum 20 tickers allowed', code: 'BAD_REQUEST' },
        { status: 400 }
      );
    }

    const response = await railwayFetch('/api/satyland/batch-calculate', {
      tickers,
      timeframe: timeframe || '5m',
      direction: direction || 'bullish',
      trading_mode: trading_mode ?? undefined,
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
    console.error('Batch calculate error:', error);
    return NextResponse.json(
      { error: 'Backend unavailable', code: 'NETWORK_ERROR' },
      { status: 502 }
    );
  }
}
