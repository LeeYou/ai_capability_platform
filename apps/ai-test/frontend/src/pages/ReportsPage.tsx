import { useEffect, useState } from 'react'
import type { TestReportItem, TestReportDetail } from '../types'
import { apiBaseUrl, fetchList, request } from '../api'
import { buildR7Workspace } from '../../../../frontend-common/src/r7Workspace.ts'

const workspace = buildR7Workspace(import.meta.env, 'ai-test')

export function ReportsPage() {
  const [reports, setReports] = useState<TestReportItem[]>([])
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null)
  const [reportTemplateType, setReportTemplateType] = useState<'research' | 'delivery'>('research')
  const [selectedReport, setSelectedReport] = useState<TestReportDetail | null>(null)
  const [loading, setLoading] = useState(true)

  async function loadData(): Promise<void> {
    setLoading(true)
    try {
      const res = await fetchList<TestReportItem>('/api/v1/test-reports')
      setReports(res.items)
      setSelectedReportId((current) => current ?? res.items[0]?.report_id ?? null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadData()
  }, [])

  useEffect(() => {
    if (selectedReportId == null) {
      setSelectedReport(null)
      return
    }
    void request<TestReportDetail>(`/api/v1/test-reports/${selectedReportId}?template_type=${reportTemplateType}`)
      .then(setSelectedReport)
      .catch(() => {
        setSelectedReport(null)
      })
  }, [selectedReportId, reportTemplateType])

  function reportExportUrl(reportId: number, format: 'json' | 'html' | 'pdf'): string {
    return `${apiBaseUrl}/api/v1/test-reports/${reportId}/export?export_format=${format}&template_type=${reportTemplateType}`
  }

  return (
    <div className="page-container">
      {loading && <p className="info-text">正在加载...</p>}
      <div className="workspace-panel-grid">
        <div className="workspace-stack">
          <article className="workspace-note-block">
            <div className="section-header">
              <h3>报告中心</h3>
              <span className="badge badge-muted">TT18-TT19</span>
            </div>
            <div className="button-row">
              <button type="button" onClick={() => setReportTemplateType('research')}>研发视角</button>
              <button type="button" onClick={() => setReportTemplateType('delivery')}>交付视角</button>
            </div>
            <div className="workspace-list" style={{ marginTop: 16 }}>
              {reports.map((item) => (
                <button
                  key={item.report_id}
                  className={`workspace-list-item${selectedReportId === item.report_id ? ' active' : ''}`}
                  onClick={() => setSelectedReportId(item.report_id)}
                  type="button"
                >
                  <strong>报告 #{item.report_id} / {item.capability_name}</strong>
                  <div className="workspace-meta-row">
                    <span>{item.model_version}</span>
                    <span>{item.passed_cases}/{item.passed_cases + item.failed_cases} 通过</span>
                    <span className={`status-pill ${item.failed_cases === 0 ? 'good' : 'warn'}`}>
                      {item.failed_cases === 0 ? '可推进' : '需复核'}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </article>
        </div>
        <div className="workspace-stack">
          <article className="workspace-note-block">
            <div className="section-header">
              <h3>报告摘要与证据链</h3>
              {selectedReport && (
                <span className={`status-pill ${selectedReport.failed_cases === 0 ? 'good' : 'warn'}`}>
                  {selectedReport.failed_cases === 0 ? '推送下游' : '问题回流'}
                </span>
              )}
            </div>
            {!selectedReport ? (
              <div className="workspace-empty">请选择报告查看摘要。</div>
            ) : (
              <>
                <div className="workspace-kpi-grid">
                  <article className="workspace-kpi-card">
                    <span>通过用例</span>
                    <strong>{selectedReport.passed_cases}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>失败用例</span>
                    <strong>{selectedReport.failed_cases}</strong>
                  </article>
                  <article className="workspace-kpi-card">
                    <span>当前视角</span>
                    <strong>{reportTemplateType}</strong>
                  </article>
                </div>
                <pre className="workspace-code-block">{JSON.stringify(selectedReport.summary, null, 2)}</pre>
                <div className="workspace-action-row">
                  <a className="workspace-action-chip" href={reportExportUrl(selectedReport.report_id, 'json')}>导出 JSON</a>
                  <a className="workspace-action-chip" href={reportExportUrl(selectedReport.report_id, 'html')}>导出 HTML</a>
                  <a className="workspace-action-chip" href={reportExportUrl(selectedReport.report_id, 'pdf')}>导出 PDF</a>
                  {workspace.nextModule && selectedReport.failed_cases === 0 && (
                    <a className="workspace-action-chip" href={workspace.nextModule.url}>
                      推送到 {workspace.nextModule.shortTitle}
                    </a>
                  )}
                </div>
              </>
            )}
          </article>
        </div>
      </div>
    </div>
  )
}
