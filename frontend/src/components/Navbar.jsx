import React from 'react';
import { Link } from 'react-router-dom';

export default function Navbar({ children, isAuthenticated, onLogout }) {
    return (
        <div className="bg-gray-50 min-h-screen flex flex-col font-sans text-gray-800">
            {/* Navigation Bar */}
            <nav className="bg-white border-b border-gray-200 sticky top-0 z-50 shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between h-16 items-center">
                        
                        {/* Brand Logo */}
                        <div className="flex-shrink-0 flex items-center">
                            <Link to="/" className="text-2xl font-black text-indigo-600 tracking-tight">VendorPulse</Link>
                        </div>
                        
                        {/* Navigation Links */}
                        <div className="hidden md:flex space-x-6 items-center">
                            <Link to="/" className="text-gray-700 hover:text-indigo-600 font-medium transition">Home</Link>
                            <Link to="/products/" className="text-gray-700 hover:text-indigo-600 font-medium transition">Products</Link>
                            <Link to="/products/listing/" className="text-gray-700 hover:text-indigo-600 font-medium transition">My Listings</Link>
                            <Link to="/orders/cart/" className="text-gray-700 hover:text-indigo-600 font-medium transition flex items-center gap-1.5">Cart</Link>
                            <Link to="/accounts/profile/" className="text-gray-700 hover:text-indigo-600 font-medium transition">Profile</Link>
                        </div>

                        <div className="flex items-center space-x-4">
                            <Link to="/products/listing/" className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-semibold text-sm shadow-sm transition">
                                + Sell Item
                            </Link>

                            {isAuthenticated ? (
                                <button 
                                    onClick={onLogout}
                                    className="text-sm font-medium text-gray-600 hover:text-red-600 transition"
                                >
                                    Logout
                                </button>
                            ) : (
                                <div className="flex items-center space-x-3 text-sm font-medium">
                                    <Link to="/accounts/login/" className="text-gray-600 hover:text-indigo-600 transition">Login</Link>
                                    <Link to="/accounts/register/" className="bg-gray-100 hover:bg-gray-200 text-gray-800 px-3 py-1.5 rounded-lg transition">Register</Link>
                                </div>
                            )}
                        </div>

                    </div>
                </div>
            </nav>

            {/* Main Content Container */}
            <main className="flex-grow">
                {children}
            </main>

            {/* Footer */}
            <footer className="bg-white border-t border-gray-200 py-6 mt-12">
                <div className="max-w-7xl mx-auto px-4 text-center text-sm text-gray-500">
                    &copy; 2026 VendorPulse. All rights reserved. Powered by React & Tailwind CSS.
                </div>
            </footer>
        </div>
    );
}