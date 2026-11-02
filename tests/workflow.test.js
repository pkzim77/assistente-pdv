import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import os from 'node:os';import path from 'node:path';
import {createHistory} from '../server/history.js';import {transition} from '../server/workflow.js';
test('confirmação exige preparação, revalida e não duplica execução',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'pdv-test-'));
 try{const h=await createHistory(dir);let checks=0;const validate=async()=>{checks++;return {checkedAt:'now'};};
 await h.save({id:'test',createdAt:'2026-10-31',state:'PROPOSED',payment:'PIX',proposal:{items:[]}});
 await assert.rejects(()=>transition(h,'test','confirm',validate));
 await transition(h,'test','prepare',validate);await transition(h,'test','confirm',validate);
 assert.equal(checks,2);assert.equal(h.get('test').result.issued,false);
 await assert.rejects(()=>transition(h,'test','confirm',validate));
 const reopened=await createHistory(dir);assert.equal(reopened.get('test').state,'SIMULATED');
 }finally{await rm(dir,{recursive:true,force:true});}
});
test('alteração de estoque bloqueia confirmação sem avançar estado',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'pdv-test-'));
 try{const h=await createHistory(dir);await h.save({id:'stale',createdAt:'2026-10-31',state:'READY_SIMULATION',proposal:{}});
 await assert.rejects(()=>transition(h,'stale','confirm',async()=>{throw new Error('Estoque mudou');}));assert.equal(h.get('stale').state,'READY_SIMULATION');
 }finally{await rm(dir,{recursive:true,force:true});}
});
