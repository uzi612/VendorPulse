import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api';
import { CITIES } from '../../cities';
import { useToast } from '../../components/Toast';

export default function Listings() {
    const toast = useToast();
    const [userItems, setUserItems] = useState([]);
    const [formData, setFormData] = useState({
        title: '',
        description: '',
        price: '',
        category: '',
        condition: '',
        location: '',
        zone: '',
        address: '',
        image: null
    });
    const [zones, setZones] = useState([]);   // zones of the selected city
    const [deleteTarget, setDeleteTarget] = useState(null);   // item pending delete confirmation

    useEffect(() => {
        fetchUserListings();
    }, []);

    const fetchUserListings = async () => {
        try {
            const res = await api('/api/products/my-listings/', { method: 'GET' });
            const data = await res.json();
            setUserItems(Array.isArray(data) ? data : data.results || []);
        } catch (err) {
            console.error("Error loading listings", err);
        }
    };

    const handleChange = (e) => {
        if (e.target.name === 'image') {
            setFormData({ ...formData, image: e.target.files[0] });
        } else if (e.target.name === 'location') {
            const city = e.target.value;
            setFormData({ ...formData, location: city, zone: '' });
            // Zone pickers need the zones of the chosen city. A seller without
            // a zone can leave this empty -> city-wide assignment fallback.
            if (city) {
                api(`/api/locations/zones/?city=${encodeURIComponent(city)}`)
                    .then(res => res.ok ? res.json() : { results: [] })
                    .then(data => setZones(data.results || []))
                    .catch(() => setZones([]));
            } else {
                setZones([]);
            }
        } else {
            setFormData({ ...formData, [e.target.name]: e.target.value });
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        const data = new FormData();
        Object.keys(formData).forEach((key) => {
            if (formData[key]) data.append(key, formData[key]);
        });

        try {
            const res = await api('/api/products/items/', {
                method: 'POST',
                body: data
            });
            if (res.ok) {
                toast.success('Listing posted! It is awaiting admin review and will appear on the marketplace once approved.');
                setFormData({ title: '', description: '', price: '', category: '', condition: '', location: '', zone: '', address: '', image: null });
                setZones([]);
                fetchUserListings();
            }
        } catch (err) {
            console.error("Failed to post listing", err);
        }
    };

    const handleDelete = (item) => {
        // Opens the in-app confirmation modal instead of window.confirm,
        // which shows an ugly "localhost says..." dialog.
        setDeleteTarget(item);
    };

    const confirmDelete = async () => {
        const id = deleteTarget?.id;
        setDeleteTarget(null);
        if (!id) return;

        try {
            const res = await api(`/api/products/items/${id}/`, { method: 'DELETE' });

            if (res.ok || res.status === 204) {
                toast.success('Listing deleted.');
                // Refresh local items state
                setUserItems(userItems.filter(item => item.id !== id));
            } else {
                toast.error('Could not delete this listing. Please try again.');
            }
        } catch (err) {
            toast.error('Something went wrong while deleting. Please try again.');
            console.error("Error deleting listing", err);
        }
    };

    return (
        <div className="max-w-7xl mx-auto px-4 py-8">
            <div className="mb-8 border-b border-gray-200 pb-4">
                <h1 className="text-3xl font-black text-gray-900 tracking-tight">My Listings Dashboard</h1>
                <p className="text-gray-500 text-sm mt-1">Post new items for sale or manage your active classifieds.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Left Column: Add New Listing Form */}
                <div className="lg:col-span-1">
                    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 sticky top-24">
                        <h2 className="text-xl font-bold text-gray-800 mb-4">Post a New Item</h2>
                        
                        <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">Title</label>
                                <input type="text" name="title" value={formData.title} onChange={handleChange} required className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">Description</label>
                                <textarea name="description" value={formData.description} onChange={handleChange} rows="3" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"></textarea>
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">Price (₹)</label>
                                <input type="number" name="price" value={formData.price} onChange={handleChange} required className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">Condition</label>
                                <select name="condition" value={formData.condition} onChange={handleChange} required className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
                                    <option value="">Select Condition</option>
                                    <option value="NEW">Brand New</option>
                                    <option value="LIKE_NEW">Like New</option>
                                    <option value="GOOD">Good</option>
                                    <option value="FAIR">Fair</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">City</label>
                                <select name="location" value={formData.location} onChange={handleChange} required className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
                                    <option value="">Select City</option>
                                    {CITIES.map(city => <option key={city} value={city}>{city}</option>)}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">
                                    Pickup Zone <span className="font-normal text-gray-400">(optional)</span>
                                </label>
                                <select
                                    name="zone"
                                    value={formData.zone}
                                    onChange={handleChange}
                                    disabled={!formData.location}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white disabled:bg-gray-50 disabled:text-gray-400"
                                >
                                    <option value="">Entire city (auto-assign anywhere)</option>
                                    {zones.map(z => (
                                        <option key={z.id} value={z.id}>
                                            {z.name} ({z.pincode_from}-{z.pincode_to})
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">Pickup Address</label>
                                <input type="text" name="address" value={formData.address} onChange={handleChange} placeholder="Street / area for agent pickup" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
                            </div>
                            <div>
                                <label className="block text-sm font-semibold text-gray-700 mb-1">Image</label>
                                <input type="file" name="image" onChange={handleChange} className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100" />
                            </div>

                            <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2.5 rounded-lg transition shadow-sm mt-4">
                                Publish Listing
                            </button>
                        </form>
                    </div>
                </div>

                {/* Right Column: User's Listed Items Feed */}
                <div className="lg:col-span-2">
                    <h2 className="text-xl font-bold text-gray-800 mb-4">Your Active Items ({userItems.length})</h2>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                        {userItems.length > 0 ? (
                            userItems.map((item) => (
                                <div key={item.id} className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-md transition flex flex-col">
                                    <div className="relative">
                                        {item.image ? (
                                            <img src={item.image} alt={item.title} className="w-full h-44 object-cover" />
                                        ) : (
                                            <div className="w-full h-44 bg-gray-100 flex items-center justify-center text-gray-400 text-sm">No Image</div>
                                        )}
                                        <div className="absolute top-3 right-3">
                                            <span className="bg-emerald-100 text-emerald-800 text-xs px-2.5 py-1 rounded-full font-bold shadow-sm">{item.status || 'Available'}</span>
                                        </div>
                                    </div>
                                    
                                    <div className="p-4 flex flex-col flex-grow">
                                        <h3 className="font-bold text-gray-800 text-lg line-clamp-1">{item.title}</h3>
                                        <p className="text-gray-500 text-sm mt-1 line-clamp-2 flex-grow">{item.description}</p>
                                        
                                        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
                                            <span className="text-xl font-black text-emerald-600">₹{item.price}</span>
                                            
                                            {/* Edit & Delete Action Buttons */}
                                            <div className="flex items-center gap-2">
                                                <Link 
                                                    to={`/products/listing/edit/${item.id}/`} 
                                                    className="bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-1.5 rounded-lg font-semibold text-xs transition"
                                                >
                                                    Edit
                                                </Link>
                                                <button 
                                                    onClick={() => handleDelete(item)}
                                                    className="bg-red-50 hover:bg-red-100 text-red-600 px-3 py-1.5 rounded-lg font-semibold text-xs transition"
                                                >
                                                    Delete
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            ))
                        ) : (
                            <div className="col-span-full text-center py-16 bg-white rounded-xl border border-gray-100 shadow-sm">
                                <h3 className="text-lg font-medium text-gray-900">No listings yet</h3>
                                <p className="mt-1 text-sm text-gray-500">Use the form on the left to publish your first item for sale!</p>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Delete confirmation modal (in-app replacement for window.confirm) */}
            {deleteTarget && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    <div
                        className="absolute inset-0 bg-gray-900/50 backdrop-blur-sm"
                        onClick={() => setDeleteTarget(null)}
                    ></div>
                    <div className="relative bg-white rounded-2xl shadow-xl max-w-sm w-full p-6">
                        <div className="flex items-start gap-4">
                            <div className="flex-shrink-0 w-11 h-11 rounded-full bg-red-100 flex items-center justify-center">
                                <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                            </div>
                            <div>
                                <h3 className="text-lg font-bold text-gray-900">Delete this listing?</h3>
                                <p className="text-sm text-gray-500 mt-1">
                                    <span className="font-semibold text-gray-700">{deleteTarget.title}</span> will be permanently removed from your listings.
                                </p>
                            </div>
                        </div>
                        <div className="flex justify-end gap-3 mt-6">
                            <button
                                onClick={() => setDeleteTarget(null)}
                                className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 transition"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmDelete}
                                className="px-4 py-2 rounded-lg text-sm font-semibold text-white bg-red-600 hover:bg-red-700 transition shadow-sm"
                            >
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}