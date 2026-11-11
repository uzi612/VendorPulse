import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';

export default function SellerDashboard() {
    const navigate = useNavigate();
    const [dashboardData, setDashboardData] = useState({
        total_revenue: 0,
        completed_payouts: 0,
        pending_payouts: 0,
        active_listings_count: 0,
        sold_items_count: 0,
        recent_sales: []
    });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchSellerData();
    }, []);

    const fetchSellerData = async () => {
        try {
            const token = localStorage.getItem('authToken');
            const res = await fetch('/api/products/seller-dashboard/', {
                method: 'GET',
                headers: {
                    'Authorization': token ? `Token ${token}` : '',
                    'Content-Type': 'application/json'
                }
            });

            if (res.ok) {
                const data = await res.json();
                setDashboardData(data);
            } else {
                console.error("Failed to load seller metrics");
            }
        } catch (err) {
            console.error("Error fetching seller dashboard data:", err);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <div className="max-w-7xl mx-auto px-4 py-16 text-center text-gray-500 font-medium">Loading seller dashboard...</div>;
    }

    return (
        <div className="max-w-7xl mx-auto px-4 py-8">
            {/* Header */}
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4 border-b border-gray-200 pb-4">
                <div>
                    <span className="bg-indigo-50 text-indigo-600 text-xs px-3 py-1 rounded-full font-bold uppercase tracking-wide">
                        Vendor Analytics
                    </span>
                    <h1 className="text-3xl font-black text-gray-900 tracking-tight mt-1">Seller Earnings Dashboard</h1>
                </div>
                <button 
                    onClick={() => navigate(-1)} 
                    className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-xl text-sm font-semibold shadow-sm transition"
                >
                    &larr; Back
                </button>
            </div>

            {/* Financial Metric Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 flex items-center justify-between">
                    <div>
                        <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">Total Revenue</p>
                        <h3 className="text-3xl font-black text-gray-900 mt-2">₹{dashboardData.total_revenue}</h3>
                    </div>
                    <div className="w-12 h-12 bg-indigo-50 rounded-xl flex items-center justify-center text-indigo-600 font-bold text-xl">
                        ₹
                    </div>
                </div>

                <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 flex items-center justify-between">
                    <div>
                        <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">Cleared Payouts</p>
                        <h3 className="text-3xl font-black text-emerald-600 mt-2">₹{dashboardData.completed_payouts}</h3>
                    </div>
                    <div className="w-12 h-12 bg-emerald-50 rounded-xl flex items-center justify-center text-emerald-600 font-bold text-xl">
                        ✓
                    </div>
                </div>

                <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 flex items-center justify-between">
                    <div>
                        <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">Pending Payouts</p>
                        <h3 className="text-3xl font-black text-amber-600 mt-2">₹{dashboardData.pending_payouts}</h3>
                    </div>
                    <div className="w-12 h-12 bg-amber-50 rounded-xl flex items-center justify-center text-amber-600 font-bold text-xl">
                        ⏳
                    </div>
                </div>
            </div>

            {/* Listings Status Summary */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 flex justify-between items-center">
                    <div>
                        <h4 className="text-gray-500 text-sm font-medium">Active Listings</h4>
                        <p className="text-2xl font-black text-gray-800 mt-1">{dashboardData.active_listings_count} Items</p>
                    </div>
                    <Link to="/products/listing/" className="text-xs font-semibold text-indigo-600 hover:underline">
                        Manage Listings &rarr;
                    </Link>
                </div>

                <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 flex justify-between items-center">
                    <div>
                        <h4 className="text-gray-500 text-sm font-medium">Sold / Reserved Items</h4>
                        <p className="text-2xl font-black text-gray-800 mt-1">{dashboardData.sold_items_count} Items</p>
                    </div>
                    <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-3 py-1 rounded-full">
                        Fulfilled
                    </span>
                </div>
            </div>

            {/* Recent Sales Table */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden p-6 md:p-8">
                <h2 className="text-xl font-bold text-gray-800 mb-6">Recent Sales History</h2>

                {dashboardData.recent_sales && dashboardData.recent_sales.length > 0 ? (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="border-b border-gray-100 text-xs font-bold text-gray-400 uppercase tracking-wider">
                                    <th className="pb-3">Order ID</th>
                                    <th className="pb-3">Item Title</th>
                                    <th className="pb-3">Buyer</th>
                                    <th className="pb-3">Price</th>
                                    <th className="pb-3">Status</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50 text-sm text-gray-700">
                                {dashboardData.recent_sales.map((sale, idx) => (
                                    <tr key={idx} className="hover:bg-gray-50 transition">
                                        <td className="py-4 font-bold text-indigo-600">#{sale.order_id}</td>
                                        <td className="py-4 font-semibold text-gray-900">{sale.item_title}</td>
                                        <td className="py-4 text-gray-500">@{sale.buyer}</td>
                                        <td className="py-4 font-bold text-emerald-600">₹{sale.item_price}</td>
                                        <td className="py-4">
                                            <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-indigo-50 text-indigo-700">
                                                {sale.status}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div className="text-center py-12 border-2 border-dashed border-gray-100 rounded-xl">
                        <p className="text-gray-400 text-sm font-medium">No sales recorded on your account yet.</p>
                    </div>
                )}
            </div>
        </div>
    );
}