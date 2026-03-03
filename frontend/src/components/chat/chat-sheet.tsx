"use client"

import { useState } from "react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { MessageCircle } from "lucide-react"
import { ChatPanel } from "./chat-panel"

export function ChatSheet() {
  const [open, setOpen] = useState(false)

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          size="icon"
          className="fixed bottom-6 right-6 z-50 size-12 rounded-full shadow-lg"
        >
          <MessageCircle className="size-5" />
        </Button>
      </SheetTrigger>
      <SheetContent
        side="right"
        className="flex w-full flex-col p-0 sm:max-w-[420px]"
      >
        <SheetHeader className="border-b px-4 py-3">
          <SheetTitle className="text-sm font-medium">
            Trading Assistant
          </SheetTitle>
        </SheetHeader>
        <ChatPanel className="flex-1 overflow-hidden" />
      </SheetContent>
    </Sheet>
  )
}
