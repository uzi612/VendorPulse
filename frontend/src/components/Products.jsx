import React, { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CITIES } from '../cities';

export default function Products() {
    const [items, setItems] = useState([]);
    const [categories] = useState(['CLOTHING', 'ELECTRONICS', 'FURNITURE', 'BOOKS', 'VEHICLES', 'OTHER']);
    const [searchParams, setSearchParams] = useSearchParams();
    const selectedCategory = searchParams.get('category');
    const selectedCity = searchParams.get('city') || '';

    // Build a products URL that keeps the OTHER filter intact, e.g. pills
    // preserve the chosen city, the city dropdown preserves the category.
    const filterUrl = (category) => {
        const params = new URLSearchParams();
        if (category) params.set('category', category);
        if (selectedCity) params.set('city', selectedCity);
        const qs = params.toString();
        return `/products/${qs ? `?${qs}` : ''}`;
    };

    const changeCity = (city) => {
        const params = new URLSearchParams();
        if (selectedCategory) params.set('category', selectedCategory);
        if (city) params.set('city', city);
        setSearchParams(params);
    };

    // Search term lives in local state so it survives category-pill clicks;
    // empty string = no search filter.
    const [searchTerm, setSearchTerm] = useState('');
    const [loading, setLoading] = useState(true);
    // Server pagination meta {count, total_pages, page, page_size}
    const [meta, setMeta] = useState(null);

    const currentPage = parseInt(searchParams.get('page'), 10) || 1;

    const changePage = (n) => {
        const params = new URLSearchParams(searchParams);
        if (n <= 1) params.delete('page');
        else params.set('page', String(n));
        setSearchParams(params);
    };

    // Drop ?page= when the search term changes so we never sit on a page
    // beyond the new (smaller) result set.
    useEffect(() => {
        if (searchParams.get('page')) {
            const params = new URLSearchParams(searchParams);
            params.delete('page');
            setSearchParams(params, { replace: true });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [searchTerm]);

    // Jump back to the top whenever a new page loads
    useEffect(() => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }, [currentPage]);

    useEffect(() => {
        const fetchProducts = async () => {
            try {
                const params = new URLSearchParams();
                if (selectedCategory) params.set('category', selectedCategory);
                if (selectedCity) params.set('city', selectedCity);
                if (searchTerm.trim()) params.set('search', searchTerm.trim());
                if (currentPage > 1) params.set('page', String(currentPage));
                params.set('page_size', '24');
                const qs = params.toString();
                const url = '/api/products/items/' + (qs ? `?${qs}` : '');
                const res = await fetch(url);
                const data = await res.json();
                // Paginated envelope: {count, total_pages, page, page_size, results}
                if (Array.isArray(data.results)) {
                    setItems(data.results);
                    setMeta(data);
                } else {
                    setItems(data.results || data);
                    setMeta(null);
                }
            } catch (err) {
                console.error("Error fetching products:", err);
            } finally {
                setLoading(false);
            }
        };
        setLoading(true);
        // Debounce: wait 350ms after the last keystroke before hitting the API,
        // so typing "mountain" fires one request, not seven.
        const timer = setTimeout(fetchProducts, searchTerm ? 350 : 0);
        return () => clearTimeout(timer);
    }, [selectedCategory, selectedCity, searchTerm, currentPage]);

    return (
        <div className="max-w-7xl mx-auto px-4 py-8">
            {/* Page Header & Category Filter Pills */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4 border-b border-gray-200 pb-6">
                <div>
                    <h1 className="text-3xl font-black text-gray-900 tracking-tight">Marketplace Feed</h1>
                    <p className="text-gray-500 text-sm mt-1">Browse available items listed by community members.</p>
                </div>
                
                {/* Category Filter Navigation Bar (pills preserve the city filter) */}
                <div className="flex flex-wrap gap-2 overflow-x-auto pb-2">
                    <Link
                        to={filterUrl()}
                        className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${!selectedCategory ? 'bg-indigo-600 text-white shadow-sm' : 'bg-white text-gray-700 border border-gray-200 hover:bg-gray-50'}`}
                    >
                        All
                    </Link>

                    {categories.map((cat, idx) => {
                        const isActive = selectedCategory === cat;
                        return (
                            <Link
                                key={idx}
                                to={filterUrl(cat)}
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

            {/* Search Bar + City Filter */}
            <div className="mb-8">
                <div className="flex flex-col sm:flex-row gap-3 max-w-3xl mx-auto">
                    <div className="relative flex-grow">
                        {/* Magnifier icon */}
                        <svg className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                        <input
                            type="text"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            placeholder="Search items by name..."
                            className="w-full pl-12 pr-12 py-3.5 rounded-xl border border-gray-300 bg-white shadow-sm
                                       text-gray-800 placeholder-gray-400
                                       focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
                        />
                        {/* Clear button appears once the user types */}
                        {searchTerm && (
                            <button
                                onClick={() => setSearchTerm('')}
                                aria-label="Clear search"
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-700 hover:bg-gray-100
                                           rounded-full p-1.5 transition"
                            >
                                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        )}
                    </div>

                    {/* City filter dropdown (mirrors the category filter in the URL) */}
                    <div className="relative sm:w-56">
                        <span className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none text-gray-400">📍</span>
                        <select
                            value={selectedCity}
                            onChange={(e) => changeCity(e.target.value)}
                            className="w-full pl-10 pr-8 py-3.5 rounded-xl border border-gray-300 bg-white shadow-sm appearance-none cursor-pointer
                                       text-gray-800
                                       focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
                            aria-label="Filter by city"
                        >
                            <option value="">All Cities</option>
                            {CITIES.map((city) => (
                                <option key={city} value={city}>{city}</option>
                            ))}
                        </select>
                        {/* Custom chevron (select's native arrow removed via appearance-none) */}
                        <svg className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                        </svg>
                    </div>
                </div>

                {/* Active city filter chip (quick way to drop just the city) */}
                {selectedCity && (
                    <div className="flex justify-center mt-3">
                        <button
                            onClick={() => changeCity('')}
                            className="inline-flex items-center gap-1.5 text-xs font-bold bg-indigo-50 text-indigo-700 border border-indigo-100 px-3 py-1.5 rounded-full hover:bg-indigo-100 transition"
                        >
                            📍 {selectedCity} · Clear city filter ✕
                        </button>
                    </div>
                )}

                {searchTerm.trim() && !loading && (
                    <p className="text-center text-sm text-gray-500 mt-3">
                        {items.length > 0
                            ? <>Found <span className="font-semibold text-indigo-600">{meta ? meta.count : items.length}</span> result{meta && meta.count === 1 ? '' : 's'} for “{searchTerm.trim()}”{selectedCategory ? <> in <span className="font-semibold">{selectedCategory}</span></> : ''}{selectedCity ? <> near <span className="font-semibold">{selectedCity}</span></> : ''}</>
                            : <>Nothing matches “{searchTerm.trim()}” — try a different keyword.</>}
                    </p>
                )}
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
                                <p className="text-xs text-gray-400 mt-1">
                                    @{item.seller_username}
                                    {item.seller_rating != null && (
                                        <> · <span className="text-amber-500 font-semibold">★ {item.seller_rating}</span> ({item.seller_rating_count})</>
                                    )}
                                </p>
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
                        <p className="mt-1 text-sm text-gray-500">
                            {searchTerm.trim()
                                ? <>Nothing matches your search{selectedCategory ? ' in this category' : ''}{selectedCity ? ` in ${selectedCity}` : ''}. Try different keywords or clear a filter.</>
                                : selectedCity
                                ? <>No available listings in <span className="font-semibold">{selectedCity}</span>{selectedCategory ? ' under this category' : ''} right now.</>
                                : 'There are no available listings under this category right now.'}
                        </p>
                        {searchTerm.trim() && (
                            <button onClick={() => setSearchTerm('')} className="inline-block mt-4 bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded-lg text-sm font-semibold transition mr-2">
                                Clear Search
                            </button>
                        )}
                        {selectedCity && (
                            <button onClick={() => changeCity('')} className="inline-block mt-4 bg-gray-100 hover:bg-gray-200 text-gray-700 px-4 py-2 rounded-lg text-sm font-semibold transition mr-2">
                                Clear City Filter
                            </button>
                        )}
                        <Link to="/products/" className="inline-block mt-4 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-indigo-700 transition">
                            View All Products
                        </Link>
                    </div>
                )}

                {/* Pagination footer (server-side, 24 per page) */}
                {meta && meta.total_pages > 1 && (
                    <div className="mt-10 flex justify-between items-center bg-white border border-gray-100 rounded-xl px-5 py-4 shadow-sm">
                        <span className="text-sm text-gray-500">
                            Page <b className="text-gray-800">{meta.page}</b> of <b className="text-gray-800">{meta.total_pages}</b>
                            <span className="mx-2 text-gray-300">|</span>
                            {meta.count} item{meta.count === 1 ? '' : 's'}
                            <span className="mx-2 text-gray-300">|</span>
                            showing {(meta.page - 1) * meta.page_size + 1}–{Math.min(meta.page * meta.page_size, meta.count)}
                        </span>
                        <div className="flex gap-2">
                            <button
                                disabled={meta.page <= 1}
                                onClick={() => changePage(meta.page - 1)}
                                className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${meta.page <= 1 ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-white border border-gray-200 text-gray-700 hover:bg-indigo-50 hover:text-indigo-600'}`}
                            >
                                ← Prev
                            </button>
                            <button
                                disabled={meta.page >= meta.total_pages}
                                onClick={() => changePage(meta.page + 1)}
                                className={`px-4 py-2 rounded-lg text-sm font-semibold transition ${meta.page >= meta.total_pages ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-white border border-gray-200 text-gray-700 hover:bg-indigo-50 hover:text-indigo-600'}`}
                            >
                                Next →
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}