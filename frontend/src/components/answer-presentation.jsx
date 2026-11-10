import {UiText,UiControl} from './ui-language';
import React from 'react';
import { chartCoordinates, validatedPresentation } from '../lib/answer-presentation';

const number = value => value.toLocaleString('ko-KR', { maximumFractionDigits: 6 });

function Citation({ citation, evidence, sourceIds, en }) {
  const source = evidence.find(item => item.id === citation.chunkId);
  return <UiControl as="button" type="button" className="citation" data-action="source"
    data-id={source.document_id} data-section={source.id} title={citation.quote}
    aria-label={`${source.title || (en ? 'Source' : '근거')} ${en ? 'original text' : '원문 보기'}`}>
    [{sourceIds.indexOf(source.document_id) + 1}{source.page ? ` · p.${source.page}` : ''}]
  </UiControl>;
}

function AnswerTable({ presentation, evidence, en }) {
  const sourceIds = [...new Set(evidence.map(item => item.document_id))];
  return <div className="tablewrap">
    <table className="presentation-table">
      <caption>{presentation.title}</caption>
      <thead><tr>
        {presentation.columns.map((column, index) => <th scope="col" key={index}>{column}</th>)}
        {presentation.source === 'documents' && <th scope="col"><UiText>{en ? 'Evidence' : '근거'}</UiText></th>}
      </tr></thead>
      <tbody>{presentation.rows.map((row, index) => <tr key={index}>
        {row.cells.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}
        {presentation.source === 'documents' && <td className="presentation-citations">
          {row.citations.map((citation, citationIndex) => <Citation key={citationIndex}
            citation={citation} evidence={evidence} sourceIds={sourceIds} en={en} />)}
        </td>}
      </tr>)}</tbody>
    </table>
  </div>;
}

function AnswerChart({ presentation, en }) {
  const plot = chartCoordinates(presentation.points, presentation.chartType);
  const yLabel = `${presentation.yLabel}${presentation.unit ? ` (${presentation.unit})` : ''}`;
  const labelStep = Math.max(1, Math.ceil(plot.points.length / 7));
  const dataTitle = `${presentation.title}${en ? ' data' : ' 데이터'}`;
  return <figure className="presentation-figure">
    <figcaption><h3>{presentation.title}</h3></figcaption>
    <svg className="presentation-chart" viewBox={`0 0 ${plot.width} ${plot.height}`}
      role="img" aria-label={`${presentation.title}. ${presentation.xLabel}. ${yLabel}`}>
      <title>{presentation.title}</title>
      <desc><UiText>{en ? 'Values from saved operation records. Exact values are available in the data table below.'
        : '저장된 운항 기록으로 만든 차트입니다. 정확한 값은 아래 데이터 표에서 확인할 수 있습니다.'}</UiText></desc>
      {plot.ticks.map((tick, index) => <g key={index}>
        <line x1={plot.left} x2={plot.left + plot.plotWidth} y1={tick.y} y2={tick.y}
          className="presentation-grid" />
        <text x={plot.left - 10} y={tick.y + 4} textAnchor="end">{number(tick.value)}</text>
      </g>)}
      <line x1={plot.left} x2={plot.left + plot.plotWidth} y1={plot.baseline} y2={plot.baseline}
        className="presentation-axis" />
      <line x1={plot.left} x2={plot.left} y1={plot.top} y2={plot.baseline} className="presentation-axis" />
      {presentation.chartType === 'line' && <polyline className="presentation-line"
        points={plot.points.map(point => `${point.x},${point.y}`).join(' ')} />}
      {plot.points.map((point, index) => <g key={index}>
        {presentation.chartType === 'bar'
          ? <rect x={point.x - plot.barWidth / 2} y={point.y} width={plot.barWidth}
              height={plot.baseline - point.y} className="presentation-mark">
              <title>{`${point.label}: ${number(point.value)} ${presentation.unit}`}</title>
            </rect>
          : <circle cx={point.x} cy={point.y} r={3.5} className="presentation-mark">
              <title>{`${point.label}: ${number(point.value)} ${presentation.unit}`}</title>
            </circle>}
        {index % labelStep === 0 && <text x={point.x} y={plot.baseline + 22} textAnchor="middle">
          <title>{point.label}</title>{point.label.length > 14 ? `${point.label.slice(0, 13)}…` : point.label}
        </text>}
      </g>)}
      <text x={plot.left + plot.plotWidth / 2} y={plot.height - 12} textAnchor="middle"
        className="presentation-axis-label">{presentation.xLabel}</text>
      <text transform={`translate(19 ${plot.top + plot.plotHeight / 2}) rotate(-90)`}
        textAnchor="middle" className="presentation-axis-label">{yLabel}</text>
    </svg>
    <details className="presentation-data">
      <summary><UiText>{en ? 'View chart data table' : '차트 데이터 표 보기'}</UiText></summary>
      <div className="tablewrap"><table className="presentation-table">
        <caption>{dataTitle}</caption>
        <thead><tr><th scope="col">{presentation.xLabel}</th><th scope="col">{yLabel}</th></tr></thead>
        <tbody>{presentation.points.map((point, index) => <tr key={index}>
          <th scope="row">{point.label}</th><td>{number(point.value)}</td>
        </tr>)}</tbody>
      </table></div>
    </details>
  </figure>;
}

export function AnswerPresentation({ answer, presentation = validatedPresentation(answer.presentation, answer.evidence) }) {
  const en = answer.language === 'en';
  const invalid = answer.presentation != null && !presentation;
  const message = typeof answer.presentationNotice === 'string' && answer.presentationNotice.trim()
    ? answer.presentationNotice : invalid
      ? en ? 'The requested table or chart is invalid. Showing the original answer text.'
        : '요청한 표·그래프 데이터를 확인할 수 없어 본문 답변을 표시합니다.'
      : '';
  if (!presentation && !message) return null;
  return <UiControl as="section" className="answer-presentation" aria-label={en ? 'Requested presentation' : '요청한 표·그래프'}>
    {message && <p className="notice">{message}</p>}
    {presentation?.type === 'table' && <AnswerTable presentation={presentation} evidence={answer.evidence || []} en={en} />}
    {presentation?.type === 'chart' && <AnswerChart presentation={presentation} en={en} />}
    {presentation && <p className="small muted presentation-source">
      <UiText>{presentation.source === 'operations' ? en ? 'Source: saved operation records' : '자료: 저장된 운항 기록'
        : en ? 'Use each row’s evidence link to review the original text.' : '각 행의 근거를 눌러 원문을 확인할 수 있습니다.'}</UiText>
      {presentation.truncated && ` · ${en ? 'Showing' : '표시'} ${presentation.type === 'table'
        ? `${presentation.rows.length} / ${presentation.totalRows}`
        : `${presentation.points.length} / ${presentation.totalPoints}`}${en ? '' : '개'}`}
    </p>}
  </UiControl>;
}
