import { NextRequest, NextResponse } from 'next/server';
import { railwayFetch } from '@/lib/railway';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { ticker } = body;

    if (!ticker) {
      return NextResponse.json(
        { error: 'ticker is required' },
        { status: 400 }
      );
    }

    const response = await railwayFetch('/api/schwab/quote', { ticker });

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
        'Cache-Control': 's-maxage=10, stale-while-revalidate=30',
      },
    });
  } catch (error) {
    console.error('Schwab quote error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
