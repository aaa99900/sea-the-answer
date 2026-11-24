import React from 'react';
export default function RecordSelection({result,en}) {
  const {rows,columns,format}=result;
  if(!rows.length) return null;
  if(format==='list') return <ul>{rows.map(row=><li key={row.id}>{row.cells.map((v,i)=>columns[i]+' '+v).join(' · ')}</li>)}</ul>;
  return <div className="report-table-scroll"><table><caption>{en?'Operation records':'운항 기록'}</caption>
    <thead><tr>{columns.map(c=><th scope="col" key={c}>{c}</th>)}</tr></thead><tbody>{rows.map(r=><tr key={r.id}>{r.cells.map((v,i)=><td key={i}>{v}</td>)}</tr>)}</tbody></table></div>;
}
