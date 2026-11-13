import React, { useState } from 'react';
import { api } from '../api';

// One reusable star-picker row
function StarPicker({ label, value, onChange, locked, lockedValue }) {
    return (
        <div className="mb-5">
            <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-bold text-gray-700">{label}</span>
                {locked && (
                    <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                        Rated {lockedValue}/5 ★
                    </span>
                )}
            </div>
            {locked ? (
                <div className="text-lg tracking-widest text-amber-400">
                    {'★'.repeat(lockedValue)}
                    <span className="text-gray-300">{'★'.repeat(5 - lockedValue)}</span>
                </div>
            ) : (
                <div className="flex gap-1">
                    {[1, 2, 3, 4, 5].map((star) => (
                        <button
                            key={star}
                            type="button"
                            onClick={() => onChange(star)}
                            className={`text-2xl leading-none transition-transform hover:scale-125 ${
                                star <= value ? 'text-amber-400' : 'text-gray-300'
                            }`}
                            aria-label={`${star} star`}
                        >
                            ★
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

export default function RatingModal({ orderItem, onClose, onRated }) {
    // Pre-lock sub-ratings the buyer already submitted earlier
    const [sellerStars, setSellerStars] = useState(0);
    const [agentStars, setAgentStars] = useState(0);
    const [sellerComment, setSellerComment] = useState('');
    const [agentComment, setAgentComment] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    if (!orderItem) return null;

    const sellerLocked = orderItem.seller_stars != null;
    const agentLocked = orderItem.agent_stars != null;
    const hasAgent = !!orderItem.agent_username;
    const fullyRated = sellerLocked && (agentLocked || !hasAgent);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');

        if (!sellerLocked && sellerStars === 0 && !agentLocked && hasAgent && agentStars === 0) {
            setError('Please pick at least one star rating.');
            return;
        }

        // Send only the sub-ratings being set this time (server forbids overwrites)
        const body = {};
        if (!sellerLocked && sellerStars > 0) {
            body.seller_stars = sellerStars;
            if (sellerComment.trim()) body.seller_comment = sellerComment.trim();
        }
        if (!agentLocked && hasAgent && agentStars > 0) {
            body.agent_stars = agentStars;
            if (agentComment.trim()) body.agent_comment = agentComment.trim();
        }

        setSubmitting(true);
        try {
            const res = await api(`/api/orders/items/${orderItem.id}/rate/`, {
                method: 'POST',
                body: JSON.stringify(body),
            });
            const data = await res.json();
            if (!res.ok) {
                setError(data.error || 'Failed to submit rating.');
            } else {
                onRated(orderItem.id, data.rating);
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
                    <h3 className="text-lg font-black text-gray-900">Rate your experience</h3>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">✕</button>
                </div>
                <p className="text-xs text-gray-500 mb-1">
                    {orderItem.item_title} — Order #{orderItem.order_id || ''}
                </p>
                <p className="text-xs text-gray-500 mb-5">
                    Seller <b className="text-gray-700">@{orderItem.seller_username}</b>
                    {hasAgent && <> · Agent <b className="text-gray-700">@{orderItem.agent_username}</b></>}
                </p>

                {fullyRated ? (
                    <div className="text-center py-4">
                        <p className="text-3xl mb-2">🎉</p>
                        <p className="text-sm font-semibold text-gray-700">You've rated this purchase fully.</p>
                        <button
                            onClick={onClose}
                            className="mt-4 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold px-5 py-2.5 rounded-xl"
                        >
                            Close
                        </button>
                    </div>
                ) : (
                    <form onSubmit={handleSubmit}>
                        <StarPicker
                            label="Seller"
                            value={sellerStars}
                            onChange={setSellerStars}
                            locked={sellerLocked}
                            lockedValue={orderItem.seller_stars}
                        />
                        {!sellerLocked && (
                            <input
                                type="text"
                                value={sellerComment}
                                onChange={(e) => setSellerComment(e.target.value)}
                                placeholder="Comment about the seller (optional)"
                                maxLength={500}
                                className="w-full px-3 py-2 mb-5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                            />
                        )}

                        {hasAgent && (
                            <>
                                <StarPicker
                                    label="Delivery Agent"
                                    value={agentStars}
                                    onChange={setAgentStars}
                                    locked={agentLocked}
                                    lockedValue={orderItem.agent_stars}
                                />
                                {!agentLocked && (
                                    <input
                                        type="text"
                                        value={agentComment}
                                        onChange={(e) => setAgentComment(e.target.value)}
                                        placeholder="Comment about the agent (optional)"
                                        maxLength={500}
                                        className="w-full px-3 py-2 mb-5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                                    />
                                )}
                            </>
                        )}

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
                                Later
                            </button>
                            <button
                                type="submit"
                                disabled={submitting}
                                className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-bold py-2.5 rounded-xl"
                            >
                                {submitting ? 'Submitting…' : 'Submit Rating'}
                            </button>
                        </div>
                    </form>
                )}
            </div>
        </div>
    );
}
