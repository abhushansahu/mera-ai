"use client";

import { useAppStore } from '@/store/useAppStore';
import ReactFlow, { Node, Edge, Background, Controls } from 'reactflow';
import 'reactflow/dist/style.css';

export function RPIWorkflow() {
  const { workflowState } = useAppStore();

  const nodes: Node[] = [
    {
      id: 'research',
      type: 'default',
      position: { x: 100, y: 100 },
      data: {
        label: (
          <div className="p-4">
            <div className="font-bold text-blue-600">🔍 Research</div>
            {workflowState.research && (
              <div className="mt-2 text-sm text-gray-600 max-w-xs">
                {workflowState.research.substring(0, 100)}...
              </div>
            )}
          </div>
        ),
      },
      style: {
        background: workflowState.stage === 'research' || (workflowState.stage !== 'idle' && workflowState.stage !== 'plan' && workflowState.stage !== 'implement' && workflowState.stage !== 'complete') 
          ? 'linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%)' 
          : workflowState.stage !== 'idle' 
          ? '#e0e7ff' 
          : '#f3f4f6',
        border: workflowState.stage === 'research' ? '2px solid #3b82f6' : '1px solid #e5e7eb',
        borderRadius: '12px',
        padding: 0,
        boxShadow: workflowState.stage === 'research' ? '0 4px 6px -1px rgba(59, 130, 246, 0.3)' : '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        transition: 'all 0.3s ease',
      },
    },
    {
      id: 'plan',
      type: 'default',
      position: { x: 400, y: 100 },
      data: {
        label: (
          <div className="p-4">
            <div className="font-bold text-yellow-600">📋 Plan</div>
            {workflowState.plan && (
              <div className="mt-2 text-sm text-gray-600 max-w-xs">
                {workflowState.plan.substring(0, 100)}...
              </div>
            )}
          </div>
        ),
      },
      style: {
        background: workflowState.stage === 'plan' || (workflowState.stage !== 'idle' && workflowState.stage !== 'research' && workflowState.stage !== 'implement' && workflowState.stage !== 'complete')
          ? 'linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)'
          : workflowState.stage !== 'idle' && workflowState.stage !== 'research'
          ? '#fef3c7'
          : '#f3f4f6',
        border: workflowState.stage === 'plan' ? '2px solid #f59e0b' : '1px solid #e5e7eb',
        borderRadius: '12px',
        padding: 0,
        boxShadow: workflowState.stage === 'plan' ? '0 4px 6px -1px rgba(245, 158, 11, 0.3)' : '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        transition: 'all 0.3s ease',
      },
    },
    {
      id: 'implement',
      type: 'default',
      position: { x: 700, y: 100 },
      data: {
        label: (
          <div className="p-4">
            <div className="font-bold text-green-600">✅ Implement</div>
            {workflowState.answer && (
              <div className="mt-2 text-sm text-gray-600 max-w-xs">
                {workflowState.answer.substring(0, 100)}...
              </div>
            )}
          </div>
        ),
      },
      style: {
        background: workflowState.stage === 'implement' || workflowState.stage === 'complete'
          ? 'linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%)'
          : '#f3f4f6',
        border: workflowState.stage === 'implement' || workflowState.stage === 'complete' ? '2px solid #10b981' : '1px solid #e5e7eb',
        borderRadius: '12px',
        padding: 0,
        boxShadow: workflowState.stage === 'implement' || workflowState.stage === 'complete' ? '0 4px 6px -1px rgba(16, 185, 129, 0.3)' : '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        transition: 'all 0.3s ease',
      },
    },
  ];

  const edges: Edge[] = [
    {
      id: 'research-plan',
      source: 'research',
      target: 'plan',
      animated: workflowState.stage === 'plan',
      style: { stroke: workflowState.stage === 'plan' ? '#3b82f6' : '#9ca3af', strokeWidth: 2 },
    },
    {
      id: 'plan-implement',
      source: 'plan',
      target: 'implement',
      animated: workflowState.stage === 'implement' || workflowState.stage === 'complete',
      style: { stroke: workflowState.stage === 'implement' || workflowState.stage === 'complete' ? '#10b981' : '#9ca3af', strokeWidth: 2 },
    },
  ];

  return (
    <div className="w-full h-full border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden bg-white dark:bg-gray-800 shadow-sm">
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background color="#e5e7eb" gap={16} />
        <Controls className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-md" />
      </ReactFlow>
    </div>
  );
}
