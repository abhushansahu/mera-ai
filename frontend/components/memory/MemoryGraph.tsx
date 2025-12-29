"use client";

import { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';
import { useAppStore } from '@/store/useAppStore';
import { chatApi } from '@/lib/api/client';

interface MemoryGraphProps {
  spaceId?: string;
}

export function MemoryGraph({ spaceId }: MemoryGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const { currentSpace } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const activeSpaceId = spaceId || currentSpace?.space_id;

  useEffect(() => {
    if (!containerRef.current || !activeSpaceId) {
      setLoading(false);
      return;
    }

    const loadMemoryGraph = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await chatApi.getSpaceVisualization(activeSpaceId);
        
        if (!containerRef.current) return;

        // Destroy existing instance
        if (cyRef.current) {
          cyRef.current.destroy();
        }

        // Build graph from memory data
        const nodes: any[] = [];
        const edges: any[] = [];
        
        if (data.memories && Array.isArray(data.memories)) {
          data.memories.forEach((memory: any, index: number) => {
            nodes.push({
              data: {
                id: `memory-${index}`,
                label: memory.text?.substring(0, 30) || `Memory ${index + 1}`,
                fullText: memory.text,
                score: memory.score,
              },
            });
            
            // Create connections between related memories (simplified - based on score similarity)
            if (index > 0 && memory.score > 0.5) {
              edges.push({
                data: {
                  id: `edge-${index}`,
                  source: `memory-${index - 1}`,
                  target: `memory-${index}`,
                },
              });
            }
          });
        }

        // If no memories, show placeholder
        if (nodes.length === 0) {
          nodes.push({
            data: { id: 'placeholder', label: 'No memories yet' },
          });
        }

        cyRef.current = cytoscape({
          container: containerRef.current,
          elements: [...nodes, ...edges],
          style: [
            {
              selector: 'node',
              style: {
                'background-color': '#3b82f6',
                label: 'data(label)',
                'text-valign': 'center',
                'text-halign': 'center',
                color: 'white',
                width: 100,
                height: 100,
                'font-size': '12px',
                'text-wrap': 'wrap',
                'text-max-width': '80px',
                shape: 'ellipse',
              },
            },
            {
              selector: 'edge',
              style: {
                'line-color': '#9ca3af',
                'target-arrow-color': '#9ca3af',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier',
                width: 2,
              },
            },
            {
              selector: 'node[label = "No memories yet"]',
              style: {
                'background-color': '#9ca3af',
                width: 150,
                height: 50,
              },
            },
          ],
          layout: {
            name: 'cose',
            idealEdgeLength: 100,
            nodeOverlap: 20,
            refresh: 20,
            fit: true,
            padding: 30,
            randomize: false,
            componentSpacing: 100,
            nodeRepulsion: 4000000,
            edgeElasticity: 100,
            nestingFactor: 5,
            gravity: 80,
            numIter: 1000,
            initialTemp: 200,
            coolingFactor: 0.95,
            minTemp: 1.0,
          },
        });

        // Add click handler
        cyRef.current.on('tap', 'node', (evt) => {
          const node = evt.target;
          const fullText = node.data('fullText');
          if (fullText) {
            alert(fullText);
          }
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load memory graph');
        console.error('Error loading memory graph:', err);
      } finally {
        setLoading(false);
      }
    };

    loadMemoryGraph();

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
      }
    };
  }, [activeSpaceId]);

  if (loading) {
    return (
      <div className="w-full h-96 border border-gray-200 dark:border-gray-700 rounded-lg flex items-center justify-center bg-gray-50 dark:bg-gray-800">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-96 border border-gray-200 dark:border-gray-700 rounded-lg flex items-center justify-center bg-gray-50 dark:bg-gray-800">
        <div className="text-center">
          <p className="text-red-600 dark:text-red-400 mb-2">Error loading graph</p>
          <p className="text-sm text-gray-600 dark:text-gray-400">{error}</p>
        </div>
      </div>
    );
  }

  if (!activeSpaceId) {
    return (
      <div className="w-full h-96 border border-gray-200 dark:border-gray-700 rounded-lg flex items-center justify-center bg-gray-50 dark:bg-gray-800">
        <p className="text-gray-500 dark:text-gray-400">Select a space to view memory graph</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="w-full h-96 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800"
    />
  );
}
