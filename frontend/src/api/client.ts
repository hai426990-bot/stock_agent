import axios from "axios"

const API_BASE = import.meta.env.VITE_API_BASE || ""

const client = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
})

client.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const msg = error.response?.data?.detail || error.message || "请求失败"
    return Promise.reject(new Error(msg))
  },
)

export default client
