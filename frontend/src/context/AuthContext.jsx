import { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../api';

// Auth state lives in the Django session (cookie), mirrored here in React
// state. App.jsx used to own this; now any component can consume it via
// useAuth() instead of receiving props through every layer.

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [auth, setAuth] = useState({ loading: true, isAuthed: false, role: null });

    const refreshAuth = async () => {
        try {
            const res = await api('/api/accounts/me/');
            if (res.ok) {
                const data = await res.json();
                if (data.authenticated) {
                    setAuth({ loading: false, isAuthed: true, role: data.role || 'customer' });
                    return;
                }
            }
        } catch (err) {
            console.error('Session check failed', err);
        }
        setAuth({ loading: false, isAuthed: false, role: null });
    };

    useEffect(() => {
        refreshAuth(); // also bootstraps the csrftoken cookie for later writes
    }, []);

    const logout = async () => {
        try {
            await api('/api/accounts/logout/', { method: 'POST' });
        } catch (err) {
            console.error('Logout request failed', err);
        } finally {
            await refreshAuth();
            window.location.href = '/accounts/login/';
        }
    };

    return (
        <AuthContext.Provider value={{ auth, refreshAuth, logout }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    return useContext(AuthContext);
}
