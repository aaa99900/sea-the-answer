// Measurements in millimetres from the top of the supplied A4 ship forms.
import {PDFDocument, rgb, pushGraphicsState, popGraphicsState, rectangle, clip, endPath} from 'pdf-lib';
import fontkit from '@pdf-lib/fontkit';
import {sections, forms, rowValues, totals} from './report-forms.js';

const MM=72/25.4, LEFT=13, RIGHT=197, BOTTOM=280, LINE=4.2, SIZE=9;
const ink=rgb(.11,.19,.23), rule=rgb(.53,.60,.62);
const typePage=['daily','voyage','fuel','arrival','departure'];

export async function createReportPdf(draft, documents, assets) {
  const pdf=await PDFDocument.create();
  pdf.registerFontkit(fontkit);
  const font=await pdf.embedFont(assets.font,{subset:false});
  const primaryChars=new Set(font.getCharacterSet());
  const fallback=assets.fallback ? await pdf.embedFont(assets.fallback,{subset:true}) : font;
  const fontFor=ch=>primaryChars.has(ch.codePointAt(0))?font:fallback;
  const b=draft.body || {}, kind=b.formType, structured=Object.hasOwn(forms,kind);
  const sheet=structured ? await pdf.embedPdf(assets.template,[typePage.indexOf(kind)]).then(p=>p[0]) : null;
  const w=sheet?.width || 210*MM, h=sheet?.height || 297*MM;
  let page, y, src, repeatHeader=null;
  pdf.setTitle(draft.title || '선박 운항 보고서');
  const widthsCache=new Map();
  function wrap(value,width) {
    const lines=[];
    for(const paragraph of String(value ?? '').replace(/\r\n?/g,'\n').split('\n')){
      let line='',used=0;
      for(const ch of paragraph.replace(/\t/g,'    ')){
        if(!widthsCache.has(ch)) widthsCache.set(ch,fontFor(ch).widthOfTextAtSize(ch,SIZE)/MM);
        const n=widthsCache.get(ch);
        if(line && used+n>width){lines.push(line);line='';used=0;}
        line+=ch;used+=n;
      }
      lines.push(line);
    }
    return lines;
  }
  function textAt(text,x,baseline,size=SIZE){
    let run='',current=font;
    function flush(){
      if(!run)return;
      page.drawText(run,{x:x*MM,y:h-baseline*MM,size,font:current,color:ink});
      x+=current.widthOfTextAtSize(run,size)/MM;run='';
    }
    for(const ch of String(text ?? '')){
      const next=fontFor(ch);
      if(next!==current){flush();current=next;}
      run+=ch;
    }
    flush();
  }
  function line(x1,y1,x2,y2){
    page.drawLine({start:{x:x1*MM,y:h-y1*MM},end:{x:x2*MM,y:h-y2*MM},thickness:.5,color:rule});
  }
  // Copy an original band at its original scale, preserving the template's typography and rules.
  function band(top,height,at=y,left=0,right=210){
    page.pushOperators(pushGraphicsState(),rectangle(left*MM,h-(at+height)*MM,(right-left)*MM,height*MM),clip(),endPath());
    page.drawPage(sheet,{x:0,y:(top-at)*MM});
    page.pushOperators(popGraphicsState());
  }
  function newPage(){
    page=pdf.addPage([w,h]);
    if(sheet){band(0,40,0);y=41;}
    else {textAt('해답 / SEA THE ANSWER',LEFT,17,11);y=23;}
    if(repeatHeader)repeatHeader();
  }
  function ensure(height){if(y+height>BOTTOM+.01)newPage();}
  function staticBand(height,reserve=0){
    ensure(height+reserve);band(src,height);src+=height;y+=height;
  }
  function fragment(cells,widths,minHeight,background){
    const content=cells.map((v,i)=>wrap(v,widths[i]-4));
    let offset=0;
    const count=Math.max(...content.map(c=>c.length));
    while(offset<count){
      ensure(Math.max(minHeight,LINE+3));
      const fit=Math.max(1,Math.floor((BOTTOM-y-3)/LINE));
      const lines=Math.min(count-offset,fit);
      const height=Math.max(minHeight,lines*LINE+2);
      if(background)background(height);
      let x=LEFT;
      for(const [i,column] of content.entries()){
        line(x,y,x,y+height);
        column.slice(offset,offset+lines).forEach((t,j)=>textAt(t,x+2,y+(minHeight>15?4.5:height/2-(lines-1)*LINE/2+1.1)+j*LINE));
        x+=widths[i];
      }
      line(RIGHT,y,RIGHT,y+height);line(LEFT,y,RIGHT,y);y+=height;line(LEFT,y,RIGHT,y);
      offset+=lines;
    }
  }
  const vals=b.values || {};
  function pair(a,c){
    const top=src;
    fragment(['',vals[a],'',vals[c]],[31,59,34,60],8,()=>band(top,8));
    src+=8;
  }
  function table(keys,widths,rows,blankRows,height,withTotal=true){
    const head=src;
    const header=()=>{band(head,7);y+=7;};
    ensure(7+height);header();repeatHeader=header;
    const data=rows.map(r=>rowValues(r,keys));
    for(let i=0;i<Math.max(blankRows,data.length);i++)
      fragment(keys.map(k=>data[i]?.[k]),widths,height);
    if(withTotal){
      const total=totals(data,keys);total[0]='합계';fragment(total,widths,height);
    }
    repeatHeader=null;
    src+=7+(blankRows+(withTotal?1:0))*height;
  }
  function rows(i){return b.tables?.[i] || [];}
  function keys(i){return sections(kind)[i].keys;}
  function paragraph(value,min=0){
    const lines=wrap(value,RIGHT-LEFT-4);
    for(const t of lines){ensure(LINE);textAt(t,LEFT+2,y+3.2);y+=LINE;}
    y+=min;
  }
  const linkedIds=new Set(Object.values(b.tables || {}).flat().flatMap(r=>[r.ref,r.source]).filter(Boolean));
  for(const id of String(vals.refs || vals.ref || '').split(', '))linkedIds.add(id);
  const refs=[...(draft.sources || []).map(id=>documents.find(d=>d.id===id)?.title || id),
    ...(b.recordIds || []).filter(id=>!linkedIds.has(id))];
  newPage();src=41;
  if(!sheet){
    paragraph(draft.title || '보고서',4);paragraph(draft.text);
  } else {
    pair('ship','imo');pair('company','voyage');pair('number','zone');
    staticBand(10,8);
    if(kind==='daily'){
      pair('start','end');pair('status','location');pair('lat','lon');pair('next','eta');
      staticBand(10,16);
      table(['distance','hours','speed','wind','wave'],[38,34,34,49,29],[vals],1,9,false);
      staticBand(6);pair('observed','ref');staticBand(10,16);
      table(keys(3),[34,32,27,27,30,34],rows(3),2,9);
    } else if(kind==='voyage'){
      ensure(7);band(src,7);
      const mode=String(vals.mode || '');
      const pos=/완료|completed/i.test(mode)?15:/진행|ongoing/i.test(mode)?62:/지정|period/i.test(mode)?114:null;
      if(pos!==null){line(pos,y+3.3,pos+1.2,y+4.8);line(pos+1.2,y+4.8,pos+3.2,y+2);}
      y+=7;src+=7;if(mode && pos===null)paragraph(mode);
      pair('origin','destination');pair('start','end');pair('expected','days');staticBand(10,15);
      const groups=rows(2).filter(r=>Object.values(r).some(v=>v!=='' && v!=null));
      const statusNames=['항해','항내','기타 / 미분류'];
      const matrix=statusNames.map((status,i)=>groups.find(r=>r.status===status || r.status===['Underway','In port','Other / unclassified'][i]) || {status});
      const ordered=[...matrix,...groups.filter(r=>!matrix.includes(r))];
      // Blank template placeholders do not contribute to totals.
      const top=src;
      table(keys(2),[34,38,38,37,37],ordered,3,7.5,false);
      const sum=totals(groups.map(r=>rowValues(r,keys(2))),keys(2));sum[0]='합계';
      fragment(sum,[34,38,38,37,37],7.5);src=top+7+4*7.5;
      staticBand(6);staticBand(10,14);
      table(keys(3),[37,32,25,30,25,35],rows(3),5,7);
    } else if(kind==='fuel'){
      pair('start','end');pair('sounding','refs');pair('proof','method');staticBand(10,14);
      const balance=rows(2).map(r=>rowValues(r,keys(2))), sums=totals(balance,keys(2)),top=src;
      const header=()=>{band(top,7);y+=7;};
      for(let i=0;i<Math.max(1,balance.length);i+=2){
        ensure(14);header();repeatHeader=header;
        keys(2).forEach((k,j)=>{
          const cells=['',balance[i]?.[k],balance[i+1]?.[k],i+2>=balance.length?sums[j]:''];
          fragment(cells,[70,38,38,38],6.5,()=>band(top+7+j*6.5,6.5,y,LEFT,LEFT+70));
        });
        repeatHeader=null;
      }
      src=top+7+9*6.5;staticBand(6);staticBand(10,15);
      table(keys(3),[30,35,34,35,50],rows(3),2,7.6);
      staticBand(6);
    } else {
      const arrival=kind==='arrival';
      pair('port','code');pair(arrival?'priorPort':'next','berth');
      pair(arrival?'eosp':'sosp',arrival?'alongside':'unberth');
      staticBand(6);staticBand(10,8);pair('fore','aft');pair('load','cargo');staticBand(10,8);
      if(arrival){pair('prior','priorTime');pair('distance','hours');}
      else pair('arrivalRef','eta');
      table(keys(4),arrival?[57,59,68]:[29,26,25,25,28,25,26],rows(4),2,9);staticBand(6);
    }
    staticBand(10,8);
    const baseTitle=[vals.ship,forms[kind].name.split('|')[b.language==='en'?1:0]].filter(Boolean).join(' · ');
    const notes=[draft.title && draft.title!==baseTitle?'제목 · '+draft.title:'',
      b.notes,b.sample?'가상 예시 운항 기록 포함':'',refs.length?'작성 근거 · '+refs.join(', '):''].filter(Boolean).join('\n');
    const noteHeight=Math.max(8,260-src);
    fragment([notes],[184],noteHeight,()=>band(src,noteHeight));
    y+=3;src=263;ensure(16);pair('author','prepared');pair('reviewer','reviewed');
  }
  if(!sheet && refs.length){ensure(12);paragraph('작성 근거',1);for(const ref of refs)paragraph(ref);}
  pdf.getPages().forEach((p,i)=>{
    page=p;
    if(sheet){band(282,10,282,0,158);line(158,283,RIGHT,283);}
    textAt((i+1)+' / '+pdf.getPageCount(),181,288,8);
  });
  return pdf.save();
}

export async function reportPdfBytes(draft,documents){
  async function asset(url){
    const response=await fetch(url);
    if(!response.ok)throw Error('PDF 출력 자료를 불러올 수 없습니다.');
    return response.arrayBuffer();
  }
  const [font,fallback,template]=await Promise.all([asset('/fonts/report/NotoSansKR.ttf'),asset('/fonts/report/DejaVuSans.ttf'),
    Object.hasOwn(forms,draft.body?.formType)?asset('/report-forms.pdf'):null]);
  return createReportPdf(draft,documents,{font,fallback,template});
}
