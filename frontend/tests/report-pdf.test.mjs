import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {PDFDocument} from 'pdf-lib';
import {makeBody,forms} from '../src/lib/report-forms.js';
import {createReportPdf} from '../src/lib/report-pdf.js';

const assets={font:readFileSync(new URL('../public/fonts/report/NotoSansKR.ttf',import.meta.url)),
  fallback:readFileSync(new URL('../public/fonts/report/DejaVuSans.ttf',import.meta.url)),
  template:readFileSync(new URL('../public/report-forms.pdf',import.meta.url))};
for(const k of [...Object.keys(forms),'free','long']){
  test('PDF output: '+k,async()=>{
    const kind=k==='long'?'voyage':k;
    const records=Array.from({length:k==='long'?58:1},(_,i)=>({id:'REC-'+String(i).padStart(3,'0'),date:'2026-11-22',fuel:18,distance:120,factor:3.114,fuelType:'VLSFO'}));
    const body=k==='free'?{}:makeBody(kind,records,{name:'해답호',imo:'1234567'},{question:'검토 완료',values:{port:'부산항',alongside:'08:30',fore:'7.5'}});
    const bytes=await createReportPdf({title:'테스트 보고서',body,sources:[],text:'자유 작성 본문 CO₂'},[],assets);
    const pdf=await PDFDocument.load(bytes);
    assert.ok(pdf.getPageCount()>=(k==='long'?2:1));
    assert.equal(Math.round(pdf.getPages()[0].getWidth()),595);
    if(process.env.REPORT_PDF_QA_DIR)writeFileSync(process.env.REPORT_PDF_QA_DIR+'/'+k+'.pdf',bytes);
  });
}
