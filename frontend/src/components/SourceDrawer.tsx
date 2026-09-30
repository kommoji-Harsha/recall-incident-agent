import React from 'react';
import {
  Calendar,
  Database,
  FileCode,
  Tag,
  X,
} from 'lucide-react';
import type { RecalledMemoryItem } from '../types/api';

interface SourceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  memoryItem: RecalledMemoryItem | null;
}

export const SourceDrawer: React.FC<SourceDrawerProps> = ({
  isOpen,
  onClose,
  memoryItem,
}) => {
  if (!isOpen || !memoryItem) return null;

  const renderScoreValue = (val?: number | null) => {
    if (val === undefined || val === null) {
      return <span className="text-slate-600 font-mono">—</span>;
    }
    return <span className="font-mono text-cyan-400 font-semibold">{val.toFixed(3)}</span>;
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/60 backdrop-blur-xs flex justify-end">
      {/* Backdrop overlay */}
      <div
        className="absolute inset-0 transition-opacity cursor-pointer"
        onClick={onClose}
      />

      {/* Slide-over panel */}
      <div className="relative w-full max-w-xl bg-slate-900 border-l border-slate-800 shadow-2xl h-full overflow-y-auto flex flex-col z-10">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950 sticky top-0 z-10">
          <div className="flex items-center space-x-2">
            <span className="px-2 py-0.5 rounded text-xs font-mono font-medium bg-cyan-950 text-cyan-300 border border-cyan-800">
              {memoryItem.type || 'memory'}
            </span>
            <span className="text-xs font-mono text-slate-300 font-semibold">
              {memoryItem.id}
            </span>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-5 flex-1">
          {/* Metadata Overview Grid */}
          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="p-2.5 bg-slate-950 border border-slate-800/80 rounded-lg">
              <span className="text-slate-500 block mb-1 flex items-center">
                <FileCode className="w-3.5 h-3.5 mr-1" />
                Document ID:
              </span>
              <span className="text-slate-200 font-medium break-all">
                {memoryItem.document_id || '—'}
              </span>
            </div>

            <div className="p-2.5 bg-slate-950 border border-slate-800/80 rounded-lg">
              <span className="text-slate-500 block mb-1 flex items-center">
                <Database className="w-3.5 h-3.5 mr-1" />
                Source Incident ID:
              </span>
              <span className="text-cyan-300 font-medium">
                {memoryItem.source_incident_id || '—'}
              </span>
            </div>
          </div>

          {/* Scores Breakdown Panel */}
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
            <span className="text-xs font-mono text-slate-400 font-semibold uppercase tracking-wider block">
              Per-Arm Memory Scores
            </span>
            <div className="grid grid-cols-4 gap-2 text-center text-xs">
              <div className="p-2 bg-slate-900 border border-slate-800 rounded">
                <span className="text-[10px] font-mono text-slate-500 block">Final</span>
                {renderScoreValue(memoryItem.scores?.final)}
              </div>
              <div className="p-2 bg-slate-900 border border-slate-800 rounded">
                <span className="text-[10px] font-mono text-slate-500 block">Reranker</span>
                {renderScoreValue(memoryItem.scores?.reranker)}
              </div>
              <div className="p-2 bg-slate-900 border border-slate-800 rounded">
                <span className="text-[10px] font-mono text-slate-500 block">Semantic</span>
                {renderScoreValue(memoryItem.scores?.semantic)}
              </div>
              <div className="p-2 bg-slate-900 border border-slate-800 rounded">
                <span className="text-[10px] font-mono text-slate-500 block">Keyword</span>
                {renderScoreValue(memoryItem.scores?.keyword)}
              </div>
            </div>
          </div>

          {/* Recalled Memory Text */}
          <div className="space-y-2">
            <span className="text-xs font-mono text-slate-400 font-semibold uppercase tracking-wider block">
              Recalled Memory Content
            </span>
            <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-lg font-mono text-xs text-slate-200 leading-relaxed whitespace-pre-wrap max-h-80 overflow-y-auto">
              {memoryItem.text}
            </div>
          </div>

          {/* Context */}
          {memoryItem.context && (
            <div className="space-y-1 text-xs">
              <span className="font-mono text-slate-500 block">Context:</span>
              <p className="p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-300 font-mono">
                {memoryItem.context}
              </p>
            </div>
          )}

          {/* Entities & Tags */}
          <div className="space-y-3">
            {memoryItem.entities && memoryItem.entities.length > 0 && (
              <div className="space-y-1">
                <span className="text-xs font-mono text-slate-500 block">Entities Extracted:</span>
                <div className="flex flex-wrap gap-1.5">
                  {memoryItem.entities.map((entity, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300"
                    >
                      {entity}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {memoryItem.tags && memoryItem.tags.length > 0 && (
              <div className="space-y-1">
                <span className="text-xs font-mono text-slate-500 block flex items-center">
                  <Tag className="w-3 h-3 mr-1" />
                  Tags:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {memoryItem.tags.map((tag, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-xs font-mono text-cyan-300"
                    >
                      #{tag}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {memoryItem.occurred_start && (
              <div className="text-xs font-mono text-slate-500 flex items-center pt-2">
                <Calendar className="w-3.5 h-3.5 mr-1.5" />
                Occurred: {memoryItem.occurred_start}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
