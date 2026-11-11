import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

export default function Products() {
    const [items, setItems] = useState([]);
    const [categories, setCategories] = useState([]);
    const [searchParams] = useSearchParams();
    const selectedCategory = searchParams.get('category');

    useEffect(() => {
        const fetchProducts = async () => {
            try {
                let url = '/api/products/items/';
                if (selectedCategory) {
                    url += `?category=${selectedCategory}`;
                }
                const res = await fetch(url);
                const data = await res.json();
                const itemsList = data.results || data;
                setItems(itemsList);

                const uniqueCategories = [...new Set(itemsList.map(item => item.category).filter(Boolean))];
                setCategories(uniqueCategories);
            } catch (err) {
                console.error("Error fetching products:", err);
            }
        };
        fetchProducts();
    }, [selectedCategory]);

    return (
        <div className="max-w-7xl mx-auto px-4 py-8">
            {/* Page Header & Category Filter Pills */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4 border-b border-gray-200 pb-6">
                <div>
                    <h1 className="text-3xl font-black text-gray-900 tracking-tight">Marketplace Feed</h1>
                    <p className="text-gray-500 text-sm mt-1">Browse available items listed by community members.</p>
                </div>
                
                {/* Category Filter Navigation Bar */}
                <div className="flex flex-wrap gap-2 overflow-x-auto pb-2">
                    <Link 
                        to="/products/" 
                        className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${!selectedCategory ? 'bg-indigo-600 text-white shadow-sm' : 'bg-white text-gray-700 border border-gray-200 hover:bg-gray-50'}`}
                    >
                        All
                    </Link>

                    {categories.map((cat, idx) => {
                        const isActive = selectedCategory === cat;
                        return (
                            <Link
                                key={idx}
                                to={`/products/?category=${cat}`}
                                className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${
                                    isActive 
                                        ? 'bg-indigo-600 text-white shadow-sm' 
                                        : 'bg-white text-gray-700 border border-gray-200 hover:bg-gray-50'
                                }`}
                            >
                                {cat}
                            </Link>
                        );
                    })}
                </div>
            </div>

            {/* Product Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                {items.length > 0 ? (
                    items.map((item) => (
                        <div key={item.id} className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-md transition flex flex-col">
                            {item.image ? (
                                <img src={item.image} alt={item.title} className="w-full h-48 object-cover" />
                            ) : (
                                <div className="w-full h-48 bg-gray-100 flex items-center justify-center text-gray-400 text-sm">No Image Available</div>
                            )}
                            
                            <div className="p-4 flex flex-col flex-grow">
                                <div className="flex justify-between items-center mb-2">
                                    <span className="bg-indigo-50 text-indigo-600 text-xs px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wide">
                                        {item.condition_display || item.condition}
                                    </span>
                                    <span className="text-xs text-gray-500 font-medium">📍 {item.location}</span>
                                </div>

                                <h3 className="font-bold text-gray-800 text-lg line-clamp-1">{item.title}</h3>
                                <p className="text-gray-500 text-sm mt-1 line-clamp-2 flex-grow">{item.description}</p>
                                
                                <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
                                    <span className="text-xl font-black text-emerald-600">₹{item.price}</span>
                                    <Link to={`/products/${item.id}/`} className="bg-indigo-50 hover:bg-indigo-600 text-indigo-600 hover:text-white px-3.5 py-2 rounded-lg text-sm font-semibold transition">
                                        View Details
                                    </Link>
                                </div>
                            </div>
                        </div>
                    ))
                ) : (
                    <div className="col-span-full text-center py-16 bg-white rounded-xl border border-gray-100 shadow-sm">
                        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
                        </svg>
                        <h3 className="mt-3 text-lg font-medium text-gray-900">No products found</h3>
                        <p className="mt-1 text-sm text-gray-500">There are no available listings under this category right now.</p>
                        <Link to="/products/" className="inline-block mt-4 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-indigo-700 transition">
                            View All Products
                        </Link>
                    </div>
                )}
            </div>
        </div>
    );
}