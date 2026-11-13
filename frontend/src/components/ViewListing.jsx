import React, { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function ViewListing() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [item, setItem] = useState(null);
    const [currentUser, setCurrentUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([
            fetch(`/api/products/items/${id}/`).then(res => res.json()),
            // me/ works for anonymous visitors too ({authenticated:false}) and
            // bootstraps the csrftoken cookie needed for the cart POST.
            api('/api/accounts/me/').then(res => res.ok ? res.json() : null)
        ])
        .then(([itemData, meData]) => {
            setItem(itemData);
            setCurrentUser(meData && meData.authenticated ? meData : null);
            setLoading(false);
        })
        .catch(err => {
            console.error("Error loading details", err);
            setLoading(false);
        });
    }, [id]);

    const addToCart = async () => {
        try {
            if (!currentUser) {
                alert("Please log in to add items to your cart.");
                return;
            }

            const res = await api(`/api/products/cart/add/${id}/`, { method: 'POST' });

            if (res.ok) {
                navigate('/orders/cart/');
            } else if (res.status === 401 || res.status === 403) {
                alert("Your session has expired. Please log in again.");
            } else {
                const errData = await res.json().catch(() => ({}));
                alert(errData.error || errData.detail || "Failed to add item to cart.");
            }
        } catch (err) {
            console.error("Error adding to cart", err);
        }
    };

    if (loading) return <div className="text-center py-20 text-gray-500">Loading item...</div>;
    if (!item) return <div className="text-center py-20 text-gray-500">Item not found.</div>;

    const username = currentUser?.username;
    const isOwner = item.is_owner === true || 
                    item.seller === username || 
                    item.seller_username === username;

    const isAvailable = item.status === 'AVAILABLE';

    return (
        <div className="max-w-7xl mx-auto px-4 py-12">
            <div className="mb-6">
                <Link to="/products/" className="inline-flex items-center text-sm font-semibold text-indigo-600 hover:text-indigo-800 transition">
                    &larr; Back to Marketplace Feed
                </Link>
            </div>

            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden grid grid-cols-1 lg:grid-cols-2 gap-8 p-6 md:p-8">
                <div className="w-full h-96 lg:h-[500px] bg-gray-100 rounded-xl overflow-hidden flex items-center justify-center relative">
                    {item.image ? (
                        <img src={item.image} alt={item.title} className="w-full h-full object-cover" />
                    ) : (
                        <span className="text-gray-400 font-medium">No Image Available</span>
                    )}
                    <div className="absolute top-4 left-4">
                        <span className="bg-white/90 backdrop-blur-sm text-indigo-600 text-xs px-3 py-1.5 rounded-full font-bold uppercase tracking-wide shadow-sm">
                            {item.condition_display || item.condition}
                        </span>
                    </div>
                </div>

                <div className="flex flex-col justify-between">
                    <div>
                        <div className="flex justify-between items-center text-sm mb-3">
                            <span className="font-bold text-indigo-600 uppercase tracking-wide">{item.category_display || item.category}</span>
                            <span className="text-gray-500 font-medium">📍 {item.location}</span>
                        </div>

                        <h1 className="text-3xl font-black text-gray-900 tracking-tight mb-4">{item.title}</h1>
                        <div className="text-3xl font-black text-emerald-600 mb-6">₹{item.price}</div>

                        <div className="border-t border-gray-100 pt-4 mb-6">
                            <h3 className="font-bold text-gray-800 mb-2">Description</h3>
                            <p className="text-gray-600 leading-relaxed whitespace-pre-line">{item.description}</p>
                        </div>
                    </div>
                    <div className="bg-gray-50 rounded-xl p-4 border border-gray-100 mb-8">
    <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Seller Information</h4>
    <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
            <p className="font-bold text-gray-800">@{item.seller_username || item.seller}</p>
            {item.seller_rating != null && (
                <span className="text-xs text-gray-600" title={`Average of ${item.seller_rating_count} buyer rating(s)`}>
                    <span className="text-amber-500 font-semibold">★ {item.seller_rating}</span> ({item.seller_rating_count})
                </span>
            )}
            {item.is_seller_verified && (
                <span className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 text-xs px-2.5 py-0.5 rounded-full font-bold border border-blue-100" title="Verified VendorPulse Seller">
                    <svg className="w-3.5 h-3.5 fill-current text-blue-600" viewBox="0 0 20 20">
                        <path d="M6.293 9.293a1 1 0 011.414 0L10 11.586l4.293-4.293a1 1 0 111.414 1.414l-5 5a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z"/>
                    </svg>
                    Verified Seller
                </span>
            )}
        </div>
        {item.seller_city && (
            <span className="text-xs bg-white border border-gray-200 text-gray-600 px-2.5 py-1 rounded-lg font-medium">
                City: {item.seller_city}
            </span>
        )}
    </div>
</div>

                    <div className="flex items-center gap-4 pt-4 border-t border-gray-100">
                        {isOwner ? (
                            <button disabled className="w-full bg-amber-50 text-amber-800 border border-amber-200 text-center font-semibold py-3 px-6 rounded-xl shadow-sm text-sm cursor-not-allowed opacity-80">
                                You are the seller yourself
                            </button>
                        ) : !isAvailable ? (
                            <button disabled className="w-full bg-gray-100 text-gray-500 border border-gray-200 text-center font-semibold py-3 px-6 rounded-xl shadow-sm text-sm cursor-not-allowed">
                                Item No Longer Available ({item.status})
                            </button>
                        ) : (
                            <button 
                                onClick={addToCart} 
                                className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 px-6 rounded-xl shadow-sm transition flex items-center justify-center gap-2">
                                🛒 Add to Cart</button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}