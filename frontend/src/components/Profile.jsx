import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

export default function Profile() {
    const [userInfo, setUserInfo] = useState({ username: '', email: '', date_joined: '' });
    const [formData, setFormData] = useState({ phone: '', city: '' });
    const [orders, setOrders] = useState([]);
    const [userListings, setUserListings] = useState([]);
    const [userSales, setUserSales] = useState([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState('');
    
    // State for separating active vs completed orders
    const [orderTab, setOrderTab] = useState('active');

    useEffect(() => {
        fetchProfileAndListings();
    }, []);

    const fetchProfileAndListings = async () => {
        try {
            const token = localStorage.getItem('authToken');
            const headers = {
                'Authorization': token ? `Token ${token}` : '',
                'Content-Type': 'application/json'
            };

            // 1. Fetch Profile, Orders, and Sales
            const profileRes = await fetch('/api/accounts/profile/', { headers });
            if (profileRes.ok) {
                const data = await profileRes.json();
                setUserInfo({
                    username: data.username || '',
                    email: data.email || '',
                    date_joined: data.date_joined || ''
                });
                setFormData({
                    phone: data.profile?.phone || data.phone || '',
                    city: data.profile?.city || data.city || ''
                });
                setOrders(data.orders || []);
                setUserSales(data.sales || []);
            }

            // 2. Fetch User's Active Listings
            const listingsRes = await fetch('/api/products/my-listings/', { headers });
            if (listingsRes.ok) {
                const listingsData = await listingsRes.json();
                setUserListings(Array.isArray(listingsData) ? listingsData : listingsData.results || []);
            }
        } catch (err) {
            console.error("Error loading profile data:", err);
        } finally {
            setLoading(false);
        }
    };

    const handleUpdateProfile = async (e) => {
        e.preventDefault();
        setSaving(true);
        setMessage('');
        try {
            const token = localStorage.getItem('authToken');
            const res = await fetch('/api/accounts/profile/', {
                method: 'PUT',
                headers: { 
                    'Authorization': token ? `Token ${token}` : '',
                    'Content-Type': 'application/json' 
                },
                body: JSON.stringify(formData)
            });
            if (res.ok) {
                setMessage('Profile updated successfully!');
            }
        } catch (err) {
            console.error("Failed to update profile:", err);
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return <div className="max-w-7xl mx-auto px-4 py-16 text-center text-gray-500">Loading profile...</div>;
    }

    // Filter orders into active and completed history based on status
    const activeOrders = orders.filter(o => o.status !== 'DELIVERED');
    const completedOrders = orders.filter(o => o.status === 'DELIVERED');
    const displayedOrders = orderTab === 'active' ? activeOrders : completedOrders;

    return (
        <div className="max-w-7xl mx-auto px-4 py-8">
            {/* Profile Header */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 md:p-8 mb-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div>
                    <span className="bg-indigo-50 text-indigo-600 text-xs px-3 py-1 rounded-full font-bold uppercase tracking-wide">
                        Member Account
                    </span>
                    <h1 className="text-3xl font-black text-gray-900 tracking-tight mt-2">
                        @{userInfo.username || 'Member'}
                    </h1>
                    <p className="text-gray-500 text-sm mt-0.5">
                        {userInfo.email} {userInfo.date_joined && `• Joined ${userInfo.date_joined}`}
                    </p>
                </div>
                
                {/* Header Action Links & Delivery Badge */}
                <div className="flex flex-wrap items-center justify-between gap-4 bg-white border border-gray-100 p-4 rounded-2xl shadow-sm">
                    <div className="flex flex-wrap items-center gap-3">
                        <Link 
                            to="/products/seller-dashboard/" 
                            className="inline-flex items-center gap-2 text-xs font-bold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-4 py-2.5 rounded-xl transition shadow-sm"
                        >
                            📊 View Seller Dashboard
                        </Link>
                        <Link 
                            to="/orders/track/" 
                            className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-bold px-5 py-2.5 rounded-xl shadow-sm hover:shadow transition-all text-xs tracking-wide"
                        >
                            <span>📦 Track Order</span>
                        </Link>
                    </div>

                    <div className="flex items-center gap-2">
                        <span className="inline-flex items-center gap-1.5 text-xs bg-emerald-50 text-emerald-700 px-3.5 py-2 rounded-xl font-bold border border-emerald-100 shadow-2xs">
                            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                            VendorPulse Delivery Active 🚚
                        </span>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Left Column: Update Profile Form */}
                <div className="lg:col-span-1">
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 sticky top-24">
                        <h2 className="text-xl font-bold text-gray-800 mb-4">Update Profile</h2>

                        {message && (
                            <div className="mb-4 p-2.5 bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-semibold rounded-lg">
                                {message}
                            </div>
                        )}

                        <form onSubmit={handleUpdateProfile} className="space-y-4">
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">Username</label>
                                <input
                                    type="text"
                                    value={userInfo.username}
                                    disabled
                                    className="w-full px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-gray-500 cursor-not-allowed"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">Phone Number</label>
                                <input
                                    type="text"
                                    value={formData.phone}
                                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                                    placeholder="Enter phone"
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">City / Location</label>
                                <input
                                    type="text"
                                    value={formData.city}
                                    onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                                    placeholder="Enter city"
                                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                                />
                            </div>

                            <button
                                type="submit"
                                disabled={saving}
                                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-xl shadow-sm transition"
                            >
                                {saving ? 'Saving...' : 'Save Changes'}
                            </button>
                        </form>
                    </div>
                </div>

                {/* Right 2 Columns: Accordions */}
                <div className="lg:col-span-2 space-y-6">
                    {/* 1. Past Orders Accordion (Separated Active vs Completed) */}
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
                                                    <span className="text-emerald-600 font-black text-lg">₹{order.total_price}</span>
                                                </div>

                                                {order.items && order.items.length > 0 && (
                                                    <div className="py-3 space-y-2">
                                                        <p className="text-xs font-bold text-gray-400 uppercase tracking-wider">Items in this order:</p>
                                                        <ul className="text-sm text-gray-700 space-y-1">
                                                            {order.items.map((oi, idx) => (
                                                                <li key={idx} className="flex justify-between">
                                                                    <span>{oi.item_title}</span>
                                                                    <span className="font-semibold">₹{oi.item_price}</span>
                                                                </li>
                                                            ))}
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
                    </div>

                    {/* 2. My Listed Items Accordion */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                        <details className="group p-6 md:p-8" open>
                            <summary className="flex justify-between items-center cursor-pointer list-none select-none">
                                <div className="flex items-center gap-3">
                                    <h2 className="text-xl font-bold text-gray-800">My Listed Items</h2>
                                    <span className="bg-gray-100 text-gray-700 text-xs font-bold px-2.5 py-0.5 rounded-full">
                                        {userListings.length}
                                    </span>
                                </div>
                                <span className="transform group-open:rotate-180 transition duration-200 text-indigo-600 font-bold">▼</span>
                            </summary>

                            <div className="mt-6 pt-6 border-t border-gray-100">
                                {userListings.length > 0 ? (
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        {userListings.map((item) => (
                                            <div key={item.id} className="border border-gray-200 rounded-xl p-4 flex gap-4 items-center">
                                                <div className="w-16 h-16 bg-gray-100 rounded-lg overflow-hidden flex-shrink-0">
                                                    {item.image ? (
                                                        <img src={item.image} alt={item.title} className="w-full h-full object-cover" />
                                                    ) : (
                                                        <div className="w-full h-full flex items-center justify-center text-xs text-gray-400">No img</div>
                                                    )}
                                                </div>
                                                <div className="flex-grow min-w-0">
                                                    <h4 className="font-bold text-gray-800 text-sm truncate">{item.title}</h4>
                                                    <p className="text-emerald-600 font-bold text-sm">₹{item.price}</p>
                                                    <div className="flex gap-3 mt-1">
                                                        <Link to={`/products/${item.id}/`} className="text-xs text-indigo-600 font-semibold hover:underline">
                                                            View
                                                        </Link>
                                                        <Link to={`/products/listing/edit/${item.id}/`} className="text-xs text-gray-600 font-semibold hover:underline">
                                                            Edit
                                                        </Link>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-center py-12 border-2 border-dashed border-gray-100 rounded-xl">
                                        <p className="text-gray-400 text-sm">You haven't listed any items for sale yet.</p>
                                    </div>
                                )}
                            </div>
                        </details>
                    </div>

                    {/* 3. Items Sold Accordion */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                        <details className="group p-6 md:p-8">
                            <summary className="flex justify-between items-center cursor-pointer list-none select-none">
                                <div className="flex items-center gap-3">
                                    <h2 className="text-xl font-bold text-gray-800">Items You've Sold</h2>
                                    <span className="bg-indigo-50 text-indigo-700 text-xs font-bold px-2.5 py-0.5 rounded-full border border-indigo-100">
                                        {userSales.length} Sold
                                    </span>
                                </div>
                                <span className="transform group-open:rotate-180 transition duration-200 text-indigo-600 font-bold">▼</span>
                            </summary>

                            <div className="mt-6 pt-6 border-t border-gray-100">
                                {userSales.length > 0 ? (
                                    <div className="space-y-4">
                                        {userSales.map((sale) => (
                                            <div key={sale.id} className="border border-gray-200 rounded-xl p-5 bg-white">
                                                <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                                                    <div>
                                                        <span className="text-xs font-bold text-indigo-600 uppercase">Item Purchased</span>
                                                        <h3 className="font-bold text-gray-900 text-base mt-0.5">{sale.item_title}</h3>
                                                    </div>
                                                    <span className="text-emerald-600 font-black text-lg">₹{sale.item_price}</span>
                                                </div>
                                                <div className="py-3 text-xs space-y-1 text-gray-600">
                                                    <p><strong className="text-gray-800">Buyer:</strong> @{sale.buyer}</p>
                                                    <p><strong className="text-gray-800">Delivery Address:</strong> {sale.shipping_address}</p>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-center py-12 border-2 border-dashed border-gray-100 rounded-xl">
                                        <p className="text-gray-400 text-sm font-medium">No sales recorded yet.</p>
                                    </div>
                                )}
                            </div>
                        </details>
                    </div>
                </div>
            </div>
        </div>
    );
}