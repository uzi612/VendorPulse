import React, { useState, useEffect } from 'react';
import { api } from '../api';

const STATUS_LABELS = {
    ORDER_PLACED: 'Order Placed (unassigned)',
    PICKUP_SCHEDULED: 'Pickup Scheduled',
    PICKED_UP: 'Picked Up',
    DISPATCHED: 'In Transit',
    DELIVERED: 'Delivered',
};


const SUMMARY_CARDS = [
    ['total_orders', 'Total Orders', '#0f172a'],
    ['completed_revenue', 'Completed Revenue', '#16a34a'],
    ['delivered_items', 'Delivered', '#2563eb'],
    ['in_transit_items', 'In Transit', '#d97706'],
    ['awaiting_assignment', 'Awaiting Assignment', '#dc2626'],
    ['active_listings', 'Active Listings', '#7c3aed'],
    ['registered_users', 'Registered Users', '#0891b2'],
    ['total_agents', 'Delivery Agents', '#4f46e5'],
];

function Bar({ label, right, value, maxValue, color }) {
    const pct = maxValue > 0 ? Math.max(2, Math.round((value / maxValue) * 100)) : 0;
    return (
        <div style={{ marginBottom: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '3px' }}>
                <span style={{ color: '#334155', fontWeight: '600' }}>{label}</span>
                <span style={{ color: '#64748b' }}>{right}</span>
            </div>
            <div style={{ backgroundColor: '#e2e8f0', borderRadius: '4px', height: '10px', overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, backgroundColor: color, height: '100%', borderRadius: '4px' }} />
            </div>
        </div>
    );
}

