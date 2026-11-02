'use strict';
const assert=require('node:assert/strict');
const W=require('./workbench.js');
class Element{
 constructor(dataset={}){this.dataset=dataset;this.attrs={};this.listeners={};this.children={};this.textContent='';}
 setAttribute(k,v){this.attrs[k]=String(v);}
 querySelector(k){return this.children[k]||null;}
 addEventListener(k,fn){(this.listeners[k]??=new Set()).add(fn);}
 removeEventListener(k,fn){this.listeners[k]?.delete(fn);}
 setPointerCapture(id){this.capture=id;}
 hasPointerCapture(id){return this.capture===id;}
 releasePointerCapture(){this.capture=null;}
 fire(k,event){for(const fn of [...(this.listeners[k]||[])])fn(event);}
}
const card={id:'int-001',pool:'integration'},draft={answer:''};const t=W.ensure(draft,card);
t.diagram.nodes=[{id:'a',label:'Каталог',type:'service',x:80,y:80},{id:'b',label:'Касса',type:'external',x:400,y:80}];t.diagram.edges=[{id:'e',from:'a',to:'b',label:'GET прайса'}];
const a=new Element({node:'a'}),b=new Element({node:'b'});for(const n of [a,b])n.children.text=new Element();
const edge=new Element({canvasEdge:'e'});for(const key of ['line','rect','text'])edge.children[key]=new Element();
const svg=new Element();svg.getBoundingClientRect=()=>({width:800,height:460});svg.querySelectorAll=k=>k==='[data-node]'?[a,b]:k==='[data-canvas-edge]'?[edge]:[];
const root={querySelector:k=>k==='.tw-diagram-svg'?svg:null,querySelectorAll:k=>k==='[data-node]'?[a,b]:[]};
global.document={querySelector:k=>k==='.tw-workbench'?root:null};let saves=0,renders=0;
W.bind(card,draft,{save:()=>saves++,render:()=>renders++,toast:()=>{},download:()=>{}});
const event=(x=100,y=100)=>({button:0,pointerId:1,clientX:x,clientY:y,preventDefault(){this.prevented=true;}});
// Clicking without moving must not recreate the page or write unchanged state.
a.onpointerdown(event());a.fire('pointerup',event());assert.equal(renders,0);assert.equal(saves,0);
// Moving preserves the DOM and updates connected arrows before pointerup.
a.onpointerdown(event());a.fire('pointermove',event(140,120));assert.equal(t.diagram.nodes[0].x,120);assert.equal(t.diagram.nodes[0].y,100);assert.equal(a.attrs.transform,'translate(120 100)');assert.ok(Number(edge.children.line.attrs.x1)>120);assert.equal(saves,0);a.fire('pointerup',event(140,120));assert.equal(saves,1);assert.equal(renders,0);assert.equal(a.capture,null);assert.equal(a.listeners.pointermove.size,0);
// Cancellation cleans listeners and retains/saves final model position.
a.onpointerdown(event());a.fire('pointermove',event(160,120));a.fire('pointercancel',event());assert.equal(saves,2);assert.equal(a.listeners.pointerup.size,0);assert.equal(a.listeners.pointercancel.size,0);
const x=t.diagram.nodes[0].x;a.onkeydown({key:'ArrowRight',shiftKey:true,preventDefault(){}});assert.equal(t.diagram.nodes[0].x,x+10);assert.equal(renders,0);
const blank={target:svg,button:0,preventDefault(){this.prevented=true;}};svg.onpointerdown(blank);assert.equal(blank.prevented,true);assert.equal(renders,0);
// An unrelated pointer cannot terminate this drag.
a.onpointerdown(event());a.fire('pointerup',{pointerId:2});assert.ok(a.listeners.pointermove.size);a.fire('pointerup',event());
console.log('diagram interaction regression checks passed');
// Moving an edge endpoint updates its visible geometry without a full redraw.
const endpoint=new Element({edgeFrom:'e'});endpoint.value='b';
root.querySelectorAll=k=>k==='[data-node]'?[a,b]:k==='[data-edge-from]'?[endpoint]:[];
W.bind(card,draft,{save:()=>saves++,render:()=>renders++,toast:()=>{},download:()=>{}});
endpoint.onchange();assert.equal(t.diagram.edges[0].from,'b');assert.equal(renders,0);
// Zoom remains a view concern and never changes exported model coordinates.
const beforeNodes=JSON.stringify(t.diagram.nodes),v={x:0,y:0,zoom:1};W.zoomView(v,.5);assert.equal(v.zoom,.5);assert.equal(v.x,-400);assert.equal(v.y,-230);assert.match(W.viewBox(v),/1600 920$/);assert.equal(JSON.stringify(t.diagram.nodes),beforeNodes);
W.zoomView(v,100);assert.equal(v.zoom,3);W.zoomView(v,.001);assert.equal(v.zoom,.1);
const fitted=W.fitView({nodes:[{x:2000,y:1000}]});assert.ok(800/fitted.zoom>=2168);assert.ok(460/fitted.zoom>=1096);
const markup=W.html(card,draft);assert.ok(markup.indexOf('data-tw="add-node"')>markup.indexOf('class="tw-node-list"'));assert.ok(markup.indexOf('data-tw="add-edge"')>markup.indexOf('class="tw-edge-list"'));assert.ok(markup.indexOf('data-tw="export-svg"')>markup.indexOf('data-tw="add-edge"'));assert.match(markup,/Масштаб схемы/);
console.log('diagram endpoint, zoom geometry and footer actions passed');
