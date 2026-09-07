// Session service abstraction
// Currently uses mocked data. Will be replaced with real API calls.
// Future endpoint: POST /api/session

export interface SessionResponse {
  session_id: string;
  mirage_ip: string;
  status: 'initializing' | 'ready' | 'expired' | 'error';
}

export interface SessionError {
  message: string;
  code: string;
}

// API base URL - will be configured for production
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * Request a new session from the backend.
 * Currently returns mocked data after a simulated delay.
 * 
 * Future implementation will POST to /api/session
 */
export async function createSession(): Promise<SessionResponse> {
  // --- MOCK IMPLEMENTATION ---
  // Replace this block with actual API call when backend is ready:
  // const response = await fetch(`${API_BASE_URL}/api/session`, {
  //   method: 'POST',
  //   headers: { 'Content-Type': 'application/json' },
  // });
  // if (!response.ok) throw new Error('Session creation failed');
  // return response.json();
  
  return new Promise((resolve) => {
    // Simulate the 90-second initialization
    // The actual delay is handled by the UI countdown
    resolve({
      session_id: `session-${generateMockId()}`,
      mirage_ip: `10.42.0.${Math.floor(Math.random() * 254) + 1}`,
      status: 'ready',
    });
  });
}

/**
 * Check session status
 */
export async function getSessionStatus(sessionId: string): Promise<SessionResponse> {
  // --- MOCK IMPLEMENTATION ---
  // Replace with: GET /api/session/:sessionId
  return {
    session_id: sessionId,
    mirage_ip: '10.42.0.1',
    status: 'ready',
  };
}

/**
 * Terminate a session
 */
export async function terminateSession(sessionId: string): Promise<void> {
  // --- MOCK IMPLEMENTATION ---
  // Replace with: DELETE /api/session/:sessionId
  console.info(`Session ${sessionId} terminated (mock)`);
}

function generateMockId(): string {
  return Math.random().toString(36).substring(2, 8);
}
