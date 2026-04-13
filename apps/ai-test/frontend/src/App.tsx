import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { SidebarLayout } from '../../../frontend-common/src/SidebarLayout.tsx'
import '../../../frontend-common/src/SidebarLayout.css'
import '../../../frontend-common/src/r7Workspace.css'
import { buildR7Workspace } from '../../../frontend-common/src/r7Workspace.ts'
import './App.css'
import { OverviewPage } from './pages/OverviewPage'
import { SingleTestPage } from './pages/SingleTestPage'
import { BatchTestPage } from './pages/BatchTestPage'
import { AcceptancePage } from './pages/AcceptancePage'
import { ReportsPage } from './pages/ReportsPage'

const workspace = buildR7Workspace(import.meta.env, 'ai-test')
const sidebarItems = [
  { path: '/overview', label: '总览', icon: '📊' },
  { path: '/single', label: '单测', icon: '🔬' },
  { path: '/batch', label: '批量测试', icon: '📋' },
  { path: '/acceptance', label: '验收', icon: '✅' },
  { path: '/reports', label: '报告', icon: '📈' },
]

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<SidebarLayout moduleTitle="ai-test 测试评估台" moduleShortTitle="测试台" sidebarItems={sidebarItems} moduleLinks={workspace.moduleLinks} />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/single" element={<SingleTestPage />} />
          <Route path="/batch" element={<BatchTestPage />} />
          <Route path="/acceptance" element={<AcceptancePage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
