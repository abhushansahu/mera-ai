"use client";

import { useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { chatApi, ChatRequest } from '@/lib/api/client';
import { useWorkflowStream } from '@/hooks/useWorkflowStream';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';

export function ChatInterface() {
  const { messages, addMessage, currentSpace, workflowState, setWorkflowState } = useAppStore();
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { startStream, isStreaming, events } = useWorkflowStream();

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = {
      id: Date.now().toString(),
      role: 'user' as const,
      content: input,
      timestamp: new Date(),
    };
    addMessage(userMessage);
    const query = input;
    setInput('');
    setIsLoading(true);
    
    // Reset workflow state
    setWorkflowState({ stage: 'idle' });

    // Track current state for progressive updates
    let research = '';
    let plan = '';
    let answer = '';
    let metadata: Record<string, any> = {};
    let researchMessageId: string | null = null;
    let planMessageId: string | null = null;
    let answerMessageId: string | null = null;

    try {
      const request: ChatRequest = {
        user_id: 'default-user',
        query: query,
        space_id: currentSpace?.space_id,
        model: currentSpace?.preferred_model,
      };

      // Use streaming with real-time callback
      await startStream(request, (event) => {
        // Process events as they arrive
        if (event.type === 'start') {
          setWorkflowState({ stage: 'research' });
        } else if (event.type === 'research' && event.content) {
          research = event.content;
          setWorkflowState({ stage: 'research', research });
          
          // Add or update research message
          if (!researchMessageId) {
            const msgId = `research-${Date.now()}`;
            researchMessageId = msgId;
            addMessage({
              id: msgId,
              role: 'research',
              content: research,
              timestamp: new Date(),
            });
          } else {
            // Update existing message (for progressive updates)
            // In a real implementation, you'd update the message in the store
          }
        } else if (event.type === 'plan' && event.content) {
          plan = event.content;
          setWorkflowState({ stage: 'plan', research, plan });
          
          if (!planMessageId) {
            const msgId = `plan-${Date.now()}`;
            planMessageId = msgId;
            addMessage({
              id: msgId,
              role: 'plan',
              content: plan,
              timestamp: new Date(),
            });
          }
        } else if (event.type === 'answer' && event.content) {
          answer = event.content;
          setWorkflowState({ stage: 'implement', research, plan, answer, metadata });
          
          if (!answerMessageId) {
            const msgId = `answer-${Date.now()}`;
            answerMessageId = msgId;
            addMessage({
              id: msgId,
              role: 'assistant',
              content: answer,
              timestamp: new Date(),
            });
          }
        } else if (event.type === 'metadata' && event.data) {
          metadata = event.data;
          setWorkflowState({ stage: workflowState.stage, research, plan, answer, metadata });
        } else if (event.type === 'done') {
          setWorkflowState({ stage: 'complete', research, plan, answer, metadata });
        } else if (event.type === 'error') {
          addMessage({
            id: `error-${Date.now()}`,
            role: 'assistant',
            content: `Error: ${event.message || 'Unknown error'}`,
            timestamp: new Date(),
          });
        }
      });
    } catch (error) {
      console.error('Chat error:', error);
      addMessage({
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: new Date(),
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex-1 overflow-y-auto p-4 min-h-0">
        <MessageList messages={messages} />
        {(isLoading || isStreaming) && (
          <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400 mt-4">
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent"></div>
            <span className="text-sm">
              {workflowState.stage === 'research' ? 'Researching...' :
               workflowState.stage === 'plan' ? 'Planning...' :
               workflowState.stage === 'implement' ? 'Implementing...' :
               'Processing...'}
            </span>
          </div>
        )}
      </div>
      <ChatInput
        value={input}
        onChange={setInput}
        onSend={handleSend}
        isLoading={isLoading || isStreaming}
      />
    </div>
  );
}
