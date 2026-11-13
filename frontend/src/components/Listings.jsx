import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { CITIES } from '../cities';

export default function Listings() {
    const [userItems, setUserItems] = useState([]);
    const [formData, setFormData] = useState({
        title: '',
        description: '',
        price: '',
        category: '',
        condition: '',
        location: '',
        address: '',
        image: null
    });

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
                setFormData({ title: '', description: '', price: '', category: '', condition: '', location: '', image: null });
                fetchUserListings();
            }
        } catch (err) {
            console.error("Failed to post listing", err);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm("Are you sure you want to delete this listing?")) return;

        try {
            const res = await api(`/api/products/items/${id}/`, { method: 'DELETE' });

            if (res.ok || res.status === 204) {
                // Refresh local items state
                setUserItems(userItems.filter(item => item.id !== id));
            } else {
                console.error("Failed to delete listing");
            }
        } catch (err) {
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
                                <label className="block text-sm font-semibold text-gray-700 mb-1">City</label>
                                <select name="location" value={formData.location} onChange={handleChange} required className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white">
                                    <option value="">Select City</option>
                                    {CITIES.map(city => <option key={city} value={city}>{city}</option>)}
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
                                                    onClick={() => handleDelete(item.id)}
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
        </div>
    );
}