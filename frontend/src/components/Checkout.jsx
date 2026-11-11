import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';

export default function Checkout() {
    const navigate = useNavigate();
    const [cartItems, setCartItems] = useState([]);
    const [totalPrice, setTotalPrice] = useState(0);
    const [formData, setFormData] = useState({
        full_name: '',
        phone: '',
        address: ''
    });

    useEffect(() => {
        const fetchCartData = async () => {
            try {
                const token = localStorage.getItem('authToken');
                const res = await fetch('/api/products/cart/', {
                    headers: {
                        'Authorization': token ? `Token ${token}` : '',
                        'Content-Type': 'application/json'
                    }
                });

                if (res.ok) {
                    const data = await res.json();
                    const itemsList = Array.isArray(data) ? data : (data.items || data.results || []);
                    setCartItems(itemsList);
                    
                    // Calculate subtotal safely if total_price is missing from root response
                    const calculatedTotal = itemsList.reduce((acc, ci) => {
                        const itemObj = ci.item || ci;
                        const price = parseFloat(itemObj.price || ci.price || 0);
                        const qty = parseInt(ci.quantity || 1, 10);
                        return acc + (price * qty);
                    }, 0);

                    setTotalPrice(data.total_price || calculatedTotal);
                }
            } catch (err) {
                console.error("Failed to load cart for checkout", err);
            }
        };

        fetchCartData();
    }, []);

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const token = localStorage.getItem('authToken');
            const res = await fetch('/api/products/checkout/', {
                method: 'POST',
                headers: {
                    'Authorization': token ? `Token ${token}` : '',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            const data = await res.json();
            if (res.ok) {
                const orderId = data.order_id || data.id;
                navigate(`/products/success/${orderId}/`);
            } else {
                console.error("Checkout submission failed", data);
            }
        } catch (err) {
            console.error("Checkout network error", err);
        }
    };

    return (
        <div className="max-w-4xl mx-auto px-4 py-8">
            <div className="mb-8 border-b border-gray-200 pb-4">
                <Link to="/orders/cart/" className="text-sm font-semibold text-indigo-600 hover:text-indigo-800 transition inline-block mb-2">
                    &larr; Back to Cart
                </Link>
                <h1 className="text-3xl font-black text-gray-900 tracking-tight">Checkout</h1>
                <p className="text-gray-500 text-sm mt-1">Review your order details and confirm your purchase.</p>
            </div>

            <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-8">
                <div className="md:col-span-2 space-y-6">
                    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
                        <h2 className="text-xl font-bold text-gray-800 mb-4">Delivery & Contact Information</h2>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">Full Name</label>
                                <input type="text" required value={formData.full_name} onChange={e => setFormData({...formData, full_name: e.target.value})} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">Phone Number</label>
                                <input type="tel" required placeholder="10-digit mobile number" value={formData.phone} onChange={e => setFormData({...formData, phone: e.target.value})} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">Delivery Address / City</label>
                                <textarea rows="3" required placeholder="Enter street address..." value={formData.address} onChange={e => setFormData({...formData, address: e.target.value})} className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"></textarea>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="md:col-span-1">
                    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 sticky top-24">
                        <h2 className="text-xl font-bold text-gray-800 mb-4">Order Summary</h2>
                        <div className="space-y-3 max-h-60 overflow-y-auto mb-4 pr-1">
                            {cartItems.map((ci, idx) => {
                                const item = ci.item || ci;
                                return (
                                    <div key={idx} className="flex justify-between text-sm">
                                        <span className="text-gray-600 truncate max-w-[150px]">{item.title || ci.title}</span>
                                        <span className="font-semibold text-gray-800">₹{item.price || ci.price}</span>
                                    </div>
                                );
                            })}
                        </div>
                        <div className="flex justify-between items-center text-lg font-black text-gray-900 mb-6 border-t pt-4">
                            <span>Total Amount</span>
                            <span className="text-emerald-600">₹{totalPrice}</span>
                        </div>
                        <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-xl shadow-sm transition flex items-center justify-center gap-2">
                            Place Order
                        </button>
                    </div>
                </div>
            </form>
        </div>
    );
}