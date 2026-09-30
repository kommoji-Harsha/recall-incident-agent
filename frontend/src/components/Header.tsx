import React, { useEffect, useState } from 'react';
import { Brain, Cpu, RefreshCw, Server } from 'lucide-react';
import { api } from '../api/client';
import type { HealthStatus } from '../types/api';

export const Header: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchHealth = async () => {
    try {
      const data = await api.getHealth();
      setHealth(data);
    } catch {
      setHealth({
        status: 'degraded',
        hindsight_reachable: false,
        groq_configured: false,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-30 px-4 py-3">
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-cyan-950/60 border border-cyan-800/50 rounded-lg text-cyan-400">
            <Brain className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-slate-100 tracking-tight text-lg">Recall</span>
              <span className="text-xs px-2 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-400 font-mono">
                Agent Memory
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Incident response agent powered by Vectorize Hindsight
            </p>
          </div>
        </div>

        {/* Status Pills */}
        <div className="flex items-center space-x-3 text-xs font-mono">
          {/* Hindsight Status */}
          <div className="flex items-center space-x-2 px-3 py-1.5 rounded-md bg-slate-950 border border-slate-800">
            <Server className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">Hindsight:</span>
            {loading ? (
              <span className="text-slate-500 animate-pulse">Checking...</span>
            ) : health?.hindsight_reachable ? (
              <span className="flex items-center text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse" />
                Connected
              </span>
            ) : (
              <span className="flex items-center text-amber-400" title={health?.bootstrap_error || 'Offline/Unreachable'}>
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mr-1.5" />
                {health?.status === 'ok' ? 'FakeMemory Mode' : 'Degraded'}
              </span>
            )}
          </div>

          {/* Model Status */}
          <div className="flex items-center space-x-2 px-3 py-1.5 rounded-md bg-slate-950 border border-slate-800">
            <Cpu className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">Model:</span>
            <span className="text-cyan-400">
              {health?.primary_model || 'openai/gpt-oss-120b'}
            </span>
          </div>

          {/* Manual Refresh */}
          <button
            onClick={fetchHealth}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-md transition-colors"
            title="Refresh System Health"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>
    </header>
  );
};
