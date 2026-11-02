import {parentPort} from 'node:worker_threads';
import {optimizeFast} from './fast-optimizer.js';
let catalog=null;
parentPort.on('message',job=>{
 try{if(job.rows)catalog=job.rows;if(!catalog)throw new Error('Catálogo não carregado.');parentPort.postMessage({id:job.id,result:optimizeFast(catalog,job.target,{candidateLimit:job.candidateLimit,budgetMs:700})});}
 catch(error){parentPort.postMessage({id:job.id,error:error.message});}
});
parentPort.postMessage({ready:true});
