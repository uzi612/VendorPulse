import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { api } from './api';
import Navbar from './components/Navbar';
import Home from './components/Home';
import Products from './components/Products';
import Listings from './components/Listings';
import Cart from './components/Cart';
import Login from './components/Login';
import Register from './components/Register';
import ViewListing from './components/ViewListing';
import Checkout from './components/Checkout';
import CheckoutSuccess from './components/CheckoutSuccess';
import Profile from './components/Profile';
import SellerDashboard from './components/SellerDashboard';
import EditListing from './components/EditListing';
import AdminDeliveries from './components/AdminDeliveries';
import AgentDashboard from './components/AgentDashboard';
import AdminLogin from './components/AdminLogin';
import AgentLogin from './components/AgentLogin';
import OrderTracking from './components/OrderTracking';

// Session-based guard: asks App whether the server-side session is active
// and carries the required role. Real enforcement still happens in Django.
function RoleRoute({ allowedRole, redirectPath, auth, children }) {
  if (auth.loading) {
    return <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>Checking session...</div>;
  }
  if (!auth.isAuthed || auth.role !== allowedRole) {
    return <Navigate to={redirectPath} replace />;
  }
  return children;
}

export default function App() {
  // Auth state now lives in the Django session (cookie), mirrored here in React state.
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

  const handleLogout = async () => {
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
    <Router>
      <Routes>
        {/* Standalone Authentication Portals */}
        <Route path="/accounts/login/" element={<Login onLoginSuccess={refreshAuth} />} />
        <Route path="/accounts/register/" element={<Register onLoginSuccess={refreshAuth} />} />
        <Route path="/admin/login/" element={<AdminLogin onLoginSuccess={refreshAuth} />} />
        <Route path="/agent/login/" element={<AgentLogin onLoginSuccess={refreshAuth} />} />

        {/* Protected Admin & Agent Dashboards (Standalone Top-Header Layout) */}
        <Route
          path="/admin/deliveries/"
          element={
            <RoleRoute allowedRole="admin" redirectPath="/admin/login/" auth={auth}>
              <AdminDeliveries onLogout={handleLogout} />
            </RoleRoute>
          }
        />
        <Route
          path="/agent/dashboard/"
          element={
            <RoleRoute allowedRole="agent" redirectPath="/agent/login/" auth={auth}>
              <AgentDashboard onLogout={handleLogout} />
            </RoleRoute>
          }
        />

        {/* Customer Marketplace Routes */}
        <Route path="/*" element={
          <Navbar isAuthenticated={auth.isAuthed} onLogout={handleLogout}>
            <Routes>
              <Route path="/" element={<Home isAuthenticated={auth.isAuthed} />} />
              <Route path="/products/" element={<Products />} />
              <Route path="/products/:id/" element={<ViewListing />} />
              <Route path="/products/listing/" element={<Listings />} />
              <Route path="/products/listing/edit/:id/" element={<EditListing />} />
              <Route path="/products/seller-dashboard/" element={<SellerDashboard />} />
              <Route path="/orders/cart/" element={<Cart />} />
              <Route path="/products/checkout/" element={<Checkout />} />
              <Route path="/orders/success/:id/" element={<CheckoutSuccess />} />
              <Route path="/orders/track/" element={<OrderTracking />} />
              <Route path="/accounts/profile/" element={<Profile />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Navbar>
        } />
      </Routes>
    </Router>
  );
}
