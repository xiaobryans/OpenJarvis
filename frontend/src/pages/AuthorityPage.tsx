/**
 * Plan 8B — Authority Page
 *
 * Route: /authority
 * Houses the full Authority Cockpit for desktop.
 */

import { AuthorityCockpit } from '../components/Authority/AuthorityCockpit';

export function AuthorityPage() {
  const now = new Date();
  const stamp = now.toISOString().replace('T', ' ').slice(0, 19) + ' UTC';

  return (
    <div className="flex-1 overflow-y-auto px-6 py-10">
      <div className="max-w-4xl mx-auto">
        <header className="mb-6">
          <div className="flex items-center justify-between">
            <h1
              className="text-lg font-semibold"
              style={{ color: 'var(--color-text)' }}
            >
              Trusted Delegation &amp; Authority Control
            </h1>
            <div className="text-xs" style={{ color: 'var(--color-text-tertiary)' }}>
              {stamp}
            </div>
          </div>
          <p
            className="text-sm mt-2 max-w-2xl"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            Plan 8 — Permission tiers, approval gates, emergency stop, audit trail,
            risk classification, rollback visibility, and spend/secret guardrails.
            All data from live{' '}
            <code
              style={{
                fontFamily: 'monospace',
                fontSize: 11,
                color: 'var(--color-text-tertiary)',
              }}
            >
              /v1/authority/*
            </code>{' '}
            routes.
          </p>
        </header>

        <AuthorityCockpit />
      </div>
    </div>
  );
}
