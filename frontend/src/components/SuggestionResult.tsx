import React from 'react';
import {
  AlertTriangle,
  ArrowDownRight,
  BookOpen,
  CheckCircle2,
  Cpu,
  FileText,
  Info,
  ShieldAlert,
  XCircle,
} from 'lucide-react';
import type { AnalysisOutput, MemoryStatus, PriorOutcome } from '../types/api';

interface SuggestionResultProps {
  output: AnalysisOutput;
  title?: string;
  onOpenSource: (sourceId: string) => void;
  onOpenIncident?: (incidentId: string) => void;
}

export const SuggestionResult: React.FC<SuggestionResultProps> = ({
  output,
  title = 'Analysis Result',
  onOpenSource,
}) => {
  const { likely_root_cause, fix_steps, runbooks, memory_status, warnings, model_used } = output;

  // Render memory_status banner with distinct copy
  const renderMemoryBanner = (status: MemoryStatus) => {
    switch (status) {
      case 'off':
        return (
          <div className="flex items-center space-x-2 p-3 bg-slate-800/80 border border-slate-700/80 rounded-lg text-xs text-slate-300 font-mono">
            <Info className="w-4 h-4 text-slate-400 shrink-0" />
            <span>Memory is OFF — suggestion generated without historical incident context.</span>
          </div>
        );
      case 'no_match':
        return (
          <div className="flex items-center space-x-2 p-3 bg-amber-950/40 border border-amber-800/50 rounded-lg text-xs text-amber-200 font-mono">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>No matching historical incidents found in memory. Output contains generic guidance.</span>
          </div>
        );
      case 'unavailable':
        return (
          <div className="flex items-center space-x-2 p-3 bg-rose-950/40 border border-rose-800/50 rounded-lg text-xs text-rose-200 font-mono">
            <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
            <span>Memory service unavailable — fallback answer generated without memory history.</span>
          </div>
        );
      case 'ok':
      default:
        return null;
    }
  };

  const renderPriorOutcomeBadge = (outcome: PriorOutcome) => {
    switch (outcome) {
      case 'worked':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-emerald-950 text-emerald-300 border border-emerald-800/60">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            <span>Worked Before</span>
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-rose-950 text-rose-300 border border-rose-800/80 animate-pulse">
            <XCircle className="w-3 h-3 text-rose-400" />
            <span>Failed Previously</span>
            <ArrowDownRight className="w-3 h-3 text-amber-400" />
          </span>
        );
      case 'unknown':
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-slate-400 border border-slate-700/60">
            Outcome Unknown
          </span>
        );
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-5 shadow-xl">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
        <h3 className="text-sm font-semibold text-slate-100 flex items-center space-x-2">
          <span>{title}</span>
        </h3>

        {/* Model Status Pill */}
        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="text-slate-400">Model:</span>
          <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-cyan-400 flex items-center space-x-1">
            <Cpu className="w-3 h-3 text-cyan-400 mr-1" />
            {model_used}
          </span>
        </div>
      </div>

      {/* Memory Status Banner */}
      {renderMemoryBanner(memory_status)}

      {/* Root Cause Card */}
      <div className="bg-slate-950/80 border border-slate-800 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono uppercase tracking-wider font-semibold text-cyan-400">
            Likely Root Cause
          </span>
          <div className="flex items-center space-x-2">
            <span className="text-xs font-mono text-slate-400">Confidence:</span>
            <div className="w-20 bg-slate-800 h-2 rounded-full overflow-hidden">
              <div
                className="bg-cyan-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.round(likely_root_cause.confidence * 100)}%` }}
              />
            </div>
            <span className="text-xs font-mono font-medium text-cyan-300">
              {Math.round(likely_root_cause.confidence * 100)}%
            </span>
          </div>
        </div>

        <p className="text-sm text-slate-200 leading-relaxed font-sans">
          {likely_root_cause.text}
        </p>

        {likely_root_cause.sources.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="text-xs font-mono text-slate-400">Cited Sources:</span>
            {likely_root_cause.sources.map((srcId) => (
              <button
                key={srcId}
                type="button"
                onClick={() => onOpenSource(srcId)}
                className="px-2 py-0.5 rounded bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-800 text-cyan-300 font-mono text-xs transition-colors"
              >
                {srcId}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Ranked Fix Steps */}
      <div className="space-y-3">
        <h4 className="text-xs font-mono uppercase tracking-wider font-semibold text-slate-300">
          Ranked Resolution Steps
        </h4>

        {fix_steps.length === 0 ? (
          <p className="text-xs text-slate-500 italic">No specific fix steps recommended.</p>
        ) : (
          <div className="space-y-2.5">
            {fix_steps.map((step) => {
              const isFailed = step.prior_outcome === 'failed';
              return (
                <div
                  key={step.rank}
                  className={`p-3.5 rounded-lg border transition-all ${
                    isFailed
                      ? 'bg-amber-950/20 border-amber-800/50 hover:border-amber-700/80'
                      : 'bg-slate-950/60 border-slate-800/80 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start space-x-3">
                      <span
                        className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-mono font-bold shrink-0 mt-0.5 ${
                          isFailed
                            ? 'bg-amber-950 text-amber-300 border border-amber-800'
                            : 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                        }`}
                      >
                        {step.rank}
                      </span>
                      <div>
                        <p
                          className={`text-sm font-medium ${
                            isFailed ? 'text-amber-200 line-through decoration-amber-500/60' : 'text-slate-100'
                          }`}
                        >
                          {step.step}
                        </p>
                        <p className="text-xs text-slate-400 mt-1 leading-relaxed">
                          {step.rationale}
                        </p>
                      </div>
                    </div>

                    <div className="shrink-0">
                      {renderPriorOutcomeBadge(step.prior_outcome)}
                    </div>
                  </div>

                  {/* Sources Chips */}
                  {(step.source_incident_ids.length > 0 || step.source_memory_ids.length > 0) && (
                    <div className="flex flex-wrap items-center gap-1.5 mt-2.5 pt-2 border-t border-slate-800/60 text-xs">
                      <span className="font-mono text-slate-500 text-[11px]">From:</span>
                      {step.source_incident_ids.map((incId) => (
                        <button
                          key={incId}
                          type="button"
                          onClick={() => onOpenSource(incId)}
                          className="px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-cyan-300 font-mono text-[11px] transition-colors"
                        >
                          {incId}
                        </button>
                      ))}
                      {step.source_memory_ids.map((memId) => (
                        <button
                          key={memId}
                          type="button"
                          onClick={() => onOpenSource(memId)}
                          className="px-2 py-0.5 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 font-mono text-[11px] transition-colors"
                        >
                          {memId}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Runbooks Section */}
      {runbooks.length > 0 && (
        <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg space-y-2">
          <div className="flex items-center space-x-2 text-xs font-mono font-semibold text-slate-300">
            <BookOpen className="w-3.5 h-3.5 text-cyan-400" />
            <span>Suggested Runbooks</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {runbooks.map((rb) => (
              <span
                key={rb}
                className="inline-flex items-center space-x-1 px-2.5 py-1 rounded bg-slate-900 border border-slate-700 text-xs font-mono text-slate-300"
              >
                <FileText className="w-3 h-3 text-slate-400 mr-1" />
                {rb}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Warnings List */}
      {warnings.length > 0 && (
        <div className="p-3 bg-slate-950/40 border border-slate-800 rounded-lg space-y-1 text-xs font-mono text-slate-400">
          <div className="flex items-center space-x-1.5 font-semibold text-amber-400 mb-1">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>System Warnings</span>
          </div>
          {warnings.map((w, idx) => (
            <p key={idx} className="text-[11px]">
              • {w}
            </p>
          ))}
        </div>
      )}
    </div>
  );
};
