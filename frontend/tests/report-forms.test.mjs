import test from 'node:test';
import assert from 'node:assert/strict';
import {forms, makeBody, formText, rowValues, totals} from '../src/lib/report-forms.js';

const ship={name:'HAE 01',imo:'0000001'};
const records=[{id:'r1',date:'2026-09-22',fuel:10,factor:3.114,distance:100,speed:9,fuelType:'HFO',sample:true},
  {id:'r2',date:'2026-09-24',fuel:2,factor:3.206,distance:20,speed:8,fuelType:'MGO'}];
test('all five paper forms work blank, survive JSON and carry only requested remarks',()=>{
  for(const kind of Object.keys(forms)){
    const body=makeBody(kind,[],null,{question:'원본 질문',note:'펌프 점검 완료'});
    assert.equal(formText(body),formText(JSON.parse(JSON.stringify(body))));
    assert.doesNotMatch(formText(body),/원본 질문/);
    assert.match(formText(body),/펌프 점검 완료/);
    assert.match(formText(body),/검토자/);
    assert.deepEqual(body.recordIds,[]);
  }
});
test('voyage and fuel use exactly the selected rows and preserve gaps and factors',()=>{
  const voyage=makeBody('voyage',records,ship);
  assert.equal(voyage.values.expected,3);assert.equal(voyage.values.days,2);
  assert.equal(voyage.tables[2][0].used,12);assert.equal(voyage.sample,true);
  const fuel=makeBody('fuel',records,ship);
  assert.deepEqual(fuel.tables[3].map(r=>r.factor),[3.114,3.206]);
  assert.match(formText(fuel),/31\.14/);
  assert.equal(makeBody('arrival',records,ship).values.eosp,undefined);
});
test('unknown operands stay blank and signed adjustments are used once',()=>{
  const keys=['opening','added','landed','correction','closing','derived','logged','diff'];
  const row={opening:100,added:20,landed:5,correction:-1,closing:90,logged:23};
  assert.deepEqual(rowValues(row,keys),{...row,derived:'24',diff:'1'});
  assert.equal(rowValues({...row,added:''},keys).diff,'');
  assert.deepEqual(totals([{used:0},{used:''}],['used']),['']);
});
test('fuel review applies the requested quantity and leaves an unprovided factor blank',()=>{
  const b=makeBody('fuel',[],null,{fuelUsed:'18',fuelGrade:'VLSFO'});
  assert.deepEqual(b.tables[3],[{fuel:'VLSFO',used:'18'}]);
  assert.equal(rowValues(b.tables[3][0],['fuel','used','factor','co2']).co2,'');
});
