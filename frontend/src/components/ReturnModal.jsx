import React, { useState } from 'react';
import { api } from '../api';

const REASONS = [
    { value: 'CHANGED_MIND', label: 'Changed my mind' },
    { value: 'DAMAGED', label: 'Item arrived damaged' },
    { value: 'NOT_AS_DESCRIBED', label: 'Not as described' },
    { value: 'WRONG_ITEM', label: 'Wrong item delivered' },
    { value: 'OTHER', label: 'Other' },
];

// Buyer requests a return for one DELIVERED item inside the 24-hour window.
// One request per item; the admin approves or rejects it with a written note.
export default function ReturnModal({ orderItem, onClose, onReturned }) {
    const [reason, setReason] = useState('');
    const [note, setNote] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    if (!orderItem) return null;

    const refundEstimate = (
        parseFloat(orderItem.item_price || 0) + parseFloat(orderItem.delivery_charge || 0)
    ).toFixed(2);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (!reason) {
            setError('Please pick a reason for the return.');
            return;
        }

        setSubmitting(true);
        try {
            const res = await api(`/api/orders/items/${orderItem.id}/return/`, {
                method: 'POST',
                body: JSON.stringify({ reason, note: note.trim() }),
            });
            const data = await res.json();
            if (!res.ok) {
                setError(data.error || 'Failed to request the return.');
            } else {
                onReturned(orderItem.id, data.return);
            }
        } catch (err) {
            setError('Something went wrong. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
            <div
                className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex justify-between items-start mb-1">
                    <h3 className="text-lg font-black text-gray-900">↩ Return this item</h3>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
                </div>
                <p className="text-xs text-gray-500 mb-1">
                    {orderItem.item_title} — ₹{orderItem.item_price}
                </p>
                <p className="text-xs text-gray-500 mb-4">
                    Sold by <b className="text-gray-700">@{orderItem.seller_username}</b> · Delivered {orderItem.delivered_at || 'recently'}
                </p>

                <div className="mb-4 bg-emerald-50 border border-emerald-100 rounded-xl p-3">
                    <p className="text-xs text-emerald-700 font-semibold">
                        If approved, you'll be refunded ₹{refundEstimate}
                    </p>
                    <p className="text-[11px] text-emerald-600 mt-0.5">
                        Item price ₹{orderItem.item_price} + delivery ₹{orderItem.delivery_charge || '0.00'}
                    </p>
                </div>

                <form onSubmit={handleSubmit}>
                    <label className="block text-sm font-semibold text-gray-700 mb-1">
                        Why are you returning it? <span className="text-red-500">*</span>
                    </label>
                    <select
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        className="w-full px-3 py-2 mb-4 border border-gray-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                    >
                        <option value="">Select a reason…</option>
                        {REASONS.map((r) => (
                            <option key={r.value} value={r.value}>{r.label}</option>
                        ))}
                    </select>

                    <label className="block text-sm font-semibold text-gray-700 mb-1">
                        Anything else we should know? <span className="font-normal text-gray-400">(optional)</span>
                    </label>
                    <textarea
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="Add details that will help our team review the return…"
                        maxLength={1000}
                        rows={3}
                        className="w-full px-3 py-2 mb-4 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none resize-none"
                    />

                    {error && (
                        <div className="mb-3 p-2.5 bg-red-50 border border-red-200 text-red-700 text-xs font-semibold rounded-lg">
                            {error}
                        </div>
                    )}

                    <div className="flex gap-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-bold py-2.5 rounded-xl"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={submitting}
                            className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-bold py-2.5 rounded-xl"
                        >
                            {submitting ? 'Submitting…' : 'Request Return'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
