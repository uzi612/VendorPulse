import React, { useState, useEffect } from 'react';
import { api } from '../../../api';

// Sellers directory, derived from the FULL deliveries list (fetched with
// ?all=1 while this tab is open). Verification toggles refetch this list;
// the Staff tab refetches its own data when it mounts.
export default function SellersTab() {
    const [allDeliveries, setAllDeliveries] = useState([]);

    useEffect(() => {
        fetchAllDeliveries();
    }, []);

    const fetchAllDeliveries = async () => {
        try {
            const response = await api('/api/deliveries/admin/deliveries/?all=1');
            if (!response.ok) throw new Error('Failed to fetch seller data.');
            const data = await response.json();
            setAllDeliveries(Array.isArray(data) ? data : data.results);
        } catch (err) {
            console.error(err);
        }
    };

    const toggleVerification = async (userId, currentStatus) => {
        if (!userId) {
            alert("Error: User ID is missing.");
            return;
        }

        try {
            const res = await api(`/api/deliveries/admin/users/${userId}/verify/`, {
                method: 'PATCH',
                body: JSON.stringify({ is_verified: !currentStatus })
            });

            if (res.ok) {
                fetchAllDeliveries();  // refresh this tab's verification badge
            } else {
                const errData = await res.json().catch(() => ({}));
                alert("Failed to update: " + (errData.error || "Unknown error"));
            }
        } catch (err) {
            console.error("Network or execution error:", err);
        }
    };

    // Derive the seller directory from the FULL deliveries list
    const sellersMap = {};
    allDeliveries.forEach(item => {
        const username = item.seller_username;
        if (!username) return;
        if (item.status === 'CANCELLED') return;  // cancelled sales aren't sales
        if (!sellersMap[username]) {
            sellersMap[username] = {
                id: item.seller_id || item.seller,
                username: username,
                city: (item.seller_address && item.seller_address !== 'N/A') ? item.seller_address : 'N/A',
                itemsSold: 0,
                totalValue: 0,
                is_verified: item.is_seller_verified || false
            };
        }
        sellersMap[username].itemsSold += 1;
        sellersMap[username].totalValue += parseFloat(item.item_price || 0);
    });
    const sellers = Object.values(sellersMap).sort((a, b) => b.totalValue - a.totalValue);

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h2 style={{ color: '#0f172a', margin: 0 }}>Sellers Directory</h2>
                <span style={{ fontSize: '13px', color: '#64748b' }}>{sellers.length} Seller{sellers.length === 1 ? '' : 's'}</span>
            </div>

            {sellers.length === 0 ? (
                <div style={{ backgroundColor: '#ffffff', padding: '32px', borderRadius: '8px', textAlign: 'center', color: '#64748b', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                    <p style={{ margin: 0 }}>No sellers found yet. Sellers appear here once they have sold an item.</p>
                </div>
            ) : (
                <div style={{ backgroundColor: '#ffffff', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', overflow: 'hidden' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                        <thead style={{ backgroundColor: '#f1f5f9', borderBottom: '1px solid #e2e8f0' }}>
                            <tr>
                                <th style={{ padding: '12px 16px', color: '#475569' }}>Seller</th>
                                <th style={{ padding: '12px 16px', color: '#475569' }}>City / Address</th>
                                <th style={{ padding: '12px 16px', color: '#475569' }}>Items Sold</th>
                                <th style={{ padding: '12px 16px', color: '#475569' }}>Total Sales Value</th>
                                <th style={{ padding: '12px 16px', color: '#475569' }}>Verified Status</th>
                                <th style={{ padding: '12px 16px', color: '#475569' }}>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {sellers.map(seller => (
                                <tr key={seller.username} style={{ borderBottom: '1px solid #e2e8f0' }}>
                                    <td style={{ padding: '12px 16px', fontWeight: '600', color: '#0f172a' }}>@{seller.username}</td>
                                    <td style={{ padding: '12px 16px' }}>{seller.city}</td>
                                    <td style={{ padding: '12px 16px' }}>{seller.itemsSold}</td>
                                    <td style={{ padding: '12px 16px', fontWeight: '600', color: '#059669' }}>₹{seller.totalValue.toFixed(2)}</td>
                                    <td style={{ padding: '12px 16px' }}>
                                        {seller.is_verified ? (
                                            <span style={{ color: '#059669', fontWeight: 'bold' }}>✓ Verified</span>
                                        ) : (
                                            <span style={{ color: '#64748b' }}>Unverified</span>
                                        )}
                                    </td>
                                    <td style={{ padding: '12px 16px' }}>
                                        <button
                                            onClick={() => toggleVerification(seller.id, seller.is_verified)}
                                            style={{ padding: '6px 12px', backgroundColor: seller.is_verified ? '#ef4444' : '#10b981', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}
                                        >
                                            {seller.is_verified ? 'Revoke' : 'Verify'}
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
