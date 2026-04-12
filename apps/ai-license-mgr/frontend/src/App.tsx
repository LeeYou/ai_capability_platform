import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { SidebarLayout } from '../../../frontend-common/src/SidebarLayout.tsx'
import '../../../frontend-common/src/SidebarLayout.css'
import '../../../frontend-common/src/r7Workspace.css'
import { buildR7Workspace } from '../../../frontend-common/src/r7Workspace.ts'
import './App.css'
import OverviewPage from './pages/OverviewPage'
import IssuancePage from './pages/IssuancePage'
import RiskPage from './pages/RiskPage'
import ValidationPage from './pages/ValidationPage'
import CustomersPage from './pages/CustomersPage'
import PoliciesPage from './pages/PoliciesPage'

const workspace = buildR7Workspace(import.meta.env, 'ai-license-mgr')

const sidebarItems = [
  { path: '/overview', label: '总览', icon: '📊' },
  { path: '/issuance', label: '签发管理', icon: '📜' },
  { path: '/risk', label: '风险管控', icon: '🛡️' },
  { path: '/validation', label: '校验诊断', icon: '✅' },
  { path: '/customers', label: '客户管理', icon: '👥' },
  { path: '/policies', label: '策略记录', icon: '📋' },
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
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/issuance" element={<IssuancePage />} />
          <Route path="/risk" element={<RiskPage />} />
          <Route path="/validation" element={<ValidationPage />} />
          <Route path="/customers" element={<CustomersPage />} />
          <Route path="/policies" element={<PoliciesPage />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
