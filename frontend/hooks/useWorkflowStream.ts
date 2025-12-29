import { useEffect, useRef, useState } from 'react';
import { ChatRequest } from '@/lib/api/client';

export interface StreamEvent {
  type: 'start' | 'research' | 'plan' | 'answer' | 'metadata' | 'done' | 'error';
  content?: string;
  message?: string;
  data?: Record<string, any>;
}

export function useWorkflowStream() {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);

  const startStream = async (
    request: ChatRequest,
    onEvent?: (event: StreamEvent) => void
  ): Promise<StreamEvent[]> => {
    setIsStreaming(true);
    setEvents([]);
    const newEvents: StreamEvent[] = [];

    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const url = `${API_URL}/chat/stream`;

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      readerRef.current = reader;
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              newEvents.push(data);
              setEvents((prev) => [...prev, data]);
              // Call callback immediately for real-time updates
              if (onEvent) {
                onEvent(data);
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Stream error:', error);
      const errorEvent: StreamEvent = {
        type: 'error',
        message: error instanceof Error ? error.message : 'Unknown error',
      };
      newEvents.push(errorEvent);
      setEvents((prev) => [...prev, errorEvent]);
      if (onEvent) {
        onEvent(errorEvent);
      }
    } finally {
      setIsStreaming(false);
      readerRef.current = null;
    }

    return newEvents;
  };

  const stopStream = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (readerRef.current) {
      readerRef.current.cancel();
      readerRef.current = null;
    }
    setIsStreaming(false);
  };

  useEffect(() => {
    return () => {
      stopStream();
    };
  }, []);

  return {
    events,
    isStreaming,
    startStream,
    stopStream,
  };
}
