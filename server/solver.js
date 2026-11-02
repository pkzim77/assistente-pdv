import {Worker} from 'node:worker_threads';
export class Solver {
 constructor({timeoutMs=3000}={}){this.timeoutMs=timeoutMs;this.counter=0;this.pending=null;this.worker=null;this.lastKey=null;this.spawn();}
 spawn(){const worker=new Worker(new URL('./optimizer-worker.js',import.meta.url));this.worker=worker;this.lastKey=null;
  worker.on('message',msg=>{const job=this.pending;if(worker!==this.worker||!job||msg.id!==job.id)return;clearTimeout(job.timer);this.pending=null;msg.error?job.reject(new Error(msg.error)):job.resolve(msg.result);});
  worker.on('error',error=>{if(worker!==this.worker)return;this.fail(error);this.worker=null;worker.terminate();});
  worker.on('exit',()=>{if(worker===this.worker){this.fail(new Error('Cálculo interrompido.'));this.worker=null;}});
 }
 fail(error){if(this.pending){clearTimeout(this.pending.timer);this.pending.reject(error);this.pending=null;}}
 solve(rows,target,candidateLimit,key){if(this.pending)return Promise.reject(new Error('Outro cálculo está em andamento.'));if(!this.worker)this.spawn();
  return new Promise((resolve,reject)=>{const id=++this.counter;const timer=setTimeout(()=>{const old=this.worker;this.worker=null;this.lastKey=null;this.fail(new Error('Cálculo excedeu o tempo de segurança. Tente novamente.'));old?.terminate();},this.timeoutMs);
   this.pending={id,resolve,reject,timer};const data={id,target,candidateLimit};if(!key||key!==this.lastKey)data.rows=rows;this.lastKey=key||null;this.worker.postMessage(data);
  });
 }
 async close(){this.fail(new Error('Cálculo encerrado.'));const worker=this.worker;this.worker=null;await worker?.terminate();}
}
