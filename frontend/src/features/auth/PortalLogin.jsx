import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api';

// Shared login form for the staff portals (admin + agent). They are the same
// page with different copy, button color, role and redirect. The customer
// login lives separately in Login.jsx: it posts to a different endpoint
// (/accounts/login/ vs /accounts/portal-login/), uses the Tailwind design
// language and links to registration.
const PORTAL_CONFIG = {
    admin: {
        title: 'VendorPulse Admin',
        subtitle: 'Sign in to manage centralized logistics and assignments.',
        usernameLabel: 'Admin Username',
        buttonLabel: 'Sign In as Admin',
        buttonColor: '#0f172a',
        fallbackError: 'Admin login failed.',
        redirect: '/admin/deliveries/',
    },
    agent: {
        title: 'Delivery Agent Portal',
        subtitle: 'Sign in to view assigned deliveries and update order status.',
        usernameLabel: 'Agent Username',
        buttonLabel: 'Sign In as Agent',
        buttonColor: '#2563eb',
        fallbackError: 'Agent login failed.',
        redirect: '/agent/dashboard/',
    },
};

export default function PortalLogin({ role, onLoginSuccess }) {
    const config = PORTAL_CONFIG[role];
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const response = await api('/api/accounts/portal-login/', {
                method: 'POST',
                body: JSON.stringify({ username, password, role }),
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || config.fallbackError);
            }

            // Session cookie is set by the server; role is re-verified against it.
            if (onLoginSuccess) await onLoginSuccess();
            navigate(config.redirect);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fafc' }}>
            <div style={{ width: '100%', maxWidth: '400px', backgroundColor: '#ffffff', padding: '32px', borderRadius: '8px', boxShadow: '0 2px 10px rgba(0,0,0,0.08)' }}>
                <h2 style={{ marginBottom: '8px', color: '#0f172a' }}>{config.title}</h2>
                <p style={{ marginBottom: '24px', color: '#64748b', fontSize: '14px' }}>{config.subtitle}</p>

                {error && <div style={{ backgroundColor: '#fee2e2', color: '#b91c1c', padding: '10px', borderRadius: '6px', marginBottom: '16px', fontSize: '14px' }}>{error}</div>}

                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: '16px' }}>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', fontWeight: '500', color: '#334155' }}>{config.usernameLabel}</label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                            style={{ width: '100%', padding: '10px', border: '1px solid #cbd5e1', borderRadius: '6px', boxSizing: 'border-box' }}
                        />
                    </div>

                    <div style={{ marginBottom: '24px' }}>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', fontWeight: '500', color: '#334155' }}>Password</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            style={{ width: '100%', padding: '10px', border: '1px solid #cbd5e1', borderRadius: '6px', boxSizing: 'border-box' }}
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        style={{ width: '100%', padding: '12px', backgroundColor: config.buttonColor, color: '#ffffff', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}
                    >
                        {loading ? 'Signing in...' : config.buttonLabel}
                    </button>
                </form>
            </div>
        </div>
    );
}
