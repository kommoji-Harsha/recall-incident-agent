import { useState } from 'react';
import {
  AlertCircle,
  BarChart3,
  BookOpen,
  Brain,
  RefreshCw,
} from 'lucide-react';
import { Header } from './components/Header';
import { AlertWorkbench } from './components/AlertWorkbench';
import { SuggestionResult } from './components/SuggestionResult';
import { SourceDrawer } from './components/SourceDrawer';
import { MemoryPanel } from './components/MemoryPanel';
import { OutcomePanel } from './components/OutcomePanel';
import { PostmortemDialog } from './components/PostmortemDialog';
import { LearningCurvePage } from './components/LearningCurvePage';
import { api } from './api/client';
import type {
  AnalyzeResponse,
  RecalledMemoryItem,
} from './types/api';

export function App() {
  const [activeView, setActiveTab] = useState<'workbench' | 'learning_curve'>('workbench');

  // Workbench state
  const [alertText, setAlertText] = useState<string>('');
  const [memoryEnabled, setMemoryEnabled] = useState<boolean>(true);
  const [compareMode, setCompareMode] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [analysisResult, setAnalysisResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Drawer & Dialog State
  const [selectedMemory, setSelectedMemory] = useState<RecalledMemoryItem | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
  const [isPostmortemOpen, setIsPostmortemOpen] = useState<boolean>(false);

  const handleAnalyze = async () => {
    if (!alertText.trim() || loading) return;
    setLoading(true);
    setError(null);

    try {
      const res = await api.analyze({
        alert_text: alertText.trim(),
        memory_enabled: memoryEnabled,
        compare: compareMode,
      });
      setAnalysisResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenSourceById = (sourceId: string) => {
    if (!analysisResult) return;
    // Find matching memory item in memory_used list
    const found = analysisResult.memory_on.memory_used.find(
      (m) => m.id === sourceId || m.source_incident_id === sourceId || m.document_id === sourceId
    );
    if (found) {
      setSelectedMemory(found);
    } else {
      // Create synthetic preview if ID cited from memory
      setSelectedMemory({
        id: sourceId,
        text: `Recalled Memory record for citation ${sourceId}.`,
        type: sourceId.startsWith('INC-') ? 'incident' : 'experience',
        source_incident_id: sourceId.startsWith('INC-') ? sourceId : null,
      });
    }
    setIsDrawerOpen(true);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* Global Header */}
      <Header />

      {/* Primary Sub-Header / Navigation */}
      <div className="border-b border-slate-800 bg-slate-900/50">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-between">
          <nav className="flex space-x-1">
            <button
              type="button"
              onClick={() => setActiveTab('workbench')}
              className={`flex items-center space-x-2 px-4 py-3 text-xs font-mono font-medium border-b-2 transition-all ${
                activeView === 'workbench'
                  ? 'border-cyan-400 text-cyan-300 bg-slate-900'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/50'
              }`}
            >
              <Brain className="w-4 h-4" />
              <span>Incident Workbench</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('learning_curve')}
              className={`flex items-center space-x-2 px-4 py-3 text-xs font-mono font-medium border-b-2 transition-all ${
                activeView === 'learning_curve'
                  ? 'border-purple-400 text-purple-300 bg-slate-900'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/50'
              }`}
            >
              <BarChart3 className="w-4 h-4" />
              <span>Learning Curve</span>
            </button>
          </nav>

          {/* Action Button: Ingest Post-Mortem */}
          <button
            type="button"
            onClick={() => setIsPostmortemOpen(true)}
            className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-mono text-xs transition-colors"
          >
            <BookOpen className="w-3.5 h-3.5 text-cyan-400" />
            <span>Ingest Post-Mortem</span>
          </button>
        </div>
      </div>

      {/* Main Body */}
      <main className="max-w-7xl mx-auto px-4 py-6 flex-1 w-full space-y-6">
        {activeView === 'learning_curve' ? (
          <LearningCurvePage />
        ) : (
          <>
            {/* Alert Input Workbench */}
            <AlertWorkbench
              alertText={alertText}
              setAlertText={setAlertText}
              memoryEnabled={memoryEnabled}
              setMemoryEnabled={setMemoryEnabled}
              compareMode={compareMode}
              setCompareMode={setCompareMode}
              onAnalyze={handleAnalyze}
              loading={loading}
            />

            {/* Error Banner */}
            {error && (
              <div className="p-4 bg-rose-950/60 border border-rose-800 rounded-xl text-xs font-mono text-rose-200 flex items-start justify-between gap-3 shadow-lg">
                <div className="flex items-start space-x-2">
                  <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold block text-rose-300">Analysis Failed</span>
                    <span>{error}</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleAnalyze}
                  className="px-3 py-1 bg-rose-900 hover:bg-rose-800 text-rose-100 rounded text-xs font-mono shrink-0 flex items-center space-x-1"
                >
                  <RefreshCw className="w-3 h-3 mr-1" />
                  Retry
                </button>
              </div>
            )}

            {/* Analysis Output Section */}
            {analysisResult && (
              <div className="space-y-6">
                {analysisResult.memory_off ? (
                  /* Side-by-Side Compare Layout */
                  <div className="space-y-3">
                    <div className="flex items-center space-x-2 text-xs font-mono text-slate-400 font-semibold uppercase tracking-wider">
                      <span>Side-by-Side Memory Comparison</span>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
                      <SuggestionResult
                        output={analysisResult.memory_on}
                        title="Memory ON (Hindsight Long-Term Memory)"
                        onOpenSource={handleOpenSourceById}
                      />
                      <SuggestionResult
                        output={analysisResult.memory_off}
                        title="Memory OFF (Baseline Generic Output)"
                        onOpenSource={handleOpenSourceById}
                      />
                    </div>
                  </div>
                ) : (
                  /* Single Column View */
                  <SuggestionResult
                    output={analysisResult.memory_on}
                    title="Incident Analysis & Ranked Suggestions"
                    onOpenSource={handleOpenSourceById}
                  />
                )}

                {/* Outcome Panel */}
                <OutcomePanel analysisId={analysisResult.analysis_id} />

                {/* Recalled Memory Panel */}
                <MemoryPanel
                  memories={analysisResult.memory_on.memory_used}
                  onOpenSource={(mem) => {
                    setSelectedMemory(mem);
                    setIsDrawerOpen(true);
                  }}
                />
              </div>
            )}
          </>
        )}
      </main>

      {/* Slide-over Source Drawer */}
      <SourceDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        memoryItem={selectedMemory}
      />

      {/* Post-Mortem Modal */}
      <PostmortemDialog
        isOpen={isPostmortemOpen}
        onClose={() => setIsPostmortemOpen(false)}
      />
    </div>
  );
}

export default App;