function Panel({ title, children }) {
    return (
        <div style={{
            backgroundColor: '#ffffff', border: '1px solid #e2e8f0',
            borderRadius: '10px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '15px', color: '#0f172a' }}>{title}</h3>
            {children}
        </div>
    );
}

const tableStyle = { width: '100%', borderCollapse: 'collapse', fontSize: '13px' };
const thStyle = { textAlign: 'left', padding: '8px 10px', borderBottom: '2px solid #e2e8f0', color: '#64748b', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px' };
const tdStyle = { padding: '8px 10px', borderBottom: '1px solid #f1f5f9', color: '#334155' };

export default function AdminAnalytics() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const load = async () => {
            try {
                const res = await api('/api/deliveries/admin/analytics/');
                if (!res.ok) throw new Error('Failed to load analytics.');
                setData(await res.json());
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        load();
    }, []);

    if (loading) return <div style={{ textAlign: 'center', color: '#64748b', padding: '40px' }}>Loading analytics...</div>;
    if (error) return <div style={{ color: 'red', padding: '20px' }}>Error: {error}</div>;
    if (!data) return null;

    const { summary, orders_per_city, status_breakdown, agents, top_sellers, revenue_trend } = data;

    const maxCity = Math.max(1, ...orders_per_city.map(c => c.orders));
    const maxStatus = Math.max(1, ...status_breakdown.map(s => s.count));
    const maxTrend = Math.max(1, ...revenue_trend.map(t => Number(t.revenue)));
    const topAgents = [...agents].sort((a, b) => (b.completed + b.active_load) - (a.completed + a.active_load)).slice(0, 10);
    const maxAgentLoad = Math.max(1, ...topAgents.map(a => a.completed + a.active_load));

    return (
        <div>
            <h2 style={{ marginBottom: '20px', color: '#0f172a' }}>Platform Analytics</h2>

            {/* Summary stat cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '14px', marginBottom: '24px' }}>
                {SUMMARY_CARDS.map(([key, label, color]) => (
                    <div key={key} style={{
                        backgroundColor: '#ffffff', border: '1px solid #e2e8f0',
                        borderRadius: '10px', padding: '16px',
                        borderLeft: `4px solid ${color}`,
                        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                    }}>
                        <div style={{ fontSize: '11px', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
                        <div style={{ fontSize: '26px', fontWeight: '800', color, marginTop: '4px' }}>
                            {key === 'completed_revenue' ? `₹${Number(summary[key] || 0).toLocaleString('en-IN')}` : (summary[key] ?? 0)}
                        </div>
                    </div>
                ))}
            </div>

            {/* Two-column chart area */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '20px', marginBottom: '20px' }}>
                <Panel title="📍 Orders per City (buyer demand)">
                    {orders_per_city.length === 0 ? (
                        <p style={{ color: '#94a3b8', fontSize: '13px' }}>No orders yet.</p>
                    ) : orders_per_city.map(c => (
                        <Bar key={c.shipping_city} label={c.shipping_city}
                             right={`${c.orders} • ₹${Number(c.revenue).toLocaleString('en-IN')}`}
                             value={c.orders} maxValue={maxCity} color="#4f46e5" />
                    ))}
                </Panel>

                <Panel title="🔄 Fulfillment Status Breakdown">
                    {status_breakdown.map(s => (
                        <Bar key={s.status} label={STATUS_LABELS[s.status] || s.status} right={s.count}
                             value={s.count} maxValue={maxStatus}
                             color={s.status === 'DELIVERED' ? '#16a34a' : (s.status === 'ORDER_PLACED' ? '#dc2626' : '#d97706')} />
                    ))}
                </Panel>

                <Panel title="📈 Revenue — last 14 days">
                    {revenue_trend.length === 0 ? (
                        <p style={{ color: '#94a3b8', fontSize: '13px' }}>No orders in the last 14 days.</p>
                    ) : revenue_trend.map(t => (
                        <Bar key={t.date} label={t.date}
                             right={`₹${Number(t.revenue).toLocaleString('en-IN')} • ${t.orders} order${t.orders === 1 ? '' : 's'}`}
                             value={Number(t.revenue)} maxValue={maxTrend} color="#0891b2" />
                    ))}
                </Panel>

                <Panel title="⭐ Top Sellers (by revenue)">
                    {top_sellers.length === 0 ? (
                        <p style={{ color: '#94a3b8', fontSize: '13px' }}>No sales yet.</p>
                    ) : (
                        <table style={tableStyle}>
                            <thead>
                                <tr><th style={thStyle}>Seller</th><th style={thStyle}>Rating</th><th style={thStyle}>Sales</th><th style={thStyle}>Revenue</th></tr>
                            </thead>
                            <tbody>
                                {top_sellers.map(s => (
                                    <tr key={s.seller__username}>
                                        <td style={tdStyle}>{s.seller__username}</td>
                                        <td style={tdStyle}>
                                            {s.avg_rating != null
                                                ? <span style={{ color: '#d97706', fontWeight: '700' }}>★ {s.avg_rating}</span>
                                                : <span style={{ color: '#94a3b8' }}>—</span>}
                                        </td>
                                        <td style={tdStyle}>{s.sales}</td>
                                        <td style={tdStyle}><b>₹{Number(s.revenue).toLocaleString('en-IN')}</b></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </Panel>
            </div>

            {/* Agent utilization table */}
            <Panel title="🚚 Agent Utilization (top 10 by workload)">
                {topAgents.length === 0 ? (
                    <p style={{ color: '#94a3b8', fontSize: '13px' }}>No delivery agents registered.</p>
                ) : (
                    <table style={tableStyle}>
                        <thead>
                            <tr>
                                <th style={thStyle}>Agent</th>
                                <th style={thStyle}>City</th>
                                <th style={thStyle}>Rating</th>
                                <th style={thStyle}>Active Load</th>
                                <th style={thStyle}>Completed</th>
                                <th style={{ ...thStyle, width: '30%' }}>Workload</th>
                            </tr>
                        </thead>
                        <tbody>
                            {topAgents.map(a => {
                                const total = a.completed + a.active_load;
                                return (
                                    <tr key={a.username}>
                                        <td style={tdStyle}>{a.username}</td>
                                        <td style={tdStyle}>{a.city || '—'}</td>
                                        <td style={tdStyle}>
                                            {a.avg_rating != null
                                                ? <span style={{ color: a.avg_rating >= 4 ? '#16a34a' : a.avg_rating >= 3 ? '#d97706' : '#dc2626', fontWeight: '700' }}>★ {a.avg_rating}</span>
                                                : <span style={{ color: '#94a3b8' }}>—</span>}
                                        </td>
                                        <td style={tdStyle}>
                                            <span style={{ color: a.active_load >= 5 ? '#dc2626' : '#d97706', fontWeight: '700' }}>
                                                {a.active_load}
                                            </span>
                                            {a.active_load >= 5 && <span style={{ fontSize: '11px', color: '#dc2626' }}> (at max)</span>}
                                        </td>
                                        <td style={tdStyle}>{a.completed}</td>
                                        <td style={tdStyle}>
                                            <div style={{ backgroundColor: '#e2e8f0', borderRadius: '4px', height: '8px', overflow: 'hidden' }}>
                                                <div style={{
                                                    width: `${maxAgentLoad > 0 ? Math.round((total / maxAgentLoad) * 100) : 0}%`,
                                                    backgroundColor: '#4f46e5', height: '100%',
                                                }} />
                                            </div>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </Panel>
        </div>
    );
}
