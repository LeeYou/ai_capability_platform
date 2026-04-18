import type { ReactNode } from 'react'

type FeedbackTone = 'info' | 'error' | 'success'

type FeedbackItem = {
  tone: FeedbackTone
  message: string
}

export function WorkspaceFeedback(props: {
  loading: boolean
  loadingMessage: string
  error: string | null
  actionMessage: string | null
}): ReactNode {
  const items: FeedbackItem[] = []
  if (props.loading) items.push({ tone: 'info', message: props.loadingMessage })
  if (props.error) items.push({ tone: 'error', message: `数据加载失败：${props.error}` })
  if (props.actionMessage) items.push({ tone: 'success', message: props.actionMessage })

  if (items.length === 0) return null

  return (
    <>
      {items.map((item, index) => {
        const className =
          item.tone === 'info' ? 'info-text' : item.tone === 'error' ? 'error-text' : 'success-text'
        return (
          <p key={`${item.tone}-${index}`} className={className}>
            {item.message}
          </p>
        )
      })}
    </>
  )
}
