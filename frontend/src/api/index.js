import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000
})

// 资讯
export const getLatestNews = (limit = 20) => api.get(`/news/latest?limit=${limit}`)
export const searchNews = (keyword) => api.get(`/news/search?keyword=${keyword}`)

// 对话
export const sendChat = (message) => api.post('/chat/send', { message })
export const getChatHistory = (limit = 50) => api.get(`/chat/history?limit=${limit}`)

// 选股
export const getTodayScreening = () => api.get('/screening/today')
export const getHistoryScreening = (date) => api.get(`/screening/history?date=${date}`)
export const getScreeningRules = () => api.get('/screening/rules')
export const getScreeningDates = () => api.get('/screening/dates')
export const triggerScreening = () => api.post('/screening/run')

// 学习
export const getPerformance = () => api.get('/learning/performance')
export const getSuggestions = () => api.get('/learning/suggestions')
export const approveRule = (ruleId) => api.post(`/learning/approve-rule?ruleId=${ruleId}`)
export const rejectRule = (ruleId) => api.post(`/learning/reject-rule?ruleId=${ruleId}`)

export default api
