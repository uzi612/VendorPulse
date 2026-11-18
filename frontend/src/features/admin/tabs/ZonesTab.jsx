import React, { useState, useEffect } from 'react';
import { api } from '../../../api';
import { useToast } from '../../../components/Toast';

// Zones management: numbered delivery zones per city, each owning a
// contiguous pincode range. Buyers resolve their zone by typing a pincode at
// checkout, so the ranges (not the names) are the real locator. Deletion is a
// soft-deactivate because orders/profiles reference zones.
const PAGE_SIZE = 24;

export default function ZonesTab() {
    const toast = useToast();
    const [rows, setRows] = useState([]);
    const [meta, setMeta] = useState({});
    const [page, setPage] = useState(1);
    const [cityFilter, setCityFilter] = useState('');
    const [loading, setLoading] = useState(true);
    const [editing, setEditing] = useState(null);      // zone object or null
    const [form, setForm] = useState({ city: '', name: '', pincode_from: '', pincode_to: '' });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const CITIES = ['Mumbai', 'Delhi', 'Bengaluru', 'Hyderabad', 'Chennai', 'Kolkata',
        'Pune', 'Ahmedabad', 'Jaipur', 'Lucknow', 'Indore', 'Chandigarh'];

    const fetchZones = async () => {
        setLoading(true);
        try {
            const q = new URLSearchParams({ page: String(page) });
            if (cityFilter) q.set('city', cityFilter);
            const res = await api(`/api/locations/admin/zones/?${q.toString()}`);
            if (!res.ok) throw new Error('Failed to load zones.');
            const data = await res.json();
            setRows(data.results || []);
            setMeta(data);
        } catch (err) {
            toast.error(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchZones(); }, [page, cityFilter]);

    const openCreate = () => {
        setEditing('new');
        setError('');
        setForm({ city: cityFilter || '', name: '', pincode_from: '', pincode_to: '' });
    };

    const openEdit = (zone) => {
        setEditing(zone);
        setError('');
        setForm({
            city: zone.city,
            name: zone.name,
            pincode_from: String(zone.pincode_from),
            pincode_to: String(zone.pincode_to),
        });
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
                pincode_from: Number(form.pincode_from),
                pincode_to: Number(form.pincode_to),
            };
            const url = editing === 'new'
                ? '/api/locations/admin/zones/'
                : `/api/locations/admin/zones/${editing.id}/`;
            const res = await api(url, {
                method: editing === 'new' ? 'POST' : 'PUT',
                body: JSON.stringify(payload),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                setError(data.error || 'Failed to save zone.');
                return;
            }
            toast.success(editing === 'new' ? 'Zone created.' : 'Zone updated.');
            closeModal();
            fetchZones();
        } catch (err) {
            setError('Network error. Please try again.');
        } finally {
            setSaving(false);
        }
    };

    const handleDeactivate = async (zone) => {
        if (!window.confirm(`Deactivate zone "${zone.name}" in ${zone.city}? Buyers with pincodes in ${zone.pincode_from}-${zone.pincode_to} will no longer resolve it.`)) return;
        try {
            const res = await api(`/api/locations/admin/zones/${zone.id}/`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Failed to deactivate zone.');
            toast.success('Zone deactivated.');
            fetchZones();
        } catch (err) {
            toast.error(err.message);
        }
    };

    const totalPages = meta.total_pages || 1;
    const th = { textAlign: 'left', padding: '10px 12px', fontSize: '12px', color: '#64748b', borderBottom: '1px solid #e2e8f0', whiteSpace: 'nowrap' };
    const td = { padding: '10px 12px', fontSize: '13.5px', color: '#334155', borderBottom: '1px solid #f1f5f9' };
    const btn = (bg, color) => ({
        padding: '6px 12px', borderRadius: '6px', border: 'none',
        backgroundColor: bg, color, fontWeight: '600', fontSize: '12px', cursor: 'pointer',
    });

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '20px' }}>
                <div>
                    <h2 style={{ color: '#0f172a', margin: '0 0 4px 0' }}>Delivery Zones</h2>
                    <p style={{ color: '#64748b', fontSize: '13px', margin: 0 }}>
                        Buyers type a pincode at checkout; its range resolves the zone. Rename zones freely - ranges are the locator.
                    </p>
                </div>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <select
                        value={cityFilter}
                        onChange={e => { setPage(1); setCityFilter(e.target.value); }}
                        style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', backgroundColor: '#fff', fontSize: '13px' }}
                    >
                        <option value="">All cities</option>
                        {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <button onClick={openCreate} style={btn('#0f172a', '#fff')}>+ New Zone</button>
                </div>
            </div>

            <div style={{ backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden' }}>
                {loading ? (
                    <p style={{ padding: '28px', textAlign: 'center', color: '#64748b' }}>Loading zones...</p>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ backgroundColor: '#f8fafc' }}>
                                <th style={th}>City</th>
                                <th style={th}>Zone</th>
                                <th style={th}>Pincode Range</th>
                                <th style={th}>Agents</th>
                                <th style={th}>Status</th>
                                <th style={{ ...th, textAlign: 'right' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.length === 0 && (
                                <tr><td colSpan="6" style={{ ...td, textAlign: 'center', color: '#64748b', padding: '24px' }}>No zones found.</td></tr>
                            )}
                            {rows.map(z => (
                                <tr key={z.id}>
                                    <td style={td}>{z.city}</td>
                                    <td style={{ ...td, fontWeight: '600' }}>{z.name}</td>
                                    <td style={td}>{z.pincode_from} - {z.pincode_to}</td>
                                    <td style={td}>{z.agents}</td>
                                    <td style={td}>
                                        <span style={{
                                            padding: '3px 10px', borderRadius: '999px', fontSize: '11px', fontWeight: '700',
                                            backgroundColor: z.is_active ? '#dcfce7' : '#fee2e2',
                                            color: z.is_active ? '#166534' : '#991b1b',
                                        }}>
                                            {z.is_active ? 'Active' : 'Inactive'}
                                        </span>
                                    </td>
                                    <td style={{ ...td, textAlign: 'right', whiteSpace: 'nowrap' }}>
                                        <button onClick={() => openEdit(z)} style={{ ...btn('#eef2ff', '#4f46e5'), marginRight: '8px' }}>Edit</button>
                                        {z.is_active && (
                                            <button onClick={() => handleDeactivate(z)} style={btn('#fee2e2', '#991b1b')}>Deactivate</button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {/* Pagination */}
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '12px', marginTop: '16px' }}>
                <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} style={{ ...btn('#f1f5f9', '#334155'), opacity: page <= 1 ? 0.5 : 1 }}>Prev</button>
                <span style={{ fontSize: '13px', color: '#64748b' }}>Page {page} of {totalPages}</span>
                <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} style={{ ...btn('#f1f5f9', '#334155'), opacity: page >= totalPages ? 0.5 : 1 }}>Next</button>
            </div>

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
                        style={{ backgroundColor: '#fff', borderRadius: '12px', padding: '24px', width: '420px', maxWidth: '100%', boxShadow: '0 20px 50px rgba(0,0,0,0.3)' }}
                    >
                        <h3 style={{ margin: '0 0 16px 0', color: '#0f172a' }}>
                            {editing === 'new' ? 'New Delivery Zone' : `Edit Zone - ${editing.city} / ${editing.name}`}
                        </h3>
                        <form onSubmit={handleSave} className="space-y-3">
                            <div style={{ marginBottom: '12px' }}>
                                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>CITY</label>
                                <select
                                    required
                                    value={form.city}
                                    onChange={e => setForm({ ...form, city: e.target.value })}
                                    style={{ width: '100%', padding: '9px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', backgroundColor: '#fff', fontSize: '14px' }}
                                >
                                    <option value="">Select city</option>
                                    {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
                                </select>
                            </div>
                            <div style={{ marginBottom: '12px' }}>
                                <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>ZONE NAME</label>
                                <input
                                    required
                                    value={form.name}
                                    onChange={e => setForm({ ...form, name: e.target.value })}
                                    placeholder="e.g. Zone 1, South Zone"
                                    style={{ width: '100%', boxSizing: 'border-box', padding: '9px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '14px' }}
                                />
                            </div>
                            <div style={{ display: 'flex', gap: '10px', marginBottom: '16px' }}>
                                <div style={{ flex: 1 }}>
                                    <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>PINCODE FROM</label>
                                    <input
                                        required
                                        type="number"
                                        min="100000"
                                        max="999999"
                                        value={form.pincode_from}
                                        onChange={e => setForm({ ...form, pincode_from: e.target.value })}
                                        style={{ width: '100%', boxSizing: 'border-box', padding: '9px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '14px' }}
                                    />
                                </div>
                                <div style={{ flex: 1 }}>
                                    <label style={{ display: 'block', fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '4px' }}>PINCODE TO</label>
                                    <input
                                        required
                                        type="number"
                                        min="100000"
                                        max="999999"
                                        value={form.pincode_to}
                                        onChange={e => setForm({ ...form, pincode_to: e.target.value })}
                                        style={{ width: '100%', boxSizing: 'border-box', padding: '9px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '14px' }}
                                    />
                                </div>
                            </div>
                            {error && <p style={{ margin: '0 0 12px 0', fontSize: '13px', fontWeight: '600', color: '#dc2626' }}>{error}</p>}
                            <div style={{ display: 'flex', gap: '10px' }}>
                                <button type="button" onClick={closeModal} style={{ ...btn('#f1f5f9', '#475569'), flex: 1, padding: '10px' }}>Cancel</button>
                                <button type="submit" disabled={saving} style={{ ...btn(saving ? '#94a3b8' : '#4f46e5', '#fff'), flex: 1, padding: '10px' }}>
                                    {saving ? 'Saving...' : 'Save Zone'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
