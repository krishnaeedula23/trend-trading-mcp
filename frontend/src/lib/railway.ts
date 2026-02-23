// ---------------------------------------------------------------------------
// Railway API client — server-side only fetch wrapper for the Saty API.
// Uses RAILWAY_API_URL env var (e.g. "https://your-app.railway.app").
// ---------------------------------------------------------------------------

import type { CalculateResponse, TradePlanResponse } from "./types";
import { RailwayError } from "./errors";

function getBaseUrl(): string {
  const url = process.env.RAILWAY_API_URL;
  if (!url) {
    throw new Error(
      "RAILWAY_API_URL environment variable is not set. " +
        "Set it to your Railway deployment URL (e.g. https://your-app.railway.app)."
    );
  }
  // Strip trailing slash for consistent path joining.
  return url.replace(/\/+$/, "");
}

/**
 * Low-level POST fetch against the Railway-hosted Saty API.
 * Returns the raw Response so callers can handle status codes themselves.
 */
export async function railwayFetch(
  path: string,
  body?: unknown
): Promise<Response> {
  const base = getBaseUrl();
  const url = `${base}${path}`;

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });

  if (!res.ok) {
    let detail: string;
    try {
      const err = await res.json();
      detail = err.detail ?? JSON.stringify(err);
    } catch {
      detail = res.statusText;
    }
    throw new RailwayError(res.status, detail, path);
  }

  return res;
}

/**
 * POST /api/satyland/calculate — returns ATR Levels, Pivot Ribbon, Phase Oscillator.
 */
export async function calculateIndicators(
  ticker: string,
  timeframe: string = "1d"
): Promise<CalculateResponse> {
  const res = await railwayFetch("/api/satyland/calculate", {
    ticker,
    timeframe,
  });
  return res.json() as Promise<CalculateResponse>;
}

/**
 * POST /api/satyland/trade-plan — full trade plan including Green Flag grading.
 */
export async function getTradePlan(
  ticker: string,
  timeframe: string = "1d",
  direction: string = "bullish",
  vix?: number
): Promise<TradePlanResponse> {
  const body: Record<string, unknown> = { ticker, timeframe, direction };
  if (vix !== undefined) {
    body.vix = vix;
  }
  const res = await railwayFetch("/api/satyland/trade-plan", body);
  return res.json() as Promise<TradePlanResponse>;
}

/**
 * POST /api/schwab/quote — real-time quote from Schwab.
 */
export async function getQuote(
  ticker: string
): Promise<Record<string, unknown>> {
  const res = await railwayFetch("/api/schwab/quote", { ticker });
  return res.json() as Promise<Record<string, unknown>>;
}
