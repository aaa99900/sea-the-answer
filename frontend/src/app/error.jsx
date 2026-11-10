'use client';

import {UiText} from '../components/ui-language';
export default function ErrorPage({ reset }) {
  return (
    <div className="card pad">
      <h2><UiText>화면을 불러오지 못했어요.</UiText></h2>
      <p><UiText>입력한 내용은 브라우저 임시 보관이나 저장된 보고서에서 확인할 수 있습니다.</UiText></p>
      <button className="btn mt" onClick={reset}>
        <UiText>다시 시도</UiText>
      </button>
    </div>
  );
}
