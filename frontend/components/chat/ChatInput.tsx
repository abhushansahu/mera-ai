"use client";

import { useAppStore } from '@/store/useAppStore';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isLoading: boolean;
}

export function ChatInput({ value, onChange, onSend, isLoading }: ChatInputProps) {
  const { clearMessages } = useAppStore();

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="border-t dark:border-gray-700 p-4 bg-white dark:bg-gray-900 flex-shrink-0">
      <div className="flex gap-2 items-end">
        <div className="flex-1">
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="Ask a question... (Press Enter to send, Shift+Enter for new line)"
            className="w-full p-3 border border-gray-300 dark:border-gray-600 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 transition-all"
            rows={3}
            disabled={isLoading}
          />
        </div>
        <div className="flex flex-col gap-2">
          <button
            onClick={onSend}
            disabled={isLoading || !value.trim()}
            className="px-6 py-3 bg-gradient-primary text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-lg transition-all font-medium"
          >
            {isLoading ? (
              <span className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                Sending...
              </span>
            ) : (
              'Send'
            )}
          </button>
          <button
            onClick={clearMessages}
            className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 transition-colors"
            title="Clear conversation"
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  );
}
