import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000
})

api.interceptors.response.use(
  response => response.data,
  error => {
    console.error('API Error:', error)
    return Promise.reject(error)
  }
)

export const searchQuestion = (data) => api.post('/search', data)

export const getQuestions = (params) => api.get('/questions', { params })
export const getQuestion = (id) => api.get(`/questions/${id}`)
export const createQuestion = (data) => api.post('/questions', data)
export const updateQuestion = (id, data) => api.put(`/questions/${id}`, data)
export const deleteQuestion = (id) => api.delete(`/questions/${id}`)

export const getPending = (params) => api.get('/pending', { params })
export const deletePending = (id) => api.delete(`/pending/${id}`)
export const pendingToQuestion = (id, data) => api.post(`/pending/${id}/to-question`, data)

export const getStats = () => api.get('/stats')
export const importJson = (formData) => api.post('/import-json', formData, {
  headers: { 'Content-Type': 'multipart/form-data' }
})
export const exportJson = () => '/api/export-json'
