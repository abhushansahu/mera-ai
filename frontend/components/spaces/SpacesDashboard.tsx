"use client";

import { useEffect, useState } from 'react';
import { useAppStore, Space } from '@/store/useAppStore';
import { chatApi } from '@/lib/api/client';
import { CreateSpaceModal } from './CreateSpaceModal';

export function SpacesDashboard() {
  const { spaces, setSpaces, currentSpace, setCurrentSpace } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    const loadSpaces = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await chatApi.getSpaces();
        setSpaces(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load spaces');
        console.error('Error loading spaces:', err);
      } finally {
        setLoading(false);
      }
    };
    loadSpaces();
  }, [setSpaces]);

  const handleSelectSpace = (space: Space) => {
    setCurrentSpace(space);
  };

  if (loading) {
    return (
      <div className="p-4">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="text-red-800 dark:text-red-200">Error: {error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-2 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (spaces.length === 0) {
    return (
      <div className="p-4">
        <h2 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">Spaces</h2>
        <div className="text-center py-12">
          <p className="text-gray-500 dark:text-gray-400 mb-4">No spaces found</p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-gradient-primary text-white rounded-lg hover:shadow-lg transition-all font-medium"
          >
            Create Space
          </button>
        </div>
      </div>
    );
  }

  const handleSpaceCreated = (space: Space) => {
    setSpaces([...spaces, space]);
    setCurrentSpace(space);
  };

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Spaces</h2>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-gradient-primary text-white rounded-lg hover:shadow-lg transition-all font-medium"
        >
          + Create Space
        </button>
      </div>
      
      <CreateSpaceModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={handleSpaceCreated}
      />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {spaces.map((space) => (
          <div
            key={space.space_id}
            className={`border rounded-lg p-4 cursor-pointer transition-all hover:shadow-lg ${
              currentSpace?.space_id === space.space_id
                ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 shadow-md'
                : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:border-gray-300 dark:hover:border-gray-600'
            }`}
            onClick={() => handleSelectSpace(space)}
          >
            <h3 className="font-bold text-lg text-gray-900 dark:text-white">{space.name}</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">{space.space_id}</p>
            <div className="mt-2 text-sm space-y-1">
              <div className="text-gray-700 dark:text-gray-300">
                Status: <span className="font-medium">{space.status}</span>
              </div>
              <div className="text-gray-700 dark:text-gray-300">
                Budget: <span className="font-medium">{space.monthly_token_budget.toLocaleString()} tokens</span>
              </div>
              <div className="text-gray-700 dark:text-gray-300">
                Model: <span className="font-medium">{space.preferred_model}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
