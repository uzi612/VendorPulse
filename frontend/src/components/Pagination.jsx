import React from 'react';

// Shared pagination footer for the admin tables (server-side pagination).
// `meta` is the page metadata object returned by the backend paginated
// endpoints: { count, total_pages, page, page_size, ...counts }.
export default function Pagination({ meta, page, setPage }) {
    if (!meta || meta.total_pages <= 1) return null;
    const btn = (disabled) => ({
        padding: '8px 14px', borderRadius: '6px', border: 'none',
        backgroundColor: disabled ? '#e2e8f0' : '#0f172a',
        color: disabled ? '#94a3b8' : '#ffffff', fontWeight: '600',
        cursor: disabled ? 'not-allowed' : 'pointer', fontSize: '13px',
    });
    return (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px' }}>
            <span style={{ fontSize: '13px', color: '#64748b' }}>
                Page <b>{meta.page}</b> of <b>{meta.total_pages}</b> — {meta.count} total
            </span>
            <div style={{ display: 'flex', gap: '8px' }}>
                <button disabled={meta.page <= 1} onClick={() => setPage(meta.page - 1)} style={btn(meta.page <= 1)}>
                    ← Prev
                </button>
                <button disabled={meta.page >= meta.total_pages} onClick={() => setPage(meta.page + 1)} style={btn(meta.page >= meta.total_pages)}>
                    Next →
                </button>
            </div>
        </div>
    );
}
