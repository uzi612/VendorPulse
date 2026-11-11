import React, { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';

export default function OrderSuccess() {
    const { id } = useParams();
    const [order, setOrder] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchOrderDetails = async () => {
            try {
                const token = localStorage.getItem('authToken');
                const res = await fetch(`/api/products/success/${id}/`, {
                    headers: {
                        'Authorization': token ? `Token ${token}` : '',
                        'Content-Type': 'application/json'
                    }
                });

                if (res.ok) {
                    const data = await res.json();
                    setOrder(data);
                }
            } catch (err) {
                console.error("Error fetching order success details", err);
            } finally {
                setLoading(false);
            }
        };

        fetchOrderDetails();
    }, [id]);

    if (loading) {
        return <div className="max-w-7xl mx-auto px-4 py-20 text-center text-gray-500 font-medium">Loading confirmation...</div>;
    }

    return (
        <div className="max-w-3xl mx-auto px-4 py-16 text-center">
            <div className="w-20 h-20 bg-emerald-50 text-emerald-600 rounded-full flex items-center justify-center mx-auto mb-6 text-3xl shadow-sm">
                ✓
            </div>
            <h1 className="text-3xl font-black text-gray-900 tracking-tight">Order Placed Successfully!</h1>
            <p className="text-gray-500 text-sm mt-2 mb-8">Thank you for your purchase. Your order #{id} has been confirmed and forwarded to the seller.</p>

            {order && (
                <div className="bg-white rounded-2xl p-6 md:p-8 shadow-sm border border-gray-100 text-left mb-8">
                    <div className="flex justify-between items-center border-b border-gray-100 pb-4 mb-4">
                        <span className="text-sm font-bold text-gray-400 uppercase tracking-wider">Order Summary</span>
                        <span className="text-indigo-600 font-bold">Total: ₹{order.total_amount}</span>
                    </div>
                    <div className="space-y-3 mb-6">
                        {order.items?.map((item, idx) => (
                            <div key={idx} className="flex justify-between text-sm text-gray-700">
                                <span>{item.item_title} (x{item.quantity})</span>
                                <span className="font-semibold">₹{item.item_price}</span>
                            </div>
                        ))}
                    </div>
                    <div className="border-t border-gray-100 pt-4 text-xs text-gray-500">
                        <p><span className="font-bold text-gray-700">Shipping Address:</span> {order.shipping_address}</p>
                    </div>
                </div>
            )}

            <div className="flex justify-center gap-4">
                <Link to="/products/" className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-6 py-3 rounded-xl transition shadow-sm">
                    Continue Shopping &rarr;
                </Link>
            </div>
        </div>
    );
}