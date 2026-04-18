import type { ReactNode } from 'react'
import { statusTone } from './statusTone.ts'

export type RiskItem = {
  id: string | number
  label: string
  meta?: string[]
  status?: string
}

export type RiskBannerProps = {
  title: string
  items: RiskItem[]
  emptyMessage: string
  onSelect?: (id: string | number) => void
  selectedId?: string | number | null
  children?: ReactNode
}

export function RiskBanner(props: RiskBannerProps): ReactNode {
  return (
    <article className="workspace-summary-card">
      <h3>{props.title}</h3>
      {props.items.length === 0 ? (
        <div className="workspace-empty">{props.emptyMessage}</div>
      ) : (
        <div className="workspace-list">
          {props.items.map((item) => (
            <button
              key={item.id}
              className={`workspace-list-item${props.selectedId === item.id ? ' active' : ''}`}
              onClick={() => props.onSelect?.(item.id)}
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
      )}
      {props.children}
    </article>
  )
}
