import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {createModel} from '../src/lib/model.js';
const require = createRequire(import.meta.url);
const React = require('react');
const babel = require('next/dist/compiled/babel/bundle');
// Exercise the production controller with isolated HTTP/render boundaries.
// Use Next's installed JSX compiler without introducing a second compiler dependency.
function load(file, imports, browser) {
  const source = readFileSync(new URL(file, import.meta.url), 'utf8');
  const {code} = babel.core().transformSync(source, {babelrc:false, configFile:false,
    presets:[[babel.presetReact().default, {runtime:'classic'}]], plugins:[babel.pluginTransformModulesCommonjs().default]});
  const module = {exports:{}};
  new Function('require','module','exports','window','document','requestAnimationFrame','cancelAnimationFrame', code)(
    id=>imports[id] || {}, module, module.exports, browser.window, browser.document, browser.raf, browser.cancel);
  return module.exports;
}
function setup() {
  const pending=[], requests=[], routes=[], scrolls=[];
  const browser={window:{scrollTo:(...args)=>scrolls.push(args)},document:{querySelector:()=>null}};
  const api={ask:body=>{requests.push(body);return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};
  const {createWorkspace}=load('../src/workspace/controller.jsx', {
    react:React, '../lib/model':{createModel}, '../lib/api':{createApiClient:()=>api},
    '../views':{createViews:()=>({})},
  },browser);
  const workspace=createWorkspace();
  workspace.attach({push:(...args)=>routes.push(args)});
  workspace.state.ready=true;workspace.state.user={id:'u1',role:'admin'};
  const click=dataset=>workspace.events.onClick({target:{closest:()=>({dataset})}});
  return {workspace, pending, requests, routes, scrolls, browser, click};
}
test('sending and completing a follow-up preserves the conversation without scrolling to the top',async()=>{
  const t=setup(),w=t.workspace;
  const first=w.ask('first');
  assert.equal(t.scrolls.length,0);
  assert.deepEqual(t.routes.at(-1),['/chat',{scroll:false}]);
  assert.equal(w.state.chatScrollRequest.phase,'pending');
  t.pending.shift().resolve({id:'q1'});await first;
  const second=w.ask('second');
  assert.equal(w.state.turns.length,1);
  assert.equal(t.requests[1].conversationId,'q1');
  t.pending.shift().resolve({id:'q2',conversationId:'q1'});await second;
  assert.deepEqual(w.state.turns.map(t=>t.question),['first','second']);
  assert.equal(t.scrolls.length,0);
  assert.equal(w.state.chatScrollRequest.phase,'complete');
  w.dispose();
});
test('chat tab starts a new conversation and discards a late response and its scroll request',async()=>{
  const t=setup(),w=t.workspace;
  w.state.turns=[{id:'old'}];w.state.conversationId='old';
  w.state.history=[{id:'old'}];w.state.question='draft';
  const request=w.ask('pending');t.click({nav:'chat'});
  assert.equal(w.state.question,'');assert.equal(w.state.conversationId,'');
  assert.deepEqual(w.state.turns,[]);assert.equal(w.state.chatScrollRequest,null);
  assert.deepEqual(w.state.history,[{id:'old'}]);assert.deepEqual(t.scrolls.at(-1),[0,0]);
  t.pending.shift().resolve({id:'late',conversationId:'old'});await request;
  assert.deepEqual(w.state.turns,[]);assert.equal(w.state.chatScrollRequest,null);
  w.dispose();
});
test('failed question keeps its text and requests the bottom error view',async()=>{
  const t=setup(),w=t.workspace;const request=w.ask('retry me');
  t.pending.shift().reject(new Error('temporary failure'));await request;
  assert.equal(w.state.pendingQuestion,'retry me');assert.equal(w.state.askError,'temporary failure');
  assert.equal(w.state.chatScrollRequest.phase,'complete');assert.equal(t.scrolls.length,0);
  w.dispose();
});
test('chat DOM commit scrolls to the bottom; cancelled requests and other pages cannot steal scroll',()=>{
  const t=setup(),w=t.workspace;w.views.chatPage=()=>null;w.views.reportPage=()=>null;
  const frames=new Map();let nextId=0,cleanup;
  const browser={...t.browser,document:{documentElement:{scrollHeight:4200}},
    raf:fn=>{frames.set(++nextId,fn);return nextId;},cancel:id=>frames.delete(id)};
  const react={...React,useContext:()=>({workspace:w}),useLayoutEffect:fn=>{cleanup=fn();}};
  const {WorkspacePage}=load('../src/workspace/provider.jsx', {react},browser);
  w.state.askSequence=3;w.state.chatScrollRequest={sequence:3,phase:'pending'};
  WorkspacePage({name:'chatPage'});frames.get(nextId)();
  assert.deepEqual(t.scrolls.at(-1),[{top:4200,behavior:'instant'}]);cleanup();
  assert.equal(frames.size,0);
  WorkspacePage({name:'chatPage'});w.state.askSequence++;frames.get(nextId)();cleanup();
  assert.equal(t.scrolls.length,1);
  w.state.chatScrollRequest={sequence:w.state.askSequence,phase:'complete'};
  WorkspacePage({name:'chatPage'});w.state.page='reports';frames.get(nextId)();cleanup();
  assert.equal(t.scrolls.length,1);
  WorkspacePage({name:'reportPage'});assert.equal(frames.size,0);
  w.dispose();
});
