// Central API helper for session-based (cookie) authentication.
// - Sends/receives the sessionid + csrftoken cookies on every request.
// - Automatically attaches the CSRF token header on unsafe methods,
//   which DRF's SessionAuthentication requires.

export function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

export async function api(url, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const headers = { ...(options.headers || {}) };

    // Let the browser set the multipart boundary for FormData uploads.
    if (options.body instanceof FormData) {
        delete headers['Content-Type'];
    } else if (typeof options.body === 'string' && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }

    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
        const csrfToken = getCookie('csrftoken');
        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }
    }

    return fetch(url, {
        credentials: 'include', 
        ...options,
        headers,
    });
}
