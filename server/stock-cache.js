export function createSnapshotCache(load,{ttlMs=10000,now=()=>Date.now()}={}){
 let cached=null,inflight=null,revision=0;
 async function readSnapshot(version){
  const startedAt=now();
  const rows=await load();
  const snapshot={rows,startedAt,loadedAt:new Date(startedAt).toISOString()};
  if(version===revision)cached=snapshot;
  return snapshot;
 }
 return async function snapshot({fresh=false}={}){
  if(fresh){
   const version=++revision;
   const request={version,promise:null};
   request.promise=readSnapshot(version);
   inflight=request;
   try{return await request.promise;}finally{if(inflight===request)inflight=null;}
  }
  if(cached&&now()-cached.startedAt<ttlMs)return cached;
  if(inflight?.version===revision)return inflight.promise;
  const request={version:revision,promise:null};
  request.promise=readSnapshot(request.version);
  inflight=request;
  try{return await request.promise;}finally{if(inflight===request)inflight=null;}
 };
}
