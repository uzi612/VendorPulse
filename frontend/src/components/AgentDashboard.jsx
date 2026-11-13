import React, { useState, useEffect } from 'react';
import { api } from '../api';
import NotificationsBell from './NotificationsBell';

export default function AgentDashboard({ onLogout }) {
    const [activeTab, setActiveTab] = useState('orders');
    const [deliveryTab, setDeliveryTab] = useState('active'); 
    const [tasks, setTasks] = useState([]);
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // OTP confirmation modal state
    const [otpModal, setOtpModal] = useState(null);   // { taskId, orderId, itemTitle }
    const [otpValue, setOtpValue] = useState('');
    const [otpError, setOtpError] = useState(null);
    const [otpSubmitting, setOtpSubmitting] = useState(false);

    const statusChoices = [
        { value: 'ORDER_PLACED', label: 'Order Placed' },
        { value: 'PICKUP_SCHEDULED', label: 'Pickup Scheduled' },
        { value: 'PICKED_UP', label: 'Picked Up from Seller' },
        { value: 'DISPATCHED', label: 'In Transit / Dispatched' },
        { value: 'DELIVERED', label: 'Delivered to Buyer' }
    ];

    const fetchAgentData = async () => {
        setLoading(true);
        try {
            const tasksRes = await api('/api/deliveries/agent/deliveries/');
            if (!tasksRes.ok) throw new Error('Failed to fetch assigned tasks.');
            const tasksData = await tasksRes.json();
            setTasks(tasksData);

            const profileRes = await api('/api/deliveries/agent/profile/');
            if (profileRes.ok) {
                const profileData = await profileRes.json();
                setProfile(profileData);
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchAgentData(); }, []);

    const updateStatus = async (id, newStatus) => {
        // DELIVERED requires the buyer's OTP -> open the OTP modal instead
        if (newStatus === 'DELIVERED') {
            const task = tasks.find(t => t.id === id);
            if (task) {
                setOtpModal({ taskId: id, orderId: task.order_id, itemTitle: task.item_title });
                setOtpValue('');
                setOtpError(null);
            }
            return;
        }
        try {
            const response = await api(`/api/deliveries/agent/deliveries/${id}/update/`, {
                method: 'PATCH',
                body: JSON.stringify({ status: newStatus })
            });

            if (!response.ok) throw new Error('Failed to update status.');
            fetchAgentData();
            alert('Delivery step updated successfully!');
        } catch (err) {
            alert(err.message);
        }
    };

    const confirmDelivery = async () => {
        setOtpSubmitting(true);
        setOtpError(null);
        try {
            const response = await api(`/api/deliveries/agent/deliveries/${otpModal.taskId}/update/`, {
                method: 'PATCH',
                body: JSON.stringify({ status: 'DELIVERED', otp: otpValue })
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                setOtpError(data.error || 'Failed to confirm delivery.');
                return;
            }
            setOtpModal(null);
            fetchAgentData();
            alert('Delivery confirmed — OTP verified!');
        } catch (err) {
            setOtpError('Network error. Please try again.');
        } finally {
            setOtpSubmitting(false);
        }
    };

    if (loading && tasks.length === 0) return <div style={{ padding: '32px', textAlign: 'center' }}>Loading Agent Dashboard...</div>;
    if (error) return <div style={{ padding: '32px', color: 'red' }}>Error: {error}</div>;

    // Filter tasks into active vs completed
    const activeTasks = tasks.filter(t => t.status !== 'DELIVERED');
    const completedTasks = tasks.filter(t => t.status === 'DELIVERED');
    const displayedTasks = deliveryTab === 'active' ? activeTasks : completedTasks;

    return (
        <div style={{ minHeight: '100vh', backgroundColor: '#f8fafc' }}>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 32px', backgroundColor: '#ffffff', borderBottom: '1px solid #e2e8f0' }}>
                <h1 style={{ fontSize: '20px', fontWeight: 'bold', color: '#0f172a', margin: 0 }}>VendorPulse Delivery Agent Portal</h1>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <NotificationsBell />
                    <button onClick={onLogout} style={{ padding: '8px 16px', backgroundColor: '#ef4444', color: '#ffffff', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Logout</button>
                </div>
            </header>

            <div style={{ display: 'flex', gap: '16px', padding: '16px 32px', backgroundColor: '#ffffff', borderBottom: '1px solid #e2e8f0' }}>
                <button onClick={() => setActiveTab('orders')} style={{ padding: '8px 16px', backgroundColor: activeTab === 'orders' ? '#0f172a' : 'transparent', color: activeTab === 'orders' ? '#ffffff' : '#64748b', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Assigned Orders</button>
                <button onClick={() => setActiveTab('profile')} style={{ padding: '8px 16px', backgroundColor: activeTab === 'profile' ? '#0f172a' : 'transparent', color: activeTab === 'profile' ? '#ffffff' : '#64748b', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>My Profile</button>
            </div>

            <main style={{ padding: '32px', maxWidth: '1000px', margin: '0 auto' }}>
                {activeTab === 'orders' && (
                    <div>
                        <h2 style={{ marginBottom: '16px', color: '#0f172a' }}>Assigned Delivery Tasks</h2>
                        
                        {/* Sub-tabs for Active vs Completed Tasks */}
                        <div style={{ display: 'flex', gap: '24px', borderBottom: '2px solid #e2e8f0', marginBottom: '24px' }}>
                            <button
                                onClick={() => setDeliveryTab('active')}
                                style={{ padding: '8px 0', background: 'none', border: 'none', borderBottom: deliveryTab === 'active' ? '2px solid #2563eb' : '2px solid transparent', color: deliveryTab === 'active' ? '#2563eb' : '#64748b', fontWeight: '600', cursor: 'pointer', marginBottom: '-2px' }}
                            >
                                Active Deliveries ({activeTasks.length})
                            </button>
                            <button
                                onClick={() => setDeliveryTab('completed')}
                                style={{ padding: '8px 0', background: 'none', border: 'none', borderBottom: deliveryTab === 'completed' ? '2px solid #2563eb' : '2px solid transparent', color: deliveryTab === 'completed' ? '#2563eb' : '#64748b', fontWeight: '600', cursor: 'pointer', marginBottom: '-2px' }}
                            >
                                Completed History ({completedTasks.length})
                            </button>
                        </div>

                        {displayedTasks.length === 0 ? (
                            <div style={{ backgroundColor: '#ffffff', padding: '32px', borderRadius: '8px', textAlign: 'center', color: '#64748b', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                                <p style={{ margin: 0 }}>
                                    {deliveryTab === 'active' ? 'No active delivery tasks assigned to you right now.' : 'No completed delivery history yet.'}
                                </p>
                            </div>
                        ) : (
                            <div style={{ display: 'grid', gap: '20px' }}>
                                {displayedTasks.map(task => (
                                    <div key={task.id} style={{ backgroundColor: '#ffffff', border: '1px solid #e2e8f0', padding: '24px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                                            <div>
                                                <h3 style={{ margin: '0 0 4px 0', color: '#0f172a' }}>Order #{task.order_id} • Item #{task.id}</h3>
                                                <div style={{ fontSize: '16px', fontWeight: '600', color: '#2563eb' }}>{task.item_title}</div>
                                            </div>
                                            <span style={{ padding: '6px 12px', borderRadius: '20px', backgroundColor: task.status === 'DELIVERED' ? '#dcfce7' : '#e0f2fe', color: task.status === 'DELIVERED' ? '#166534' : '#0369a1', fontSize: '12px', fontWeight: '600' }}>
                                                {task.status}
                                            </span>
                                        </div>
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', margin: '16px 0', fontSize: '14px', color: '#475569' }}>
                                            <div><b>Seller Pickup From:</b> <span style={{ color: '#d97706' }}>{task.seller_username} ({task.seller_address})</span></div>
                                            <div><b>Buyer Shipping Address:</b> {task.shipping_address}</div>
                                            <div><b>Phone:</b> {task.phone}</div>
                                            <div><b>Tracking Number:</b> {task.tracking_number || 'N/A'}</div>
                                        </div>
                                        <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                                            <label style={{ fontSize: '14px', fontWeight: '600', color: '#0f172a' }}>Update Fulfillment Step:</label>
                                            <select value={task.status} onChange={(e) => updateStatus(task.id, e.target.value)} style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', backgroundColor: '#fff', fontWeight: '500' }}>
                                                {statusChoices.map(choice => (
                                                    <option key={choice.value} value={choice.value}>{choice.label}</option>
                                                ))}
                                            </select>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'profile' && (
                    <div>
                        <h2 style={{ marginBottom: '16px', color: '#0f172a' }}>My Profile</h2>
                        <div style={{ backgroundColor: '#ffffff', padding: '24px', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', maxWidth: '500px' }}>
                            <p style={{ color: '#64748b', fontSize: '13px', marginBottom: '20px' }}>
                                Profile details are read-only and managed by your administrator.
                            </p>
                            <div style={{ marginBottom: '16px' }}>
                                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>AGENT ID</label>
                                <div style={{ fontSize: '16px', fontWeight: '500', color: '#0f172a' }}>#{profile?.id || 'N/A'}</div>
                            </div>
                            <div style={{ marginBottom: '16px' }}>
                                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>USERNAME</label>
                                <div style={{ fontSize: '16px', fontWeight: '500', color: '#0f172a' }}>{profile?.username || 'N/A'}</div>
                            </div>
                            <div style={{ marginBottom: '16px' }}>
                                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>EMAIL ADDRESS</label>
                                <div style={{ fontSize: '16px', fontWeight: '500', color: '#0f172a' }}>{profile?.email || 'N/A'}</div>
                            </div>
                            <div style={{ marginBottom: '16px' }}>
                                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>ASSIGNED CITY / ADDRESS</label>
                                <div style={{ fontSize: '16px', fontWeight: '500', color: '#0f172a' }}>{profile?.address || 'N/A'}</div>
                            </div>
                            <div>
                                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>ROLE</label>
                                <div style={{ fontSize: '16px', fontWeight: '500', color: '#16a34a' }}>Delivery Agent</div>
                            </div>
                        </div>
                    </div>
                )}
            </main>

            {/* OTP Confirmation Modal */}
            {otpModal && (
                <div
                    onClick={() => !otpSubmitting && setOtpModal(null)}
                    style={{
                        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                        backgroundColor: 'rgba(15, 23, 42, 0.55)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        zIndex: 2000, padding: '16px',
                    }}
                >
                    <div
                        onClick={(e) => e.stopPropagation()}
                        style={{
                            backgroundColor: '#ffffff', borderRadius: '12px', padding: '28px',
                            width: '360px', maxWidth: '100%', boxShadow: '0 20px 50px rgba(0,0,0,0.3)',
                        }}
                    >
                        <h3 style={{ margin: '0 0 6px 0', fontSize: '18px', color: '#0f172a' }}>
                            🔐 Confirm Delivery
                        </h3>
                        <p style={{ margin: '0 0 4px 0', fontSize: '14px', fontWeight: '600', color: '#2563eb' }}>
                            {otpModal.itemTitle}
                        </p>
                        <p style={{ margin: '0 0 16px 0', fontSize: '13px', color: '#64748b', lineHeight: 1.5 }}>
                            Ask the buyer for their <b>4-digit delivery code</b> (shown on their order
                            receipt) and enter it below. Delivery can only be confirmed with the correct code.
                        </p>

                        <input
                            type="text"
                            inputMode="numeric"
                            autoFocus
                            maxLength={4}
                            value={otpValue}
                            onChange={(e) => setOtpValue(e.target.value.replace(/\D/g, '').slice(0, 4))}
                            onKeyDown={(e) => { if (e.key === 'Enter' && otpValue.length === 4) confirmDelivery(); }}
                            placeholder="• • • •"
                            disabled={otpSubmitting}
                            style={{
                                width: '100%', boxSizing: 'border-box', padding: '12px',
                                fontSize: '24px', letterSpacing: '0.5em', textAlign: 'center',
                                fontWeight: '700', color: '#0f172a',
                                border: '2px solid #cbd5e1', borderRadius: '8px',
                                outline: 'none', marginBottom: '12px',
                            }}
                        />

                        {otpError && (
                            <p style={{ margin: '0 0 12px 0', fontSize: '13px', fontWeight: '600', color: '#dc2626' }}>
                                ⚠️ {otpError}
                            </p>
                        )}

                        <div style={{ display: 'flex', gap: '10px' }}>
                            <button
                                onClick={() => setOtpModal(null)}
                                disabled={otpSubmitting}
                                style={{
                                    flex: 1, padding: '10px', borderRadius: '8px',
                                    backgroundColor: '#f1f5f9', color: '#475569',
                                    border: 'none', fontWeight: '600', cursor: 'pointer',
                                }}
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmDelivery}
                                disabled={otpValue.length !== 4 || otpSubmitting}
                                style={{
                                    flex: 1, padding: '10px', borderRadius: '8px',
                                    backgroundColor: otpValue.length === 4 && !otpSubmitting ? '#16a34a' : '#e2e8f0',
                                    color: otpValue.length === 4 && !otpSubmitting ? '#ffffff' : '#94a3b8',
                                    border: 'none', fontWeight: '600', cursor: 'pointer',
                                }}
                            >
                                {otpSubmitting ? 'Verifying...' : 'Confirm Delivery'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}