export function createSnapshotCache(load,{ttlMs=10000,now=()=>Date.now()}={}){
 let cached=null,inflight=null;
 return async function snapshot(){
  if(cached&&now()-cached.startedAt<ttlMs)return cached;
  if(inflight)return inflight;
  const startedAt=now();
  inflight=(async()=>{const rows=await load();cached={rows,startedAt,loadedAt:new Date(startedAt).toISOString()};return cached;})();
  try{return await inflight;}finally{inflight=null;}
 };
}
