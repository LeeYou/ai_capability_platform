import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { SidebarLayout } from '../../../frontend-common/src/SidebarLayout.tsx'
import '../../../frontend-common/src/SidebarLayout.css'
import '../../../frontend-common/src/r7Workspace.css'
import { buildR7Workspace } from '../../../frontend-common/src/r7Workspace.ts'
import './App.css'
import OverviewPage from './pages/OverviewPage'
import WizardPage from './pages/WizardPage'
import TasksPage from './pages/TasksPage'
import PackagePage from './pages/PackagePage'

const workspace = buildR7Workspace(import.meta.env, 'ai-builder')
const sidebarItems = [
  { path: '/overview', label: '总览', icon: '📊' },
  { path: '/wizard', label: '构建向导', icon: '🧙' },
  { path: '/tasks', label: '构建任务', icon: '📋' },
  { path: '/package', label: '交付包', icon: '📦' },
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
          <Route path="/wizard" element={<WizardPage />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/package" element={<PackagePage />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
