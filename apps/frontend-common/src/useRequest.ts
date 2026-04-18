import { useCallback, useState } from 'react'
import { fetchListItems, fetchListResponse, requestJson } from './http.ts'
import type { ListResponse } from './http.ts'

export type AsyncState = {
  loading: boolean
  error: string | null
  actionMessage: string | null
}

export type UseRequestReturn = AsyncState & {
  request: <T>(path: string, init?: RequestInit) => Promise<T>
  fetchList: <T>(path: string) => Promise<T[]>
  fetchListResponse: <T>(path: string) => Promise<ListResponse<T>>
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setActionMessage: (message: string | null) => void
  clearActionMessage: () => void
}

export function useRequest(baseUrl: string, options?: { initialLoading?: boolean }): UseRequestReturn {
  const [loading, setLoading] = useState(options?.initialLoading ?? false)
  const [error, setError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  const request = useCallback(
    <T,>(path: string, init?: RequestInit): Promise<T> => {
      return requestJson<T>(baseUrl, path, init)
    },
    [baseUrl],
  )

  const fetchList = useCallback(
    <T,>(path: string): Promise<T[]> => {
      return fetchListItems<T>(baseUrl, path)
    },
    [baseUrl],
  )

  const fetchListResponseBound = useCallback(
    <T,>(path: string): Promise<ListResponse<T>> => {
      return fetchListResponse<T>(baseUrl, path)
    },
    [baseUrl],
  )

  const clearActionMessage = useCallback(() => {
    setActionMessage(null)
  }, [])

  return {
    loading,
    error,
    actionMessage,
    request,
    fetchList,
    fetchListResponse: fetchListResponseBound,
    setLoading,
    setError,
    setActionMessage,
    clearActionMessage,
  }
}
