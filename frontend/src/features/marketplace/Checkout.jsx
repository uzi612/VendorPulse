import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../../api';

// Pincode-first checkout: the buyer types their 6-digit pincode and the
// backend resolves the delivery city + zone from its pincode ranges - so
// there is no city dropdown and no long address box, just a short optional
// detail (flat / house no., landmark).
export default function Checkout() {
    const navigate = useNavigate();
    const [cartItems, setCartItems] = useState([]);
    const [totalPrice, setTotalPrice] = useState(0);
    const [formData, setFormData] = useState({
        full_name: '',
        phone: '',
        pincode: '',
        address: ''
    });
    // Resolved zone from the pincode: { zone_id, zone_name, city } | null
    const [resolvedZone, setResolvedZone] = useState(null);
    const [zoneError, setZoneError] = useState('');
    // Live price preview from /checkout/quote/ (per-item delivery + totals).
    const [quote, setQuote] = useState(null);
    const [quoteError, setQuoteError] = useState('');
    const [submitError, setSubmitError] = useState('');
    const [placing, setPlacing] = useState(false);
    const resolveTimer = useRef(null);

    useEffect(() => {
        const fetchCartData = async () => {
            try {
                const res = await api('/api/products/cart/');

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

    // Debounced live pincode resolution: resolves once 6 digits are typed.
    const handlePincodeChange = (pincode) => {
        setFormData({ ...formData, pincode });
        setResolvedZone(null);
        setZoneError('');
        setQuote(null);
        setQuoteError('');

        if (resolveTimer.current) clearTimeout(resolveTimer.current);
        if (!/^\d{6}$/.test(pincode)) return;   // only resolve a complete pincode

        resolveTimer.current = setTimeout(async () => {
            try {
                const res = await api(`/api/locations/zones/resolve/?pincode=${pincode}`);
                const data = await res.json();
                if (res.ok) {
                    setResolvedZone(data);
                } else {
                    setZoneError(data.error || "We don't deliver to this pincode yet.");
                }
            } catch (err) {
                console.error("Pincode resolution failed", err);
                setZoneError("Could not verify the pincode. Please try again.");
            }
        }, 350);
    };

    useEffect(() => () => resolveTimer.current && clearTimeout(resolveTimer.current), []);

    // Once the pincode resolves, price the cart exactly as checkout will:
    // /checkout/quote/ applies the same intra-city / intercity rate per item.
    useEffect(() => {
        if (!resolvedZone || !formData.pincode || cartItems.length === 0) {
            setQuote(null);
            return;
        }
        let cancelled = false;
        (async () => {
            try {
                const res = await api(`/api/products/checkout/quote/?pincode=${formData.pincode}`);
                const data = await res.json();
                if (cancelled) return;
                if (res.ok) {
                    setQuote(data);
                    setQuoteError('');
                } else {
                    setQuote(null);
                    setQuoteError(data.error || 'Could not calculate the delivery charge.');
                }
            } catch (err) {
                if (!cancelled) setQuoteError('Could not calculate the delivery charge.');
            }
        })();
        return () => { cancelled = true; };
    }, [resolvedZone, formData.pincode, cartItems]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSubmitError('');
        if (!resolvedZone) {
            setSubmitError("Please enter a valid 6-digit pincode we deliver to.");
            return;
        }
        setPlacing(true);
        try {
            const res = await api('/api/products/checkout/', {
                method: 'POST',
                body: JSON.stringify(formData)
            });

            const data = await res.json();
            if (res.ok) {
                const orderId = data.order_id || data.id;
                navigate(`/orders/success/${orderId}/`);
            } else {
                setSubmitError(data.error || "Checkout failed. Please try again.");
                console.error("Checkout submission failed", data);
            }
        } catch (err) {
            console.error("Checkout network error", err);
            setSubmitError("Network error. Please try again.");
        } finally {
            setPlacing(false);
        }
    };

    const inputCls = "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none";

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
                                <input type="text" required value={formData.full_name} onChange={e => setFormData({...formData, full_name: e.target.value})} className={inputCls} />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">Phone Number</label>
                                <input type="tel" required placeholder="10-digit mobile number" value={formData.phone} onChange={e => setFormData({...formData, phone: e.target.value})} className={inputCls} />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">Delivery Pincode</label>
                                <input
                                    type="text"
                                    inputMode="numeric"
                                    pattern="\d{6}"
                                    maxLength={6}
                                    required
                                    placeholder="6-digit pincode"
                                    value={formData.pincode}
                                    onChange={e => handlePincodeChange(e.target.value.replace(/\D/g, ''))}
                                    className={inputCls}
                                />
                                {/* Zone confirmation badge: shows which city/zone the
                                    pincode resolves to, so the buyer sees delivery
                                    coverage before placing the order. */}
                                {resolvedZone && (
                                    <div className="mt-2 inline-flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm font-semibold px-3 py-1.5 rounded-lg">
                                        <span className="w-2 h-2 bg-emerald-500 rounded-full"></span>
                                        Delivering to {resolvedZone.city} &middot; {resolvedZone.zone_name}
                                    </div>
                                )}
                                {zoneError && (
                                    <div className="mt-2 inline-flex items-center gap-2 bg-red-50 border border-red-200 text-red-600 text-sm font-semibold px-3 py-1.5 rounded-lg">
                                        {zoneError}
                                    </div>
                                )}
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">
                                    Address Detail <span className="font-normal text-gray-400">(optional - flat / house no., landmark)</span>
                                </label>
                                <input
                                    type="text"
                                    maxLength={255}
                                    placeholder="e.g. Flat 402, Sunrise Apartments"
                                    value={formData.address}
                                    onChange={e => setFormData({...formData, address: e.target.value})}
                                    className={inputCls}
                                />
                            </div>
                        </div>
                    </div>
                </div>

                <div className="md:col-span-1">
                    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 sticky top-24">
                        <h2 className="text-xl font-bold text-gray-800 mb-4">Order Summary</h2>
                        <div className="space-y-3 max-h-60 overflow-y-auto mb-4 pr-1">
                            {(quote?.items || cartItems.map((ci) => {
                                const item = ci.item || ci;
                                return { title: item.title || ci.title, price: item.price || ci.price };
                            })).map((line, idx) => (
                                <div key={idx} className="text-sm">
                                    <div className="flex justify-between">
                                        <span className="text-gray-600 truncate max-w-[150px]">{line.title}</span>
                                        <span className="font-semibold text-gray-800">₹{line.price}</span>
                                    </div>
                                    {line.delivery_charge && (
                                        <div className="flex justify-between text-[11px] text-gray-400">
                                            <span>{line.is_intercity ? 'Intercity delivery' : 'Same-city delivery'}</span>
                                            <span>₹{line.delivery_charge}</span>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>

                        {/* Live price breakdown: item subtotal + per-item delivery. */}
                        <div className="space-y-2 text-sm border-t pt-4 mb-2">
                            <div className="flex justify-between text-gray-600">
                                <span>Item Subtotal</span>
                                <span className="font-semibold text-gray-900">₹{quote ? quote.subtotal : totalPrice}</span>
                            </div>
                            <div className="flex justify-between text-gray-600">
                                <span>Delivery Charge</span>
                                <span className="font-semibold text-emerald-600">
                                    {quote ? `₹${quote.delivery_charge}` : 'from ₹39 / item'}
                                </span>
                            </div>
                        </div>
                        <div className="flex justify-between items-center text-lg font-black text-gray-900 mb-4 border-t pt-3">
                            <span>Total Payable</span>
                            <span className="text-emerald-600">₹{quote ? quote.total_price : totalPrice}</span>
                        </div>
                        {quoteError && (
                            <p className="text-xs text-red-600 font-semibold mb-3">{quoteError}</p>
                        )}
                        {resolvedZone && (
                            <div className="flex justify-between items-center text-sm text-gray-500 mb-4">
                                <span>Delivery zone</span>
                                <span className="font-semibold text-gray-700">{resolvedZone.zone_name}, {resolvedZone.city}</span>
                            </div>
                        )}
                        {submitError && (
                            <p className="text-sm text-red-600 font-semibold mb-3">{submitError}</p>
                        )}
                        <button
                            type="submit"
                            disabled={placing || !resolvedZone}
                            className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl shadow-sm transition flex items-center justify-center gap-2"
                        >
                            {placing ? 'Placing Order...' : 'Place Order'}
                        </button>
                    </div>
                </div>
            </form>
        </div>
    );
}
