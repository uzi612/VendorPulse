import React, { useState, useEffect } from 'react';
import { api } from '../../../api';
import Pagination from '../../../components/Pagination';
import { useToast } from '../../../components/Toast';

// Buyer disputes queue with resolve/reject decisions (a resolution note is
// required — it is shown to both the buyer and the seller). Status filter and
// page state are lifted into AdminPortal so they survive switching tabs.
export default function DisputesTab({ status, setStatus, page, setPage }) {
    const toast = useToast();
    const [disputes, setDisputes] = useState([]);
    const [disputeMeta, setDisputeMeta] = useState(null);     // {count, total_pages, page, page_size, open_count, resolved_count, rejected_count}
    const [resolvingDisputeId, setResolvingDisputeId] = useState(null);
    const [resolutionNote, setResolutionNote] = useState('');
    const [loadingDisputes, setLoadingDisputes] = useState(false);

    const fetchDisputes = async () => {
        setLoadingDisputes(true);
        try {
            const response = await api(`/api/deliveries/admin/disputes/?page=${page}&page_size=10&status=${status}`);
            if (!response.ok) throw new Error('Failed to fetch disputes.');
            const data = await response.json();
            setDisputes(data.results);
            setDisputeMeta(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoadingDisputes(false);
        }
    };

    useEffect(() => { fetchDisputes(); }, [page, status]);

    const handleResolveDispute = async (disputeId, decision) => {
        if (!resolutionNote.trim()) {
            toast.error('A resolution note is required — it is shown to both the buyer and the seller.');
            return;
        }
        try {
            const response = await api(`/api/deliveries/admin/disputes/${disputeId}/resolve/`, {
                method: 'POST',
                body: JSON.stringify({ status: decision, note: resolutionNote.trim() })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to resolve dispute.');
            toast.success(`Dispute ${decision.toLowerCase()} successfully!`);
            setResolvingDisputeId(null);
            setResolutionNote('');
            fetchDisputes();
        } catch (err) {
            toast.error(err.message);
        }
    };

    return (
        <div>
            <h2 style={{ marginBottom: '16px', color: '#0f172a' }}>⚑ Buyer Disputes</h2>

            <div style={{ display: 'flex', gap: '24px', borderBottom: '2px solid #e2e8f0', marginBottom: '24px' }}>
                {[
                    ['open', 'Open', '#d97706'],
                    ['resolved', 'Resolved', '#16a34a'],
                    ['rejected', 'Rejected', '#64748b'],
                ].map(([value, label, color]) => (
                    <button
                        key={value}
                        onClick={() => { setStatus(value); setPage(1); setResolvingDisputeId(null); }}
                        style={{ padding: '8px 0', background: 'none', border: 'none', borderBottom: status === value ? `2px solid ${color}` : '2px solid transparent', color: status === value ? color : '#64748b', fontWeight: '600', cursor: 'pointer', marginBottom: '-2px' }}
                    >
                        {label} ({disputeMeta ? disputeMeta[`${value}_count`] : '…'})
                    </button>
                ))}
            </div>

            {loadingDisputes ? <p>Loading disputes...</p> : disputes.length === 0 ? (
                <div style={{ backgroundColor: '#ffffff', padding: '32px', borderRadius: '8px', textAlign: 'center', color: '#64748b', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                    <p style={{ margin: 0 }}>
                        {status === 'open' ? 'No open disputes — all clear.' : `No ${status} disputes.`}
                    </p>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {disputes.map(d => (
                        <div key={d.id} style={{ backgroundColor: '#ffffff', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '16px 20px', borderLeft: `4px solid ${d.status === 'OPEN' ? '#d97706' : d.status === 'RESOLVED' ? '#16a34a' : '#94a3b8'}` }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', flexWrap: 'wrap' }}>
                                <div style={{ minWidth: '240px' }}>
                                    <div style={{ fontWeight: '700', color: '#0f172a', fontSize: '14px' }}>
                                        #{d.id} · {d.item_title} · ₹{d.item_price}
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                                        Order #{d.order_id} · Tracking: {d.tracking_number || '—'} · Filed {d.created_at}
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#334155', marginTop: '4px' }}>
                                        Buyer <b>@{d.buyer}</b> vs Seller <b>@{d.seller}</b> · Reason: <b style={{ color: '#b45309' }}>{String(d.reason).replaceAll('_', ' ').toLowerCase()}</b>
                                    </div>
                                </div>

                                {d.status === 'OPEN' ? (
                                    resolvingDisputeId === d.id ? (
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '320px' }}>
                                            <textarea
                                                rows="2"
                                                placeholder="Resolution note (shown to buyer & seller)…"
                                                value={resolutionNote}
                                                onChange={(e) => setResolutionNote(e.target.value)}
                                                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #cbd5e1', boxSizing: 'border-box', fontSize: '13px' }}
                                            />
                                            <div style={{ display: 'flex', gap: '8px' }}>
                                                <button onClick={() => handleResolveDispute(d.id, 'RESOLVED')} style={{ padding: '6px 12px', backgroundColor: '#16a34a', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: '600', fontSize: '12px' }}>✓ Resolve</button>
                                                <button onClick={() => handleResolveDispute(d.id, 'REJECTED')} style={{ padding: '6px 12px', backgroundColor: '#ef4444', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: '600', fontSize: '12px' }}>✕ Reject</button>
                                                <button onClick={() => { setResolvingDisputeId(null); setResolutionNote(''); }} style={{ padding: '6px 12px', backgroundColor: '#64748b', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>Cancel</button>
                                            </div>
                                        </div>
                                    ) : (
                                        <button
                                            onClick={() => { setResolvingDisputeId(d.id); setResolutionNote(''); }}
                                            style={{ padding: '8px 14px', backgroundColor: '#0f172a', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '13px' }}
                                        >
                                            Review
                                        </button>
                                    )
                                ) : (
                                    <div style={{ textAlign: 'right', maxWidth: '340px' }}>
                                        <span style={{ padding: '4px 8px', borderRadius: '4px', backgroundColor: d.status === 'RESOLVED' ? '#dcfce7' : '#f1f5f9', color: d.status === 'RESOLVED' ? '#166534' : '#64748b', fontSize: '11px', fontWeight: '600' }}>
                                            {d.status}
                                        </span>
                                        <div style={{ fontSize: '12px', color: '#475569', marginTop: '6px' }}>“{d.resolution_note}”</div>
                                        <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>
                                            by {d.resolved_by} · {d.resolved_at}
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #f1f5f9', fontSize: '13px', color: '#334155' }}>
                                <b>Buyer's report:</b> {d.description}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            <Pagination meta={disputeMeta} page={page} setPage={setPage} />
        </div>
    );
}
