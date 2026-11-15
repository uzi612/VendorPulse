import React, { useState, useEffect } from 'react';
import { api } from '../../../api';
import Pagination from '../../../components/Pagination';

// Staff & delivery-agent directory: create/edit staff accounts and toggle
// seller verification. Page state is lifted into AdminPortal so it survives
// switching tabs.
export default function StaffTab({ page, setPage }) {
    const [staffList, setStaffList] = useState([]);
    const [staffMeta, setStaffMeta] = useState(null);         // {count, total_pages, page, page_size}
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

    const fetchStaff = async () => {
        setLoadingStaff(true);
        try {
            const response = await api(`/api/deliveries/admin/staff/?page=${page}&page_size=10`);
            if (!response.ok) throw new Error('Failed to fetch staff list.');
            const data = await response.json();
            setStaffList(data.results);
            setStaffMeta(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoadingStaff(false);
        }
    };

    useEffect(() => { fetchStaff(); }, [page]);

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
                // Refresh this tab's list. The Sellers tab refetches its own
                // data when it mounts, so its badge stays consistent too.
                fetchStaff();
            } else {
                const errData = await res.json().catch(() => ({}));
                alert("Failed to update: " + (errData.error || "Unknown error"));
            }
        } catch (err) {
            console.error("Network or execution error:", err);
        }
    };

    const handleCreateStaff = async (e) => {
        e.preventDefault();
        try {
            const response = await api('/api/deliveries/admin/staff/', {
                method: 'POST',
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
            const response = await api(`/api/deliveries/admin/staff/${id}/update/`, {
                method: 'PATCH',
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

    return (
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
                                <th style={{ padding: '12px 16px', color: '#475569' }}>Verified Status</th>
                                <th style={{ padding: '12px 16px', color: '#475569' }}>Actions</th>
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
                                            <td style={{ padding: '12px 16px' }}>{member.is_verified ? 'Verified' : 'Unverified'}</td>
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
                                                {member.is_verified ? (
                                                    <span style={{ color: '#059669', fontWeight: 'bold' }}>✓ Verified</span>
                                                ) : (
                                                    <span style={{ color: '#64748b' }}>Unverified</span>
                                                )}
                                            </td>
                                            <td style={{ padding: '12px 16px', display: 'flex', gap: '8px' }}>
                                                <button
                                                    onClick={() => {
                                                        setEditingStaffId(member.id);
                                                        setEditEmail(member.email || '');
                                                        setEditAddress(member.address === 'N/A' ? '' : (member.address || ''));
                                                        setEditRole(member.is_staff ? 'admin' : 'agent');
                                                    }}
                                                    style={{ padding: '6px 12px', backgroundColor: '#0f172a', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '13px' }}
                                                >
                                                    Edit
                                                </button>
                                                <button
                                                    onClick={() => toggleVerification(member.id, member.is_verified)}
                                                    style={{ padding: '6px 12px', backgroundColor: member.is_verified ? '#ef4444' : '#10b981', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '13px' }}
                                                >
                                                    {member.is_verified ? 'Revoke' : 'Verify'}
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

            <Pagination meta={staffMeta} page={page} setPage={setPage} />
        </div>
    );
}
