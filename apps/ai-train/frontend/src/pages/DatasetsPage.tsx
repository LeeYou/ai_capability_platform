import { useEffect, useState } from 'react'
import type { DatasetItem } from '../types'
import { fetchList, statusTone } from '../api'

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const items = await fetchList<DatasetItem>('/api/v1/datasets')
        if (!cancelled) setDatasets(items)
      } catch (loadError) {
        if (!cancelled) setError(loadError instanceof Error ? loadError.message : '加载数据失败')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
  }, [])

  return (
    <div className="page-container">
      <section className="panel">
        <div className="section-header">
          <div>
            <h2>数据集管理</h2>
            <p>浏览和管理训练数据集，查看数据集状态与绑定关系。</p>
          </div>
          <span className="badge">DS</span>
        </div>
        {loading && <p className="info-text">正在加载数据集数据...</p>}
        {error && <p className="error-text">数据加载失败：{error}</p>}
        {!loading && !error && datasets.length === 0 && (
          <p className="info-text">暂无数据集记录。</p>
        )}
        {!loading && !error && datasets.length > 0 && (
          <div className="workspace-table-wrap">
            <table className="workspace-table">
              <thead>
                <tr>
                  <th>能力名称</th>
                  <th>数据集路径</th>
                  <th>状态</th>
                  <th>来源</th>
                </tr>
              </thead>
              <tbody>
                {datasets.map((item) => (
                  <tr key={`${item.capability_name}-${item.dataset_path}`}>
                    <td>{item.capability_name}</td>
                    <td>{item.dataset_path}</td>
                    <td><span className={`status-pill ${statusTone(item.dataset_status)}`}>{item.dataset_status}</span></td>
                    <td>{item.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
