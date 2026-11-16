import React, { useState, useEffect } from 'react';
import { api } from '../../../api';
import Pagination from '../../../components/Pagination';
import { useToast } from '../../../components/Toast';

// Listing moderation queue: every seller listing waits for admin approval
// before it appears on the marketplace. Approve / Reject (reason required,
// shown to the seller). Status filter and page state are lifted into
// AdminPortal so they survive switching tabs.
export default function ModerationTab({ status, setStatus, page, setPage }) {
    const toast = useToast();
    const [listings, setListings] = useState([]);
    const [listingMeta, setListingMeta] = useState(null);   // {count, total_pages, page, page_size, pending_count, approved_count, rejected_count}
    const [rejectingListingId, setRejectingListingId] = useState(null);
    const [rejectionReason, setRejectionReason] = useState('');
    const [loadingListings, setLoadingListings] = useState(false);

    const fetchListings = async () => {
        setLoadingListings(true);
        try {
            const response = await api(`/api/products/admin/moderation/?page=${page}&page_size=12&status=${status}`);
            if (!response.ok) throw new Error('Failed to fetch listings.');
            const data = await response.json();
            setListings(data.results);
            setListingMeta(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoadingListings(false);
        }
    };

    useEffect(() => { fetchListings(); }, [page, status]);

    const handleListingDecision = async (itemId, decision) => {
        if (decision === 'REJECTED' && !rejectionReason.trim()) {
            toast.error('A rejection reason is required — it is shown to the seller.');
            return;
        }
        try {
            const response = await api(`/api/products/admin/moderation/${itemId}/review/`, {
                method: 'POST',
                body: JSON.stringify({
                    decision,
                    reason: decision === 'REJECTED' ? rejectionReason.trim() : undefined
                })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to review listing.');
            toast.success(`Listing ${decision.toLowerCase()} — the seller has been notified.`);
            setRejectingListingId(null);
            setRejectionReason('');
            fetchListings();
        } catch (err) {
            toast.error(err.message);
        }
    };

    return (
        <div>
            <h2 style={{ marginBottom: '16px', color: '#0f172a' }}>🗂 Listing Moderation</h2>

            <div style={{ display: 'flex', gap: '24px', borderBottom: '2px solid #e2e8f0', marginBottom: '24px' }}>
                {[
                    ['pending', 'Pending Review', '#d97706'],
                    ['approved', 'Approved', '#16a34a'],
                    ['rejected', 'Rejected', '#dc2626'],
                ].map(([value, label, color]) => (
                    <button
                        key={value}
                        onClick={() => { setStatus(value); setPage(1); setRejectingListingId(null); }}
                        style={{ padding: '8px 0', background: 'none', border: 'none', borderBottom: status === value ? `2px solid ${color}` : '2px solid transparent', color: status === value ? color : '#64748b', fontWeight: '600', cursor: 'pointer', marginBottom: '-2px' }}
                    >
                        {label} ({listingMeta ? listingMeta[`${value}_count`] : '…'})
                    </button>
                ))}
            </div>

            {loadingListings ? <p>Loading listings...</p> : listings.length === 0 ? (
                <div style={{ backgroundColor: '#ffffff', padding: '32px', borderRadius: '8px', textAlign: 'center', color: '#64748b', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                    <p style={{ margin: 0 }}>
                        {status === 'pending' ? 'No listings awaiting review — queue is clear.' : `No ${status} listings.`}
                    </p>
                </div>
            ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
                    {listings.map(item => (
                        <div key={item.id} style={{ backgroundColor: '#ffffff', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            <div style={{ display: 'flex', gap: '12px' }}>
                                <div style={{ width: '96px', height: '96px', backgroundColor: '#f1f5f9', borderRadius: '6px', overflow: 'hidden', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '11px', color: '#94a3b8' }}>
                                    {item.image
                                        ? <img src={item.image} alt={item.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                        : 'No image'}
                                </div>
                                <div style={{ minWidth: 0 }}>
                                    <div style={{ fontWeight: '700', color: '#0f172a', fontSize: '14px' }}>{item.title}</div>
                                    <div style={{ fontWeight: '700', color: '#059669', fontSize: '14px', marginTop: '2px' }}>₹{item.price}</div>
                                    <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                                        {item.category} · {String(item.condition).replaceAll('_', ' ').toLowerCase()} · 📍{item.location || '—'}
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#334155', marginTop: '4px' }}>
                                        by <b>@{item.seller_username}</b>{' '}
                                        {item.is_seller_verified
                                            ? <span style={{ color: '#16a34a', fontWeight: '600' }}>✓ Verified</span>
                                            : <span style={{ color: '#d97706', fontWeight: '600' }}>Unverified</span>}
                                    </div>
                                    <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>Posted {item.created_at}</div>
                                </div>
                            </div>

                            <div style={{ fontSize: '12px', color: '#475569', backgroundColor: '#f8fafc', borderRadius: '6px', padding: '8px', border: '1px solid #f1f5f9', maxHeight: '72px', overflowY: 'auto' }}>
                                {item.description}
                            </div>

                            {item.approval_status === 'REJECTED' && item.rejection_reason && (
                                <div style={{ fontSize: '12px', color: '#b91c1c', backgroundColor: '#fef2f2', borderRadius: '6px', padding: '8px' }}>
                                    Rejected: {item.rejection_reason}
                                </div>
                            )}

                            <div style={{ marginTop: 'auto', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                {item.approval_status !== 'APPROVED' && (
                                    <button onClick={() => handleListingDecision(item.id, 'APPROVED')} style={{ padding: '8px 14px', backgroundColor: '#16a34a', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '12px' }}>
                                        ✓ Approve
                                    </button>
                                )}
                                {item.approval_status !== 'REJECTED' && (
                                    rejectingListingId === item.id ? (
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: 1, minWidth: '220px' }}>
                                            <textarea
                                                rows="2"
                                                placeholder="Rejection reason (shown to the seller)…"
                                                value={rejectionReason}
                                                onChange={(e) => setRejectionReason(e.target.value)}
                                                style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid #cbd5e1', boxSizing: 'border-box', fontSize: '12px' }}
                                            />
                                            <div style={{ display: 'flex', gap: '6px' }}>
                                                <button onClick={() => handleListingDecision(item.id, 'REJECTED')} style={{ padding: '6px 10px', backgroundColor: '#dc2626', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: '600', fontSize: '11px' }}>✕ Confirm Reject</button>
                                                <button onClick={() => { setRejectingListingId(null); setRejectionReason(''); }} style={{ padding: '6px 10px', backgroundColor: '#64748b', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '11px' }}>Cancel</button>
                                            </div>
                                        </div>
                                    ) : (
                                        <button onClick={() => { setRejectingListingId(item.id); setRejectionReason(''); }} style={{ padding: '8px 14px', backgroundColor: '#ef4444', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '600', fontSize: '12px' }}>
                                            ✕ Reject
                                        </button>
                                    )
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            <Pagination meta={listingMeta} page={page} setPage={setPage} />
        </div>
    );
}
