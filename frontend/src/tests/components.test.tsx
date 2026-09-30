import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { SuggestionResult } from '../components/SuggestionResult';
import { AlertWorkbench, SAMPLE_ALERTS } from '../components/AlertWorkbench';
import { OutcomePanel } from '../components/OutcomePanel';
import type { AnalysisOutput } from '../types/api';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    recordOutcome: vi.fn().mockResolvedValue({
      status: 'recorded',
      analysis_id: 'test-123',
      result: 'fixed',
      retained_doc_id: 'doc-1',
      idempotent_duplicate: false,
    }),
  },
}));

describe('SuggestionResult Component', () => {
  const baseOutput: AnalysisOutput = {
    likely_root_cause: {
      text: 'Database pool size limit reached during flash sale.',
      confidence: 0.88,
      sources: ['INC-101'],
    },
    fix_steps: [
      {
        rank: 1,
        step: 'Increase pool size to 300',
        rationale: 'Worked in INC-101',
        source_incident_ids: ['INC-101'],
        source_memory_ids: ['mem-101'],
        prior_outcome: 'worked',
      },
      {
        rank: 2,
        step: 'Restart pods without pool increase',
        rationale: 'Tried first in INC-101 but failed',
        source_incident_ids: ['INC-101'],
        source_memory_ids: ['mem-101'],
        prior_outcome: 'failed',
      },
    ],
    runbooks: ['runbook-db.md'],
    memory_used: [],
    memory_status: 'ok',
    warnings: [],
    model_used: 'openai/gpt-oss-120b',
  };

  it('renders root cause and ranked fix steps correctly', () => {
    render(<SuggestionResult output={baseOutput} onOpenSource={vi.fn()} />);

    expect(screen.getByText(/Database pool size limit reached/i)).toBeInTheDocument();
    expect(screen.getByText('Increase pool size to 300')).toBeInTheDocument();
    expect(screen.getByText('Restart pods without pool increase')).toBeInTheDocument();
    expect(screen.getByText('88%')).toBeInTheDocument();
  });

  it('renders distinct copy for memory_status variants', () => {
    // 1. Memory OFF
    const { rerender } = render(
      <SuggestionResult output={{ ...baseOutput, memory_status: 'off' }} onOpenSource={vi.fn()} />
    );
    expect(screen.getByText(/Memory is OFF/i)).toBeInTheDocument();

    // 2. No Match
    rerender(
      <SuggestionResult output={{ ...baseOutput, memory_status: 'no_match' }} onOpenSource={vi.fn()} />
    );
    expect(screen.getByText(/No matching historical incidents found/i)).toBeInTheDocument();

    // 3. Unavailable
    rerender(
      <SuggestionResult output={{ ...baseOutput, memory_status: 'unavailable' }} onOpenSource={vi.fn()} />
    );
    expect(screen.getByText(/Memory service unavailable/i)).toBeInTheDocument();
  });

  it('styles failed-fix step distinctly with Failed Previously badge', () => {
    render(<SuggestionResult output={baseOutput} onOpenSource={vi.fn()} />);

    expect(screen.getByText('Failed Previously')).toBeInTheDocument();
    expect(screen.getByText('Worked Before')).toBeInTheDocument();
  });
});

describe('AlertWorkbench Compare View', () => {
  it('renders side-by-side compare options and updates alert text from sample chips', () => {
    const setAlertText = vi.fn();
    const setCompareMode = vi.fn();

    render(
      <AlertWorkbench
        alertText=""
        setAlertText={setAlertText}
        memoryEnabled={true}
        setMemoryEnabled={vi.fn()}
        compareMode={false}
        setCompareMode={setCompareMode}
        onAnalyze={vi.fn()}
        loading={false}
      />
    );

    expect(screen.getByText('Compare Side-by-Side')).toBeInTheDocument();

    // Click sample chip
    const firstChip = screen.getByText(SAMPLE_ALERTS[0].title);
    fireEvent.click(firstChip);
    expect(setAlertText).toHaveBeenCalledWith(SAMPLE_ALERTS[0].text);
  });
});

describe('OutcomePanel Component', () => {
  it('disables outcome buttons after submission and shows confirmation', async () => {
    render(<OutcomePanel analysisId="analysis-test-1" />);

    const fixedButton = screen.getByText('Fixed Issue');
    expect(fixedButton).toBeEnabled();

    fireEvent.click(fixedButton);

    await waitFor(() => {
      expect(screen.getByText(/Outcome Recorded: FIXED/i)).toBeInTheDocument();
    });

    expect(api.recordOutcome).toHaveBeenCalledWith({
      analysis_id: 'analysis-test-1',
      result: 'fixed',
      notes: '',
    });
  });
});
