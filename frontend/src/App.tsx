import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, STAFF, useAuth } from './lib/auth'
import type { Role } from './lib/types'
import AppShell from './components/AppShell'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Students from './pages/Students'
import Academics from './pages/Academics'
import RiskPage from './pages/RiskPage'
import Interventions from './pages/Interventions'
import Reports from './pages/Reports'
import DataPage from './pages/DataPage'
import Settings from './pages/Settings'
import AiAssistant from './pages/AiAssistant'
import type { ReactNode } from 'react'

function Guard({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { can } = useAuth()
  return can(...roles) ? <>{children}</> : <Navigate to="/" replace />
}

function Routed() {
  const { user } = useAuth()
  if (!user) return <Login />
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="students" element={<Guard roles={STAFF}><Students /></Guard>} />
          <Route path="academics" element={<Academics />} />
          <Route path="academic-risk" element={<Guard roles={STAFF}><RiskPage kind="academic" /></Guard>} />
          <Route path="placement-risk" element={<Guard roles={STAFF}><RiskPage kind="placement" /></Guard>} />
          <Route path="segments" element={<Navigate to="/" replace />} />
          <Route path="interventions" element={<Guard roles={STAFF}><Interventions /></Guard>} />
          <Route path="reports" element={<Guard roles={STAFF}><Reports /></Guard>} />
          <Route path="assistant" element={<AiAssistant />} />
          <Route path="data" element={<DataPage />} />
          <Route path="settings" element={<Settings />} />
          <Route path="discovery" element={<Navigate to="/students" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default function App() {
  return <AuthProvider><Routed /></AuthProvider>
}
