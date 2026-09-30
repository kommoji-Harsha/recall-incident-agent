import React, { useState } from 'react';
import {
  BookOpen,
  CheckCircle2,
  FileText,
  X,
} from 'lucide-react';
import { api } from '../api/client';
import type { PostmortemResponse } from '../types/api';

interface PostmortemDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export const PostmortemDialog: React.FC<PostmortemDialogProps> = ({
  isOpen,
  onClose,
}) => {
  const [title, setTitle] = useState<string>('');
  const [text, setText] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<PostmortemResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || loading) return;

    setLoading(true);
    setError(null);

    try {
      const res = await api.submitPostmortem({
        title: title.trim() || null,
        text: text.trim(),
      });
      setResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setTitle('');
    setText('');
    setResult(null);
    setError(null);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/75 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 bg-slate-950 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="p-1.5 bg-cyan-950 border border-cyan-800 rounded text-cyan-400">
              <BookOpen className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-100">Ingest Incident Post-Mortem</h3>
              <p className="text-[11px] text-slate-400">
                Retain post-mortem findings into Hindsight Cloud memory bank
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {result ? (
            <div className="space-y-4">
              <div className="p-4 bg-emerald-950/40 border border-emerald-800/60 rounded-lg space-y-2">
                <div className="flex items-center space-x-2 text-xs font-mono font-semibold text-emerald-400">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Post-Mortem Ingested Successfully</span>
                </div>
                <p className="text-xs font-mono text-slate-300">
                  Post-Mortem ID: <span className="text-cyan-300">{result.postmortem_id}</span>
                </p>
              </div>

              {/* Follow-up Recall Sample */}
              <div className="space-y-2">
                <span className="text-xs font-mono text-slate-400 font-semibold uppercase tracking-wider block">
                  Follow-up Extraction Verification
                </span>
                <p className="text-xs text-slate-400">
                  Hindsight recalled the following facts from memory immediately after retention:
                </p>

                {result.recalled_sample.length === 0 ? (
                  <p className="text-xs italic text-slate-500 font-mono">No immediate match returned.</p>
                ) : (
                  <div className="space-y-2">
                    {result.recalled_sample.map((s) => (
                      <div
                        key={s.id}
                        className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-1 font-mono text-xs"
                      >
                        <div className="flex items-center justify-between text-slate-500 text-[11px]">
                          <span>{s.document_id || s.id}</span>
                          <span className="text-cyan-400">{s.type}</span>
                        </div>
                        <p className="text-slate-200">{s.text}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={handleReset}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-mono transition-colors"
                >
                  Ingest Another
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-mono font-medium transition-colors"
                >
                  Done
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">
                  Post-Mortem Title (optional)
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Post-Mortem: INC-101 Checkout Connection Pool Exhaustion"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500 transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-slate-400 mb-1">
                  Post-Mortem Content (Markdown / Text) *
                </label>
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste Markdown post-mortem document text including Root Cause, What Worked, and What Didn't Work..."
                  rows={10}
                  required
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500 transition-all resize-y"
                />
              </div>

              {error && (
                <div className="p-3 bg-rose-950/50 border border-rose-800 rounded-lg text-xs font-mono text-rose-300">
                  {error}
                </div>
              )}

              <div className="flex items-center justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-mono transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!text.trim() || loading}
                  className="flex items-center space-x-2 px-5 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-xs font-mono font-medium transition-all disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-1" />
                      <span>Retaining...</span>
                    </>
                  ) : (
                    <>
                      <FileText className="w-3.5 h-3.5 mr-1" />
                      <span>Ingest Post-Mortem</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
