import React, { useState } from 'react';
import { api } from '../api';

const DELIVERY_STAGES = [
    { key: 'ORDER_PLACED', label: 'Order Placed', desc: 'Your order has been placed and confirmed.' },
    { key: 'PICKUP_SCHEDULED', label: 'Pickup Scheduled', desc: 'VendorPulse logistics scheduled a pickup with the seller.' },
    { key: 'PICKED_UP', label: 'Picked Up', desc: 'Item picked up from seller location.' },
    { key: 'DISPATCHED', label: 'Dispatched', desc: 'Item is on the way to your delivery address.' },
    { key: 'DELIVERED', label: 'Delivered', desc: 'Package successfully delivered to buyer.' }
];

export default function OrderTracking() {
    const [trackingNumber, setTrackingNumber] = useState('');
    const [orderData, setOrderData] = useState(null);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleTrack = (e) => {
        e.preventDefault();
        if (!trackingNumber.trim()) return;

        setLoading(true);
        setError('');
        setOrderData(null);

        api(`/api/orders/track/${trackingNumber.trim()}/`)
        .then(res => {
            if (!res.ok) {
                throw new Error("Invalid Tracking Id");
            }
            return res.json();
        })
        .then(data => {
            setOrderData(data);
            setLoading(false);
        })
        .catch(err => {
            setError(err.message);
            setLoading(false);
        });
    };

    // Determine current stage index for progress bar progression
    const getCurrentStageIndex = (status) => {
        const index = DELIVERY_STAGES.findIndex(stage => stage.key === status);
        return index !== -1 ? index : 0;
    };

    const currentStageIdx = orderData ? getCurrentStageIndex(orderData.status) : 0;

    return (
        <div className="max-w-xl mx-auto px-4 py-12">
            <div className="text-center mb-8">
                <h1 className="text-2xl font-black text-gray-900 tracking-tight">Track Your Order</h1>
                <p className="text-gray-500 text-sm mt-1">Enter your tracking ID below to check live fulfillment status.</p>
            </div>

            <form onSubmit={handleTrack} className="flex gap-2 mb-6">
                <input
                    type="text"
                    placeholder="Enter Tracking ID (e.g. TRK-...)"
                    value={trackingNumber}
                    onChange={(e) => setTrackingNumber(e.target.value)}
                    className="flex-1 px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm bg-white"
                />
                <button
                    type="submit"
                    disabled={loading}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-6 py-3 rounded-xl transition text-sm disabled:opacity-50"
                >
                    {loading ? 'Searching...' : 'Track'}
                </button>
            </form>

            {error && (
                <div className="bg-red-50 border border-red-200 text-red-600 text-sm p-4 rounded-xl text-center font-medium">
                    {error}
                </div>
            )}

            {orderData && (
                <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm space-y-6">
                    {/* Item & Order Summary */}
                    <div className="flex justify-between items-start pb-4 border-b border-gray-100">
                        <div>
                            <span className="text-xs font-bold text-indigo-600 uppercase">Item Details</span>
                            <h3 className="font-bold text-gray-900 text-lg mt-0.5">{orderData.item_title}</h3>
                            <p className="text-xs text-gray-500 mt-1">Order #{orderData.order_id} • Tracking: <span className="font-mono font-medium text-gray-700">{orderData.tracking_number}</span></p>
                        </div>
                        <span className="text-emerald-600 font-black text-lg">₹{orderData.item_price}</span>
                    </div>

                    {/* Vertical Progress Timeline */}
                    <div>
                        <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-6">Fulfillment Progress</h4>
                        <div className="relative pl-6 space-y-8 before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-0.5 before:bg-gray-100">
                            {DELIVERY_STAGES.map((stage, idx) => {
                                const isCompleted = idx <= currentStageIdx;
                                const isCurrent = idx === currentStageIdx;

                                return (
                                    <div key={stage.key} className="relative flex items-start group">
                                        {/* Status Dot */}
                                        <div className={`absolute -left-6 mt-0.5 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                                            isCompleted 
                                                ? 'bg-indigo-600 text-white shadow-sm ring-4 ring-indigo-50' 
                                                : 'bg-gray-100 text-gray-400'
                                        }`}>
                                            {isCompleted ? '✓' : idx + 1}
                                        </div>

                                        <div className="ml-2">
                                            <p className={`text-sm font-bold ${isCompleted ? 'text-gray-900' : 'text-gray-400'}`}>
                                                {stage.label}
                                            </p>
                                            <p className="text-xs text-gray-500 mt-0.5">{stage.desc}</p>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Delivery Address Details */}
                    <div className="bg-gray-50 p-4 rounded-xl border border-gray-100 text-xs text-gray-600 space-y-1">
                        <p><strong className="text-gray-800">Shipping Address:</strong> {orderData.shipping_address}</p>
                        <p><strong className="text-gray-800">Contact Number:</strong> {orderData.phone}</p>
                    </div>
                </div>
            )}
        </div>
    );
}