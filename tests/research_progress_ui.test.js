'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'../tools/desk/app.js'),'utf8');
const functions = source.slice(source.indexOf('function renderProgress()'),source.indexOf('function notice('));
function node(tag,text) {
  return {tag,text,children:[],value:'',disabled:false,textContent:'',
    append(...children){this.children.push(...children);},
    replaceChildren(...children){this.children=children;this.options=children;}};
}
const nodes = Object.fromEntries(['progress-records','progress-topic','progress-count'].map(id=>['#'+id,node('div')]));
const row={id:'demo',title:'Previous result',topic:'Demo',updated_on:'2026-10-19',evidence_label:'Illustrative model',
  available:true,result:'Previous numerical claim',boundary:'Synthetic',next_step:'Qualify data',artifacts:[{label:'Prior report',url:'/old-report'}]};
const context={el:node,badge:text=>node('span',text),safeLink:(text,url)=>({tag:'a',text,url}),
  Option:function(text,value){this.text=text;this.value=value;},$:selector=>nodes[selector],progressRecords:null,progressRequestGeneration:0,
  api:async()=>({updates:[row],count:1})};
vm.createContext(context);
vm.runInContext(functions,context);
(async()=>{
  await context.refreshProgress();
  assert.equal(context.progressRecords.length,1);
  assert.ok(JSON.stringify(nodes['#progress-records']).includes('Previous numerical claim'));
  let reject;
  context.api=()=>new Promise((resolve,rejectApi)=>{reject=rejectApi;});
  const pending=context.refreshProgress();
  assert.equal(context.progressRecords,null);
  assert.ok(!JSON.stringify(nodes['#progress-records']).includes('Previous numerical claim'));
  reject(new Error('Unavailable'));
  await assert.rejects(pending,/Unavailable/);
  assert.equal(context.progressRecords,null);
  assert.ok(!JSON.stringify(nodes['#progress-records']).includes('/old-report'));
  assert.equal(nodes['#progress-topic'].disabled,true);
  context.api=async()=>({updates:[row],count:1});
  await context.refreshProgress();
  assert.equal(nodes['#progress-topic'].disabled,false);
  assert.equal(context.progressRecords.length,1);
  // Newer unavailable data must beat an older successful response.
  const requests=[];
  context.api=()=>new Promise((resolve,reject)=>requests.push({resolve,reject}));
  const older=context.refreshProgress(),newer=context.refreshProgress();
  requests[1].resolve({updates:[{...row,available:false,title:'Progress entry needs review',result:undefined,artifacts:undefined,message:'Files changed'}],count:1});
  await newer;
  requests[0].resolve({updates:[row],count:1});
  await older;
  assert.ok(!JSON.stringify(nodes['#progress-records']).includes('Previous numerical claim'));
  assert.ok(JSON.stringify(nodes['#progress-records']).includes('Progress entry needs review'));
  // A superseded error must not clear a newer successful result.
  requests.length=0;
  const staleError=context.refreshProgress(),fresh=context.refreshProgress();
  requests[1].resolve({updates:[row],count:1});
  await fresh;
  requests[0].reject(new Error('Superseded error'));
  await staleError;
  assert.equal(context.progressRecords.length,1);
  assert.ok(JSON.stringify(nodes['#progress-records']).includes('Previous numerical claim'));
  console.log('Progress refresh: visible results withheld during recheck/failure, restored after success');
})().catch(error=>{console.error(error);process.exitCode=1;});
