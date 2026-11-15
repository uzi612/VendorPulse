import React, { useState } from 'react';
import NotificationsBell from '../../components/NotificationsBell';
import OrdersTab from './tabs/OrdersTab';
import StaffTab from './tabs/StaffTab';
import SellersTab from './tabs/SellersTab';
import DisputesTab from './tabs/DisputesTab';
import ModerationTab from './tabs/ModerationTab';
import AdminAnalytics from './AdminAnalytics';

// Admin portal shell: header + tab bar only. Each tab owns its data fetching
// in its own component file. Sub-tab/page state lives here (not inside the
// tab components) so it survives switching tabs — the same persistence the
// pre-split monolith had. Tabs are mounted on demand; re-entering a tab
// refetches its data from the server.
export default function AdminPortal({ onLogout }) {
    const [activeTab, setActiveTab] = useState('deliveries');

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
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 32px', backgroundColor: '#ffffff', borderBottom: '1px solid #e2e8f0' }}>
                <h1 style={{ fontSize: '20px', fontWeight: 'bold', color: '#0f172a', margin: 0 }}>VendorPulse Admin Portal</h1>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <NotificationsBell />
                    <button onClick={onLogout} style={{ padding: '8px 16px', backgroundColor: '#ef4444', color: '#ffffff', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Logout</button>
                </div>
            </header>

            <div style={{ display: 'flex', gap: '16px', padding: '16px 32px', backgroundColor: '#ffffff', borderBottom: '1px solid #e2e8f0' }}>
                <button onClick={() => setActiveTab('deliveries')} style={{ padding: '8px 16px', backgroundColor: activeTab === 'deliveries' ? '#0f172a' : 'transparent', color: activeTab === 'deliveries' ? '#ffffff' : '#64748b', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Orders & Deliveries</button>
                <button onClick={() => setActiveTab('staff')} style={{ padding: '8px 16px', backgroundColor: activeTab === 'staff' ? '#0f172a' : 'transparent', color: activeTab === 'staff' ? '#ffffff' : '#64748b', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Staff Management</button>
                <button onClick={() => setActiveTab('sellers')} style={{ padding: '8px 16px', backgroundColor: activeTab === 'sellers' ? '#0f172a' : 'transparent', color: activeTab === 'sellers' ? '#ffffff' : '#64748b', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Sellers</button>
                <button onClick={() => setActiveTab('disputes')} style={{ padding: '8px 16px', backgroundColor: activeTab === 'disputes' ? '#0f172a' : 'transparent', color: activeTab === 'disputes' ? '#ffffff' : '#64748b', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>⚑ Disputes</button>
                <button onClick={() => setActiveTab('moderation')} style={{ padding: '8px 16px', backgroundColor: activeTab === 'moderation' ? '#0f172a' : 'transparent', color: activeTab === 'moderation' ? '#ffffff' : '#64748b', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>🗂 Listings</button>
                <button onClick={() => setActiveTab('analytics')} style={{ padding: '8px 16px', backgroundColor: activeTab === 'analytics' ? '#0f172a' : 'transparent', color: activeTab === 'analytics' ? '#ffffff' : '#64748b', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>📊 Analytics</button>
            </div>

            <main style={{ padding: '32px' }}>
                {activeTab === 'deliveries' && (
                    <OrdersTab
                        deliveryTab={deliveryTab} setDeliveryTab={setDeliveryTab}
                        page={deliveryPage} setPage={setDeliveryPage}
                    />
                )}
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
