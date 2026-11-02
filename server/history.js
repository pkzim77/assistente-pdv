import {mkdir,readFile,open} from 'node:fs/promises';
import path from 'node:path';
import pg from 'pg';
export async function createHistory(directory) {
 const url=process.env.ROBOT_DATABASE_URL;
 let db;
 if(url){const parsed=new URL(url); if(decodeURIComponent(parsed.pathname.slice(1))!=='pdv_robo') throw new Error('Histórico deve usar o banco separado pdv_robo.'); db=new pg.Pool({connectionString:url,max:1}); await db.query('SELECT event FROM robot_events LIMIT 0');}
 else await mkdir(directory,{recursive:true});
 const file=path.join(directory,'events.jsonl');
 let events=[];
 if(db){events=(await db.query('SELECT event FROM robot_events ORDER BY id')).rows.map(r=>r.event);}
 else {try {const text=await readFile(file,'utf8');events=text.split('\n').filter(Boolean).map(line=>JSON.parse(line));}catch(e){if(e.code!=='ENOENT')throw new Error('Histórico local inválido. Preserve o arquivo e revise antes de continuar.');}}
 const states=new Map(); for(const event of events)states.set(event.run.id,event.run);
 let tail=Promise.resolve();
 return {
  storage:db?'PostgreSQL separado':'Arquivo local',
  list:()=>[...states.values()].sort((a,b)=>b.createdAt.localeCompare(a.createdAt)),
  get:id=>states.get(id),
  async save(run){const event={at:new Date().toISOString(),run:structuredClone(run)};
   const op=tail.then(async()=>{if(db)await db.query('INSERT INTO robot_events(event) VALUES($1::jsonb)',[JSON.stringify(event)]);else{const fd=await open(file,'a');try{await fd.writeFile(JSON.stringify(event)+'\n');await fd.sync();}finally{await fd.close();}}states.set(run.id,event.run);});tail=op.catch(()=>{});await op;return event.run;},
  async close(){await tail;if(db)await db.end();}
 };
}
