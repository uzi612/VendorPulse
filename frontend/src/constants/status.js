// Canonical order-status presentation constants.
// Keep the keys in sync with the OrderItem STATUS_CHOICES in
// Backend/orders/models.py — the backend is the source of truth.

export const STATUS_LABELS = {
    ORDER_PLACED: 'Order Placed',
    PICKUP_SCHEDULED: 'Pickup Scheduled',
    PICKED_UP: 'Picked Up',
    DISPATCHED: 'In Transit',
    DELIVERED: 'Delivered',
    CANCELLED: 'Cancelled',
};

// Tailwind badge classes for customer-facing pages (Profile orders list).
export const STATUS_BADGE_STYLES = {
    ORDER_PLACED: 'bg-gray-100 text-gray-500',
    PICKUP_SCHEDULED: 'bg-sky-100 text-sky-700',
    PICKED_UP: 'bg-sky-100 text-sky-700',
    DISPATCHED: 'bg-amber-100 text-amber-700',
    DELIVERED: 'bg-emerald-100 text-emerald-700',
    CANCELLED: 'bg-red-100 text-red-600',
};

// Inline hex colors for the admin/agent portals (inline-style system):
// status bars in analytics and status pill backgrounds.
export const STATUS_BAR_COLORS = {
    ORDER_PLACED: '#dc2626',
    PICKUP_SCHEDULED: '#d97706',
    PICKED_UP: '#d97706',
    DISPATCHED: '#d97706',
    DELIVERED: '#16a34a',
    CANCELLED: '#ef4444',
};
