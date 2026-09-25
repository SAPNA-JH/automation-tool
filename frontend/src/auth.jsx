import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken } from './api'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!getToken()) {
      setLoading(false)
      return
    }
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false))
  }, [])

  const finishLogin = useCallback((res) => {
    setToken(res.token)
    setUser(res.user)
    return res.user
  }, [])

  const takeRef = () => {
    const ref = localStorage.getItem('postpilot_ref') || ''
    return ref
  }
  const clearRef = () => localStorage.removeItem('postpilot_ref')

  const loginWithGoogle = useCallback(
    (credential) => api.googleLogin(credential, takeRef()).then((r) => (clearRef(), finishLogin(r))),
    [finishLogin],
  )

  const loginDev = useCallback(
    (email, name) => api.devLogin(email, name, takeRef()).then((r) => (clearRef(), finishLogin(r))),
    [finishLogin],
  )

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, loginWithGoogle, loginDev, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
