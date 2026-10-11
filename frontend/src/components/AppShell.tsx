import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Activity, BookOpenCheck, ChevronDown, ChevronLeft, Database, FileChartColumn, LayoutDashboard,
  LogOut, Menu, Search, Settings2, ShieldAlert, Briefcase, Users, X, Sparkles,
} from 'lucide-react'
import { STAFF, roleLabel, useAuth } from '../lib/auth'
import type { Role } from '../lib/types'
import { useEscape } from './Primitives'

interface NavItem { to: string; label: string; icon: typeof Users; roles?: Role[] }
const groups: { label: string; items: NavItem[] }[] = [
  { label: 'Workspace', items: [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/students', label: 'Students', icon: Users, roles: STAFF },
    { to: '/academics', label: 'Academic analytics', icon: BookOpenCheck },
    { to: '/academic-risk', label: 'Academic risk', icon: ShieldAlert, roles: STAFF },
    { to: '/placement-risk', label: 'Placement readiness', icon: Activity, roles: STAFF },
  ] },
  { label: 'Insights', items: [
    { to: '/interventions', label: 'Interventions', icon: Briefcase, roles: STAFF },
    { to: '/reports', label: 'Reports', icon: FileChartColumn, roles: STAFF },
    { to: '/assistant', label: 'AI data assistant', icon: Sparkles },
  ] },
  { label: 'Manage', items: [
    { to: '/data', label: 'Data management', icon: Database },
    { to: '/settings', label: 'Methodology', icon: Settings2 },
  ] },
]
const titles: Record<string, string> = {
  '/': 'Dashboard', '/students': 'Students', '/academics': 'Academic analytics', '/academic-risk': 'Academic risk',
  '/placement-risk': 'Placement readiness', '/interventions': 'Interventions',
  '/reports': 'Reports', '/assistant': 'AI data assistant', '/data': 'Data management', '/settings': 'Methodology',
}

export default function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchText, setSearchText] = useState('')
  const location = useLocation()
  const navigate = useNavigate()
  const { user, can, signOut } = useAuth()

  useEscape(() => { setSearchOpen(false); setMobileOpen(false) }, searchOpen || mobileOpen)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k' && can(...STAFF)) { e.preventDefault(); setSearchOpen(open => !open) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [can])
  useEffect(() => { window.scrollTo(0, 0) }, [location.pathname])

  const submitSearch = () => {
    const q = searchText.trim()
    navigate(q ? `/students?q=${encodeURIComponent(q)}` : '/students')
    setSearchOpen(false); setSearchText('')
  }

  return (
    <div className={`app-shell ${collapsed ? 'is-collapsed' : ''}`}>
      {mobileOpen && <button className="mobile-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`} aria-label="Primary">
        <div className="brand-row">
          <img className="brand-mark" src="/academia-mark.png" alt="" width={30} height={30} />
          {!collapsed && <div className="brand-text"><span className="brand-name">Academia</span><span className="brand-tag">Campus Intelligence</span></div>}
          <button className="icon-button sidebar-collapse" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
            <ChevronLeft size={17} style={{ transform: collapsed ? 'rotate(180deg)' : undefined }} />
          </button>
          <button className="icon-button mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={18} /></button>
        </div>
        {!collapsed && (
          <button className="workspace-switch" aria-label="Workspace: QIS College of Engineering">
            <span className="workspace-avatar">Q</span>
            <span className="workspace-copy"><strong>QIS College of Engineering</strong><small>Institution workspace</small></span>
            <ChevronDown size={15} />
          </button>
        )}
        <nav className="nav-groups">
          {groups.map(group => ({ ...group, items: group.items.filter(i => !i.roles || can(...i.roles)) })).filter(g => g.items.length).map(group => (
            <div className="nav-group" key={group.label}>
              {!collapsed && <div className="nav-label">{group.label}</div>}
              {group.items.map(item => {
                const Icon = item.icon
                return (
                  <NavLink key={item.to} to={item.to} end={item.to === '/'} onClick={() => setMobileOpen(false)}
                    className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`} title={collapsed ? item.label : undefined}>
                    <Icon size={18} strokeWidth={1.8} />
                    {!collapsed && <span>{item.label}</span>}
                  </NavLink>
                )
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="user-row">
            <div className="avatar-circle">{(user?.username ?? '?').slice(0, 2).toUpperCase()}</div>
            {!collapsed && <div className="user-copy"><strong>{user?.username}</strong><span>{user ? roleLabel[user.role] : ''}</span></div>}
            <button className="icon-button sidebar-signout" onClick={signOut} aria-label="Sign out" title="Sign out"><LogOut size={17} /></button>
          </div>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
            <nav className="breadcrumbs" aria-label="Breadcrumb"><span>Academia</span><span className="crumb-slash">/</span><strong>{titles[location.pathname] ?? 'Overview'}</strong></nav>
          </div>
          <div className="topbar-actions">
            {can(...STAFF) && <button className="global-search" onClick={() => setSearchOpen(open => !open)} aria-label="Search students">
              <Search size={16} /><span>Search students</span><kbd>⌘K</kbd>
            </button>}
                        <div className="avatar-circle" aria-label={`Signed in as ${user?.username}`}>{(user?.username ?? '?').slice(0, 2).toUpperCase()}</div>
          </div>
        </header>

        {searchOpen && (
          <>
            <button className="mobile-scrim" style={{ display: 'block', background: 'transparent', zIndex: 45 }} aria-label="Close search" onClick={() => setSearchOpen(false)} />
            <div className="search-popover" role="dialog" aria-label="Search students">
              <div className="search-popover-field">
                <Search size={17} />
                <input autoFocus value={searchText} onChange={e => setSearchText(e.target.value)} placeholder="Search by student name or ID…"
                  onKeyDown={e => { if (e.key === 'Enter') submitSearch() }} aria-label="Search by student name or ID" />
                <kbd>Esc</kbd>
              </div>
              <div className="search-popover-hint">Press Enter to see matching students in the directory.</div>
            </div>
          </>
        )}

        <main className="page-container"><Outlet /></main>
        <footer className="app-footer">
          <span>Designed with ♥ &amp; debugged with ☕ — Lazy Bugs</span>
        </footer>
      </div>
    </div>
  )
}
