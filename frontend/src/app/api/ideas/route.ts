import { NextRequest, NextResponse } from 'next/server';
import { createServerClient } from '@/lib/supabase/server';

export async function GET(request: NextRequest) {
  try {
    const supabase = createServerClient();
    const { searchParams } = new URL(request.url);

    const status = searchParams.get('status');
    const ticker = searchParams.get('ticker');

    let query = supabase
      .from('ideas')
      .select('*')
      .order('created_at', { ascending: false });

    if (status) {
      query = query.eq('status', status);
    }

    if (ticker) {
      query = query.eq('ticker', ticker.toUpperCase());
    }

    const { data, error } = await query;

    if (error) {
      console.error('Supabase query error:', error);
      return NextResponse.json(
        { error: error.message },
        { status: 500 }
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error('Ideas GET error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const supabase = createServerClient();
    const body = await request.json();

    const {
      ticker,
      direction,
      timeframe,
      grade,
      score,
      indicator_snapshot,
      status,
      notes,
      entry_price,
      stop_loss,
      target_1,
      target_2,
      ribbon_state,
      bias_candle,
      phase,
      atr_status,
      current_price,
      call_trigger,
      put_trigger,
    } = body;

    if (!ticker) {
      return NextResponse.json(
        { error: 'ticker is required' },
        { status: 400 }
      );
    }

    const { data, error } = await supabase
      .from('ideas')
      .insert({
        ticker: ticker.toUpperCase(),
        direction: direction || 'bullish',
        timeframe: timeframe || '5m',
        grade: grade || null,
        score: score ?? null,
        indicator_snapshot: indicator_snapshot || null,
        status: status || 'watching',
        notes: notes || null,
        entry_price: entry_price ?? null,
        stop_loss: stop_loss ?? null,
        target_1: target_1 ?? null,
        target_2: target_2 ?? null,
        ribbon_state: ribbon_state || null,
        bias_candle: bias_candle || null,
        phase: phase || null,
        atr_status: atr_status || null,
        current_price: current_price ?? null,
        call_trigger: call_trigger ?? null,
        put_trigger: put_trigger ?? null,
      })
      .select()
      .single();

    if (error) {
      console.error('Supabase insert error:', error);
      return NextResponse.json(
        { error: error.message },
        { status: 500 }
      );
    }

    return NextResponse.json(data, { status: 201 });
  } catch (error) {
    console.error('Ideas POST error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
