"use client";

import { useMemo } from 'react';
import { Message } from '@/store/useAppStore';
import { MessageBubble } from './MessageBubble';

interface MessageListProps {
  messages: Message[];
}

export function MessageList({ messages }: MessageListProps) {
  const visibleMessages = useMemo(() => {
    const maxVisible = 200;
    if (messages.length <= maxVisible) {
      return messages;
    }
    return messages.slice(messages.length - maxVisible);
  }, [messages]);

  return (
    <div className="space-y-4">
      {messages.length > visibleMessages.length && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-800 dark:bg-amber-900/20 dark:text-amber-200">
          Showing latest {visibleMessages.length} messages for faster rendering.
        </div>
      )}
      {visibleMessages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
    </div>
  );
}
