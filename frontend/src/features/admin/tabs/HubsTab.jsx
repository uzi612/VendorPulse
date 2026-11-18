import React, { useState, useEffect } from 'react';
import { api } from '../../../api';
import { CITIES } from '../../../cities';
import { useToast } from '../../../components/Toast';

// Delivery hubs management: one physical sorting/collection point per city
// (min). Intercity orders travel seller -> origin hub -> line-haul ->
// destination hub -> buyer. Deletion is a soft-deactivate because the hub is
// referenced by in-flight fulfillment flows.
export default function HubsTab() {
    const toast = useToast();
    const [hubs, setHubs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editing, setEditing] = useState(null);   // hub object | 'new' | null
    const [form, setForm] = useState({ city: '', name: '', address: '', zone: '' });
    const [zones, setZones] = useState([]);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const fetchHubs = async () => {
        setLoading(true);
        try {
            const res = await api('/api/locations/admin/hubs/');
            if (!res.ok) throw new Error('Failed to load hubs.');
            const data = await res.json();
            setHubs(data.results || []);
        } catch (err) {
            toast.error(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchHubs(); }, []);

    // Zone picker options follow the chosen city (a hub may sit inside a zone)
    const loadZonesForCity = async (city) => {
        if (!city) { setZones([]); return; }
        try {
            const res = await api(`/api/locations/zones/?city=${encodeURIComponent(city)}`);
            const data = res.ok ? await res.json() : { results: [] };
            setZones(data.results || []);
        } catch {
            setZones([]);
        }
    };

    const openCreate = () => {
        setEditing('new');
        setError('');
        setForm({ city: '', name: '', address: '', zone: '' });
        setZones([]);
    };

    const openEdit = (hub) => {
        setEditing(hub);
        setError('');
        setForm({
            city: hub.city,
            name: hub.name,
            address: hub.address,
            zone: hub.zone || '',
        });
        loadZonesForCity(hub.city);
    };

    const closeModal = () => { setEditing(null); setError(''); };

    const handleSave = async (e) => {
        e.preventDefault();
        setSaving(true);
        setError('');
        try {
            const payload = {
                city: form.city,
                name: form.name.trim(),
                address: form.address.trim(),
                zone: form.zone || null,
            };
            const url = editing === 'new'
                ? '/api/locations/admin/hubs/'
                : `/api/locations/admin/hubs/${editing.id}/`;
            const res = await api(url, {
                method: editing === 'new' ? 'POST' : 'PUT',
                body: JSON.stringify(payload),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                setError(data.error || 'Failed to save hub.');
                return;
            }
            toast.success(editing === 'new' ? 'Hub created.' : 'Hub updated.');
            closeModal();
            fetchHubs();
        } catch (err) {
            setError('Network error. Please try again.');
        } finally {
            setSaving(false);
        }
    };

    const handleDeactivate = async (hub) => {
        if (!window.confirm(`Deactivate "${hub.name}" in ${hub.city}? Agents will no longer be shown this hub for drop-off/collection.`)) return;
        try {
            const res = await api(`/api/locations/admin/hubs/${hub.id}/`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Failed to deactivate hub.');
            toast.success('Hub deactivated.');
            fetchHubs();
        } catch (err) {
            toast.error(err.message);
        }
    };

    const selectStyle = { width: '100%', padding: '9px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', backgroundColor: '#fff', fontSize: '14px', boxSizing: 'border-box' };
    const btn = (bg, color) => ({
        padding: '6px 12px', borderRadius: '6px', border: 'none',
        backgroundColor: bg, color, fontWeight: '600', fontSize: '12px', cursor: 'pointer',
    });

    // Group by city for a compact overview
    const byCity = hubs.reduce((acc, h) => {
        (acc[h.city] = acc[h.city] || []).push(h);
        return acc;
    }, {});

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '20px' }}>
                <div>
                    <h2 style={{ color: '#0f172a', margin: '0 0 4px 0' }}>Delivery Hubs</h2>
                    <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>
                        Intercity orders travel: pickup agent → <b>origin hub</b> → line-haul → <b>destination hub</b> → delivery agent → buyer.
                    </p>
                </div>
                <button onClick={openCreate} style={btn('#0f172a', '#fff')}>+ New Hub</button>
            </div>

            {loading ? (
                <p style={{ padding: '28px', textAlign: 'center', color: '#64748b' }}>Loading hubs...</p>
            ) : (
                Object.keys(byCity).sort().map(city => (
                    <div key={city} style={{ marginBottom: '20px' }}>
                        <h3 style={{ color: '#0f172a', fontSize: '15px', marginBottom: '8px' }}>{city}</h3>
                        <div style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                                <thead style={{ backgroundColor: '#f8fafc' }}>
                                    <tr>
                                        <th style={{ padding: '8px 12px', fontSize: '12px', color: '#64748b' }}>Hub</th>
                                        <th style={{ padding: '8px 12px', fontSize: '12px', color: '#64748b' }}>Address</th>
                                        <th style={{ padding: '8px 12px', fontSize: '12px', color: '#64748b' }}>Zone</th>
                                        <th style={{ padding: '8px 12px', fontSize: '12px', color: '#64748b' }}>Status</th>
                                        <th style={{ padding: '8px 12px', fontSize: '12px', color: '#64748b', textAlign: 'right' }}>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {byCity[city].map(h => (
                                        <tr key={h.id} style={{ borderTop: '1px solid #f1f5f9' }}>
                                            <td style={{ padding: '9px 12px', fontSize: '13.5px', fontWeight: '600', color: '#0f172a' }}>{h.name}</td>
                                            <td style={{ padding: '9px 12px', fontSize: '13px', color: '#475569' }}>{h.address}</td>
                                            <td style={{ padding: '9px 12px', fontSize: '13px', color: '#475569' }}>{h.zone_name || 'City-wide'}</td>
                                            <td style={{ padding: '9px 12px' }}>
                                                <span style={{
                                                    padding: '3px 10px', borderRadius: '999px', fontSize: '11px', fontWeight: '700',
                                                    backgroundColor: h.is_active ? '#dcfce7' : '#fee2e2',
                                                    color: h.is_active ? '#166534' : '#991b1b',
                                                }}>
                                                    {h.is_active ? 'Active' : 'Inactive'}
                                                </span>
                                            </td>
                                            <td style={{ padding: '9px 12px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                                                <button onClick={() => openEdit(h)} style={{ ...btn('#eef2ff', '#4f46e5'), marginRight: '8px' }}>Edit</button>
                                                {h.is_active && (
                                                    <button onClick={() => handleDeactivate(h)} style={btn('#fee2e2', '#991b1b')}>Deactivate</button>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                ))
            )}

            {/* Create/Edit modal */}
            {editing && (
                <div
                    onClick={closeModal}
                    style={{
                        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                        backgroundColor: 'rgba(15, 23, 42, 0.55)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000, padding: '16px',
                    }}
                >
                    <div
                        onClick={e => e.stopPropagation()}
                        style={{ backgroundColor: '#fff', borderRadius: '12px', padding: '24px', width: '440px', maxWidth: '100%', boxShadow: '0 20px 50px rgba(0,0,0,0.3)' }}
                    >
                        <h3 style={{ margin: '0 0 16px 0', color: '#0f172a' }}>
                            {editing === 'new' ? 'New Delivery Hub' : `Edit Hub - ${editing.city} / ${editing.name}`}
                        </h3>
                        <form onSubmit={handleSave}>
                            <div style={{ marginBottom: '12px' }}>
                                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>CITY</label>
                                <select
                                    required
                                    value={form.city}
                                    onChange={e => { setForm({ ...form, city: e.target.value, zone: '' }); loadZonesForCity(e.target.value); }}
                                    disabled={editing !== 'new'}
                                    style={{ ...selectStyle, backgroundColor: editing !== 'new' ? '#f8fafc' : '#fff' }}
                                >
                                    <option value="">Select city</option>
                                    {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
                                </select>
                            </div>
                            <div style={{ marginBottom: '12px' }}>
                                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>HUB NAME</label>
                                <input
                                    required
                                    value={form.name}
                                    onChange={e => setForm({ ...form, name: e.target.value })}
                                    placeholder="e.g. Central Hub"
                                    style={selectStyle}
                                />
                            </div>
                            <div style={{ marginBottom: '12px' }}>
                                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>ADDRESS</label>
                                <input
                                    required
                                    maxLength={255}
                                    value={form.address}
                                    onChange={e => setForm({ ...form, address: e.target.value })}
                                    placeholder="Street address agents navigate to"
                                    style={selectStyle}
                                />
                            </div>
                            <div style={{ marginBottom: '16px' }}>
                                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>ZONE (optional)</label>
                                <select
                                    value={form.zone}
                                    onChange={e => setForm({ ...form, zone: e.target.value })}
                                    disabled={!form.city}
                                    style={{ ...selectStyle, backgroundColor: form.city ? '#fff' : '#f8fafc' }}
                                >
                                    <option value="">Entire city</option>
                                    {zones.map(z => (
                                        <option key={z.id} value={z.id}>{z.name} ({z.pincode_from}-{z.pincode_to})</option>
                                    ))}
                                </select>
                            </div>
                            {error && <p style={{ margin: '0 0 12px 0', fontSize: '13px', fontWeight: '600', color: '#dc2626' }}>{error}</p>}
                            <div style={{ display: 'flex', gap: '10px' }}>
                                <button type="button" onClick={closeModal} style={{ ...btn('#f1f5f9', '#475569'), flex: 1, padding: '10px' }}>Cancel</button>
                                <button type="submit" disabled={saving} style={{ ...btn(saving ? '#94a3b8' : '#4f46e5', '#fff'), flex: 1, padding: '10px' }}>
                                    {saving ? 'Saving...' : 'Save Hub'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
