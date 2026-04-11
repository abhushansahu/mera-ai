"use client";

import { useEffect, useMemo, useState } from 'react';
import ReactFlow, { Node, Edge, Background, Controls } from 'reactflow';
import 'reactflow/dist/style.css';
import { chatApi } from '@/lib/api/client';

interface AgentFlowProps {
  sessionId?: string;
}

export function AgentFlow({ sessionId }: AgentFlowProps) {
  const [agents, setAgents] = useState<any[]>([]);

  useEffect(() => {
    let mounted = true;
    if (sessionId) {
      chatApi.getAgentActivity(sessionId).then((data) => {
        if (mounted) {
          setAgents(data.agents || []);
        }
      });
    } else {
      setAgents([]);
    }
    return () => {
      mounted = false;
    };
  }, [sessionId]);

  const nodes: Node[] = useMemo(() => agents.map((agent, index) => ({
    id: agent.name || `agent-${index}`,
    type: 'default',
    position: { x: index * 200, y: 100 },
    data: {
      label: (
        <div className="p-2">
          <div className="font-bold">{agent.name}</div>
          <div className="text-xs text-gray-600">{agent.role}</div>
          <div className={`text-xs mt-1 ${agent.status === 'active' ? 'text-green-600' : 'text-gray-400'}`}>
            {agent.status}
          </div>
        </div>
      ),
    },
    style: {
      background: agent.status === 'active' ? '#dbeafe' : '#f3f4f6',
      border: agent.status === 'active' ? '2px solid #3b82f6' : '1px solid #e5e7eb',
      borderRadius: '8px',
    },
  })), [agents]);

  const edges: Edge[] = useMemo(() => {
    const computed: Edge[] = [];
    for (let i = 0; i < nodes.length - 1; i++) {
      computed.push({
        id: `edge-${i}`,
        source: nodes[i].id,
        target: nodes[i + 1].id,
        animated: agents[i]?.status === 'active',
      });
    }
    return computed;
  }, [agents, nodes]);

  return (
    <div className="w-full h-64 border rounded-lg">
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
