"use client";

import { Message } from '@/store/useAppStore';
import ReactMarkdown from 'react-markdown';
import { useState } from 'react';

interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isResearch = message.role === 'research';
  const isPlan = message.role === 'plan';
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatTime = (date: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    }).format(date);
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4 animate-fade-in`}>
      <div className={`max-w-3xl rounded-xl p-4 shadow-md transition-all hover:shadow-lg ${
        isUser
          ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white'
          : isResearch
          ? 'bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/30 dark:to-blue-800/30 text-blue-900 dark:text-blue-100 border border-blue-200 dark:border-blue-700'
          : isPlan
          ? 'bg-gradient-to-br from-amber-50 to-amber-100 dark:from-amber-900/30 dark:to-amber-800/30 text-amber-900 dark:text-amber-100 border border-amber-200 dark:border-amber-700'
          : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700'
      }`}>
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex items-center gap-2">
            {isResearch && (
              <span className="text-xs font-semibold px-2 py-1 rounded-full bg-blue-200 dark:bg-blue-800 text-blue-800 dark:text-blue-200">
                🔍 Research
              </span>
            )}
            {isPlan && (
              <span className="text-xs font-semibold px-2 py-1 rounded-full bg-amber-200 dark:bg-amber-800 text-amber-800 dark:text-amber-200">
                📋 Plan
              </span>
            )}
            {!isUser && !isResearch && !isPlan && (
              <span className="text-xs font-semibold px-2 py-1 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300">
                🤖 Assistant
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs opacity-70">
              {formatTime(message.timestamp)}
            </span>
            {!isUser && (
              <button
                onClick={handleCopy}
                className="p-1 rounded hover:bg-black/10 dark:hover:bg-white/10 transition-colors"
                aria-label="Copy message"
              >
                {copied ? '✓' : '📋'}
              </button>
            )}
          </div>
        </div>
        <div className={`prose prose-sm max-w-none ${
          isUser ? 'prose-invert' : ''
        } dark:prose-invert`}>
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
