/**
 * Returns a one-shot client upload token for Vercel Blob.
 * Called by the chart-upload-dropzone component before PUTting the file.
 */
import { handleUpload, type HandleUploadBody } from "@vercel/blob/client"
import { NextResponse } from "next/server"

export async function POST(request: Request) {
  const body = (await request.json()) as HandleUploadBody
  try {
    const jsonResponse = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async (pathname) => {
        // restrict to .png/.jpg/.webp under swing-charts/
        if (!pathname.startsWith("swing-charts/")) {
          throw new Error("Invalid pathname")
        }
        return {
          allowedContentTypes: ["image/png", "image/jpeg", "image/webp"],
          tokenPayload: JSON.stringify({}),
        }
      },
      onUploadCompleted: async ({ blob }) => {
        // Nothing server-side here — the client component posts the URL to Railway
        // after the PUT resolves.
        console.log("Blob uploaded:", blob.url)
      },
    })
    return NextResponse.json(jsonResponse)
  } catch (error) {
    return NextResponse.json({ error: (error as Error).message }, { status: 400 })
  }
}
