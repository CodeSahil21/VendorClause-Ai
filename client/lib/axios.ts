import axios from "axios";
import { useAuthStore } from "@/store";
import toast from "react-hot-toast";

const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:4000";
const apiOrigin = apiBase.replace(/\/$/, "").replace(/\/api\/v1$/, "");

const axiosInstance = axios.create({
  baseURL: `${apiOrigin}/api/v1`,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,
});

let isRedirecting = false;

axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;

    if (status === 401 && !isRedirecting) {
      isRedirecting = true;
      useAuthStore.getState().clearAuth();
      toast.error('Session expired. Please login again.');
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }

    return Promise.reject(error);
  }
);

export default axiosInstance;
