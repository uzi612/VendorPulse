import React from 'react';

// "Items You've Sold" accordion — purely presentational; sales come from the
// same profile fetch as the orders in OrdersAccordion.
export default function SalesList({ sales }) {
    return (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <details className="group p-6 md:p-8">
                <summary className="flex justify-between items-center cursor-pointer list-none select-none">
                    <div className="flex items-center gap-3">
                        <h2 className="text-xl font-bold text-gray-800">Items You've Sold</h2>
                        <span className="bg-indigo-50 text-indigo-700 text-xs font-bold px-2.5 py-0.5 rounded-full border border-indigo-100">
                            {sales.length} Sold
                        </span>
                    </div>
                    <span className="transform group-open:rotate-180 transition duration-200 text-indigo-600 font-bold">▼</span>
                </summary>

                <div className="mt-6 pt-6 border-t border-gray-100">
                    {sales.length > 0 ? (
                        <div className="space-y-4">
                            {sales.map((sale) => (
                                <div key={sale.id} className="border border-gray-200 rounded-xl p-5 bg-white">
                                    <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                                        <div>
                                            <span className="text-xs font-bold text-indigo-600 uppercase">Item Purchased</span>
                                            <h3 className="font-bold text-gray-900 text-base mt-0.5">{sale.item_title}</h3>
                                        </div>
                                        <span className="text-emerald-600 font-black text-lg">₹{sale.item_price}</span>
                                    </div>
                                    <div className="py-3 text-xs space-y-1 text-gray-600">
                                        <p><strong className="text-gray-800">Buyer:</strong> @{sale.buyer}</p>
                                        <p><strong className="text-gray-800">Delivery Address:</strong> {sale.shipping_address}</p>
                                        {sale.return_status === 'APPROVED' ? (
                                            <p className="text-rose-600 font-semibold">
                                                ↩ Return approved — buyer refunded; your payout for this item was reversed.
                                            </p>
                                        ) : (
                                            <p>
                                                <strong className="text-gray-800">Platform fee:</strong> −₹{sale.platform_fee ?? 0}
                                                {' · '}
                                                <strong className="text-emerald-700">You receive: ₹{sale.seller_payout ?? sale.item_price}</strong>
                                            </p>
                                        )}
                                        {sale.return_status && sale.return_status !== 'APPROVED' && (
                                            <p className="text-amber-600 font-semibold">↩ Return {sale.return_status.toLowerCase()}</p>
                                        )}
                                        {sale.status === 'CANCELLED' && sale.cancel_reason && (
                                            <p className="text-red-600 font-semibold">
                                                ✕ Cancelled by buyer — Reason: {sale.cancel_reason.replaceAll('_', ' ').toLowerCase()}
                                                {sale.cancel_note ? ` · "${sale.cancel_note}"` : ''}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="text-center py-12 border-2 border-dashed border-gray-100 rounded-xl">
                            <p className="text-gray-400 text-sm font-medium">No sales recorded yet.</p>
                        </div>
                    )}
                </div>
            </details>
        </div>
    );
}
