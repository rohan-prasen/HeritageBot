const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const sendMessage = async (query, modelId) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query,
        model_id: modelId,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      throw new Error(errorData?.detail || `HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return {
      answer: data.answer,
      modelUsed: data.model_used,
    };
  } catch (error) {
    console.error('API Error:', error);
    throw error;
  }
};

export const checkHealth = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    return await response.json();
  } catch (error) {
    console.error('Health check failed:', error);
    return { status: 'unhealthy' };
  }
};
