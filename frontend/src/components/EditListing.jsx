import React, { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';

export default function EditListing() {
    const { id } = useParams();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [formData, setFormData] = useState({
        title: '',
        description: '',
        price: '',
        category: 'ELECTRONICS',
        condition: 'NEW',
        location: '',
        image: null
    });
    const [previewImage, setPreviewImage] = useState(null);

    // Exact database choices matching your Django model
    const categoryChoices = [
        { label: 'Clothing', value: 'CLOTHING' },
        { label: 'Electronics', value: 'ELECTRONICS' },
        { label: 'Furniture', value: 'FURNITURE' },
        { label: 'Books', value: 'BOOKS' },
        { label: 'Vehicles', value: 'VEHICLES' },
        { label: 'Other', value: 'OTHER' }
    ];

    const conditionChoices = [
        { label: 'Brand New', value: 'NEW' },
        { label: 'Like New', value: 'LIKE_NEW' },
        { label: 'Good', value: 'GOOD' },
        { label: 'Fair', value: 'FAIR' }
    ];

    useEffect(() => {
        const fetchItemDetails = async () => {
            try {
                const token = localStorage.getItem('authToken');
                const res = await fetch(`/api/products/items/${id}/`, {
                    headers: {
                        'Authorization': token ? `Token ${token}` : '',
                        'Content-Type': 'application/json'
                    }
                });

                if (res.ok) {
                    const data = await res.json();
                    
                    // Normalize and validate category & condition against available options
                    const fetchedCategory = data.category ? data.category.toUpperCase() : 'ELECTRONICS';
                    const validCategory = categoryChoices.some(c => c.value === fetchedCategory) ? fetchedCategory : 'ELECTRONICS';

                    const fetchedCondition = data.condition ? data.condition.toUpperCase() : 'NEW';
                    const validCondition = conditionChoices.some(c => c.value === fetchedCondition) ? fetchedCondition : 'NEW';

                    setFormData({
                        title: data.title || '',
                        description: data.description || '',
                        price: data.price || '',
                        category: validCategory,
                        condition: validCondition,
                        location: data.location || '',
                        image: null
                    });
                    setPreviewImage(data.image || null);
                } else {
                    console.error("Failed to load item for editing");
                }
            } catch (err) {
                console.error("Error fetching item details:", err);
            } finally {
                setLoading(false);
            }
        };

        fetchItemDetails();
    }, [id]);

    const handleChange = (e) => {
        if (e.target.name === 'image') {
            setFormData({ ...formData, image: e.target.files[0] });
            setPreviewImage(URL.createObjectURL(e.target.files[0]));
        } else {
            setFormData({ ...formData, [e.target.name]: e.target.value });
        }
    };

    const handleUpdate = async (e) => {
        e.preventDefault();
        const data = new FormData();
        
        Object.keys(formData).forEach((key) => {
            if (formData[key] !== null && formData[key] !== '' && formData[key] !== undefined) {
                data.append(key, formData[key]);
            }
        });

        try {
            const token = localStorage.getItem('authToken');
            const res = await fetch(`/api/products/items/${id}/`, {
                method: 'PUT',
                headers: {
                    'Authorization': token ? `Token ${token}` : ''
                },
                body: data
            });

            if (res.ok) {
                navigate('/products/listing/');
            } else {
                const errData = await res.json();
                console.error("Failed to update listing. Server errors:", errData);
            }
        } catch (err) {
            console.error("Error updating listing:", err);
        }
    };

    if (loading) {
        return <div className="text-center py-20 text-gray-500 font-medium">Loading listing details...</div>;
    }

    return (
        <div className="max-w-3xl mx-auto px-4 py-8">
            <div className="mb-6">
                <Link to="/products/listing/" className="text-sm font-semibold text-indigo-600 hover:text-indigo-800 transition">
                    &larr; Back to My Listings
                </Link>
            </div>

            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 md:p-8">
                <h1 className="text-2xl font-black text-gray-900 tracking-tight mb-6">Edit Product Listing</h1>

                <form onSubmit={handleUpdate} className="space-y-5" autoComplete="off">
                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-1">Title</label>
                        <input 
                            type="text" 
                            name="title" 
                            value={formData.title} 
                            onChange={handleChange} 
                            required 
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none" 
                        />
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-1">Price (₹)</label>
                            <input 
                                type="number" 
                                name="price" 
                                value={formData.price} 
                                onChange={handleChange} 
                                required 
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none" 
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-1">Location</label>
                            <input 
                                type="text" 
                                name="location" 
                                value={formData.location} 
                                onChange={handleChange} 
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none" 
                            />
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-1">Category</label>
                            <select 
                                name="category" 
                                value={formData.category} 
                                onChange={handleChange} 
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white"
                            >
                                {categoryChoices.map((choice) => (
                                    <option key={choice.value} value={choice.value}>
                                        {choice.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-1">Condition</label>
                            <select 
                                name="condition" 
                                value={formData.condition} 
                                onChange={handleChange} 
                                className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white"
                            >
                                {conditionChoices.map((choice) => (
                                    <option key={choice.value} value={choice.value}>
                                        {choice.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-1">Description</label>
                        <textarea 
                            name="description" 
                            value={formData.description} 
                            onChange={handleChange} 
                            rows="4" 
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                        ></textarea>
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-1">Product Image</label>
                        <div className="flex items-center gap-4 mt-2">
                            {previewImage && (
                                <div className="w-20 h-20 bg-gray-100 rounded-lg overflow-hidden flex-shrink-0 border border-gray-200">
                                    <img src={previewImage} alt="Preview" className="w-full h-full object-cover" />
                                </div>
                            )}
                            <input 
                                type="file" 
                                name="image" 
                                onChange={handleChange} 
                                className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100" 
                            />
                        </div>
                    </div>

                    <div className="flex items-center gap-4 pt-4 border-t border-gray-100">
                        <button 
                            type="submit" 
                            className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-xl transition shadow-sm text-center"
                        >
                            Save Changes
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}