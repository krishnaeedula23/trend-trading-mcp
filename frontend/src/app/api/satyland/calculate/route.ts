import { NextRequest, NextResponse } from 'next/server';
import { railwayFetch } from '@/lib/railway';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { ticker, timeframe } = body;

    if (!ticker) {
      return NextResponse.json(
        { error: 'ticker is required' },
        { status: 400 }
      );
    }

    const response = await railwayFetch('/api/satyland/calculate', {
      ticker,
      timeframe: timeframe || '5m',
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
    console.error('Satyland calculate error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
