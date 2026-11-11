import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
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

function RoleRoute({ allowedRole, redirectPath, children }) {
  const token = localStorage.getItem('authToken');
  const userRole = localStorage.getItem('userRole');

  if (!token || userRole !== allowedRole) {
    return <Navigate to={redirectPath} replace />;
  }
  return children;
}

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return localStorage.getItem('authToken') ? true : false;
  });

  const handleLogout = async () => {
    try {
      const token = localStorage.getItem('authToken');
      await fetch('/api/accounts/logout/', {
        method: 'POST',
        headers: {
          'Authorization': `Token ${token}`,
          'Content-Type': 'application/json'
        }
      });
    } catch (err) {
      console.error("Logout request failed", err);
    } finally {
      localStorage.removeItem('authToken');
      localStorage.removeItem('userRole');
      setIsAuthenticated(false);
      window.location.href = '/accounts/login/';
    }
  };

  return (
    <Router>
      <Routes>
        {/* Standalone Authentication Portals */}
        <Route path="/accounts/login/" element={<Login setIsAuthenticated={setIsAuthenticated} />} />
        <Route path="/accounts/register/" element={<Register setIsAuthenticated={setIsAuthenticated} />} />
        <Route path="/admin/login/" element={<AdminLogin setIsAuthenticated={setIsAuthenticated} />} />
        <Route path="/agent/login/" element={<AgentLogin setIsAuthenticated={setIsAuthenticated} />} />

        {/* Protected Admin & Agent Dashboards (Standalone Top-Header Layout) */}
        <Route
          path="/admin/deliveries/"
          element={
            <RoleRoute allowedRole="admin" redirectPath="/admin/login/">
              <AdminDeliveries onLogout={handleLogout} />
            </RoleRoute>
          }
        />
        <Route
          path="/agent/dashboard/"
          element={
            <RoleRoute allowedRole="agent" redirectPath="/agent/login/">
              <AgentDashboard onLogout={handleLogout} />
            </RoleRoute>
          }
        />

        {/* Customer Marketplace Routes */}
        <Route path="/*" element={
          <Navbar isAuthenticated={isAuthenticated} onLogout={handleLogout}>
            <Routes>
              <Route path="/" element={<Home isAuthenticated={isAuthenticated} />} />
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