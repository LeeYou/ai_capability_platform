import type { ReactNode } from 'react'
import { statusTone } from './statusTone.ts'

export type ListItem = {
  id: string | number
  label: string
  meta?: string[]
  status?: string
}

export type ListDetailLayoutProps = {
  listTitle: string
  listBadge?: string
  items: ListItem[]
  selectedId: string | number | null
  onSelect: (id: string | number) => void
  detailTitle: string
  detailBadge?: string
  detailStatus?: string
  detail: ReactNode
  emptyMessage: string
}

export function ListDetailLayout(props: ListDetailLayoutProps): ReactNode {
  return (
    <div className="workspace-panel-grid">
      <div className="workspace-stack">
        <article className="workspace-note-block">
          <div className="section-header">
            <h3>{props.listTitle}</h3>
            {props.listBadge && <span className="badge badge-muted">{props.listBadge}</span>}
          </div>
          <div className="workspace-list">
            {props.items.map((item) => (
              <button
                key={item.id}
                className={`workspace-list-item${props.selectedId === item.id ? ' active' : ''}`}
                onClick={() => props.onSelect(item.id)}
                type="button"
              >
                <strong>{item.label}</strong>
                {(item.meta?.length || item.status) && (
                  <div className="workspace-meta-row">
                    {item.meta?.map((m, i) => <span key={i}>{m}</span>)}
                    {item.status && (
                      <span className={`status-pill ${statusTone(item.status)}`}>{item.status}</span>
                    )}
                  </div>
                )}
              </button>
            ))}
          </div>
        </article>
      </div>
      <div className="workspace-stack">
        <article className="workspace-note-block">
          <div className="section-header">
            <h3>{props.detailTitle}</h3>
            {props.detailBadge && <span className="badge badge-muted">{props.detailBadge}</span>}
            {props.detailStatus && (
              <span className={`status-pill ${statusTone(props.detailStatus)}`}>{props.detailStatus}</span>
            )}
          </div>
          {props.selectedId == null ? (
            <div className="workspace-empty">{props.emptyMessage}</div>
          ) : (
            props.detail
          )}
        </article>
      </div>
    </div>
  )
}
