import React, { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import NotificationsBell from '../../components/NotificationsBell';
import OrdersTab from './tabs/OrdersTab';
import StaffTab from './tabs/StaffTab';
import SellersTab from './tabs/SellersTab';
import DisputesTab from './tabs/DisputesTab';
import ModerationTab from './tabs/ModerationTab';
import ZonesTab from './tabs/ZonesTab';
import HubsTab from './tabs/HubsTab';
import AdminAnalytics from './AdminAnalytics';

// Admin portal shell: header + tab bar only. Each tab owns its data fetching
// in its own component file. Sub-tab/page state lives here (not inside the
// tab components) so it survives switching tabs — the same persistence the
// pre-split monolith had. Tabs are mounted on demand; re-entering a tab
// refetches its data from the server.
// The ACTIVE tab is the URL path (/admin/staff/, /admin/analytics/, ...), so
// tabs are deep-linkable and survive refresh — the URL is the state.
// Nav definition (key doubles as the URL segment below)
const NAV_TABS = [
    { key: 'deliveries', label: '📦 Orders & Deliveries' },
    { key: 'zones', label: '🗺 Delivery Zones' },
    { key: 'hubs', label: '🏢 Hubs' },
    { key: 'staff', label: '👥 Staff' },
    { key: 'sellers', label: '🏪 Sellers' },
    { key: 'disputes', label: '⚑ Disputes' },
    { key: 'moderation', label: '🗂 Listings' },
    { key: 'analytics', label: '📊 Analytics' },
];

export default function AdminPortal({ onLogout }) {
    const location = useLocation();
    const navigate = useNavigate();

    // Active tab from the URL: /admin/<key>/ → key. Bare /admin/ falls
    // through to the default deliveries tab; unknown paths redirect there.
    const urlKey = location.pathname.split('/').filter(Boolean)[1];
    const isValid = !urlKey || NAV_TABS.some(t => t.key === urlKey);
    const activeTab = isValid && urlKey ? urlKey : 'deliveries';
    const setActiveTab = (key) => navigate(`/admin/${key}/`);
    if (!isValid) return <Navigate to="/admin/deliveries/" replace />;

    // Orders tab
    const [deliveryTab, setDeliveryTab] = useState('active'); // 'active' | 'completed' | 'cancelled'
    const [deliveryPage, setDeliveryPage] = useState(1);

    // Staff tab
    const [staffPage, setStaffPage] = useState(1);

    // Disputes tab
    const [disputeStatus, setDisputeStatus] = useState('open'); // ?status= filter
    const [disputePage, setDisputePage] = useState(1);

    // Moderation tab
    const [listingStatus, setListingStatus] = useState('pending'); // ?status= filter
    const [listingPage, setListingPage] = useState(1);

    return (
        <div style={{ minHeight: '100vh', backgroundColor: '#f8fafc' }}>
            {/* Top navbar: brand left, tab links center, actions right */}
            <header
                style={{
                    position: 'sticky', top: 0, zIndex: 20,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    gap: '10px', flexWrap: 'wrap',
                    padding: '10px 20px', backgroundColor: '#ffffff',
                    borderBottom: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(15, 23, 42, 0.05)',
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '19px', fontWeight: 'bold', color: '#0f172a' }}>VendorPulse</span>
                    <span style={{
                        padding: '3px 10px', backgroundColor: '#eef2ff', color: '#4f46e5',
                        borderRadius: '999px', fontSize: '11px', fontWeight: '700', letterSpacing: '1px',
                    }}>ADMIN</span>
                </div>

                <nav style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
                    {NAV_TABS.map(tab => {
                        const active = activeTab === tab.key;
                        return (
                            <button
                                key={tab.key}
                                onClick={() => setActiveTab(tab.key)}
                                onMouseEnter={e => { if (!active) e.currentTarget.style.backgroundColor = '#f1f5f9'; }}
                                onMouseLeave={e => { if (!active) e.currentTarget.style.backgroundColor = 'transparent'; }}
                                style={{
                                    padding: '8px 14px', border: 'none', borderRadius: '8px',
                                    backgroundColor: active ? '#eef2ff' : 'transparent',
                                    color: active ? '#4f46e5' : '#64748b',
                                    fontWeight: active ? '700' : '600',
                                    fontSize: '13.5px', cursor: 'pointer',
                                    transition: 'background-color 0.15s, color 0.15s',
                                }}
                            >
                                {tab.label}
                            </button>
                        );
                    })}
                </nav>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <NotificationsBell />
                    <button onClick={onLogout} style={{ padding: '8px 16px', backgroundColor: '#ef4444', color: '#ffffff', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Logout</button>
                </div>
            </header>

            <main style={{ padding: '32px' }}>
                {activeTab === 'deliveries' && (
                    <OrdersTab
                        deliveryTab={deliveryTab} setDeliveryTab={setDeliveryTab}
                        page={deliveryPage} setPage={setDeliveryPage}
                    />
                )}
                {activeTab === 'zones' && <ZonesTab />}
                {activeTab === 'hubs' && <HubsTab />}
                {activeTab === 'staff' && (
                    <StaffTab page={staffPage} setPage={setStaffPage} />
                )}
                {activeTab === 'sellers' && <SellersTab />}
                {activeTab === 'disputes' && (
                    <DisputesTab
                        status={disputeStatus} setStatus={setDisputeStatus}
                        page={disputePage} setPage={setDisputePage}
                    />
                )}
                {activeTab === 'moderation' && (
                    <ModerationTab
                        status={listingStatus} setStatus={setListingStatus}
                        page={listingPage} setPage={setListingPage}
                    />
                )}
                {activeTab === 'analytics' && <AdminAnalytics />}
            </main>
        </div>
    );
}
