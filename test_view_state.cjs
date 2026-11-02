'use strict';
const assert=require('node:assert/strict'),V=require('./view-state.js');
function element(id,docTop,height=40){return {id,attrs:{},getAttribute(k){return this.attrs[k]??null;},getBoundingClientRect(){return {top:docTop-win.scrollY,height};},focus(opts){this.focusOpts=opts;},setSelectionRange(a,b){this.range=[a,b];}};}
const win={scrollX:0,scrollY:500,innerHeight:800,scrollTo(p){this.scrollX=p.left;this.scrollY=p.top;}};
const oldField=element('field',600);oldField.selectionStart=2;oldField.selectionEnd=5;
const oldDetail={id:'more',open:true},oldPan=element('',900);oldPan.attrs['data-ui-scroll']='diagram-canvas';oldPan.scrollLeft=40;oldPan.scrollTop=20;
const makeHost=(field,detail,pan)=>({ownerDocument:{activeElement:field},contains:e=>e===field,querySelectorAll(sel){if(sel==='details')return [detail];if(sel==='[data-ui-scroll]')return [pan];return [field,pan];}});
const before=V.capture(makeHost(oldField,oldDetail,oldPan),win);
const newField=element('field',800),newDetail={id:'more',open:false},newPan=element('',900);newPan.attrs['data-ui-scroll']='diagram-canvas';newPan.scrollLeft=0;newPan.scrollTop=0;
// Inserting a row above the active field keeps the field at the same viewport position.
V.restore(before,makeHost(newField,newDetail,newPan),win);
assert.equal(newDetail.open,true);assert.equal(win.scrollY,700);assert.equal(newField.getBoundingClientRect().top,100);assert.deepEqual(newField.focusOpts,{preventScroll:true});assert.deepEqual(newField.range,[2,5]);assert.equal(newPan.scrollLeft,40);assert.equal(newPan.scrollTop,20);
// If the anchor is removed, fall back to the recorded pixel scroll rather than page top.
win.scrollY=0;V.restore({...before,anchor:{key:'id:removed',top:100},focus:null},makeHost(newField,newDetail,newPan),win);assert.equal(win.scrollY,500);
const action=element('',600);action.attrs['data-stage']='4';assert.equal(V.identity(action),'data-stage:4');
console.log('view state: scroll anchor, details, focus, selection and canvas scroll passed');
