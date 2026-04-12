import { NavLink, Outlet } from 'react-router-dom'
import type { R7ModuleLink } from './r7Workspace.ts'

export type SidebarMenuItem = {
  path: string
  label: string
  icon: string
}

type SidebarLayoutProps = {
  moduleTitle: string
  moduleShortTitle: string
  sidebarItems: SidebarMenuItem[]
  moduleLinks: R7ModuleLink[]
}

export function SidebarLayout({
  moduleTitle,
  moduleShortTitle,
  sidebarItems,
  moduleLinks,
}: SidebarLayoutProps) {
  return (
    <div className="sidebar-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo">⭐</div>
          <div className="sidebar-brand">
            <strong>{moduleShortTitle}</strong>
            <span>Agile Star</span>
          </div>
        </div>

        <nav className="sidebar-menu">
          {sidebarItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `sidebar-menu-item${isActive ? ' active' : ''}`
              }
            >
              <span className="sidebar-icon">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-divider" />

        <div className="sidebar-section-title">平台模块</div>
        <nav className="sidebar-menu sidebar-cross-nav">
          {moduleLinks.map((link) => (
            <a
              key={link.id}
              className={`sidebar-menu-item sidebar-cross-item${link.isCurrent ? ' current' : ''}`}
              href={link.url}
            >
              <span className="sidebar-icon">
                {link.id === 'ai-train' && '🏋️'}
                {link.id === 'ai-test' && '🧪'}
                {link.id === 'ai-license-mgr' && '🔑'}
                {link.id === 'ai-builder' && '📦'}
                {link.id === 'ai-prod' && '🚀'}
              </span>
              <span>{link.shortTitle}</span>
              {link.isCurrent && <span className="sidebar-current-badge">当前</span>}
            </a>
          ))}
        </nav>
      </aside>

      <div className="main-area">
        <header className="main-header">
          <div className="main-header-title">
            <h1>{moduleTitle}</h1>
          </div>
          <nav className="main-header-nav">
            {moduleLinks.map((link) => (
              <a
                key={link.id}
                className={`header-nav-link${link.isCurrent ? ' active' : ''}`}
                href={link.url}
              >
                {link.shortTitle}
              </a>
            ))}
          </nav>
        </header>
        <main className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
