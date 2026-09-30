import React, { useState } from 'react';
import {
  CheckCircle2,
  Send,
  ThumbsDown,
  ThumbsUp,
  XCircle,
} from 'lucide-react';
import { api } from '../api/client';
import type { OutcomeResult } from '../types/api';

interface OutcomePanelProps {
  analysisId: string;
}

export const OutcomePanel: React.FC<OutcomePanelProps> = ({ analysisId }) => {
  const [notes, setNotes] = useState<string>('');
  const [submitted, setSubmitted] = useState<boolean>(false);
  const [submittedResult, setSubmittedResult] = useState<OutcomeResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (result: OutcomeResult) => {
    if (loading || submitted) return;
    setLoading(true);
    setError(null);

    try {
      await api.recordOutcome({
        analysis_id: analysisId,
        result,
        notes,
      });
      setSubmitted(true);
      setSubmittedResult(result);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <h4 className="text-xs font-mono uppercase tracking-wider font-semibold text-slate-200 flex items-center space-x-2">
          <Send className="w-3.5 h-3.5 text-cyan-400 mr-1.5" />
          <span>Outcome Feedback</span>
        </h4>
        <span className="text-[11px] font-mono text-slate-500">
          Analysis ID: {analysisId}
        </span>
      </div>

      {submitted ? (
        <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
          <div className="flex items-center space-x-2 text-xs font-mono font-semibold">
            {submittedResult === 'fixed' ? (
              <span className="text-emerald-400 flex items-center">
                <CheckCircle2 className="w-4 h-4 mr-1.5 text-emerald-400" />
                Outcome Recorded: FIXED
              </span>
            ) : (
              <span className="text-rose-400 flex items-center">
                <XCircle className="w-4 h-4 mr-1.5 text-rose-400" />
                Outcome Recorded: DID NOT WORK
              </span>
            )}
          </div>
          <p className="text-xs font-sans text-slate-300">
            Retained in Hindsight memory. Successful fixes are retained for future recall, and failed attempts are demoted.
          </p>
          {notes && (
            <p className="text-xs font-mono text-slate-400 bg-slate-900 p-2 rounded border border-slate-800 mt-2">
              Note: {notes}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-slate-400">
            Did this suggestion resolve the incident? Mark the outcome to improve future agent recall.
          </p>

          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add optional notes (e.g. 'Increased pool to 300, load normalized within 2 mins')..."
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500 transition-all"
          />

          {error && (
            <div className="p-2.5 bg-rose-950/50 border border-rose-800 rounded text-xs font-mono text-rose-300">
              {error}
            </div>
          )}

          <div className="flex items-center space-x-3 pt-1">
            <button
              type="button"
              onClick={() => handleSubmit('fixed')}
              disabled={loading}
              className="flex-1 flex items-center justify-center space-x-2 px-4 py-2 rounded-lg bg-emerald-950 hover:bg-emerald-900 text-emerald-300 border border-emerald-800 font-mono text-xs font-medium transition-colors disabled:opacity-50"
            >
              <ThumbsUp className="w-3.5 h-3.5" />
              <span>Fixed Issue</span>
            </button>

            <button
              type="button"
              onClick={() => handleSubmit('didnt_work')}
              disabled={loading}
              className="flex-1 flex items-center justify-center space-x-2 px-4 py-2 rounded-lg bg-rose-950 hover:bg-rose-900 text-rose-300 border border-rose-800 font-mono text-xs font-medium transition-colors disabled:opacity-50"
            >
              <ThumbsDown className="w-3.5 h-3.5" />
              <span>Didn't Work</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
