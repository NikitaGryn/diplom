function getCsrfToken() {
    const name = 'csrftoken';
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const trimmed = cookie.trim();
        if (trimmed.startsWith(name + '=')) {
            return decodeURIComponent(trimmed.substring(name.length + 1));
        }
    }
    // Fallback: get from hidden input if present
    const input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
}

async function apiPost(url, data) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'Accept': 'application/json',
            },
            body: JSON.stringify(data),
        });
        if (!response.ok) {
            const text = await response.text();
            console.error('API error:', response.status, text);
            return { success: false, error: `HTTP ${response.status}` };
        }
        return await response.json();
    } catch (err) {
        console.error('apiPost error:', err);
        return { success: false, error: err.message };
    }
}

async function apiGet(url) {
    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
        });
        if (!response.ok) {
            console.error('API error:', response.status);
            return { success: false, error: `HTTP ${response.status}` };
        }
        return await response.json();
    } catch (err) {
        console.error('apiGet error:', err);
        return { success: false, error: err.message };
    }
}
