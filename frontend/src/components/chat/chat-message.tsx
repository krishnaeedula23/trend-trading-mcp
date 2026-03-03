"use client"

import type { UIMessage } from "ai"
import { isToolUIPart } from "ai"
import { cn } from "@/lib/utils"
import { ToolResultCard } from "./tool-result-card"
import { Bot, User } from "lucide-react"

interface ChatMessageProps {
  message: UIMessage
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user"

  return (
    <div className={cn("flex gap-3 py-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex size-7 shrink-0 items-center justify-center rounded-full border",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-muted-foreground",
        )}
      >
        {isUser ? <User className="size-4" /> : <Bot className="size-4" />}
      </div>
      <div className={cn("flex-1 space-y-2", isUser && "text-right")}>
        {message.parts.map((part, i) => {
          const key = `${message.id}-${i}`
          if (part.type === "text") {
            return (
              <div
                key={key}
                className="prose prose-sm prose-invert max-w-none"
              >
                {part.text}
              </div>
            )
          }
          if (isToolUIPart(part)) {
            // v6: tool name is embedded in part.type as "tool-{name}"
            const toolName = part.type.replace(/^tool-/, "")
            return (
              <ToolResultCard
                key={key}
                toolName={toolName}
                state={part.state}
                input={(part.input ?? {}) as Record<string, unknown>}
                output={
                  part.state === "output-available" ? part.output : undefined
                }
              />
            )
          }
          return null
        })}
      </div>
    </div>
  )
}
