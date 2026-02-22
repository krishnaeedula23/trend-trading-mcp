// ---------------------------------------------------------------------------
// Browser-side Supabase client (singleton).
// Uses NEXT_PUBLIC_* env vars so the values are inlined at build time.
// ---------------------------------------------------------------------------

import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl) {
  throw new Error(
    "Missing NEXT_PUBLIC_SUPABASE_URL environment variable. " +
      "Add it to .env.local or your deployment settings."
  );
}

if (!supabaseAnonKey) {
  throw new Error(
    "Missing NEXT_PUBLIC_SUPABASE_ANON_KEY environment variable. " +
      "Add it to .env.local or your deployment settings."
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
