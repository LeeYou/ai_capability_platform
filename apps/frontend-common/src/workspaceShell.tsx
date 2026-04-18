import type { ReactNode } from 'react'

import { buildR7Workspace, type R7ModuleId } from './r7Workspace'

export function WorkspaceShell(props: {
  moduleId: R7ModuleId
  title: string
  subtitle: string
  children: ReactNode
}): ReactNode {
  const workspace = buildR7Workspace(import.meta.env, props.moduleId)

  return (
    <div className="page">
      <div className="workspace-topbar">
        <div className="workspace-brand">
          <strong>Agile Star AI Capability Platform</strong>
          <span>
            {props.subtitle} / 当前模块：{workspace.currentModule.title}
          </span>
        </div>
        <nav className="workspace-nav">
          {workspace.moduleLinks.map((item) => (
            <a key={item.id} className={`workspace-nav-link${item.isCurrent ? ' active' : ''}`} href={item.url}>
              <strong>{item.shortTitle}</strong>
              <span>{item.stageLabel}</span>
            </a>
          ))}
        </nav>
      </div>

      <div className="workflow-strip">
        {workspace.workflowSteps.map((item) => (
          <a key={item.moduleId} className={`workflow-step${item.isCurrent ? ' active' : ''}`} href={item.url}>
            <span>步骤 {item.order}</span>
            <strong>{item.label}</strong>
            <span>{item.summary}</span>
          </a>
        ))}
      </div>

      {props.children}
    </div>
  )
}
