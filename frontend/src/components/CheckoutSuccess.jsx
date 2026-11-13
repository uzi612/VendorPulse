import React, { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api';

export default function CheckoutSuccess() {
    const { id } = useParams(); 
    const [order, setOrder] = useState(null);

    useEffect(() => {
        api(`/api/orders/success/${id}/`)
        .then(res => {
            if (!res.ok) throw new Error("Failed to load order details");
            return res.json();
        })
        .then(data => setOrder(data))
        .catch(err => console.error(err));
    }, [id]);

    return (
        <div className="max-w-2xl mx-auto px-4 py-16 text-center">
            <div className="w-20 h-20 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-6 shadow-sm">
                ✓
            </div>
            <h1 className="text-3xl font-black text-gray-900 tracking-tight mt-3">Order Placed Successfully!</h1>
            <p className="text-gray-500 text-sm mt-2">Thank you for your purchase. Assigned to VendorPulse Delivery Services.</p>

            {order && (
                <div className="bg-white border border-gray-200 rounded-2xl p-6 mt-8 text-left shadow-sm">
                    <div className="flex justify-between items-center pb-4 border-b border-gray-100">
                        <div>
                            <span className="text-xs font-bold text-indigo-600 uppercase">Order Reference</span>
                            <h3 className="font-bold text-gray-900 text-lg">#{order.order_id}</h3>
                        </div>
                        <span className="text-emerald-600 font-black text-xl">₹{order.total_price}</span>
                    </div>
                    <div className="py-4 space-y-2 text-xs text-gray-600">
                        <p><strong className="text-gray-800">Delivery Address:</strong> {order.shipping_address}</p>
                        <p><strong className="text-gray-800">Contact Number:</strong> {order.phone}</p>
                    </div>

                    {/* Delivery OTP — shown only to the buyer */}
                    {order.delivery_otp && (
                        <div className="mt-2 bg-indigo-50 border border-indigo-100 rounded-xl p-5 flex items-center justify-between gap-4">
                            <div>
                                <p className="text-xs font-bold text-indigo-600 uppercase tracking-wide">🔐 Delivery OTP</p>
                                <p className="text-xs text-gray-500 mt-1 leading-snug">
                                    Give this 4-digit code to the delivery agent <strong className="text-gray-700">only after you receive your item</strong>.
                                </p>
                            </div>
                            <div className="text-3xl font-black text-indigo-700 tracking-[0.35em] shrink-0">
                                {order.delivery_otp}
                            </div>
                        </div>
                    )}
                </div>
            )}

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mt-8">
                <Link to="/accounts/profile/" className="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-6 py-3 rounded-xl shadow-sm transition">
                    View Live Tracking in Profile &rarr;
                </Link>
                <Link to="/products/" className="w-full sm:w-auto bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold px-6 py-3 rounded-xl transition">
                    Continue Shopping
                </Link>
            </div>
        </div>
    );
}