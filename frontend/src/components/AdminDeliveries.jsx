import React, { useState, useEffect } from 'react';

export default function AdminDeliveries({ onLogout }) {
    const [activeTab, setActiveTab] = useState('deliveries');
    const [deliveryTab, setDeliveryTab] = useState('active'); // 'active' or 'completed'
    
    // Deliveries state
    const [deliveries, setDeliveries] = useState([]);
    const [loadingDeliveries, setLoadingDeliveries] = useState(true);
    const [selectedDeliveryId, setSelectedDeliveryId] = useState(null);
    const [agentId, setAgentId] = useState('');
    const [trackingNumber, setTrackingNumber] = useState('');

    // Staff state
    const [staffList, setStaffList] = useState([]);
    const [loadingStaff, setLoadingStaff] = useState(false);
    const [showNewStaffForm, setShowNewStaffForm] = useState(false);
    const [newUsername, setNewUsername] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [newEmail, setNewEmail] = useState('');
    const [newAddress, setNewAddress] = useState('');
    const [newRole, setNewRole] = useState('agent');

    // Edit Staff state
    const [editingStaffId, setEditingStaffId] = useState(null);
    const [editEmail, setEditEmail] = useState('');
    const [editAddress, setEditAddress] = useState('');
    const [editRole, setEditRole] = useState('agent');

    const fetchDeliveries = async () => {
        try {
            const token = localStorage.getItem('authToken');
            const response = await fetch('http://127.0.0.1:8000/deliveries/admin/deliveries/', {
                headers: { 'Authorization': `Token ${token}` }
            });
            if (!response.ok) throw new Error('Failed to fetch deliveries.');
            const data = await response.json();
            setDeliveries(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoadingDeliveries(false);
        }
    };

    const toggleVerification = async (userId, currentStatus) => {
    try {
        const token = localStorage.getItem('authToken');
        const res = await fetch(`http://127.0.0.1:8000/deliveries/admin/users/${userId}/verify/`, {
            method: 'PATCH',
            headers: {
                'Authorization': `Token ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ is_verified: !currentStatus })
        });
        if (res.ok) {
            fetchStaff(); 
        }
    } catch (err) {
        console.error("Failed to update verification", err);
    }
};

    const fetchStaff = async () => {
        setLoadingStaff(true);
        try {
            const token = localStorage.getItem('authToken');
            const response = await fetch('http://127.0.0.1:8000/deliveries/admin/staff/', {
                headers: { 'Authorization': `Token ${token}` }
            });
            if (!response.ok) throw new Error('Failed to fetch staff list.');
            const data = await response.json();
            setStaffList(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoadingStaff(false);
        }
    };

    useEffect(() => { fetchDeliveries(); }, []);
    useEffect(() => { if (activeTab === 'staff') fetchStaff(); }, [activeTab]);

    const handleAssign = async (e, id) => {
        e.preventDefault();
        try {
            const token = localStorage.getItem('authToken');
            const response = await fetch(`http://127.0.0.1:8000/deliveries/admin/deliveries/${id}/assign/`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Token ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    assigned_agent: agentId ? parseInt(agentId) : null,
                    tracking_number: trackingNumber
                })
            });

            if (!response.ok) throw new Error('Failed to assign delivery.');
            fetchDeliveries();
            setSelectedDeliveryId(null);
            alert('Delivery updated successfully!');
        } catch (err) {
            alert(err.message);
        }
    };

    const handleCreateStaff = async (e) => {
        e.preventDefault();
        try {
            const token = localStorage.getItem('authToken');
            const response = await fetch('http://127.0.0.1:8000/deliveries/admin/staff/', {
                method: 'POST',
                headers: {
                    'Authorization': `Token ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: newUsername,
                    password: newPassword,
                    email: newEmail,
                    address: newAddress,
                    role: newRole
                })
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to create staff.');

            alert('Staff created successfully!');
            setNewUsername('');
            setNewPassword('');
            setNewEmail('');
            setNewAddress('');
            setShowNewStaffForm(false);
            fetchStaff();
        } catch (err) {
            alert(err.message);
        }
    };

    const handleUpdateStaff = async (e, id) => {
        e.preventDefault();
        try {
            const token = localStorage.getItem('authToken');
            const response = await fetch(`http://127.0.0.1:8000/deliveries/admin/staff/${id}/update/`, {
                method: 'PATCH',
                headers: {
                    'Authorization': `Token ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    email: editEmail,
                    address: editAddress,
                    role: editRole
                })
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to update staff profile.');

            alert('Staff profile updated!');
            setEditingStaffId(null);
            fetchStaff();
        } catch (err) {
            alert(err.message);
        }
    };

    // Filter deliveries into active fulfillment and completed history
    const activeDeliveries = deliveries.filter(item => item.status !== 'DELIVERED');
    const completedDeliveries = deliveries.filter(item => item.status === 'DELIVERED');
    const displayedDeliveries = deliveryTab === 'active' ? activeDeliveries : completedDeliveries;

    // Sellers section: derive the seller directory from the existing deliveries data
    // (no backend changes — each order item carries seller_username + seller_address)
    const sellersMap = {};
    deliveries.forEach(item => {
        const username = item.seller_username;
        if (!username) return;
        if (!sellersMap[username]) {
            sellersMap[username] = {
                username: username,
                city: (item.seller_address && item.seller_address !== 'N/A') ? item.seller_address : 'N/A',
                itemsSold: 0,
                totalValue: 0
            };
        }
        sellersMap[username].itemsSold += 1;
        sellersMap[username].totalValue += parseFloat(item.item_price || 0);
    });
    const sellers = Object.values(sellersMap).sort((a, b) => b.totalValue - a.totalValue);

    return (
        <div style={{ minHeight: '100vh', backgroundColor: '#f8fafc' }}>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 32px', backgroundColor: '#ffffff', borderBottom: '1px solid #e2e8f0' }}>
                <h1 style={{ fontSize: '20px', fontWeight: 'bold', color: '#0f172a', margin: 0 }}>VendorPulse Admin Portal</h1>
                <button onClick={onLogout} style={{ padding: '8px 16px', backgroundColor: '#ef4444', color: '#ffffff', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Logout</button>
            </header>

            <div style={{ display: 'flex', gap: '16px', padding: '16px 32px', backgroundColor: '#ffffff', borderBottom: '1px solid #e2e8f0' }}>
                <button onClick={() => setActiveTab('deliveries')} style={{ padding: '8px 16px', backgroundColor: activeTab === 'deliveries' ? '#0f172a' : 'transparent', color: activeTab === 'deliveries' ? '#ffffff' : '#64748b', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Orders & Deliveries</button>
                <button onClick={() => setActiveTab('staff')} style={{ padding: '8px 16px', backgroundColor: activeTab === 'staff' ? '#0f172a' : 'transparent', color: activeTab === 'staff' ? '#ffffff' : '#64748b', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Staff Management</button>
                <button onClick={() => setActiveTab('sellers')} style={{ padding: '8px 16px', backgroundColor: activeTab === 'sellers' ? '#0f172a' : 'transparent', color: activeTab === 'sellers' ? '#ffffff' : '#64748b', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Sellers</button>
            </div>

            <main style={{ padding: '32px' }}>
                {activeTab === 'deliveries' && (
                    <div>
                        <h2 style={{ marginBottom: '16px', color: '#0f172a' }}>Orders & Fulfillment Tracking</h2>

                        {/* Sub-tabs for Active vs Completed Deliveries */}
                        <div style={{ display: 'flex', gap: '24px', borderBottom: '2px solid #e2e8f0', marginBottom: '24px' }}>
                            <button
                                onClick={() => setDeliveryTab('active')}
                                style={{ padding: '8px 0', background: 'none', border: 'none', borderBottom: deliveryTab === 'active' ? '2px solid #2563eb' : '2px solid transparent', color: deliveryTab === 'active' ? '#2563eb' : '#64748b', fontWeight: '600', cursor: 'pointer', marginBottom: '-2px' }}
                            >
                                Active Orders ({activeDeliveries.length})
                            </button>
                            <button
                                onClick={() => setDeliveryTab('completed')}
                                style={{ padding: '8px 0', background: 'none', border: 'none', borderBottom: deliveryTab === 'completed' ? '2px solid #2563eb' : '2px solid transparent', color: deliveryTab === 'completed' ? '#2563eb' : '#64748b', fontWeight: '600', cursor: 'pointer', marginBottom: '-2px' }}
                            >
                                Completed History ({completedDeliveries.length})
                            </button>
                        </div>

                        {loadingDeliveries ? <p>Loading orders...</p> : displayedDeliveries.length === 0 ? (
                            <div style={{ backgroundColor: '#ffffff', padding: '32px', borderRadius: '8px', textAlign: 'center', color: '#64748b', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                                <p style={{ margin: 0 }}>
                                    {deliveryTab === 'active' ? 'No active orders requiring fulfillment.' : 'No completed delivery history.'}
                                </p>
                            </div>
                        ) : (
                            <div style={{ backgroundColor: '#ffffff', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', overflow: 'hidden' }}>
                                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                                    <thead style={{ backgroundColor: '#f1f5f9', borderBottom: '1px solid #e2e8f0' }}>
                                        <tr>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Order # / Item</th>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Shipping Address</th>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Phone</th>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Status</th>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Assigned Agent</th>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Tracking #</th>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {displayedDeliveries.map(item => (
                                            <tr key={item.id} style={{ borderBottom: '1px solid #e2e8f0', verticalAlign: 'top' }}>
                                                <td style={{ padding: '12px 16px' }}>
                                                    <div style={{ fontWeight: '600', color: '#0f172a' }}>Order #{item.order_id}</div>
                                                    <div style={{ fontSize: '13px', color: '#2563eb', marginTop: '4px' }}>{item.item_title}</div>
                                                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                                                        <b>Seller:</b> {item.seller_username} (<span style={{ color: '#d97706' }}>{item.seller_address}</span>)
                                                    </div>
                                                </td>
                                                <td style={{ padding: '12px 16px' }}>{item.shipping_address}</td>
                                                <td style={{ padding: '12px 16px' }}>{item.phone}</td>
                                                <td style={{ padding: '12px 16px' }}>
                                                    <span style={{ padding: '4px 8px', borderRadius: '4px', backgroundColor: item.status === 'DELIVERED' ? '#dcfce7' : '#e0f2fe', color: item.status === 'DELIVERED' ? '#166534' : '#0369a1', fontSize: '11px', fontWeight: '600' }}>
                                                        {item.status}
                                                    </span>
                                                </td>
                                                <td style={{ padding: '12px 16px' }}>{item.agent_username || 'Unassigned'}</td>
                                                <td style={{ padding: '12px 16px' }}>{item.tracking_number || 'None'}</td>
                                                <td style={{ padding: '12px 16px' }}>
                                                    {selectedDeliveryId === item.id ? (
                                                        <form onSubmit={(e) => handleAssign(e, item.id)}>
                                                            <input type="number" placeholder="Agent ID" value={agentId} onChange={(e) => setAgentId(e.target.value)} style={{ padding: '6px', width: '90px', marginRight: '6px', marginBottom: '6px', borderRadius: '4px', border: '1px solid #cbd5e1' }} />
                                                            <input type="text" placeholder="Tracking #" value={trackingNumber} onChange={(e) => setTrackingNumber(e.target.value)} style={{ padding: '6px', width: '110px', marginRight: '6px', marginBottom: '6px', borderRadius: '4px', border: '1px solid #cbd5e1' }} />
                                                            <button type="submit" style={{ padding: '6px 10px', backgroundColor: '#10b981', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Save</button>
                                                            <button type="button" onClick={() => setSelectedDeliveryId(null)} style={{ padding: '6px 10px', backgroundColor: '#64748b', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', marginLeft: '4px' }}>Cancel</button>
                                                        </form>
                                                    ) : (
                                                        <button onClick={() => { setSelectedDeliveryId(item.id); setAgentId(item.assigned_agent || ''); setTrackingNumber(item.tracking_number || ''); }} style={{ padding: '6px 12px', backgroundColor: '#2563eb', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Assign / Edit</button>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'staff' && (
                    <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                            <h2 style={{ color: '#0f172a', margin: 0 }}>Staff & Delivery Agent Directory</h2>
                            <button onClick={() => setShowNewStaffForm(!showNewStaffForm)} style={{ padding: '10px 16px', backgroundColor: '#0f172a', color: '#ffffff', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>
                                {showNewStaffForm ? 'Cancel' : '+ Add New Staff/Agent'}
                            </button>
                        </div>

                        {showNewStaffForm && (
                            <div style={{ backgroundColor: '#ffffff', padding: '24px', borderRadius: '8px', marginBottom: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', maxWidth: '500px' }}>
                                <h3 style={{ marginTop: 0, marginBottom: '16px' }}>Create New Staff Account</h3>
                                <form onSubmit={handleCreateStaff}>
                                    <div style={{ marginBottom: '12px' }}>
                                        <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '4px' }}>Username</label>
                                        <input type="text" value={newUsername} onChange={(e) => setNewUsername(e.target.value)} required style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #cbd5e1', boxSizing: 'border-box' }} />
                                    </div>
                                    <div style={{ marginBottom: '12px' }}>
                                        <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '4px' }}>Email</label>
                                        <input type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #cbd5e1', boxSizing: 'border-box' }} />
                                    </div>
                                    <div style={{ marginBottom: '12px' }}>
                                        <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '4px' }}>Address / City</label>
                                        <input type="text" value={newAddress} onChange={(e) => setNewAddress(e.target.value)} placeholder="e.g. Pune, Maharashtra" style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #cbd5e1', boxSizing: 'border-box' }} />
                                    </div>
                                    <div style={{ marginBottom: '12px' }}>
                                        <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '4px' }}>Password</label>
                                        <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #cbd5e1', boxSizing: 'border-box' }} />
                                    </div>
                                    <div style={{ marginBottom: '20px' }}>
                                        <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', marginBottom: '4px' }}>Role</label>
                                        <select value={newRole} onChange={(e) => setNewRole(e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #cbd5e1', boxSizing: 'border-box' }}>
                                            <option value="agent">Delivery Agent</option>
                                            <option value="admin">Admin / Staff</option>
                                        </select>
                                    </div>
                                    <button type="submit" style={{ padding: '10px 16px', backgroundColor: '#10b981', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Create Account</button>
                                </form>
                            </div>
                        )}

                        {loadingStaff ? <p>Loading staff...</p> : (
                            <div style={{ backgroundColor: '#ffffff', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', overflow: 'hidden' }}>
                                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                                    <thead style={{ backgroundColor: '#f1f5f9', borderBottom: '1px solid #e2e8f0' }}>
                                        <tr>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>User ID</th>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Username</th>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Email</th>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Address / City</th>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Role</th>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Actions</th>
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Verification</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {staffList.map(member => (
                                            <tr key={member.id} style={{ borderBottom: '1px solid #e2e8f0' }}>
                                                <td style={{ padding: '12px 16px' }}>#{member.id}</td>
                                                <td style={{ padding: '12px 16px', fontWeight: '500' }}>{member.username}</td>
                                                
                                                {editingStaffId === member.id ? (
                                                    <>
                                                        <td style={{ padding: '12px 16px' }}>
                                                            <input type="email" value={editEmail} onChange={(e) => setEditEmail(e.target.value)} style={{ padding: '6px', borderRadius: '4px', border: '1px solid #cbd5e1', width: '160px' }} />
                                                        </td>
                                                        <td style={{ padding: '12px 16px' }}>
                                                            <input type="text" value={editAddress} onChange={(e) => setEditAddress(e.target.value)} style={{ padding: '6px', borderRadius: '4px', border: '1px solid #cbd5e1', width: '160px' }} />
                                                        </td>
                                                        <td style={{ padding: '12px 16px' }}>
                                                            <select value={editRole} onChange={(e) => setEditRole(e.target.value)} style={{ padding: '6px', borderRadius: '4px', border: '1px solid #cbd5e1' }}>
                                                                <option value="agent">Delivery Agent</option>
                                                                <option value="admin">Admin</option>
                                                            </select>
                                                        </td>
                                                        <td style={{ padding: '12px 16px' }}>
                                                            <button onClick={(e) => handleUpdateStaff(e, member.id)} style={{ padding: '6px 10px', backgroundColor: '#10b981', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', marginRight: '4px' }}>Save</button>
                                                            <button onClick={() => setEditingStaffId(null)} style={{ padding: '6px 10px', backgroundColor: '#64748b', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Cancel</button>
                                                        </td>
                                                    </>
                                                ) : (
                                                    <>
                                                        <td style={{ padding: '12px 16px' }}>{member.email || 'N/A'}</td>
                                                        <td style={{ padding: '12px 16px' }}>{member.address || 'N/A'}</td>
                                                        <td style={{ padding: '12px 16px' }}>
                                                            {member.is_staff && <span style={{ marginRight: '6px', padding: '3px 8px', backgroundColor: '#fef3c7', color: '#d97706', borderRadius: '4px', fontSize: '12px', fontWeight: '600' }}>Admin</span>}
                                                            {member.is_agent && <span style={{ padding: '3px 8px', backgroundColor: '#dcfce7', color: '#16a34a', borderRadius: '4px', fontSize: '12px', fontWeight: '600' }}>Delivery Agent</span>}
                                                        </td>
                                                        <td style={{ padding: '12px 16px' }}>
                                                            <button 
                                                                onClick={() => {
                                                                    setEditingStaffId(member.id);
                                                                    setEditEmail(member.email || '');
                                                                    setEditAddress(member.address === 'N/A' ? '' : (member.address || ''));
                                                                    setEditRole(member.is_staff ? 'admin' : 'agent');
                                                                }}
                                                                style={{ padding: '6px 12px', backgroundColor: '#0f172a', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '13px' }}
                                                            >
                                                                Update Profile
                                                            </button>
                                                        </td>
                                                        <td style={{ padding: '12px 16px' }}>
                                                            {member.is_verified ? (
                                                                <span style={{ color: '#059669', fontWeight: 'bold', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                                                    ✓ Verified
                                                                </span>
                                                            ) : (
                                                                <span style={{ color: '#64748b' }}>Unverified</span>
                                                            )}
                                                        </td>
                                                        <td style={{ padding: '12px 16px' }}>
                                                            <button 
                                                                onClick={() => toggleVerification(member.id, member.is_verified)}
                                                                style={{ padding: '6px 12px', backgroundColor: member.is_verified ? '#ef4444' : '#10b981', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}
                                                            >
                                                                {member.is_verified ? 'Revoke Verification' : 'Verify Seller'}
                                                            </button>
                                                        </td>
                                                    </>
                                                )}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'sellers' && (
                    <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                            <h2 style={{ color: '#0f172a', margin: 0 }}>Sellers Directory</h2>
                            <span style={{ fontSize: '13px', color: '#64748b' }}>{sellers.length} Seller{sellers.length === 1 ? '' : 's'}</span>
                        </div>

                        {loadingDeliveries ? <p>Loading sellers...</p> : sellers.length === 0 ? (
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
                                            <th style={{ padding: '12px 16px', color: '#475569' }}>Verified Seller</th>

                                        </tr>
                                    </thead>
                                    <tbody>
                                        {sellers.map(seller => (
                                            <tr key={seller.username} style={{ borderBottom: '1px solid #e2e8f0' }}>
                                                <td style={{ padding: '12px 16px', fontWeight: '600', color: '#0f172a' }}>@{seller.username}</td>
                                                <td style={{ padding: '12px 16px' }}>{seller.city}</td>
                                                <td style={{ padding: '12px 16px' }}>{seller.itemsSold}</td>
                                                <td style={{ padding: '12px 16px', fontWeight: '600', color: '#059669' }}>₹{seller.totalValue.toFixed(2)}</td>
                                                {/* <td style={{ padding: '12px 16px' }}>
                                                            {member.is_verified ? (
                                                                <span style={{ color: '#059669', fontWeight: 'bold', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                                                    ✓ Verified
                                                                </span>
                                                            ) : (
                                                                <span style={{ color: '#64748b' }}>Unverified</span>
                                                            )}
                                                        </td>
                                                        <td style={{ padding: '12px 16px' }}>
                                                            <button 
                                                                onClick={() => toggleVerification(member.id, member.is_verified)}
                                                                style={{ padding: '6px 12px', backgroundColor: member.is_verified ? '#ef4444' : '#10b981', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}
                                                            >
                                                                {member.is_verified ? 'Revoke Verification' : 'Verify Seller'}
                                                            </button>
                                                        </td> */}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                )}
            </main>
        </div>
    );
}