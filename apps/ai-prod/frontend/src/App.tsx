import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { SidebarLayout } from '../../../frontend-common/src/SidebarLayout.tsx'
import '../../../frontend-common/src/SidebarLayout.css'
import '../../../frontend-common/src/r7Workspace.css'
import { buildR7Workspace } from '../../../frontend-common/src/r7Workspace.ts'
import './App.css'
import OverviewPage from './pages/OverviewPage'
import VerifyPage from './pages/VerifyPage'
import ControlPage from './pages/ControlPage'
import DiagnosticsPage from './pages/DiagnosticsPage'

const workspace = buildR7Workspace(import.meta.env, 'ai-prod')

const sidebarItems = [
  { path: '/overview', label: '总览', icon: '📊' },
  { path: '/verify', label: '在线验证', icon: '🔍' },
  { path: '/control', label: '版本控制', icon: '🎛️' },
  { path: '/diagnostics', label: '监控诊断', icon: '📈' },
]

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          element={
            <SidebarLayout
              moduleTitle={workspace.currentModule.title}
              moduleShortTitle={workspace.currentModule.shortTitle}
              sidebarItems={sidebarItems}
              moduleLinks={workspace.moduleLinks}
            />
          }
        >
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/verify" element={<VerifyPage />} />
          <Route path="/control" element={<ControlPage />} />
          <Route path="/diagnostics" element={<DiagnosticsPage />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
