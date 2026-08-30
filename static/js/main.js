// UICT E-Attendance System - Main JavaScript

// Get CSRF token
function getCsrfToken() {
    const cookie = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1] : '';
}

// Show toast notification
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) {
        const newContainer = document.createElement('div');
        newContainer.id = 'toastContainer';
        newContainer.style.cssText = `
            position: fixed; top: 20px; right: 20px; z-index: 9999; max-width: 400px;
        `;
        document.body.appendChild(newContainer);
    }
    
    const toast = document.createElement('div');
    const colors = { success: '#2e7d32', error: '#c62828', warning: '#f9a825', info: '#43a047' };
    toast.style.cssText = `
        background: white; padding: 16px 20px; margin-bottom: 10px; border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15); border-left: 4px solid ${colors[type] || colors.info};
        color: #333; font-size: 14px; animation: slideIn 0.3s ease;
    `;
    toast.textContent = message;
    document.getElementById('toastContainer').appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.5s ease';
        setTimeout(() => toast.remove(), 500);
    }, 5000);
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    @keyframes fadeOut { from { opacity: 1; } to { opacity: 0; } }
`;
document.head.appendChild(style);

// Get location
function getLocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) reject('Geolocation not supported');
        navigator.geolocation.getCurrentPosition(
            position => resolve({ latitude: position.coords.latitude, longitude: position.coords.longitude }),
            error => reject('Location permission required')
        );
    });
}

// Take attendance
async function takeAttendance(lectureId, verificationCode) {
    try {
        const location = await getLocation();
        const deviceId = localStorage.getItem('deviceId') || 
            `device_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        localStorage.setItem('deviceId', deviceId);
        
        const response = await fetch('/api/attendance/take_attendance/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({
                lecture_id: lectureId,
                verification_code: verificationCode,
                latitude: location.latitude,
                longitude: location.longitude,
                device_identifier: deviceId
            })
        });
        
        const data = await response.json();
        if (response.ok) {
            showToast('Attendance recorded successfully!', 'success');
            return data;
        } else {
            showToast(data.error || 'Failed to record attendance', 'error');
            throw new Error(data.error);
        }
    } catch (error) {
        showToast(error.message || 'An error occurred', 'error');
        throw error;
    }
}

// Start lecture
async function startLecture(lectureId) {
    try {
        const response = await fetch('/api/attendance/start_lecture/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ lecture_id: lectureId })
        });
        const data = await response.json();
        if (response.ok) {
            showToast(`Lecture started! Code: ${data.verification_code}`, 'success');
            location.reload();
            return data;
        } else {
            showToast(data.error || 'Failed to start lecture', 'error');
            throw new Error(data.error);
        }
    } catch (error) {
        showToast(error.message, 'error');
        throw error;
    }
}

// End lecture
async function endLecture(lectureId) {
    try {
        const response = await fetch('/api/attendance/end_lecture/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ lecture_id: lectureId })
        });
        const data = await response.json();
        if (response.ok) {
            showToast('Lecture ended successfully', 'success');
            location.reload();
            return data;
        } else {
            showToast(data.error || 'Failed to end lecture', 'error');
            throw new Error(data.error);
        }
    } catch (error) {
        showToast(error.message, 'error');
        throw error;
    }
}

// Generate code
async function generateCode(lectureId) {
    try {
        const response = await fetch('/api/attendance/generate_code/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
            body: JSON.stringify({ lecture_id: lectureId })
        });
        const data = await response.json();
        if (response.ok) {
            showToast(`New code: ${data.verification_code}`, 'success');
            location.reload();
            return data;
        } else {
            showToast(data.error || 'Failed to generate code', 'error');
            throw new Error(data.error);
        }
    } catch (error) {
        showToast(error.message, 'error');
        throw error;
    }
}

// Export functions
window.takeAttendance = takeAttendance;
window.startLecture = startLecture;
window.endLecture = endLecture;
window.generateCode = generateCode;
window.getLocation = getLocation;
window.showToast = showToast;