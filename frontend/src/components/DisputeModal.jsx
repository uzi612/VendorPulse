import React, { useState } from 'react';
import { api } from '../api';

const REASONS = [
    { value: 'DAMAGED', label: 'Item arrived damaged' },
    { value: 'NOT_AS_DESCRIBED', label: 'Not as described' },
    { value: 'NOT_RECEIVED', label: 'Never received the item' },
    { value: 'OTHER', label: 'Other' },
];

// Buyer reports a problem with a DELIVERED item (one dispute per item).
// The admin reviews it and resolves/rejects with a written note.
export default function DisputeModal({ orderItem, onClose, onDisputed }) {
    const [reason, setReason] = useState('');
    const [description, setDescription] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    if (!orderItem) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (!reason) {
            setError('Please pick what went wrong.');
            return;
        }
        if (description.trim().length < 10) {
            setError('Please describe the problem (at least 10 characters).');
            return;
        }

        setSubmitting(true);
        try {
            const res = await api(`/api/orders/items/${orderItem.id}/dispute/`, {
                method: 'POST',
                body: JSON.stringify({
                    reason,
                    description: description.trim(),
                }),
            });
            const data = await res.json();
            if (!res.ok) {
                setError(data.error || 'Failed to file the dispute.');
            } else {
                onDisputed(orderItem.id, data.dispute);
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
                    <h3 className="text-lg font-black text-gray-900">⚑ Report a problem</h3>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
                </div>
                <p className="text-xs text-gray-500 mb-1">
                    {orderItem.item_title} — ₹{orderItem.item_price}
                </p>
                <p className="text-xs text-gray-500 mb-5">
                    Sold by <b className="text-gray-700">@{orderItem.seller_username}</b> · Our team will review and get back to you.
                </p>

                <form onSubmit={handleSubmit}>
                    <label className="block text-sm font-semibold text-gray-700 mb-1">
                        What went wrong? <span className="text-red-500">*</span>
                    </label>
                    <select
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        className="w-full px-3 py-2 mb-4 border border-gray-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-amber-500 focus:outline-none"
                    >
                        <option value="">Select an issue…</option>
                        {REASONS.map((r) => (
                            <option key={r.value} value={r.value}>{r.label}</option>
                        ))}
                    </select>

                    <label className="block text-sm font-semibold text-gray-700 mb-1">
                        Describe the problem <span className="text-red-500">*</span>
                    </label>
                    <textarea
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Tell us what happened so we can help…"
                        maxLength={1000}
                        rows={4}
                        className="w-full px-3 py-2 mb-5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-amber-500 focus:outline-none resize-none"
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
                            Not Now
                        </button>
                        <button
                            type="submit"
                            disabled={submitting}
                            className="flex-1 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-white text-sm font-bold py-2.5 rounded-xl"
                        >
                            {submitting ? 'Submitting…' : 'Submit Report'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
