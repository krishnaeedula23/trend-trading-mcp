export type ErrorCode =
  | "BAD_REQUEST"
  | "NOT_FOUND"
  | "UPSTREAM_ERROR"
  | "NETWORK_ERROR"
  | "UNKNOWN"

export class RailwayError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public path: string
  ) {
    super(`Railway ${status} on ${path}: ${detail}`)
    this.name = "RailwayError"
  }

  get code(): ErrorCode {
    if (this.status >= 400 && this.status < 500) return "BAD_REQUEST"
    if (this.status >= 500) return "UPSTREAM_ERROR"
    return "UNKNOWN"
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: ErrorCode,
    public detail: string
  ) {
    super(detail)
    this.name = "ApiError"
  }
}

export function categorizeError(error: unknown): {
  code: ErrorCode
  message: string
} {
  if (error instanceof ApiError) {
    return { code: error.code, message: error.detail }
  }
  if (error instanceof RailwayError) {
    return { code: error.code, message: error.detail }
  }
  if (error instanceof TypeError && error.message.includes("fetch")) {
    return { code: "NETWORK_ERROR", message: "Network error — check your connection" }
  }
  if (error instanceof Error) {
    return { code: "UNKNOWN", message: error.message }
  }
  return { code: "UNKNOWN", message: "An unexpected error occurred" }
}

export function userMessage(code: ErrorCode): string {
  switch (code) {
    case "BAD_REQUEST":
      return "Invalid request — check the ticker symbol"
    case "NOT_FOUND":
      return "Not found"
    case "UPSTREAM_ERROR":
      return "Backend unavailable — try again shortly"
    case "NETWORK_ERROR":
      return "Network error — check your connection"
    case "UNKNOWN":
      return "Something went wrong"
  }
}
