import React, { createContext, useCallback, useContext, useRef, useState } from 'react';

// Tiny toast system replacing browser alert() dialogs.
// Usage:  const toast = useToast();  toast.success('Saved!');  toast.error(err.message);
// Toasts stack top-right and auto-dismiss after 3.5s (click to dismiss early).

const ToastContext = createContext(null);

const STYLES = {
    success: {
        icon: '✓',
        border: 'border-emerald-200',
        iconBg: 'bg-emerald-100 text-emerald-700',
        title: 'text-emerald-800',
    },
    error: {
        icon: '✕',
        border: 'border-red-200',
        iconBg: 'bg-red-100 text-red-700',
        title: 'text-red-800',
    },
};

export function ToastProvider({ children }) {
    const [toasts, setToasts] = useState([]);
    const idRef = useRef(0);

    const dismiss = useCallback((id) => {
        setToasts((list) => list.filter((t) => t.id !== id));
    }, []);

    const push = useCallback((type, text) => {
        const id = ++idRef.current;
        setToasts((list) => [...list.slice(-3), { id, type, text }]);  // keep max 4 on screen
        window.setTimeout(() => dismiss(id), 3500);
    }, [dismiss]);

    // Stable API object: toast.success(text) / toast.error(text)
    const toast = {
        success: useCallback((text) => push('success', text), [push]),
        error: useCallback((text) => push('error', text), [push]),
    };

    return (
        <ToastContext.Provider value={toast}>
            {children}
            {/* Toast stack */}
            <div className="fixed top-20 right-4 z-[100] flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)]">
                {toasts.map((t) => {
                    const s = STYLES[t.type] || STYLES.error;
                    return (
                        <div
                            key={t.id}
                            onClick={() => dismiss(t.id)}
                            className={`flex items-start gap-3 bg-white border ${s.border} rounded-xl shadow-lg px-4 py-3 cursor-pointer animate-[toastIn_.2s_ease-out]`}
                            role="status"
                        >
                            <span className={`w-6 h-6 flex-shrink-0 rounded-full ${s.iconBg} flex items-center justify-center text-xs font-black`}>
                                {s.icon}
                            </span>
                            <p className={`text-sm font-semibold leading-snug ${s.title}`}>{t.text}</p>
                        </div>
                    );
                })}
            </div>
        </ToastContext.Provider>
    );
}

export function useToast() {
    return useContext(ToastContext);
}
