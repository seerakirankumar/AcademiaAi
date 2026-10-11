import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as api from './api'
import type { AuthUser, Role } from './types'

interface AuthState {
  user: AuthUser | null
  signIn: (username: string, password: string) => Promise<void>
  signOut: () => void
  can: (...roles: Role[]) => boolean
}
const Ctx = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const saved = api.loadSession()
    if (saved) api.setToken(saved.token)
    return saved?.user ?? null
  })

  const signOut = useCallback(() => { api.setToken(null); api.saveSession(null); setUser(null) }, [])
  useEffect(() => { api.onUnauthorized(signOut); return () => api.onUnauthorized(null) }, [signOut])

  const signIn = useCallback(async (username: string, password: string) => {
    const session = await api.login(username.trim(), password)
    api.setToken(session.token); api.saveSession(session); setUser(session.user)
  }, [])

  const value = useMemo<AuthState>(() => ({
    user, signIn, signOut, can: (...roles) => !!user && roles.includes(user.role),
  }), [user, signIn, signOut])
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}

/** Roles that may read student-level data, per the backend's RBAC. */
export const STAFF: Role[] = ['admin', 'faculty', 'placement_officer']
export const roleLabel: Record<Role, string> = {
  admin: 'Administrator', faculty: 'Faculty', placement_officer: 'Placement officer', judge_demo: 'Demo viewer',
}
