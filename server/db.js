import {createSnapshotCache} from './stock-cache.js';
import pg from 'pg';
const arpaSchema=(process.env.ARPA_SCHEMA||'public').trim();
if(!/^[A-Za-z_][A-Za-z0-9_]*$/.test(arpaSchema))throw new Error('ARPA_SCHEMA deve conter somente letras, números e underscore, iniciando por letra/underscore.');
const table=name=>'"'+arpaSchema+'"."'+name+'"';
function positiveMs(name,defaultValue){const value=Number(process.env[name]||defaultValue);if(!Number.isInteger(value)||value<100||value>30000)throw new Error(name+' deve ser um inteiro entre 100 e 30000 milissegundos.');return value;}
const connectionTimeoutMs=positiveMs('ARPA_CONNECTION_TIMEOUT_MS',2000);
const queryTimeoutMs=positiveMs('ARPA_QUERY_TIMEOUT_MS',5000);
export const pool = new pg.Pool({host:process.env.ARPA_HOST||'127.0.0.1',port:Number(process.env.ARPA_PORT||5432),database:process.env.ARPA_DATABASE||'control',user:process.env.ARPA_USER||'postgres',password:process.env.ARPA_PASSWORD||undefined,max:3,connectionTimeoutMillis:connectionTimeoutMs,idleTimeoutMillis:15000,keepAlive:true,keepAliveInitialDelayMillis:10000,options:'-c default_transaction_read_only=on -c statement_timeout='+queryTimeoutMs,application_name:'pdv-robo-leitura'});

const RETRYABLE_CODES=new Set(['ECONNRESET','ECONNREFUSED','ECONNABORTED','ETIMEDOUT','EHOSTUNREACH','ENETUNREACH','57P01','57P02','57P03','08000','08001','08003','08004','08006','08007','08P01']);
export function isConnectionError(error){
 return RETRYABLE_CODES.has(error?.code)||String(error?.message||'').toLowerCase().match(/connection terminated|connection timeout|connection refused|connection reset|server closed the connection|socket hang up|could not connect|terminating connection/)!==null;
}

pool.on('error',error=>console.error('Conexão PostgreSQL ociosa descartada:',error.code||error.message));

export async function read(sql,params=[]) {
  let lastError;
  for(let attempt=1;attempt<=3;attempt++){
   let client;
   try{
    client=await pool.connect();
    await client.query('BEGIN READ ONLY');
    const result=await client.query(sql,params);
    await client.query('COMMIT');
    client.release();
    return result.rows;
   }catch(error){
    lastError=error;
    const retryable=isConnectionError(error);
    if(client){
     if(!retryable)await client.query('ROLLBACK').catch(()=>{});
     client.release(retryable?error:undefined);
    }
    if(!retryable||attempt===3)throw error;
    console.warn(`Falha transitória na conexão com Arpa; reconexão ${attempt}/2.`,error.code||error.message);
    await new Promise(resolve=>setTimeout(resolve,attempt*350));
   }
  }
  throw lastError;
}
export async function connectionStatus(){
 const rows=await read('SELECT current_database() AS database,current_setting(\'transaction_read_only\') AS readonly');
 return {connected:true,...rows[0],checkedAt:new Date().toISOString()};
}
export async function notes(search='') {
 return read(`SELECT codigo AS id,nota AS number,to_char(data,'DD/MM/YYYY') AS date,total_nota::text AS total,status FROM ${table('cabecalho_nota_compra')} WHERE ($1='' OR nota::text=$1 OR chave_nfe=$1) ORDER BY data DESC,codigo DESC LIMIT 100`,[search]);
}
const allowedUnits=new Set(['PC','UN','CJ','PAR','PCT','KIT']);
export async function catalog(noteId) {
 const rows=await read(`SELECT p.codigo AS id,p.codigodefabrica AS reference,p.descricao AS description,p.unidade AS unit,p.quantidade::text AS stock,p.precovenda::text AS price,p.ativo::text AS active,p.baixa AS stock_type,p.grade,p.utiliza_lote AS uses_lot,p.usa_serial_compra AS uses_serial FROM ${table('produtos')} p WHERE EXISTS (SELECT 1 FROM ${table('itens_nota_compra')} i WHERE i.cd_nota=$1 AND i.produto=p.codigo) ORDER BY p.codigo`,[noteId]);
 return rows.map(row=>({...row,eligible:row.active==='0' && row.stock_type==='P' && Number(row.stock)>=1 && Number(row.price)>=0.01 && allowedUnits.has(row.unit?.trim()) && !row.grade && !row.uses_lot && !row.uses_serial}));
}
export async function validateProposal(proposal) {
 const ids=proposal.items.map(item=>item.id);
 const rows=await productsByIds(ids); const byId=new Map(rows.map(row=>[row.id,row]));
 for(const item of proposal.items){ const current=byId.get(item.id); if(!current?.eligible || Number(current.stock)<item.quantity || current.price!==item.price) throw new Error('Estoque ou preço mudou no produto '+item.id+'. Gere outra proposta.'); }
 return {checkedAt:new Date().toISOString()};
}

const productFields="p.codigo AS id,p.codigodefabrica AS reference,p.descricao AS description,p.unidade AS unit,p.quantidade::text AS stock,p.precovenda::text AS price,p.ativo::text AS active,p.baixa AS stock_type,p.grade,p.utiliza_lote AS uses_lot,p.usa_serial_compra AS uses_serial";
function eligible(row){return {...row,eligible:row.active==='0'&&row.stock_type==='P'&&Number(row.stock)>=1&&Number(row.price)>=0.01&&allowedUnits.has(row.unit?.trim())&&!row.grade&&!row.uses_lot&&!row.uses_serial};}
export async function productsByIds(ids){return (await read('SELECT '+productFields+' FROM '+table('produtos')+' p WHERE p.codigo=ANY($1::int[]) ORDER BY p.codigo',[ids])).map(eligible);}
export const stockSnapshot=createSnapshotCache(async()=>{
 const rows=await read('SELECT '+productFields+' FROM '+table('produtos')+" p WHERE p.ativo=0 AND p.baixa='P' AND p.quantidade>=1 AND p.precovenda>=0.01 AND trim(p.unidade)=ANY($1::text[]) AND p.grade IS NULL AND COALESCE(p.utiliza_lote,false)=false AND COALESCE(p.usa_serial_compra,false)=false ORDER BY p.codigo",[[...allowedUnits]]);
 return rows.map(eligible).filter(r=>r.eligible);
});
