import { google } from "@ai-sdk/google"
import {
  convertToModelMessages,
  stepCountIs,
  streamText,
  type UIMessage,
} from "ai"
import { tradingTools } from "@/lib/ai/tools"
import { TRADING_SYSTEM_PROMPT } from "@/lib/ai/system-prompt"

export const maxDuration = 60

export async function POST(req: Request) {
  const { messages }: { messages: UIMessage[] } = await req.json()

  const result = streamText({
    model: google("gemini-2.5-flash"),
    system: TRADING_SYSTEM_PROMPT,
    messages: await convertToModelMessages(messages),
    tools: tradingTools,
    stopWhen: stepCountIs(5),
  })

  return result.toUIMessageStreamResponse()
}
