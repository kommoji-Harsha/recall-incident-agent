import React, { useEffect, useState } from 'react';
import {
  Brain,
  Eye,
  Layers,
  RefreshCw,
} from 'lucide-react';
import { api } from '../api/client';
import type { Observation, RecalledMemoryItem } from '../types/api';

interface MemoryPanelProps {
  memories: RecalledMemoryItem[];
  onOpenSource: (memoryItem: RecalledMemoryItem) => void;
}

export const MemoryPanel: React.FC<MemoryPanelProps> = ({
  memories,
  onOpenSource,
}) => {
  const [activeTab, setActiveTab] = useState<'recalled' | 'observations'>('recalled');
  const [observations, setObservations] = useState<Observation[]>([]);
  const [loadingObs, setLoadingObs] = useState<boolean>(false);
  const [obsError, setObsError] = useState<string | null>(null);

  const fetchObservations = async () => {
    setLoadingObs(true);
    setObsError(null);
    try {
      const res = await api.getObservations(50);
      setObservations(res.observations);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setObsError(msg);
    } finally {
      setLoadingObs(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'observations' && observations.length === 0) {
      fetchObservations();
    }
  }, [activeTab]);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
      {/* Tab Navigation Bar */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={() => setActiveTab('recalled')}
            className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
              activeTab === 'recalled'
                ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <Brain className="w-3.5 h-3.5" />
            <span>Recalled Memories ({memories.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('observations')}
            className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
              activeTab === 'observations'
                ? 'bg-purple-950 text-purple-300 border border-purple-800'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            <Eye className="w-3.5 h-3.5" />
            <span>Consolidated Observations</span>
          </button>
        </div>

        {activeTab === 'observations' && (
          <button
            type="button"
            onClick={fetchObservations}
            disabled={loadingObs}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded transition-colors"
            title="Refresh Observations"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingObs ? 'animate-spin' : ''}`} />
          </button>
        )}
      </div>

      {/* Recalled Memories Tab Content */}
      {activeTab === 'recalled' && (
        <div className="space-y-3">
          {memories.length === 0 ? (
            <div className="p-8 text-center border border-dashed border-slate-800 rounded-lg">
              <Layers className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <p className="text-xs font-mono text-slate-400">
                No memories recalled for this query. Run an alert analysis with Memory ON.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {memories.map((m) => (
                <div
                  key={m.id}
                  onClick={() => onOpenSource(m)}
                  className="p-3.5 bg-slate-950 border border-slate-800/80 hover:border-cyan-800/80 rounded-lg cursor-pointer transition-all space-y-2 group"
                >
                  <div className="flex items-center justify-between text-xs font-mono">
                    <div className="flex items-center space-x-2">
                      <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-[11px] text-cyan-400 font-medium">
                        {m.type}
                      </span>
                      {m.source_incident_id && (
                        <span className="text-cyan-300 font-semibold group-hover:underline">
                          {m.source_incident_id}
                        </span>
                      )}
                    </div>
                    <span className="text-slate-500 text-[11px]">
                      Score: {m.scores?.final !== undefined && m.scores?.final !== null ? m.scores.final.toFixed(3) : '—'}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 font-mono line-clamp-3 leading-relaxed">
                    {m.text}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Consolidated Observations Tab Content */}
      {activeTab === 'observations' && (
        <div className="space-y-3">
          {loadingObs ? (
            <div className="p-8 text-center text-xs font-mono text-slate-400 flex items-center justify-center space-x-2">
              <div className="w-4 h-4 border-2 border-purple-400/30 border-t-purple-400 rounded-full animate-spin" />
              <span>Fetching Hindsight consolidated observations...</span>
            </div>
          ) : obsError ? (
            <div className="p-4 bg-rose-950/40 border border-rose-800/60 rounded-lg text-xs font-mono text-rose-300">
              Failed to load observations: {obsError}
            </div>
          ) : observations.length === 0 ? (
            <div className="p-8 text-center border border-dashed border-slate-800 rounded-lg">
              <p className="text-xs font-mono text-slate-400">
                No observations consolidated yet in this memory bank.
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {observations.map((obs) => (
                <div
                  key={obs.id}
                  className="p-3.5 bg-slate-950 border border-slate-800 rounded-lg space-y-2"
                >
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-purple-400 font-semibold">{obs.id}</span>
                    {obs.tags && obs.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {obs.tags.map((t, idx) => (
                          <span
                            key={idx}
                            className="px-1.5 py-0.5 rounded bg-purple-950/80 border border-purple-800 text-[10px] text-purple-300"
                          >
                            #{t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <p className="text-xs font-sans text-slate-200 leading-relaxed">
                    {obs.text}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
