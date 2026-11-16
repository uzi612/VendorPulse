import React, { useState, useEffect } from 'react';
import { api } from '../../../api';
import { CITIES } from '../../../cities';
import Pagination from '../../../components/Pagination';
import { useToast } from '../../../components/Toast';

// Orders & Deliveries tab: fulfillment table with agent assignment,
// tracking numbers and shipping-detail editing. Sub-tab/page state is
// lifted into AdminPortal so it survives switching tabs.
export default function OrdersTab({ deliveryTab, setDeliveryTab, page, setPage }) {
    const toast = useToast();
    const [deliveries, setDeliveries] = useState([]);
    const [deliveryMeta, setDeliveryMeta] = useState(null);   // {count, total_pages, page, page_size, active_count, completed_count, cancelled_count}
    const [loadingDeliveries, setLoadingDeliveries] = useState(true);
    const [selectedDeliveryId, setSelectedDeliveryId] = useState(null);
    const [agentId, setAgentId] = useState('');
    const [trackingNumber, setTrackingNumber] = useState('');

    // Edit Order state (shipping details, shared across all rows of one order)
    const [editingOrderId, setEditingOrderId] = useState(null);
    const [orderForm, setOrderForm] = useState({ shipping_city: '', shipping_address: '', phone: '' });

    const fetchDeliveries = async () => {
        setLoadingDeliveries(true);
        try {
            const response = await api(`/api/deliveries/admin/deliveries/?page=${page}&page_size=10&status_group=${deliveryTab}`);
            if (!response.ok) throw new Error('Failed to fetch deliveries.');
            const data = await response.json();
            setDeliveries(data.results);
            setDeliveryMeta(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoadingDeliveries(false);
        }
    };

    useEffect(() => { fetchDeliveries(); }, [page, deliveryTab]);

    const handleAssign = async (e, id) => {
        e.preventDefault();
        try {
            const response = await api(`/api/deliveries/admin/deliveries/${id}/assign/`, {
                method: 'PATCH',
                body: JSON.stringify({
                    assigned_agent: agentId ? parseInt(agentId) : null,
                    tracking_number: trackingNumber
                })
            });

            if (!response.ok) throw new Error('Failed to assign delivery.');
            fetchDeliveries();
            setSelectedDeliveryId(null);
            toast.success('Delivery updated successfully!');
        } catch (err) {
            toast.error(err.message);
        }
    };

    const startEditOrder = (item) => {
        setEditingOrderId(item.order_id);
        setOrderForm({
            shipping_city: item.shipping_city || '',
            shipping_address: item.shipping_address === 'N/A' ? '' : (item.shipping_address || ''),
            phone: item.phone === 'N/A' ? '' : (item.phone || '')
        });
    };

    const handleOrderUpdate = async (orderId) => {
        try {
            const response = await api(`/api/deliveries/admin/orders/${orderId}/update/`, {
                method: 'PATCH',
                body: JSON.stringify(orderForm)
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to update order.');
            toast.success('Order updated successfully!');
            setEditingOrderId(null);
            fetchDeliveries();
        } catch (err) {
            toast.error(err.message);
        }
    };

    // Server already filtered by deliveryTab (?status_group=) — use as-is
    const displayedDeliveries = deliveries;

    return (
        <div>
            <h2 style={{ marginBottom: '16px', color: '#0f172a' }}>Orders & Fulfillment Tracking</h2>

            <div style={{ display: 'flex', gap: '24px', borderBottom: '2px solid #e2e8f0', marginBottom: '24px' }}>
                <button
                    onClick={() => { setDeliveryTab('active'); setPage(1); }}
                    style={{ padding: '8px 0', background: 'none', border: 'none', borderBottom: deliveryTab === 'active' ? '2px solid #2563eb' : '2px solid transparent', color: deliveryTab === 'active' ? '#2563eb' : '#64748b', fontWeight: '600', cursor: 'pointer', marginBottom: '-2px' }}
                >
                    Active Orders ({deliveryMeta ? deliveryMeta.active_count : '…'})
                </button>
                <button
                    onClick={() => { setDeliveryTab('completed'); setPage(1); }}
                    style={{ padding: '8px 0', background: 'none', border: 'none', borderBottom: deliveryTab === 'completed' ? '2px solid #2563eb' : '2px solid transparent', color: deliveryTab === 'completed' ? '#2563eb' : '#64748b', fontWeight: '600', cursor: 'pointer', marginBottom: '-2px' }}
                >
                    Completed History ({deliveryMeta ? deliveryMeta.completed_count : '…'})
                </button>
                <button
                    onClick={() => { setDeliveryTab('cancelled'); setPage(1); }}
                    style={{ padding: '8px 0', background: 'none', border: 'none', borderBottom: deliveryTab === 'cancelled' ? '2px solid #dc2626' : '2px solid transparent', color: deliveryTab === 'cancelled' ? '#dc2626' : '#64748b', fontWeight: '600', cursor: 'pointer', marginBottom: '-2px' }}
                >
                    ✕ Cancelled ({deliveryMeta ? deliveryMeta.cancelled_count : '…'})
                </button>
            </div>

            {loadingDeliveries ? <p>Loading orders...</p> : displayedDeliveries.length === 0 ? (
                <div style={{ backgroundColor: '#ffffff', padding: '32px', borderRadius: '8px', textAlign: 'center', color: '#64748b', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                    <p style={{ margin: 0 }}>
                        {deliveryTab === 'active' ? 'No active orders requiring fulfillment.' : deliveryTab === 'cancelled' ? 'No cancelled orders.' : 'No completed delivery history.'}
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
                                    <td style={{ padding: '12px 16px' }}>
                                        {editingOrderId === item.order_id ? (
                                            <>
                                                <select value={orderForm.shipping_city} onChange={(e) => setOrderForm({ ...orderForm, shipping_city: e.target.value })} style={{ width: '100%', padding: '6px', marginBottom: '6px', borderRadius: '4px', border: '1px solid #cbd5e1', boxSizing: 'border-box', backgroundColor: '#fff' }}>
                                                    <option value="">Select City</option>
                                                    {CITIES.map(city => <option key={city} value={city}>{city}</option>)}
                                                </select>
                                                <textarea rows="2" value={orderForm.shipping_address} onChange={(e) => setOrderForm({ ...orderForm, shipping_address: e.target.value })} style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid #cbd5e1', boxSizing: 'border-box' }} />
                                            </>
                                        ) : (
                                            <>
                                                {item.shipping_city && <div style={{ fontSize: '12px', color: '#2563eb', fontWeight: '600', marginBottom: '2px' }}>📍 {item.shipping_city}</div>}
                                                {item.shipping_address}
                                            </>
                                        )}
                                    </td>
                                    <td style={{ padding: '12px 16px' }}>
                                        {editingOrderId === item.order_id ? (
                                            <input type="text" value={orderForm.phone} onChange={(e) => setOrderForm({ ...orderForm, phone: e.target.value })} style={{ width: '120px', padding: '6px', borderRadius: '4px', border: '1px solid #cbd5e1' }} />
                                        ) : (
                                            item.phone
                                        )}
                                    </td>
                                    <td style={{ padding: '12px 16px' }}>
                                        <span style={{ padding: '4px 8px', borderRadius: '4px', backgroundColor: item.status === 'DELIVERED' ? '#dcfce7' : item.status === 'CANCELLED' ? '#fee2e2' : '#e0f2fe', color: item.status === 'DELIVERED' ? '#166534' : item.status === 'CANCELLED' ? '#b91c1c' : '#0369a1', fontSize: '11px', fontWeight: '600' }}>
                                            {item.status}
                                        </span>
                                        {item.status === 'CANCELLED' && item.cancel_reason && (
                                            <div style={{ fontSize: '11px', color: '#b91c1c', marginTop: '4px' }}>
                                                Reason: {String(item.cancel_reason).replaceAll('_', ' ').toLowerCase()}
                                                {item.cancel_note && <div style={{ color: '#64748b' }}>“{item.cancel_note}”</div>}
                                            </div>
                                        )}
                                    </td>
                                    <td style={{ padding: '12px 16px' }}>{item.agent_username || 'Unassigned'}</td>
                                    <td style={{ padding: '12px 16px' }}>{item.tracking_number || 'None'}</td>
                                    <td style={{ padding: '12px 16px' }}>
                                        {item.status === 'CANCELLED' ? (
                                            <span style={{ fontSize: '12px', color: '#64748b' }}>Read-only</span>
                                        ) : editingOrderId === item.order_id ? (
                                            <>
                                                <button type="button" onClick={() => handleOrderUpdate(item.order_id)} style={{ padding: '6px 10px', backgroundColor: '#10b981', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Save Order</button>
                                                <button type="button" onClick={() => setEditingOrderId(null)} style={{ padding: '6px 10px', backgroundColor: '#64748b', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', marginLeft: '4px' }}>Cancel</button>
                                            </>
                                        ) : selectedDeliveryId === item.id ? (
                                            <form onSubmit={(e) => handleAssign(e, item.id)}>
                                                <input type="number" placeholder="Agent ID" value={agentId} onChange={(e) => setAgentId(e.target.value)} style={{ padding: '6px', width: '90px', marginRight: '6px', marginBottom: '6px', borderRadius: '4px', border: '1px solid #cbd5e1' }} />
                                                <input type="text" placeholder="Tracking #" value={trackingNumber} onChange={(e) => setTrackingNumber(e.target.value)} style={{ padding: '6px', width: '110px', marginRight: '6px', marginBottom: '6px', borderRadius: '4px', border: '1px solid #cbd5e1' }} />
                                                <button type="submit" style={{ padding: '6px 10px', backgroundColor: '#10b981', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Save</button>
                                                <button type="button" onClick={() => setSelectedDeliveryId(null)} style={{ padding: '6px 10px', backgroundColor: '#64748b', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', marginLeft: '4px' }}>Cancel</button>
                                            </form>
                                        ) : (
                                            <>
                                                <button onClick={() => { setSelectedDeliveryId(item.id); setAgentId(item.assigned_agent || ''); setTrackingNumber(item.tracking_number || ''); }} style={{ padding: '6px 12px', backgroundColor: '#2563eb', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Assign / Edit</button>
                                                <button type="button" onClick={() => startEditOrder(item)} style={{ padding: '6px 12px', backgroundColor: '#0f172a', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', marginLeft: '4px' }}>Edit Order</button>
                                            </>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            <Pagination meta={deliveryMeta} page={page} setPage={setPage} />
        </div>
    );
}
