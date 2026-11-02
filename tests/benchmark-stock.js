import {performance} from 'node:perf_hooks';import {writeFile} from 'node:fs/promises';
import {stockSnapshot,pool} from '../server/db.js';import {optimizeFast} from '../server/fast-optimizer.js';
const started=performance.now();
try{const snapshot=await stockSnapshot();const loadMs=performance.now()-started;const cases=[];
for(const candidateLimit of [100,200])for(const target of ['50.01','100','137.19','500','1000','5000']){const r=optimizeFast(snapshot.rows,target,{candidateLimit});cases.push({candidateLimit,target,total:r.total,delta:r.difference,ms:r.elapsedMs,timedOut:r.timedOut,exact:r.exact});}
const synthetic=Array.from({length:100000},(_,i)=>({id:i+1,price:String(5+i%200*5),stock:String(1+i%50)}));
const stress=optimizeFast(synthetic,'137.01',{candidateLimit:200});
const report={at:new Date().toISOString(),catalogCount:snapshot.rows.length,loadMs:Math.round(loadMs),cases,synthetic:{catalogCount:synthetic.length,ms:stress.elapsedMs,timedOut:stress.timedOut,delta:stress.difference,candidates:stress.candidateCount}};
await writeFile('docs/benchmark-stock.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}finally{await pool.end();}
