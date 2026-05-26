import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? decodeURIComponent(match[2]) : null;
}

api.interceptors.request.use((config) => {
  const token = getCookie("csrftoken");
  if (token && config.method !== "get") {
    config.headers["X-CSRFToken"] = token;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      const path = window.location.pathname;
      if (!path.startsWith("/login") && !path.startsWith("/status/")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

export default api;
