export type ListResponse<T> = {
  items: T[]
}

export async function requestJson<T>(baseUrl: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `请求失败：${path}`)
  }
  return (await response.json()) as T
}

export async function fetchListResponse<T>(baseUrl: string, path: string): Promise<ListResponse<T>> {
  return requestJson<ListResponse<T>>(baseUrl, path)
}

export async function fetchListItems<T>(baseUrl: string, path: string): Promise<T[]> {
  const payload = await fetchListResponse<T>(baseUrl, path)
  return payload.items
}
