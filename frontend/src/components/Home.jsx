import React from 'react';
import { Link } from 'react-router-dom';

export default function Home({ isAuthenticated }) {
    return (
        <div>
            {/* Hero Section */}
            <div className="relative bg-gradient-to-b from-indigo-50/50 to-white py-16 md:py-24 border-b border-gray-100">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
                    <span className="bg-indigo-100 text-indigo-700 text-xs font-extrabold uppercase px-3 py-1 rounded-full tracking-wider mb-4 inline-block">
                        Welcome to VendorPulse C2C Marketplace
                    </span>
                    <h1 className="text-4xl sm:text-5xl md:text-6xl font-black text-gray-900 tracking-tight max-w-3xl mx-auto leading-tight">
                        Discover, Buy & Sell with <span className="text-indigo-600">Confidence</span>
                    </h1>
                    <p className="mt-4 text-base sm:text-lg text-gray-600 max-w-2xl mx-auto">
                        Your trusted community-driven marketplace powered by reliable VendorPulse Delivery Services and direct peer-to-peer connections.
                    </p>
                    <div className="mt-8 flex flex-col sm:flex-row justify-center gap-4">
                        <Link to="/products/" className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold px-8 py-3.5 rounded-xl shadow-sm transition">
                            Browse Marketplace Feed
                        </Link>
                        {!isAuthenticated && (
                            <Link to="/accounts/register/" className="bg-white hover:bg-gray-50 text-gray-800 border border-gray-300 font-bold px-8 py-3.5 rounded-xl transition">
                                Create Account
                            </Link>
                        )}
                    </div>
                </div>
            </div>

            {/* Features / Value Proposition Section */}
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
                <div className="text-center mb-12">
                    <h2 className="text-2xl sm:text-3xl font-black text-gray-900 tracking-tight">Why Choose VendorPulse?</h2>
                    <p className="text-gray-500 text-sm mt-1">Built for seamless buying, selling, and tracking.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm hover:border-indigo-100 transition">
                        <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center font-bold text-xl mb-4">
                            🚚
                        </div>
                        <h3 className="text-lg font-bold text-gray-900 mb-2">VendorPulse Delivery</h3>
                        <p className="text-sm text-gray-600">
                            Every order is backed by dependable logistics with estimated delivery tracking right in your profile dashboard.
                        </p>
                    </div>

                    <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm hover:border-indigo-100 transition">
                        <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center font-bold text-xl mb-4">
                            💼
                        </div>
                        <h3 className="text-lg font-bold text-gray-900 mb-2">Seller Dashboard</h3>
                        <p className="text-sm text-gray-600">
                            Manage your active listings, track items you've sold, and view buyer shipping details all in one place.
                        </p>
                    </div>

                    <div className="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm hover:border-indigo-100 transition">
                        <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-xl flex items-center justify-center font-bold text-xl mb-4">
                            🔒
                        </div>
                        <h3 className="text-lg font-bold text-gray-900 mb-2">Secure & Simple</h3>
                        <p className="text-sm text-gray-600">
                            Safe user authentication accounts, intuitive cart management, and seamless direct checkout flows.
                        </p>
                    </div>
                </div>
            </div>

            {/* Call to Action Banner */}
            <div className="bg-indigo-600 py-12">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-white">
                    <h2 className="text-2xl sm:text-3xl font-black tracking-tight">Ready to explore listings or sell an item?</h2>
                    <p className="mt-2 text-indigo-100 text-sm max-w-xl mx-auto">Join the VendorPulse network today and manage your marketplace activity instantly.</p>
                    <div className="mt-6">
                        <Link to="/products/" className="inline-block bg-white text-indigo-600 hover:bg-gray-100 font-bold px-8 py-3 rounded-xl transition shadow-sm">
                            Get Started Now
                        </Link>
                    </div>
                </div>
            </div>
        </div>
    );
}