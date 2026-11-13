import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

export default function AdminLogin({ onLoginSuccess }) {
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
        body: JSON.stringify({ username, password, role: 'admin' }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Admin login failed.');
      }

      // Session cookie is set by the server; role is re-verified against it.
      if (onLoginSuccess) await onLoginSuccess();
      navigate('/admin/deliveries/');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f8fafc' }}>
      <div style={{ width: '100%', maxWidth: '400px', backgroundColor: '#ffffff', padding: '32px', borderRadius: '8px', boxShadow: '0 2px 10px rgba(0,0,0,0.08)' }}>
        <h2 style={{ marginBottom: '8px', color: '#0f172a' }}>VendorPulse Admin</h2>
        <p style={{ marginBottom: '24px', color: '#64748b', fontSize: '14px' }}>Sign in to manage centralized logistics and assignments.</p>

        {error && <div style={{ backgroundColor: '#fee2e2', color: '#b91c1c', padding: '10px', borderRadius: '6px', marginBottom: '16px', fontSize: '14px' }}>{error}</div>}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '14px', fontWeight: '500', color: '#334155' }}>Admin Username</label>
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
            style={{ width: '100%', padding: '12px', backgroundColor: '#0f172a', color: '#ffffff', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}
          >
            {loading ? 'Signing in...' : 'Sign In as Admin'}
          </button>
        </form>
      </div>
    </div>
  );
}