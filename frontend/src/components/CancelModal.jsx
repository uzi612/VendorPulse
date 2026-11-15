import React, { useState } from 'react';
import { api } from '../api';

const REASONS = [
    { value: 'CHANGED_MIND', label: 'Changed my mind' },
    { value: 'WRONG_ADDRESS', label: 'Wrong shipping address' },
    { value: 'FOUND_ELSEWHERE', label: 'Found it elsewhere' },
    { value: 'OTHER', label: 'Other' },
];

// Buyer cancels one order item BEFORE the agent picks it up.
// Requires a reason (shown to the seller); optional short note.
export default function CancelModal({ orderItem, onClose, onCancelled }) {
    const [reason, setReason] = useState('');
    const [note, setNote] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    if (!orderItem) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (!reason) {
            setError('Please pick a cancellation reason.');
            return;
        }

        setSubmitting(true);
        try {
            const res = await api(`/api/orders/items/${orderItem.id}/cancel/`, {
                method: 'POST',
                body: JSON.stringify({
                    reason,
                    note: note.trim() || undefined,
                }),
            });
            const data = await res.json();
            if (!res.ok) {
                setError(data.error || 'Failed to cancel this order.');
            } else {
                onCancelled(orderItem.id, data.item);
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
                    <h3 className="text-lg font-black text-red-600">Cancel this order?</h3>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
                </div>
                <p className="text-xs text-gray-500 mb-1">
                    {orderItem.item_title} — ₹{orderItem.item_price}
                </p>
                <p className="text-xs text-gray-500 mb-5">
                    Sold by <b className="text-gray-700">@{orderItem.seller_username}</b> · The seller will see your reason.
                </p>

                <form onSubmit={handleSubmit}>
                    <label className="block text-sm font-semibold text-gray-700 mb-1">
                        Why are you cancelling? <span className="text-red-500">*</span>
                    </label>
                    <select
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        className="w-full px-3 py-2 mb-4 border border-gray-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-red-500 focus:outline-none"
                    >
                        <option value="">Select a reason…</option>
                        {REASONS.map((r) => (
                            <option key={r.value} value={r.value}>{r.label}</option>
                        ))}
                    </select>

                    <label className="block text-sm font-semibold text-gray-700 mb-1">
                        Additional note (optional)
                    </label>
                    <textarea
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="Anything the seller should know…"
                        maxLength={500}
                        rows={2}
                        className="w-full px-3 py-2 mb-5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:outline-none resize-none"
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
                            Keep Order
                        </button>
                        <button
                            type="submit"
                            disabled={submitting}
                            className="flex-1 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm font-bold py-2.5 rounded-xl"
                        >
                            {submitting ? 'Cancelling…' : 'Cancel Order'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
