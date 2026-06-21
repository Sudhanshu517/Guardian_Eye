/**
 * GuardianEye API Client
 * 
 * Central API client for all backend communication
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export interface ApiError {
  message: string;
  status: number;
}

class GuardianEyeAPI {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options?.headers,
        },
      });

      if (!response.ok) {
        const error: ApiError = {
          message: `API Error: ${response.statusText}`,
          status: response.status,
        };
        throw error;
      }

      return await response.json();
    } catch (error) {
      if ((error as ApiError).status) {
        throw error;
      }
      throw {
        message: 'Network error or server unavailable',
        status: 0,
      } as ApiError;
    }
  }

  // ===== INCIDENTS =====
  
  async getIncidents(params?: {
    skip?: number;
    limit?: number;
    severity?: string;
    status?: string;
    camera_id?: string;
  }) {
    const query = new URLSearchParams(params as Record<string, string>).toString();
    return this.request(`/incidents${query ? `?${query}` : ''}`);
  }

  async getIncident(id: string) {
    return this.request(`/incidents/${id}`);
  }

  async getRecentIncidents(hours: number = 24, limit: number = 10) {
    return this.request(`/incidents/recent?hours=${hours}&limit=${limit}`);
  }

  async updateIncidentStatus(id: string, status: string) {
    return this.request(`/incidents/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  }

  async getViolationsToday() {
    return this.request('/incidents/stats/violations-today');
  }

  async getViolationTrend(hours: number = 24) {
    return this.request(`/incidents/stats/trend?hours=${hours}`);
  }

  async getTopViolations(limit: number = 5) {
    return this.request(`/incidents/stats/top-violations?limit=${limit}`);
  }

  // ===== DASHBOARD =====
  
  async getDashboardStats() {
    return this.request('/dashboard/stats');
  }

  async getHeatmapData() {
    return this.request('/dashboard/heatmap');
  }

  // ===== ALERTS =====
  
  async getAlerts(params?: {
    skip?: number;
    limit?: number;
    alert_type?: string;
    status?: string;
    severity?: string;
  }) {
    const query = new URLSearchParams(params as Record<string, string>).toString();
    return this.request(`/alerts${query ? `?${query}` : ''}`);
  }

  async getAlert(id: string) {
    return this.request(`/alerts/${id}`);
  }

  async sendPoliceAlert(incidentId: string) {
    return this.request(`/alerts/send-police?incident_id=${incidentId}`, {
      method: 'POST',
    });
  }

  async sendHospitalAlert(incidentId: string) {
    return this.request(`/alerts/send-hospital?incident_id=${incidentId}`, {
      method: 'POST',
    });
  }

  async updateAlertStatus(id: string, status: string) {
    return this.request(`/alerts/${id}/status?status=${status}`, {
      method: 'PATCH',
    });
  }

  async getPendingAlerts() {
    return this.request('/alerts/stats/pending');
  }

  // ===== CAMERAS =====
  
  async getCameras() {
    return this.request('/cameras');
  }

  async getCamera(id: string) {
    return this.request(`/cameras/${id}`);
  }

  // ===== VEHICLES =====
  
  async getVehicleHistory(licensePlate: string) {
    return this.request(`/vehicles/${licensePlate}`);
  }

  async getRepeatOffenders(minViolations: number = 3, limit: number = 50) {
    return this.request(`/vehicles?min_violations=${minViolations}&limit=${limit}`);
  }

  // ===== UTILITY =====
  
  /**
   * Resolve an evidence image to a displayable URL.
   *
   * Priority:
   *   1. If `filename` is already a full URL (e.g. a Cloudinary https:// URL) → return as-is.
   *   2. Otherwise construct the legacy local-file URL: <backend>/evidence/<filename>
   *
   * This ensures backward compatibility with existing records that only have a
   * local filename stored, while new records with Cloudinary URLs work without
   * any extra mapping.
   */
  getEvidenceUrl(filename: string): string {
    if (!filename) return '/placeholder.svg';
    // Full URL — already hosted on Cloudinary (or any CDN)
    if (filename.startsWith('http://') || filename.startsWith('https://')) {
      return filename;
    }
    // Legacy: local filename served by backend StaticFiles mount
    return `${this.baseUrl.replace('/api', '')}/evidence/${filename}`;
  }

  async healthCheck() {
    return fetch(`${this.baseUrl.replace('/api', '')}/health`).then(r => r.json());
  }
}

// Export singleton instance
export const api = new GuardianEyeAPI(API_BASE);

// Export for use in other modules
export default api;
