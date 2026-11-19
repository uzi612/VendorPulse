import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { STATUS_BADGE_STYLES } from '../../constants/status';
import RatingModal from '../../components/RatingModal';
import CancelModal from '../../components/CancelModal';
import DisputeModal from '../../components/DisputeModal';
import ReturnModal from '../../components/ReturnModal';

// "My Orders & Tracking" accordion: active vs completed sub-tabs, per-item
// rate/cancel/report/return actions and their modals. `orders` lives in
// Profile.jsx (single fetch for profile + orders + sales); mutations bubble up
// through the on* callbacks.
export default function OrdersAccordion({ orders, onRated, onCancelled, onDisputed, onReturned }) {
    // State for separating active vs completed orders
    const [orderTab, setOrderTab] = useState('active');

    // Rating modal state (holds the order item being rated, + its order id)
    const [ratingItem, setRatingItem] = useState(null);

    // Cancel / dispute / return modal state (holds the order item being acted on)
    const [cancelItem, setCancelItem] = useState(null);
    const [disputeItem, setDisputeItem] = useState(null);
    const [returnItem, setReturnItem] = useState(null);

    // Filter orders into active and completed history based on status.
    // CANCELLED is terminal too, so it lives in the history tab.
    const activeOrders = orders.filter(o => o.status !== 'DELIVERED' && o.status !== 'CANCELLED');
    const completedOrders = orders.filter(o => o.status === 'DELIVERED' || o.status === 'CANCELLED');
    const displayedOrders = orderTab === 'active' ? activeOrders : completedOrders;

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <details className="group p-6 md:p-8" open>
                <summary className="flex justify-between items-center cursor-pointer list-none select-none">
                    <div className="flex items-center gap-3">
                        <h2 className="text-xl font-bold text-gray-800">My Orders & Tracking</h2>
                        <span className="bg-gray-100 text-gray-700 text-xs font-bold px-2.5 py-0.5 rounded-full">
                            {orders.length}
                        </span>
                    </div>
                    <span className="transform group-open:rotate-180 transition duration-200 text-indigo-600 font-bold">▼</span>
                </summary>

                <div className="mt-6 pt-6 border-t border-gray-100">
                    {/* Sub-tabs for Active vs Completed Orders */}
                    <div className="flex border-b border-gray-200 mb-6">
                        <button
                            type="button"
                            onClick={() => setOrderTab('active')}
                            className={`pb-3 px-4 font-bold text-sm border-b-2 transition ${
                                orderTab === 'active'
                                    ? 'border-indigo-600 text-indigo-600'
                                    : 'border-transparent text-gray-400 hover:text-gray-600'
                            }`}
                        >
                            Active Orders ({activeOrders.length})
                        </button>
                        <button
                            type="button"
                            onClick={() => setOrderTab('completed')}
                            className={`pb-3 px-4 font-bold text-sm border-b-2 transition ${
                                orderTab === 'completed'
                                    ? 'border-indigo-600 text-indigo-600'
                                    : 'border-transparent text-gray-400 hover:text-gray-600'
                            }`}
                        >
                            Completed History ({completedOrders.length})
                        </button>
                    </div>

                    {displayedOrders.length > 0 ? (
                        <div className="space-y-6">
                            {displayedOrders.map((order) => (
                                <div key={order.id} className="border border-gray-200 rounded-xl p-5 hover:border-indigo-200 transition">
                                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center pb-4 border-b border-gray-100 gap-2">
                                        <div>
                                            <span className="text-xs font-bold text-indigo-600 uppercase">Order #{order.id}</span>
                                            <p className="text-xs text-gray-500 mt-0.5">Placed on {order.created_at}</p>
                                        </div>
                                        <div className="text-right">
                                            <span className="text-emerald-600 font-black text-lg">₹{order.total_price}</span>
                                            {order.subtotal != null && (
                                                <p className="text-[11px] text-gray-400 mt-0.5">
                                                    Items ₹{order.subtotal} + delivery ₹{order.delivery_charge}
                                                </p>
                                            )}
                                        </div>
                                    </div>

                                    {order.items && order.items.length > 0 && (
                                        <div className="py-3 space-y-3">
                                            <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">Items in this order:</p>
                                            <ul className="text-sm text-gray-700 space-y-2">
                                                {order.items.map((oi, idx) => {
                                                    const canRateSeller = oi.status === 'DELIVERED' && oi.seller_stars == null;
                                                    const canRateAgent = oi.status === 'DELIVERED' && oi.agent_username && oi.agent_stars == null;
                                                    const showRateBtn = canRateSeller || canRateAgent;
                                                    // Cancel only while the goods are still with the seller
                                                    const canCancel = oi.status === 'ORDER_PLACED' || oi.status === 'PICKUP_SCHEDULED';
                                                    // Report problems only after delivery (one per item)
                                                    const canDispute = oi.status === 'DELIVERED' && !oi.dispute;
                                                    // Returns: backend says the 24-hour window is
                                                    // still open and no request exists yet.
                                                    const canReturn = !!oi.can_request_return;
                                                    const statusStyle = STATUS_BADGE_STYLES[oi.status] || 'bg-gray-100 text-gray-500';
                                                    return (
                                                        <li key={oi.id ?? idx} className="flex flex-wrap justify-between items-center gap-2 border-b border-gray-50 pb-2 last:border-0 last:pb-0">
                                                            <div className="min-w-0">
                                                                <div className="flex items-center gap-2 flex-wrap">
                                                                    <span className="font-medium">{oi.item_title}</span>
                                                                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${statusStyle}`}>{oi.status}</span>
                                                                    {oi.dispute && (
                                                                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${oi.dispute.status === 'OPEN' ? 'bg-amber-100 text-amber-700' : oi.dispute.status === 'RESOLVED' ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-600'}`}>
                                                                            ⚑ {oi.dispute.status === 'OPEN' ? 'Dispute Open' : oi.dispute.status === 'RESOLVED' ? 'Dispute Resolved' : 'Dispute Rejected'}
                                                                        </span>
                                                                    )}
                                                                    {oi.return_request && (
                                                                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${oi.return_request.status === 'REQUESTED' ? 'bg-amber-100 text-amber-700' : oi.return_request.status === 'APPROVED' ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-600'}`}>
                                                                            ↩ {oi.return_request.status === 'REQUESTED' ? 'Return Requested' : oi.return_request.status === 'APPROVED' ? 'Return Approved' : 'Return Rejected'}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                                <p className="text-[11px] text-gray-400 mt-0.5">
                                                                    Sold by @{oi.seller_username}
                                                                    {oi.agent_username && <> · {oi.status === 'DELIVERED' ? 'Delivered by' : 'Agent'} @{oi.agent_username}</>}
                                                                    {oi.seller_stars != null && <> · Seller <span className="text-amber-500">{'★'.repeat(oi.seller_stars)}</span></>}
                                                                    {oi.agent_stars != null && <> · Agent <span className="text-amber-500">{'★'.repeat(oi.agent_stars)}</span></>}
                                                                    {oi.status === 'CANCELLED' && oi.cancel_reason && <> · Cancelled: <span className="text-red-500">{oi.cancel_reason.replaceAll('_', ' ').toLowerCase()}</span></>}
                                                                    {Number(oi.delivery_charge) > 0 && <> · Delivery ₹{oi.delivery_charge}</>}
                                                                </p>
                                                                {canReturn && oi.return_window_ends_at && (
                                                                    <p className="text-[11px] text-indigo-500 mt-0.5 font-semibold">
                                                                        ↩ Return window open until {new Date(oi.return_window_ends_at).toLocaleString([], { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                                                                    </p>
                                                                )}
                                                                {oi.return_request?.admin_note && (
                                                                    <p className="text-[11px] text-gray-500 mt-0.5 bg-gray-50 border border-gray-100 rounded px-2 py-1">
                                                                        <b>VendorPulse team:</b> {oi.return_request.admin_note}
                                                                    </p>
                                                                )}
                                                                {oi.dispute?.status !== 'OPEN' && oi.dispute?.resolution_note && (
                                                                    <p className="text-[11px] text-gray-500 mt-0.5 bg-gray-50 border border-gray-100 rounded px-2 py-1">
                                                                        <b>VendorPulse team:</b> {oi.dispute.resolution_note}
                                                                    </p>
                                                                )}
                                                            </div>
                                                            <div className="flex items-center gap-2 flex-shrink-0">
                                                                <span className="font-semibold">₹{oi.item_price}</span>
                                                                {showRateBtn && (
                                                                    <button
                                                                        onClick={() => setRatingItem({ ...oi, order_id: order.id })}
                                                                        className="bg-amber-400 hover:bg-amber-500 text-white text-xs font-bold px-3 py-1.5 rounded-lg transition"
                                                                    >
                                                                        ⭐ Rate
                                                                    </button>
                                                                )}
                                                                {canCancel && (
                                                                    <button
                                                                        onClick={() => setCancelItem({ ...oi, order_id: order.id })}
                                                                        className="bg-red-100 hover:bg-red-200 text-red-600 text-xs font-bold px-3 py-1.5 rounded-lg transition"
                                                                    >
                                                                        ✕ Cancel
                                                                    </button>
                                                                )}
                                                                {canDispute && (
                                                                    <button
                                                                        onClick={() => setDisputeItem({ ...oi, order_id: order.id })}
                                                                        className="bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-bold px-3 py-1.5 rounded-lg transition"
                                                                    >
                                                                        ⚑ Report
                                                                    </button>
                                                                )}
                                                                {canReturn && (
                                                                    <button
                                                                        onClick={() => setReturnItem({ ...oi, order_id: order.id })}
                                                                        className="bg-indigo-100 hover:bg-indigo-200 text-indigo-700 text-xs font-bold px-3 py-1.5 rounded-lg transition"
                                                                    >
                                                                        ↩ Return
                                                                    </button>
                                                                )}
                                                            </div>
                                                        </li>
                                                    );
                                                })}
                                            </ul>
                                        </div>
                                    )}

                                    <div className="mt-3 pt-3 border-t border-gray-100 flex items-center justify-between text-xs">
                                        <span className="font-medium text-indigo-900">
                                            {order.status === 'DELIVERED'
                                                ? '🎉 Delivered safely by VendorPulse Delivery Services!'
                                                : order.status === 'DISPATCHED'
                                                ? '🚚 Out for delivery! Your courier is on the way.'
                                                : '⏳ Order registered with VendorPulse Delivery.'}
                                        </span>
                                        <span className="px-2.5 py-1 rounded-full font-bold bg-indigo-50 text-indigo-700">
                                            {order.status || 'ORDER_PLACED'}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-12 border-2 border-dashed border-gray-100 rounded-xl">
                            <p className="text-gray-400 text-sm">
                                {orderTab === 'active' ? "No active orders right now." : "No completed delivery history yet."}
                            </p>
                            <Link to="/products/" className="inline-block mt-3 text-indigo-600 text-sm font-semibold hover:underline">
                                Browse Marketplace Feed &rarr;
                            </Link>
                        </div>
                    )}
                </div>
            </details>

            {ratingItem && (
                <RatingModal
                    orderItem={ratingItem}
                    onClose={() => setRatingItem(null)}
                    onRated={onRated}
                />
            )}

            {cancelItem && (
                <CancelModal
                    orderItem={cancelItem}
                    onClose={() => setCancelItem(null)}
                    onCancelled={onCancelled}
                />
            )}

            {disputeItem && (
                <DisputeModal
                    orderItem={disputeItem}
                    onClose={() => setDisputeItem(null)}
                    onDisputed={onDisputed}
                />
            )}

            {returnItem && (
                <ReturnModal
                    orderItem={returnItem}
                    onClose={() => setReturnItem(null)}
                    onReturned={(itemId, returnRequest) => {
                        setReturnItem(null);
                        if (onReturned) onReturned(itemId, returnRequest);
                    }}
                />
            )}
        </div>
    );
}
