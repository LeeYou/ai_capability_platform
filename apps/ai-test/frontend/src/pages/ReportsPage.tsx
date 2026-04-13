import { useEffect, useMemo, useState } from 'react'
import type { TestReportItem, TestReportDetail } from '../types'
import { apiBaseUrl, fetchList, request } from '../api'
import { buildR7Workspace } from '../../../../frontend-common/src/r7Workspace.ts'
import { buildReportActions, clampScore, scoreTone } from '../enterprise'

const workspace = buildR7Workspace(import.meta.env, 'ai-test')

type TemplateSummary = {
  title?: string
  focus?: string
  checklist?: Array<Record<string, unknown>>
  case_breakdown?: Array<Record<string, unknown>>
  delivery_conclusion?: string
}

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

  const templateSummary = (selectedReport?.summary?.template_summary ?? {}) as TemplateSummary
  const evidenceChain = (selectedReport?.summary?.evidence_chain ?? {}) as Record<string, unknown>
  const results = Array.isArray(selectedReport?.summary?.results) ? selectedReport?.summary?.results : []
  const decisionScore = clampScore(
    selectedReport == null
      ? 0
      : ((selectedReport.failed_cases === 0 ? 1 : 0) * 50) +
        ((selectedReport.passed_cases > 0 ? 1 : 0) * 30) +
        ((selectedReport.summary?.evidence_chain ? 1 : 0) * 20),
  )
  const reportActions = useMemo(() => buildReportActions(selectedReport), [selectedReport])

  return (
    <div className="page-container">
      {loading && <p className="info-text">正在加载...</p>}

      <section className="panel">
        <div className="section-header">
          <div>
            <h2>报告中心</h2>
            <p>对齐参考工程中的“报告 / 导出”能力，同时把报告页升级为证据链、双视角摘要与下游推进的决策面板。</p>
          </div>
          <span className="badge">TT20-TT24</span>
        </div>
        <div className="enterprise-hero-grid">
          <article className={`enterprise-score-card tone-${scoreTone(decisionScore)}`}>
            <span>报告推进信心</span>
            <strong>{decisionScore}</strong>
            <p>根据失败用例、通过结果和证据链完整度综合判断。</p>
          </article>
          <article className="enterprise-note-card">
            <strong>视角切换</strong>
            <div className="tab-list">
              <button className={`tab-button${reportTemplateType === 'research' ? ' active' : ''}`} type="button" onClick={() => setReportTemplateType('research')}>研发视角</button>
              <button className={`tab-button${reportTemplateType === 'delivery' ? ' active' : ''}`} type="button" onClick={() => setReportTemplateType('delivery')}>交付视角</button>
            </div>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="workspace-panel-grid">
          <div className="workspace-stack">
            <article className="workspace-note-block">
              <div className="section-header">
                <h3>报告列表</h3>
                <span className="badge badge-muted">{reports.length} 份</span>
              </div>
              <div className="workspace-list">
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
                    <article className="workspace-kpi-card">
                      <span>导出时间</span>
                      <strong className="kpi-date">{selectedReport.exported_at ?? '-'}</strong>
                    </article>
                  </div>

                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>{templateSummary.title ?? '模板摘要'}</strong>
                      <p>{templateSummary.focus ?? '暂无模板摘要。'}</p>
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
                    </article>
                    <article className="enterprise-note-card">
                      <strong>推荐动作</strong>
                      <ul className="enterprise-list">
                        {reportActions.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </article>
                  </div>

                  <div className="enterprise-two-column">
                    <article className="enterprise-note-card">
                      <strong>证据链</strong>
                      <div className="workspace-table-wrap">
                        <table className="workspace-table">
                          <tbody>
                            {Object.entries(evidenceChain).map(([key, value]) => (
                              <tr key={key}>
                                <th>{key}</th>
                                <td><pre className="comparison-pre">{JSON.stringify(value, null, 2)}</pre></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </article>
                    <article className="enterprise-note-card">
                      <strong>模板化结果摘要</strong>
                      {reportTemplateType === 'delivery' ? (
                        <div className="workspace-table-wrap">
                          <table className="workspace-table">
                            <thead>
                              <tr>
                                <th>检查项</th>
                                <th>状态</th>
                                <th>证据</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(templateSummary.checklist ?? []).map((item, index) => (
                                <tr key={index}>
                                  <td>{String(item.item_name ?? '-')}</td>
                                  <td>{String(item.status ?? '-')}</td>
                                  <td>{String(item.evidence ?? '-')}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <div className="workspace-table-wrap">
                          <table className="workspace-table">
                            <thead>
                              <tr>
                                <th>Case</th>
                                <th>Status</th>
                                <th>Provider</th>
                                <th>Duration</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(templateSummary.case_breakdown ?? []).map((item, index) => (
                                <tr key={index}>
                                  <td>{String(item.case_name ?? '-')}</td>
                                  <td>{String(item.status ?? '-')}</td>
                                  <td>{String(item.provider ?? '-')}</td>
                                  <td>{String(item.duration_ms ?? '-')}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </article>
                  </div>

                  <article className="enterprise-note-card">
                    <strong>原始报告摘要</strong>
                    <pre className="workspace-code-block">{JSON.stringify(selectedReport.summary, null, 2)}</pre>
                  </article>

                  {results.length > 0 && (
                    <article className="enterprise-note-card">
                      <strong>结果明细快照</strong>
                      <div className="workspace-table-wrap">
                        <table className="workspace-table">
                          <thead>
                            <tr>
                              <th>Case</th>
                              <th>状态</th>
                              <th>Provider</th>
                              <th>耗时</th>
                              <th>得分</th>
                            </tr>
                          </thead>
                          <tbody>
                            {results.slice(0, 8).map((item, index) => (
                              <tr key={index}>
                                <td>{String((item as Record<string, unknown>).case_name ?? '-')}</td>
                                <td>{String((item as Record<string, unknown>).status ?? '-')}</td>
                                <td>{String((item as Record<string, unknown>).provider ?? '-')}</td>
                                <td>{String((item as Record<string, unknown>).duration_ms ?? '-')}</td>
                                <td>{String((item as Record<string, unknown>).score ?? '-')}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </article>
                  )}
                </>
              )}
            </article>
          </div>
        </div>
      </section>
    </div>
  )
}
