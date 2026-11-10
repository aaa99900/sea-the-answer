import {UiText} from '../components/ui-language';
import Link from 'next/link';
export default function NotFound() {
  return (
    <div className="card pad">
      <h1><UiText>페이지를 찾을 수 없어요</UiText></h1>
      <Link href="/chat"><UiText>통합 질문으로 돌아가기</UiText></Link>
    </div>
  );
}
