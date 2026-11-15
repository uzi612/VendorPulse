import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import { AuthProvider, useAuth } from './context/AuthContext';
import Home from './features/marketplace/Home';
import Products from './features/marketplace/Products';
import PostListing from './features/seller/PostListing';
import Cart from './features/marketplace/Cart';
import Login from './features/auth/Login';
import Register from './features/auth/Register';
import PortalLogin from './features/auth/PortalLogin';
import ViewListing from './features/marketplace/ViewListing';
import Checkout from './features/marketplace/Checkout';
import CheckoutSuccess from './features/marketplace/CheckoutSuccess';
import Profile from './features/profile/Profile';
import SellerDashboard from './features/seller/SellerDashboard';
import EditListing from './features/seller/EditListing';
import AdminPortal from './features/admin/AdminPortal';
import AgentDashboard from './features/agent/AgentDashboard';
import OrderTracking from './features/marketplace/OrderTracking';

// Session-based guard: asks the AuthContext whether the server-side session
// is active and carries the required role. Real enforcement still happens
// in Django.
function RoleRoute({ allowedRole, redirectPath, children }) {
  const { auth } = useAuth();
  if (auth.loading) {
    return <div style={{ padding: '32px', textAlign: 'center', color: '#64748b' }}>Checking session...</div>;
  }
  if (!auth.isAuthed || auth.role !== allowedRole) {
    return <Navigate to={redirectPath} replace />;
  }
  return children;
}

export default function App() {
  const { auth, refreshAuth, logout } = useAuth();

  return (
    <Router>
      <Routes>
        {/* Standalone Authentication Portals */}
        <Route path="/accounts/login/" element={<Login onLoginSuccess={refreshAuth} />} />
        <Route path="/accounts/register/" element={<Register onLoginSuccess={refreshAuth} />} />
        <Route path="/admin/login/" element={<PortalLogin role="admin" onLoginSuccess={refreshAuth} />} />
        <Route path="/agent/login/" element={<PortalLogin role="agent" onLoginSuccess={refreshAuth} />} />

        {/* Protected Admin & Agent Dashboards (Standalone Top-Header Layout) */}
        <Route
          path="/admin/deliveries/"
          element={
            <RoleRoute allowedRole="admin" redirectPath="/admin/login/">
              <AdminPortal onLogout={logout} />
            </RoleRoute>
          }
        />
        <Route
          path="/agent/dashboard/"
          element={
            <RoleRoute allowedRole="agent" redirectPath="/agent/login/">
              <AgentDashboard onLogout={logout} />
            </RoleRoute>
          }
        />

        {/* Customer Marketplace Routes */}
        <Route path="/*" element={
          <Navbar isAuthenticated={auth.isAuthed} onLogout={logout}>
            <Routes>
              <Route path="/" element={<Home isAuthenticated={auth.isAuthed} />} />
              <Route path="/products/" element={<Products />} />
              <Route path="/products/:id/" element={<ViewListing />} />
              <Route path="/products/listing/" element={<PostListing />} />
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
