import React from 'react';
import {UiText} from './ui-language';
import { icons } from '../lib/icons';
export const esc = (value) => String(value ?? ''); // React escapes text at render time.
export const I = (name) => (
  <svg className="icon" aria-hidden="true" viewBox="0 0 24 24">
    <path d={icons[name] || icons.file} />
  </svg>
);
export function Button({ children, action, className = '', icon = '', ...props }) {
  return (
    <button type="button" className={`btn ${className}`} data-action={action} {...props}>
      {icon && I(icon)}
      <UiText>{children}</UiText>
    </button>
  );
}
export const btn = (label, action, cls = '', icon = '', extra = {}) => (
  <Button action={action} className={cls} icon={icon} {...extra}>
    <UiText>{label}</UiText>
  </Button>
);
export const badge = (text, cls = '') => <span className={`badge ${cls}`}><UiText>{text}</UiText></span>;
export const n = (v, d = 1) =>
  Number(v).toLocaleString('ko-KR', {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
export const dateText = (date, language = 'ko') =>
  date
    ? new Date(date).toLocaleString(language === 'en' ? 'en-GB' : 'ko-KR', {
        timeZone: 'Asia/Seoul',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '—';
export const options = (list) =>
  list.map((item) => {
    const [v, label] = Array.isArray(item) ? item : [item, item];
    return (
      <option key={v} value={v}>
        <UiText>{label}</UiText>
      </option>
    );
  });
export function PageHeader({ title, description, children }) {
  return (
    <div className="pagehead">
      <div>
        <h1><UiText>{title}</UiText></h1>
        <p><UiText>{description}</UiText></p>
      </div>
      <div className="actions wrap"><UiText>{children}</UiText></div>
    </div>
  );
}
export const head = (title, sub, actions = null) => (
  <PageHeader title={title} description={sub}>
    {actions}
  </PageHeader>
);
export function Notice({ children, kind = '' }) {
  return (
    <div className={`notice ${kind}`}>
      {I(kind === 'warning' ? 'alert' : 'info')}
      <span><UiText>{children}</UiText></span>
    </div>
  );
}
export const notice = (text, kind = '') => <Notice kind={kind}><UiText>{text}</UiText></Notice>;
export const empty = (title, sub, action = null) => (
  <div className="empty">
    {I('file')}
    <h3><UiText>{title}</UiText></h3>
    <p><UiText>{sub}</UiText></p>
    <div className="mt">{action}</div>
  </div>
);
export const stat = (label, value, unit, sub, icon = 'chart') => (
  <div className="card stat">
    <div className="stat-top">
      <span><UiText>{label}</UiText></span>
      {I(icon)}
    </div>
    <div className="stat-value mono">
      {value} <small><UiText>{unit}</UiText></small>
    </div>
    <div className="small muted"><UiText>{sub}</UiText></div>
  </div>
);
export function safeUrl(value) {
  try {
    const u = new URL(value);
    return u.protocol === 'https:' && !u.username && !u.password ? u.href : '';
  } catch {
    return '';
  }
}
export const docKind = (d) =>
  d.kind === 'sample'
    ? '가상 샘플'
    : d.kind === 'official-summary'
      ? '공식 안내 요약'
      : '선내 문서';
export function download(name, content, type = 'text/plain;charset=utf-8') {
  const url = URL.createObjectURL(
      new Blob([content], {
        type,
      }),
    ),
    a = document.createElement('a');
  a.href = url;
  a.download = name.replace(/[\\/:*?"<>|]/g, '_');
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
