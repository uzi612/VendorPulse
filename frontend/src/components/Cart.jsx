import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function Cart() {
    const navigate = useNavigate();
    const [cartItems, setCartItems] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchCart();
    }, []);

    const fetchCart = async () => {
        try {
            const res = await api('/api/products/cart/', { method: 'GET' });

            if (res.ok) {
                const data = await res.json();
                const itemsList = Array.isArray(data) ? data : (data.items || data.results || data.cart_items || []);
                setCartItems(itemsList);
            } else {
                console.error("Failed to fetch cart items");
            }
        } catch (err) {
            console.error("Error loading cart:", err);
        } finally {
            setLoading(false);
        }
    };

    const handleRemoveItem = async (cartItemId) => {
        try {
            const res = await api(`/api/products/cart/remove/${cartItemId}/`, { method: 'DELETE' });

            if (res.ok) {
                fetchCart();
            } else {
                console.error("Failed to remove item from cart");
            }
        } catch (err) {
            console.error("Error removing item:", err);
        }
    };

    const totalPrice = cartItems.reduce((acc, cartItem) => {
        const itemObj = cartItem.item || cartItem;
        const price = parseFloat(itemObj.price || cartItem.price || 0);
        const qty = parseInt(cartItem.quantity || 1, 10);
        return acc + (price * qty);
    }, 0);

    if (loading) {
        return <div className="max-w-7xl mx-auto px-4 py-20 text-center text-gray-500 font-medium">Loading your cart...</div>;
    }

    return (
        <div className="max-w-7xl mx-auto px-4 py-8">
            <div className="mb-8 border-b border-gray-200 pb-4">
                <h1 className="text-3xl font-black text-gray-900 tracking-tight">Shopping Cart</h1>
                <p className="text-gray-500 text-sm mt-1">Review your selected items before proceeding to secure checkout.</p>
            </div>

            {cartItems.length > 0 ? (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <div className="lg:col-span-2 space-y-4">
                        {cartItems.map((cartItem, index) => {
                            const item = cartItem.item || cartItem;
                            const title = item.title || cartItem.title || 'Product Item';
                            const price = item.price || cartItem.price || 0;
                            const image = item.image || cartItem.image;
                            const uniqueId = cartItem.id || item.id;

                            return (
                                <div key={uniqueId || index} className="bg-white rounded-2xl p-4 sm:p-6 shadow-sm border border-gray-100 flex flex-col sm:flex-row items-center justify-between gap-4">
                                    <div className="flex items-center gap-4 w-full sm:w-auto">
                                        <div className="w-20 h-20 bg-gray-100 rounded-xl overflow-hidden flex-shrink-0 flex items-center justify-center">
                                            {image ? (
                                                <img src={image} alt={title} className="w-full h-full object-cover" />
                                            ) : (
                                                <span className="text-xs text-gray-400 font-medium">No Img</span>
                                            )}
                                        </div>
                                        <div>
                                            <h3 className="font-bold text-gray-900 text-base">{title}</h3>
                                            <p className="text-emerald-600 font-black text-lg mt-1">₹{price}</p>
                                            <span className="text-xs text-gray-400 font-medium">Qty: {cartItem.quantity || 1}</span>
                                        </div>
                                    </div>

                                    <button 
                                        onClick={() => handleRemoveItem(uniqueId)}
                                        className="text-red-500 hover:text-red-700 text-sm font-semibold bg-red-50 hover:bg-red-100 px-4 py-2 rounded-xl transition w-full sm:w-auto text-center"
                                    >
                                        Remove
                                    </button>
                                </div>
                            );
                        })}
                    </div>

                    <div className="lg:col-span-1">
                        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 sticky top-24">
                            <h2 className="text-xl font-bold text-gray-800 mb-4">Order Summary</h2>

                            <div className="space-y-3 pb-6 border-b border-gray-100 text-sm">
                                <div className="flex justify-between text-gray-600">
                                    <span>Subtotal</span>
                                    <span className="font-semibold text-gray-900">₹{totalPrice}</span>
                                </div>
                                <div className="flex justify-between text-gray-600">
                                    <span>Delivery Fee</span>
                                    <span className="text-emerald-600 font-semibold">FREE</span>
                                </div>
                            </div>

                            <div className="flex justify-between items-center py-4">
                                <span className="font-bold text-gray-900 text-base">Total Amount</span>
                                <span className="font-black text-2xl text-indigo-600">₹{totalPrice}</span>
                            </div>

                            <button 
                                onClick={() => navigate('/products/checkout/')}
                                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-xl shadow-sm transition text-center block mt-2"
                            >
                                Proceed to Checkout
                            </button>
                        </div>
                    </div>
                </div>
            ) : (
                <div className="text-center py-20 bg-white rounded-2xl border border-gray-100 shadow-sm max-w-2xl mx-auto">
                    <div className="w-16 h-16 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl">
                        🛒
                    </div>
                    <h2 className="text-2xl font-bold text-gray-900">Your cart is empty</h2>
                    <p className="text-gray-500 text-sm mt-1 mb-6">Looks like you haven't added any items to your cart yet.</p>
                    <Link 
                        to="/products/" 
                        className="inline-block bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-6 py-3 rounded-xl transition shadow-sm"
                    >
                        Start Shopping &rarr;
                    </Link>
                </div>
            )}
        </div>
    );
}