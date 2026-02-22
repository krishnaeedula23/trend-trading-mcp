import { NextRequest, NextResponse } from 'next/server';
import { railwayFetch } from '@/lib/railway';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { ticker, timeframe, direction, vix } = body;

    if (!ticker) {
      return NextResponse.json(
        { error: 'ticker is required' },
        { status: 400 }
      );
    }

    const response = await railwayFetch('/api/satyland/trade-plan', {
      ticker,
      timeframe: timeframe || '5m',
      direction: direction || 'bullish',
      vix: vix ?? undefined,
    });

    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json(
        { error: `Railway API error: ${response.status}`, details: errorText },
        { status: response.status }
      );
    }

    const data = await response.json();

    return NextResponse.json(data, {
      headers: {
        'Cache-Control': 's-maxage=60, stale-while-revalidate=300',
      },
    });
  } catch (error) {
    console.error('Satyland trade-plan error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
