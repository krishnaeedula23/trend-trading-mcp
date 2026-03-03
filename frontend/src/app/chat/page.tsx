import { ChatPanel } from "@/components/chat/chat-panel"

export default function ChatPage() {
  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <div className="border-b px-4 py-3">
        <h1 className="text-lg font-semibold">Trading Assistant</h1>
        <p className="text-sm text-muted-foreground">
          Ask about setups, run screeners, or analyze tickers
        </p>
      </div>
      <ChatPanel className="flex-1 overflow-hidden" />
    </div>
  )
}
