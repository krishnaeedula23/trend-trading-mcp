// ---------------------------------------------------------------------------
// Railway API client — server-side only fetch wrapper for the Saty API.
// Uses RAILWAY_API_URL env var (e.g. "https://your-app.railway.app").
// ---------------------------------------------------------------------------

import type {
  AtmStraddle,
  CalculateResponse,
  IvMetrics,
  TradePlanResponse,
} from "./types";
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
  timeframe: string = "1d",
  opts?: { use_current_close?: boolean }
): Promise<CalculateResponse> {
  const body: Record<string, unknown> = { ticker, timeframe };
  if (opts?.use_current_close !== undefined) {
    body.use_current_close = opts.use_current_close;
  }
  const res = await railwayFetch("/api/satyland/calculate", body);
  return res.json() as Promise<CalculateResponse>;
}

/**
 * POST /api/satyland/trade-plan — full trade plan including Green Flag grading.
 */
export async function getTradePlan(
  ticker: string,
  timeframe: string = "1d",
  direction: string = "bullish",
  vix?: number,
  opts?: { use_current_close?: boolean }
): Promise<TradePlanResponse> {
  const body: Record<string, unknown> = { ticker, timeframe, direction };
  if (vix !== undefined) {
    body.vix = vix;
  }
  if (opts?.use_current_close !== undefined) {
    body.use_current_close = opts.use_current_close;
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

/**
 * POST /api/options/atm-straddle — ATM straddle pricing + expected move + IV.
 */
export async function getAtmStraddle(
  ticker: string,
  strikeCount: number = 10
): Promise<AtmStraddle> {
  const res = await railwayFetch("/api/options/atm-straddle", {
    ticker,
    strike_count: strikeCount,
  });
  return res.json() as Promise<AtmStraddle>;
}

/**
 * POST /api/options/iv-metrics — IV Rank + IV Percentile from VIX history.
 */
export async function getIvMetrics(
  ticker: string
): Promise<IvMetrics> {
  const res = await railwayFetch("/api/options/iv-metrics", { ticker });
  return res.json() as Promise<IvMetrics>;
}
