import React, { useState, useEffect, useRef } from 'react';
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
    const [fetchError, setFetchError] = useState('');
    const [searchTerm, setSearchTerm] = useState('');
    const [appliedSearch, setAppliedSearch] = useState('');
    const [selectedDeliveryId, setSelectedDeliveryId] = useState(null);
    const [agentId, setAgentId] = useState('');
    const [deliveryAgentId, setDeliveryAgentId] = useState('');
    const [trackingNumber, setTrackingNumber] = useState('');

    // Monotonic request id: rapid tab clicks start overlapping fetches, and
    // only the LATEST response may touch state. Without this guard an older
    // "active" response arriving last would overwrite the completed/
    // cancelled rows - every section would show active data.
    const fetchSeq = useRef(0);

    // Edit Order state (shipping details, shared across all rows of one order)
    const [editingOrderId, setEditingOrderId] = useState(null);
    const [orderForm, setOrderForm] = useState({ shipping_city: '', shipping_address: '', phone: '' });

    const fetchDeliveries = async () => {
        const seq = ++fetchSeq.current;
        setLoadingDeliveries(true);
        setFetchError('');
        try {
            const searchParam = appliedSearch ? `&search=${encodeURIComponent(appliedSearch)}` : '';
            const response = await api(`/api/deliveries/admin/deliveries/?page=${page}&page_size=10&status_group=${deliveryTab}${searchParam}`);
            if (!response.ok) throw new Error(`Server responded ${response.status}.`);
            const data = await response.json();
            if (seq !== fetchSeq.current) return;   // superseded by a newer tab/page fetch
            setDeliveries(data.results);
            setDeliveryMeta(data);
        } catch (err) {
            if (seq !== fetchSeq.current) return;
            console.error(err);
            // Never leave stale rows on screen pretending to be this tab's
            // data: clear them and tell the admin what happened.
            setDeliveries([]);
            setFetchError(
                `Could not load ${deliveryTab} orders (${err.message}). ` +
                'The backend may be down or restarting - retry in a moment.'
            );
        } finally {
            if (seq === fetchSeq.current) setLoadingDeliveries(false);
        }
    };

    // Debounced search: 300ms after typing stops, jump back to page 1 and
    // refetch. Typing does not hammer the API on every keystroke.
    useEffect(() => {
        const timer = setTimeout(() => {
            const next = searchTerm.trim();
            if (next !== appliedSearch) {
                setAppliedSearch(next);
                setPage(1);
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [searchTerm]);

    useEffect(() => { fetchDeliveries(); }, [page, deliveryTab, appliedSearch]);

    const handleAssign = async (e, id) => {
        e.preventDefault();
        try {
            const response = await api(`/api/deliveries/admin/deliveries/${id}/assign/`, {
                method: 'PATCH',
                body: JSON.stringify({
                    assigned_agent: agentId ? parseInt(agentId) : null,
                    tracking_number: trackingNumber,
                    // Only sent when set, so leaving the field empty can never
                    // accidentally clear an auto-assigned intercity delivery agent.
                    ...(deliveryAgentId ? { delivery_agent: parseInt(deliveryAgentId) } : {})
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

    // Line-haul control (intercity hub flow): the admin drives the item
    // between the two city hubs. AT_DESTINATION_HUB auto-assigns the local
    // delivery agent on the backend.
    // IN_TRANSIT is now TIMED: dispatching stamps an ETA from the hub route
    // duration and the item arrives by itself (settle_linehaul_arrivals).
    // The button stays as an optional "arrive early" override.
    const LINEHAUL_ACTIONS = {
        'DROPPED_AT_ORIGIN_HUB': { next: 'IN_TRANSIT', label: '🚚 Dispatch Line-haul', color: '#2563eb' },
        'IN_TRANSIT': { next: 'AT_DESTINATION_HUB', label: '⏩ Arrive Early', color: '#7c3aed' },
        'DISPATCHED': { next: 'AT_DESTINATION_HUB', label: '🏢 Mark Arrived at Hub', color: '#7c3aed' },  // legacy pre-hub items
    };

    const formatEta = (iso) => {
        if (!iso) return null;
        const d = new Date(iso);
        if (isNaN(d.getTime())) return null;
        return d.toLocaleString([], { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    };

    const handleLineHaul = async (id, nextStatus) => {
        try {
            const response = await api(`/api/deliveries/admin/deliveries/${id}/status/`, {
                method: 'PATCH',
                body: JSON.stringify({ status: nextStatus })
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(data.error || 'Failed to update fulfillment status.');
            if (data.linehaul_eta_at) {
                toast.success(`Line-haul dispatched — auto-arriving at destination hub by ${formatEta(data.linehaul_eta_at)}.`);
            } else {
                toast.success(data.delivery_agent
                    ? `Arrived at destination hub — delivery agent ${data.delivery_agent} assigned!`
                    : 'Fulfillment status updated!');
            }
            fetchDeliveries();
        } catch (err) {
            toast.error(err.message);
        }
    };

    // Server already filtered by deliveryTab (?status_group=) — use as-is
    const displayedDeliveries = deliveries;

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px', marginBottom: '16px', flexWrap: 'wrap' }}>
                <h2 style={{ margin: 0, color: '#0f172a' }}>Orders & Fulfillment Tracking</h2>
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                    <span style={{ position: 'absolute', left: '10px', color: '#94a3b8', fontSize: '14px', pointerEvents: 'none' }}>🔍</span>
                    <input
                        type="search"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value.toUpperCase())}
                        placeholder="Search by Tracking ID (e.g. TRK-13)"
                        aria-label="Search orders by tracking ID"
                        style={{
                            width: '300px', maxWidth: '100%', padding: '8px 32px 8px 32px',
                            border: '1px solid #cbd5e1', borderRadius: '8px', fontSize: '13px',
                            fontFamily: 'monospace', letterSpacing: '0.3px',
                            backgroundColor: '#fff', color: '#0f172a',
                        }}
                    />
                    {searchTerm && (
                        <button
                            onClick={() => setSearchTerm('')}
                            title="Clear search"
                            style={{ position: 'absolute', right: '8px', background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', fontSize: '14px', padding: '2px' }}
                        >
                            ✕
                        </button>
                    )}
                </div>
            </div>

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

            {fetchError && (
                <div style={{
                    backgroundColor: '#fef3c7', border: '1px solid #f59e0b', color: '#92400e',
                    padding: '12px 16px', borderRadius: '8px', marginBottom: '16px',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px',
                }}>
                    <span style={{ fontSize: '13px', fontWeight: '600' }}>⚠ {fetchError}</span>
                    <button
                        onClick={fetchDeliveries}
                        style={{ padding: '6px 14px', backgroundColor: '#b45309', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: '600', fontSize: '13px' }}
                    >
                        Retry
                    </button>
                </div>
            )}

            {loadingDeliveries ? <p>Loading orders...</p> : displayedDeliveries.length === 0 ? (
                <div style={{ backgroundColor: '#ffffff', padding: '32px', borderRadius: '8px', textAlign: 'center', color: '#64748b', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                    <p style={{ margin: 0 }}>
                        {appliedSearch
                            ? `No orders in this section match tracking ID "${appliedSearch}".`
                            : deliveryTab === 'active' ? 'No active orders requiring fulfillment.' : deliveryTab === 'cancelled' ? 'No cancelled orders.' : 'No completed delivery history.'}
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
                                <th style={{ padding: '12px 16px', color: '#475569' }}>Money</th>
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
                                        <div style={{ fontWeight: '600', color: '#0f172a' }}>
                                            Order #{item.order_id}
                                            {item.is_intercity && (
                                                <span style={{ marginLeft: '8px', padding: '2px 8px', borderRadius: '999px', backgroundColor: '#ede9fe', color: '#5b21b6', fontSize: '10px', fontWeight: '700' }}>
                                                    ✈ INTERCITY
                                                </span>
                                            )}
                                        </div>
                                        <div style={{ fontSize: '13px', color: '#2563eb', marginTop: '4px' }}>{item.item_title}</div>
                                        <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                                            <b>Seller:</b> {item.seller_username} (<span style={{ color: '#d97706' }}>{item.seller_address}</span>)
                                        </div>
                                        {item.pickup_zone && (
                                            <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                                                <b>Pickup zone:</b> {item.pickup_zone}
                                            </div>
                                        )}
                                        {item.is_intercity && (item.origin_hub || item.destination_hub) && (
                                            <div style={{ fontSize: '11px', color: '#7c3aed', marginTop: '2px' }}>
                                                🏢 {item.origin_hub || '—'} → {item.destination_hub || '—'}
                                            </div>
                                        )}
                                        {item.status === 'IN_TRANSIT' && item.linehaul_eta_at && (
                                            <div style={{ fontSize: '11px', color: '#b45309', marginTop: '2px', fontWeight: '600' }}>
                                                ⏱ Arrives at {item.destination_hub || 'destination hub'}: {formatEta(item.linehaul_eta_at)} (auto)
                                            </div>
                                        )}
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
                                                {item.shipping_city && (
                                                    <div style={{ fontSize: '12px', color: '#2563eb', fontWeight: '600', marginBottom: '2px' }}>
                                                        📍 {item.shipping_city}{item.shipping_zone ? ` / ${item.shipping_zone}` : ''}{item.pincode ? ` - ${item.pincode}` : ''}
                                                    </div>
                                                )}
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
                                    {/* Per-item money snapshot taken at checkout
                                        (vendorpulse_core.pricing). */}
                                    <td style={{ padding: '12px 16px', fontSize: '11px', color: '#475569', whiteSpace: 'nowrap' }}>
                                        <div>
                                            <b>Buyer:</b> ₹{(Number(item.item_subtotal || 0) + Number(item.delivery_charge || 0)).toFixed(2)}
                                        </div>
                                        <div style={{ color: '#94a3b8' }}>item ₹{item.item_subtotal} + del ₹{item.delivery_charge}</div>
                                        <div><b style={{ color: '#dc2626' }}>Fee 5%:</b> ₹{item.platform_fee}</div>
                                        <div><b style={{ color: '#16a34a' }}>Seller:</b> ₹{item.seller_payout}</div>
                                        <div><b style={{ color: '#7c3aed' }}>Agent:</b> ₹{item.agent_pay}</div>
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
                                        {item.return_status && (
                                            <div style={{ fontSize: '11px', marginTop: '4px', fontWeight: '700', color: item.return_status === 'APPROVED' ? '#166534' : item.return_status === 'REQUESTED' ? '#b45309' : '#64748b' }}>
                                                ↩ Return {item.return_status}
                                            </div>
                                        )}
                                    </td>
                                    <td style={{ padding: '12px 16px' }}>
                                        {item.agent_username || 'Unassigned'}
                                        {item.delivery_agent_username && (
                                            <div style={{ fontSize: '11px', color: '#92400e', marginTop: '4px' }}>
                                                <b>Delivers:</b> {item.delivery_agent_username}
                                            </div>
                                        )}
                                    </td>
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
                                                {/* Intercity leg-2 override: optional; blank leaves the auto-assigned delivery agent untouched. */}
                                                <input type="number" placeholder="Delivery Agent ID (intercity)" value={deliveryAgentId} onChange={(e) => setDeliveryAgentId(e.target.value)} style={{ padding: '6px', width: '150px', marginRight: '6px', marginBottom: '6px', borderRadius: '4px', border: '1px solid #cbd5e1' }} />
                                                <button type="submit" style={{ padding: '6px 10px', backgroundColor: '#10b981', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Save</button>
                                                <button type="button" onClick={() => setSelectedDeliveryId(null)} style={{ padding: '6px 10px', backgroundColor: '#64748b', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', marginLeft: '4px' }}>Cancel</button>
                                            </form>
                                        ) : (
                                            <>
                                                <button onClick={() => { setSelectedDeliveryId(item.id); setAgentId(item.assigned_agent || ''); setDeliveryAgentId(item.delivery_agent || ''); setTrackingNumber(item.tracking_number || ''); }} style={{ padding: '6px 12px', backgroundColor: '#2563eb', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Assign / Edit</button>
                                                <button type="button" onClick={() => startEditOrder(item)} style={{ padding: '6px 12px', backgroundColor: '#0f172a', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', marginLeft: '4px' }}>Edit Order</button>
                                                {item.is_intercity && LINEHAUL_ACTIONS[item.status] && (
                                                    <button
                                                        onClick={() => handleLineHaul(item.id, LINEHAUL_ACTIONS[item.status].next)}
                                                        style={{ padding: '6px 12px', backgroundColor: LINEHAUL_ACTIONS[item.status].color, color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', marginLeft: '4px' }}
                                                    >
                                                        {LINEHAUL_ACTIONS[item.status].label}
                                                    </button>
                                                )}
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
