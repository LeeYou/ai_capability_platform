import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { SidebarLayout } from '../../../frontend-common/src/SidebarLayout.tsx'
import '../../../frontend-common/src/SidebarLayout.css'
import '../../../frontend-common/src/r7Workspace.css'
import { buildR7Workspace } from '../../../frontend-common/src/r7Workspace.ts'
import './App.css'
import OverviewPage from './pages/OverviewPage.tsx'
import AnnotationPage from './pages/AnnotationPage.tsx'
import TrainingPage from './pages/TrainingPage.tsx'
import ModelPage from './pages/ModelPage.tsx'

const workspace = buildR7Workspace(import.meta.env, 'ai-train')
const sidebarItems = [
  { path: '/overview', label: '总览', icon: '📊' },
  { path: '/annotation', label: '标注工作台', icon: '📝' },
  { path: '/training', label: '训练工作台', icon: '🏋️' },
  { path: '/model', label: '模型资产', icon: '📦' },
]

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<SidebarLayout moduleTitle="ai-train 研发训练台" moduleShortTitle="训练台" sidebarItems={sidebarItems} moduleLinks={workspace.moduleLinks} />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/annotation" element={<AnnotationPage />} />
          <Route path="/training" element={<TrainingPage />} />
          <Route path="/model" element={<ModelPage />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
