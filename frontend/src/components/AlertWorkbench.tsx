import React from 'react';
import { AlertTriangle, Brain, Columns, Sparkles } from 'lucide-react';

export interface SampleAlert {
  id: string;
  title: string;
  service: string;
  text: string;
}

export const SAMPLE_ALERTS: SampleAlert[] = [
  {
    id: 'db-pool',
    title: 'DB Pool Exhaustion',
    service: 'checkout-api',
    text: `[checkout-api] ERROR [203.0.113.12] psycopg2.OperationalError: FATAL: remaining connection slots are reserved for non-replication superuser connections
[checkout-api] ERROR [203.0.113.12] sqlalchemy.exc.TimeoutError: QueuePool limit of size 100 overflow 20 reached, connection timed out, timeout 10.00
[checkout-api] CRITICAL [203.0.113.14] Healthcheck failed: Unable to acquire database connection from pool within 5000ms`,
  },
  {
    id: 'redis-eviction',
    title: 'Redis Eviction Storm',
    service: 'checkout-api',
    text: `[checkout-api] WARN [198.51.100.10] Redis maxmemory reached, volatile-lru eviction policy triggered
[checkout-api] ERROR [198.51.100.12] Redis evictions per second spiked from 50/s to 45,000/s
[checkout-api] ERROR [198.51.100.12] Cache miss rate increased to 92% on user session keys
[checkout-api] CRITICAL [198.51.100.15] Checkout session lookup failing, forcing fallback to primary database`,
  },
  {
    id: 'bad-deploy',
    title: 'Bad Deploy v3.1.0',
    service: 'checkout-api',
    text: `[checkout-api] INFO [192.0.2.10] Deploying release release-v3.1.0 to production
[checkout-api] ERROR [192.0.2.12] TypeError: Cannot read property 'id' of undefined in CheckoutController.ts:88
[checkout-api] ERROR [192.0.2.15] HTTP 500 status rate spiked to 88% on POST /api/v2/checkout/submit
[checkout-api] CRITICAL [192.0.2.15] Kubernetes readiness probe failed for 6/10 pods`,
  },
  {
    id: 'expired-cert',
    title: 'Expired TLS Cert',
    service: 'auth-gateway',
    text: `[auth-gateway] ERROR [203.0.113.60] SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate has expired (_ssl.c:1129)
[auth-gateway] ERROR [203.0.113.62] Handshake failure: Certificate expired at 2024-06-29 02:00:00 UTC
[auth-gateway] CRITICAL [203.0.113.65] Ingress controller cert-manager failed to auto-renew cert auth-tls-secret`,
  },
  {
    id: 'memory-leak',
    title: 'OOM Container Crash',
    service: 'checkout-api',
    text: `[checkout-api] WARN [198.51.100.110] Pod checkout-api-5c4d-99a memory usage: 1.95GB / 2.0GB (97%)
[checkout-api] ERROR [198.51.100.110] Kernel: Out of memory: Kill process 14201 (python) score 980 or sacrifice child
[checkout-api] CRITICAL [198.51.100.110] Container checkout-api terminated with exit code 137 (OOMKilled)`,
  },
];

interface AlertWorkbenchProps {
  alertText: string;
  setAlertText: (text: string) => void;
  memoryEnabled: boolean;
  setMemoryEnabled: (enabled: boolean) => void;
  compareMode: boolean;
  setCompareMode: (compare: boolean) => void;
  onAnalyze: () => void;
  loading: boolean;
}

export const AlertWorkbench: React.FC<AlertWorkbenchProps> = ({
  alertText,
  setAlertText,
  memoryEnabled,
  setMemoryEnabled,
  compareMode,
  setCompareMode,
  onAnalyze,
  loading,
}) => {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl space-y-4">
      {/* Top Header & Sample Alert Chips */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-2 text-sm font-semibold text-slate-200">
          <AlertTriangle className="w-4 h-4 text-cyan-400" />
          <span>Paste Alert or Error Log</span>
        </div>

        {/* Sample Chips */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-slate-400 font-mono text-[11px] mr-1">Load sample:</span>
          {SAMPLE_ALERTS.map((sample) => (
            <button
              key={sample.id}
              type="button"
              onClick={() => setAlertText(sample.text)}
              className="px-2.5 py-1 rounded-md bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-cyan-300 border border-slate-700/60 font-mono text-[11px] transition-colors"
            >
              {sample.title}
            </button>
          ))}
        </div>
      </div>

      {/* Textarea */}
      <div className="relative">
        <textarea
          value={alertText}
          onChange={(e) => setAlertText(e.target.value)}
          placeholder="Paste incident log, stack trace, or alert payload here..."
          rows={6}
          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3.5 font-mono text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 resize-y transition-all"
        />
        {alertText && (
          <div className="absolute bottom-3 right-3 text-[10px] font-mono text-slate-500">
            {alertText.length.toLocaleString()} chars
          </div>
        )}
      </div>

      {/* Control Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-1 border-t border-slate-800/80">
        {/* Mode Selector */}
        <div className="flex items-center space-x-1.5 p-1 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono">
          <button
            type="button"
            onClick={() => {
              setCompareMode(false);
              setMemoryEnabled(true);
            }}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-all ${
              !compareMode && memoryEnabled
                ? 'bg-cyan-950 text-cyan-300 border border-cyan-800 font-medium'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Brain className="w-3.5 h-3.5" />
            <span>Memory ON</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setCompareMode(false);
              setMemoryEnabled(false);
            }}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-all ${
              !compareMode && !memoryEnabled
                ? 'bg-slate-800 text-slate-200 border border-slate-700 font-medium'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <span>Memory OFF</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setCompareMode(true);
              setMemoryEnabled(true);
            }}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-all ${
              compareMode
                ? 'bg-purple-950/80 text-purple-300 border border-purple-800 font-medium'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Columns className="w-3.5 h-3.5" />
            <span>Compare Side-by-Side</span>
          </button>
        </div>

        {/* Action Button */}
        <button
          type="button"
          onClick={onAnalyze}
          disabled={!alertText.trim() || loading}
          className={`flex items-center space-x-2 px-5 py-2 rounded-lg font-medium text-xs transition-all shadow-lg ${
            !alertText.trim() || loading
              ? 'bg-slate-800 text-slate-500 border border-slate-700/50 cursor-not-allowed'
              : compareMode
              ? 'bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 text-white border border-purple-400/30'
              : 'bg-cyan-600 hover:bg-cyan-500 text-white border border-cyan-400/30'
          }`}
        >
          {loading ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin mr-1" />
              <span>Analyzing Incident...</span>
            </>
          ) : (
            <>
              <Sparkles className="w-3.5 h-3.5" />
              <span>{compareMode ? 'Analyze & Compare' : 'Analyze Alert'}</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
