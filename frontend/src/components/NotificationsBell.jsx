import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api';

// Icons per notification type
const TYPE_ICONS = {
    AGENT_ASSIGNED: '🚚',
    NEW_TASK: '📦',
    STATUS_UPDATE: '🔄',
    ORDER_UPDATED: '✏️',
    NEW_SALE: '💰',
    VERIFICATION: '✅',
    RATING: '⭐',
    ASSIGNMENT_NEEDED: '⚠️',
};

// Poll interval: notifications refresh every 20 seconds while the page is open
const POLL_MS = 20000;

export default function NotificationsBell() {
    const [open, setOpen] = useState(false);
    const [items, setItems] = useState([]);
    const [unread, setUnread] = useState(0);
    const boxRef = useRef(null);

    const load = async () => {
        try {
            const res = await api('/api/notifications/');
            if (res.ok) {
                const data = await res.json();
                setItems(data.notifications || []);
                setUnread(data.unread_count || 0);
            }
        } catch (err) {
            // Silently ignore polling failures (e.g. server restarting)
        }
    };

    // Initial load + poll while mounted
    useEffect(() => {
        load();
        const timer = setInterval(load, POLL_MS);
        return () => clearInterval(timer);
    }, []);

    // Close the dropdown when clicking anywhere outside it
    useEffect(() => {
        const onClick = (e) => {
            if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
        };
        document.addEventListener('mousedown', onClick);
        return () => document.removeEventListener('mousedown', onClick);
    }, []);

    const markOneRead = async (n) => {
        if (n.is_read) return;
        setItems(prev => prev.map(i => i.id === n.id ? { ...i, is_read: true } : i));
        setUnread(prev => Math.max(0, prev - 1));
        try { await api(`/api/notifications/${n.id}/read/`, { method: 'POST' }); } catch (err) {}
    };

    const markAllRead = async () => {
        setItems(prev => prev.map(i => ({ ...i, is_read: true })));
        setUnread(0);
        try { await api('/api/notifications/read-all/', { method: 'POST' }); } catch (err) {}
    };

    const toggleOpen = () => {
        const next = !open;
        setOpen(next);
        if (next) load(); // fresh data on every open
    };

    return (
        <div ref={boxRef} style={{ position: 'relative' }}>
            {/* Bell button with unread badge */}
            <button
                onClick={toggleOpen}
                aria-label="Notifications"
                style={{
                    position: 'relative',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '6px',
                    display: 'flex',
                    alignItems: 'center',
                    fontSize: '20px',
                    lineHeight: 1,
                }}
            >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#475569"
                     strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
                {unread > 0 && (
                    <span style={{
                        position: 'absolute', top: '0px', right: '-2px',
                        backgroundColor: '#ef4444', color: '#ffffff',
                        fontSize: '10px', fontWeight: '700',
                        minWidth: '16px', height: '16px', borderRadius: '8px',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        padding: '0 4px',
                    }}>
                        {unread > 9 ? '9+' : unread}
                    </span>
                )}
            </button>

            {/* Dropdown */}
            {open && (
                <div style={{
                    position: 'absolute', right: 0, top: '40px',
                    width: '340px', maxHeight: '420px', overflowY: 'auto',
                    backgroundColor: '#ffffff', borderRadius: '10px',
                    boxShadow: '0 10px 30px rgba(0,0,0,0.15)',
                    border: '1px solid #e2e8f0', zIndex: 1000,
                }}>
                    {/* Header */}
                    <div style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '12px 16px', borderBottom: '1px solid #e2e8f0',
                        position: 'sticky', top: 0, backgroundColor: '#ffffff',
                    }}>
                        <strong style={{ fontSize: '14px', color: '#0f172a' }}>
                            Notifications {unread > 0 && <span style={{ color: '#ef4444' }}>({unread} new)</span>}
                        </strong>
                        {unread > 0 && (
                            <button
                                onClick={markAllRead}
                                style={{
                                    background: 'transparent', border: 'none',
                                    color: '#4f46e5', fontSize: '12px', fontWeight: '600',
                                    cursor: 'pointer', padding: 0,
                                }}
                            >
                                Mark all read
                            </button>
                        )}
                    </div>

                    {/* List */}
                    {items.length === 0 ? (
                        <div style={{ padding: '24px 16px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
                            No notifications yet.
                        </div>
                    ) : items.map(n => (
                        <div
                            key={n.id}
                            onClick={() => markOneRead(n)}
                            title={n.is_read ? '' : 'Click to mark as read'}
                            style={{
                                display: 'flex', gap: '10px', alignItems: 'flex-start',
                                padding: '12px 16px', cursor: 'pointer',
                                borderBottom: '1px solid #f1f5f9',
                                backgroundColor: n.is_read ? '#ffffff' : '#eef2ff',
                            }}
                        >
                            <span style={{ fontSize: '18px', lineHeight: 1.2 }}>
                                {TYPE_ICONS[n.notification_type] || '🔔'}
                            </span>
                            <div style={{ flex: 1 }}>
                                <div style={{
                                    fontSize: '13px', color: '#1e293b', lineHeight: 1.4,
                                    fontWeight: n.is_read ? 400 : 600,
                                }}>
                                    {n.message}
                                </div>
                                <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                                    {n.created_at}
                                </div>
                            </div>
                            {!n.is_read && (
                                <span style={{
                                    width: '8px', height: '8px', borderRadius: '4px',
                                    backgroundColor: '#4f46e5', marginTop: '6px', flexShrink: 0,
                                }} />
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
