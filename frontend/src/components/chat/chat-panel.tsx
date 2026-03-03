"use client"

import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"
import { ChatMessage } from "./chat-message"
import { ChatInput } from "./chat-input"
import { useEffect, useRef, useState } from "react"
import { Bot } from "lucide-react"

interface ChatPanelProps {
  className?: string
}

const transport = new DefaultChatTransport({ api: "/api/chat" })

export function ChatPanel({ className }: ChatPanelProps) {
  const [input, setInput] = useState("")
  const { messages, sendMessage, status } = useChat({ transport })
  const scrollRef = useRef<HTMLDivElement>(null)
  const isLoading = status === "streaming" || status === "submitted"

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const onSubmit = () => {
    if (!input.trim()) return
    sendMessage({ text: input })
    setInput("")
  }

  return (
    <div className={`flex flex-col ${className ?? ""}`}>
      <div className="flex-1 overflow-y-auto px-3" ref={scrollRef}>
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-12 text-muted-foreground">
            <Bot className="size-8" />
            <p className="text-sm">Ask me about your trading setups</p>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))
        )}
      </div>
      <ChatInput
        value={input}
        onChange={setInput}
        onSubmit={onSubmit}
        isLoading={isLoading}
      />
    </div>
  )
}
