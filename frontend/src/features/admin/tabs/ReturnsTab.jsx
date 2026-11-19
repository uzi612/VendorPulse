import React, { useState, useEffect } from 'react';
import { api } from '../../../api';
import Pagination from '../../../components/Pagination';
import { useToast } from '../../../components/Toast';

// Buyer return requests (24 h after delivery). Approving refunds the item
// price + delivery charge, reverses the seller's payout and restocks the
// listing; rejecting closes it. A decision note is required either way.
// Status filter and page state are lifted into AdminPortal so they survive
// switching tabs.
export default function ReturnsTab({ status, setStatus, page, setPage }) {
    const toast = useToast();
    const [returns, setReturns] = useState([]);
    const [returnMeta, setReturnMeta] = useState(null);   // {count, total_pages, requested_count, approved_count, rejected_count}
    const [resolvingReturnId, setResolvingReturnId] = useState(null);
    const [decisionNote, setDecisionNote] = useState('');
    const [loadingReturns, setLoadingReturns] = useState(false);

    const fetchReturns = async () => {
        setLoadingReturns(true);
        try {
            const response = await api(`/api/deliveries/admin/returns/?page=${page}&page_size=10&status=${status}`);
            if (!response.ok) throw new Error('Failed to fetch return requests.');
            const data = await response.json();
            setReturns(data.results);
            setReturnMeta(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoadingReturns(false);
        }
    };

    useEffect(() => { fetchReturns(); }, [page, status]);

    const handleResolveReturn = async (returnId, decision) => {
        if (!decisionNote.trim()) {
            toast.error('A decision note is required — it is shown to both the buyer and the seller.');
            return;
        }
        try {
            const response = await api(`/api/deliveries/admin/returns/${returnId}/resolve/`, {
                method: 'POST',
                body: JSON.stringify({ status: decision, note: decisionNote.trim() })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to resolve the return.');
            toast.success(`Return ${decision.toLowerCase()} successfully!`);
            setResolvingReturnId(null);
            setDecisionNote('');
            fetchReturns();
        } catch (err) {
            toast.error(err.message);
        }
    };

    return (
        <div>
            <h2 style={{ marginBottom: '16px', color: '#0f172a' }}>↩ Buyer Returns</h2>

            <div style={{ display: 'flex', gap: '24px', borderBottom: '2px solid #e2e8f0', marginBottom: '24px' }}>
                {[
                    ['requested', 'Requested', '#d97706'],
                    ['approved', 'Approved', '#16a34a'],
                    ['rejected', 'Rejected', '#64748b'],
                ].map(([value, label, color]) => (
                    <button
                        key={value}
                        onClick={() => { setStatus(value); setPage(1); setResolvingReturnId(null); }}
                        style={{ padding: '8px 0', background: 'none', border: 'none', borderBottom: status === value ? `2px solid ${color}` : '2px solid transparent', color: status === value ? color : '#64748b', fontWeight: '600', cursor: 'pointer', marginBottom: '-2px' }}
                    >
                        {label} ({returnMeta ? returnMeta[`${value}_count`] : '…'})
                    </button>
                ))}
            </div>

            {loadingReturns ? <p>Loading return requests...</p> : returns.length === 0 ? (
                <div style={{ backgroundColor: '#ffffff', padding: '32px', borderRadius: '8px', textAlign: 'center', color: '#64748b', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                    <p style={{ margin: 0 }}>
                        {status === 'requested' ? 'No return requests waiting — all clear.' : `No ${status} returns.`}
                    </p>
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {returns.map(r => (
                        <div key={r.id} style={{ backgroundColor: '#ffffff', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '16px 20px', borderLeft: `4px solid ${r.status === 'REQUESTED' ? '#d97706' : r.status === 'APPROVED' ? '#16a34a' : '#94a3b8'}` }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', flexWrap: 'wrap' }}>
                                <div style={{ minWidth: '260px' }}>
                                    <div style={{ fontWeight: '700', color: '#0f172a', fontSize: '14px' }}>
                                        #{r.id} · {r.item_title} · ₹{r.item_price}
                                        <span style={{ marginLeft: '8px', fontWeight: '600', color: '#64748b', fontSize: '12px' }}>
                                            + ₹{r.delivery_charge} delivery
                                        </span>
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                                        Order #{r.order_id} · Tracking: {r.tracking_number || '—'} · Delivered {r.delivered_at || '—'}
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#334155', marginTop: '4px' }}>
                                        Buyer <b>@{r.buyer}</b> vs Seller <b>@{r.seller}</b> · Reason: <b style={{ color: '#b45309' }}>{String(r.reason).replaceAll('_', ' ').toLowerCase()}</b>
                                    </div>
                                    {r.note && (
                                        <div style={{ fontSize: '12px', color: '#475569', marginTop: '4px' }}>
                                            <b>Buyer's note:</b> {r.note}
                                        </div>
                                    )}
                                    <div style={{ fontSize: '12px', color: '#0f172a', marginTop: '6px', fontWeight: '700' }}>
                                        Refund on approval: ₹{r.refund_amount && Number(r.refund_amount) > 0 ? r.refund_amount : (Number(r.item_price) + Number(r.delivery_charge)).toFixed(2)}
                                    </div>
                                </div>

                                {r.status === 'REQUESTED' ? (
                                    resolvingReturnId === r.id ? (
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '340px' }}>
                                            <textarea
                                                rows="2"
                                                placeholder="Decision note (shown to buyer & seller)…"
                                                value={decisionNote}
                                                onChange={(e) => setDecisionNote(e.target.value)}
                                                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #cbd5e1', boxSizing: 'border-box', fontSize: '13px' }}
                                            />
                                            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                                <button onClick={() => handleResolveReturn(r.id, 'APPROVED')} style={{ padding: '6px 12px', backgroundColor: '#16a34a', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: '600', fontSize: '12px' }}>✓ Approve refund</button>
                                                <button onClick={() => handleResolveReturn(r.id, 'REJECTED')} style={{ padding: '6px 12px', backgroundColor: '#ef4444', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: '600', fontSize: '12px' }}>✕ Reject</button>
                                                <button onClick={() => { setResolvingReturnId(null); setDecisionNote(''); }} style={{ padding: '6px 12px', backgroundColor: '#64748b', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>Cancel</button>
                                            </div>
                                        </div>
                                    ) : (
                                        <button
                                            onClick={() => { setResolvingReturnId(r.id); setDecisionNote(''); }}
                                            style={{ padding: '8px 14px', backgroundColor: '#0f172a', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '13px' }}
                                        >
                                            Review
                                        </button>
                                    )
                                ) : (
                                    <div style={{ textAlign: 'right', maxWidth: '340px' }}>
                                        <span style={{ padding: '4px 8px', borderRadius: '4px', backgroundColor: r.status === 'APPROVED' ? '#dcfce7' : '#f1f5f9', color: r.status === 'APPROVED' ? '#166534' : '#64748b', fontSize: '11px', fontWeight: '600' }}>
                                            {r.status}
                                        </span>
                                        {r.status === 'APPROVED' && (
                                            <div style={{ fontSize: '12px', color: '#16a34a', marginTop: '6px', fontWeight: '700' }}>
                                                Refunded ₹{r.refund_amount}
                                            </div>
                                        )}
                                        <div style={{ fontSize: '12px', color: '#475569', marginTop: '6px' }}>“{r.admin_note}”</div>
                                        <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>
                                            by {r.resolved_by} · {r.resolved_at}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            <Pagination meta={returnMeta} page={page} setPage={setPage} />
        </div>
    );
}
