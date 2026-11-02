import express from 'express';
import {randomUUID,randomBytes} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {Solver} from './solver.js';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {existsSync} from 'node:fs';
import {pool,read,notes,catalog,validateProposal,stockSnapshot,connectionStatus,isConnectionError} from './db.js';
import {createHistory} from './history.js';
import {transition} from './workflow.js';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const port=Number(process.env.PORT||4318);
const execFileAsync=promisify(execFile);
const history=await createHistory(path.join(root,'data'));
const token=randomBytes(32).toString('hex');
const app=express();
app.disable('x-powered-by');
app.use((req,res,next)=>{
 if(!['127.0.0.1','localhost'].includes(req.hostname))return res.status(403).json({error:'Acesso somente local.'});
 res.set('Cache-Control','no-store');res.set('X-Content-Type-Options','nosniff');
 if(req.method!=='GET' && req.method!=='HEAD'){
  if(req.get('X-Robot-Token')!==token || !req.is('application/json'))return res.status(403).json({error:'Sessão inválida. Recarregue o painel.'});
 }next();
});
app.use(express.json({limit:'32kb'}));
let working=false;
async function exclusive(fn){if(working)throw new Error('Outra operação está em andamento. Aguarde.');working=true;try{return await fn();}finally{working=false;}}
function integer(value){const n=Number(value);if(!Number.isSafeInteger(n)||n<=0)throw new Error('Identificador inválido.');return n;}
async function executePdvBatch(run,items,previousExecution=null){
 if(!process.env.PDV_PYTHON)throw new Error('Configure PDV_PYTHON para habilitar a ponte local.');
 const previousAdded=previousExecution?.addedItems||[];
 const startedAt=new Date().toISOString();
 await history.save({...run,pdvExecution:{...(previousExecution||{}),status:'IN_PROGRESS',startedAt,
  expectedItemIds:run.proposal.items.map(item=>item.id),expectedSubtotal:run.proposal.total,
  addedItems:previousAdded}});
 const script=path.join(root,'agent','build_sale_win32.py');
 const payload=JSON.stringify({items:items.map(item=>({id:item.id,reference:item.reference,
  description:item.description,quantity:item.quantity,price:item.price,subtotal:item.subtotal}))});
 let result;
 try{
  const {stdout}=await execFileAsync(process.env.PDV_PYTHON,[script,payload],
   {timeout:180000,windowsHide:true,maxBuffer:1024*1024});
  result=JSON.parse(stdout);
 }catch(error){
  try{result=JSON.parse(error.stdout||'');}catch{}
  if(!result){
   const latest=history.get(run.id);
   const updated=await history.save({...latest,pdvExecution:{...latest.pdvExecution,
    status:'UNKNOWN',finishedAt:new Date().toISOString(),addedItems:previousAdded,
    error:'A conexão com o agente foi interrompida; confira o cupom manualmente.',
    mustInspectBeforeRetry:true}});
   return {ok:false,unknownOutcome:true,addedItems:previousAdded,run:updated,
    message:'Não foi possível confirmar o resultado da automação. Confira os itens no PDV e não repita automaticamente.'};
  }
 }
 const addedItems=[...previousAdded,...(result.addedItems||[])];
 const expectedIds=run.proposal.items.map(item=>item.id);
 const actualIds=addedItems.map(item=>Number(item.id));
 const batchSubtotal=items.reduce((sum,item)=>sum+Number(item.subtotal),0);
 const combinedSubtotal=addedItems.reduce((sum,item)=>sum+Number(item.subtotal),0);
 const allAdded=result.ok===true&&JSON.stringify(actualIds)===JSON.stringify(expectedIds)&&
  Number(result.expectedSubtotal)===batchSubtotal&&combinedSubtotal===Number(run.proposal.total)&&
  result.paymentSent===false&&result.f6Sent===false&&result.nfcIssued===false;
 const latest=history.get(run.id);
 const status=allAdded?'ITEMS_ADDED':addedItems.length?'PARTIAL':'STOPPED';
 const updated=await history.save({...latest,pdvExecution:{...latest.pdvExecution,status,
  finishedAt:new Date().toISOString(),addedItems,uncertainItem:result.uncertainItem||null,
  stage:result.stage||null,quantityMayHaveChanged:result.quantityMayHaveChanged===true,
  itemMayHaveBeenAdded:result.itemMayHaveBeenAdded===true,
  error:allAdded?null:(result.error||'O PDV não confirmou todos os itens.'),
  mustInspectBeforeRetry:!allAdded,paymentSent:false,f6Sent:false,nfcIssued:false}});
 return {ok:allAdded,addedItems,uncertainItem:result.uncertainItem||null,
  expectedSubtotal:allAdded?run.proposal.total:null,
  message:allAdded?'Itens incluídos e conferências de linha concluídas. Confira o subtotal no PDV; o painel para antes do F6.':
   'A automação parou. Confira o cupom no PDV antes de continuar; não repita os itens já lançados.',run:updated};
}
const solver=new Solver();
app.get('/api/bootstrap',async(req,res)=>{
 const database=await connectionStatus();
 res.json({token,mode:'simulation',liveEnabled:false,database,historyStorage:history.storage});
});
app.get('/api/connection-status',async(req,res)=>res.json(await connectionStatus()));
app.get('/api/notes',async(req,res)=>res.json(await notes(String(req.query.search||'').slice(0,44))));
app.get('/api/notes/:id/products',async(req,res)=>res.json(await catalog(integer(req.params.id))));
app.get('/api/catalog',async(req,res)=>{const snapshot=await stockSnapshot();res.json({count:snapshot.rows.length,loadedAt:snapshot.loadedAt,cacheTtlMs:10000});});
app.get('/api/pdv/status',async(req,res)=>{
 try{
  if(!process.env.PDV_PYTHON){res.json({available:false,windowCount:0,window:null,message:'Configure PDV_PYTHON com o caminho do Python do Windows.'});return;}
  const script=path.join(root,'agent','inspect_pdv_win32.py');
  const {stdout}=await execFileAsync(process.env.PDV_PYTHON,[script,'--stdout'],{timeout:4000,windowsHide:true,maxBuffer:1024*1024});
  const inspection=JSON.parse(stdout);
  const sales=inspection.windows.filter(window=>window.title==='PDV-FISCAL'&&window.class==='TFVendas');
  const closing=inspection.windows.filter(window=>window.title.toUpperCase().includes('FECHAMENTO DE VENDA'));
  const logins=inspection.windows.filter(window=>window.title.toUpperCase().includes('CUPOM FISCAL'));
  const required=['quantity','product_search','sale_price','line_total'];
  const roleCounts=sales.length===1?Object.fromEntries(required.map(role=>[role,sales[0].controls.filter(control=>control.role===role).length])):{};
  const bounds=sales.length===1?sales[0].rectangle:null;
  const inside=(rect,outer)=>Array.isArray(rect)&&rect.length===4&&Array.isArray(outer)&&outer.length===4&&
   rect[0]>=outer[0]&&rect[1]>=outer[1]&&rect[2]<=outer[2]&&rect[3]<=outer[3]&&rect[2]>rect[0]&&rect[3]>rect[1];
  const clippedFields=sales.length===1?['quantity','product_search','sale_price','line_total','pdv_status_display','sale_items_area']
   .filter(role=>{const matches=sales[0].controls.filter(control=>control.role===role);return matches.length===1&&!inside(matches[0].rectangle,bounds)||
    (['quantity','product_search','sale_price','line_total'].includes(role)&&matches.length===1&&matches[0].within_window!==true);}):[];
  const mapped=sales.length===1?required.filter(role=>roleCounts[role]===1&&
   sales[0].controls.some(control=>control.role===role&&control.enabled&&Number(control.hwnd)>0&&
    inside(control.rectangle,bounds)&&control.within_window===true)):[];
  const windowUsable=sales.length===1&&sales[0].visible!==false&&!sales[0].minimized;
  const ready=sales.length===1&&windowUsable&&closing.length===0&&mapped.length===required.length&&clippedFields.length===0;
  const fields=ready?Object.fromEntries(sales[0].controls.filter(control=>required.includes(control.role)).map(control=>[control.role,control.value??''])):{};
  const missing=required.filter(role=>roleCounts[role]!==1);
  const disabled=required.filter(role=>roleCounts[role]===1&&!sales[0].controls.find(control=>control.role===role)?.enabled);
  const message=ready?'Janela visível e quatro campos únicos, habilitados e mapeados. Nenhuma entrada foi enviada.':
   closing.length?'Fechamento de venda aberto; controle do PDV Livre bloqueado.':
   logins.length?'Tela de login do PDV encontrada; entre no PDV antes de automatizar.':
   sales.length>1?'Há mais de uma janela de venda; controle bloqueado.':
   sales.length===1&&!windowUsable?'A janela do PDV está oculta ou minimizada; controle bloqueado.':
   sales.length===1&&clippedFields.length?`Layout do PDV excede a janela atual (${bounds?.[2]-bounds?.[0]}×${bounds?.[3]-bounds?.[1]}). Controles fora da tela: ${[...new Set(clippedFields)].join(', ')}. Feche e reabra o PDV neste monitor para refazer o layout. Controle bloqueado.`:
   sales.length===1&&missing.length?`Mapa incompleto ou ambíguo: ${missing.join(', ')}. Controle bloqueado.`:
   sales.length===1&&disabled.length?`Campos desabilitados: ${disabled.join(', ')}. Controle bloqueado.`:
   'Nenhuma janela de venda acessível nesta sessão do Windows. O processo pode estar em outra sessão ou com nível de permissão diferente.';
  res.json({available:ready,checkedAt:new Date().toISOString(),windowCount:sales.length,window:sales.length===1?sales[0]:null,mappedFields:mapped,fields,
   diagnostics:{roleCounts,closingWindows:closing.length,loginWindows:logins.length,windowUsable,
    windowSize:bounds?{width:bounds[2]-bounds[0],height:bounds[3]-bounds[1]}:null,
    clippedFields:[...new Set(clippedFields)],layoutFits:sales.length===1&&clippedFields.length===0&&mapped.length===required.length,
    windows:inspection.windows.map(window=>({title:window.title,class:window.class,process_id:window.process_id,
     hwnd:window.hwnd,visible:window.visible,minimized:window.minimized}))},message});
 }catch(error){
  let detail=error.code==='ENOENT'?'Python não encontrado; ajuste PDV_PYTHON.':error.stderr?.trim()||error.message;
  try{const result=JSON.parse(error.stdout||'');if(result.error)detail=result.error;}catch{}
  res.json({available:false,windowCount:0,window:null,message:'Não foi possível consultar a janela do PDV: '+String(detail).slice(0,280)});
 }
});
app.post('/api/pdv/launch',async(req,res)=>res.json(await exclusive(async()=>{
 if(!process.env.PDV_PYTHON)throw new Error('Configure PDV_PYTHON para habilitar a inicialização do PDV.');
 const script=path.join(root,'agent','launch_pdv_win32.py');
 let stdout;
 try{({stdout}=await execFileAsync(process.env.PDV_PYTHON,[script],{timeout:8000,windowsHide:true,maxBuffer:1024*1024}));}
 catch(error){let detail=error.stderr?.trim()||error.message;try{const agent=JSON.parse(error.stdout||'');if(agent.error)detail=agent.error;}catch{}throw new Error('Inicialização do PDV: '+String(detail).slice(0,280));}
 const result=JSON.parse(stdout);
 if(!result.ok||(!result.launched&&!result.alreadyRunning))throw new Error('O PDV não confirmou a inicialização.');
 return result;
})));
app.post('/api/pdv/clear-quantity',(req,res)=>res.status(409).json({error:'Use o botão único para montar todos os itens no PDV.'}));
app.post('/api/pdv/set-quantity',(req,res)=>res.status(409).json({error:'Use o botão único para montar todos os itens no PDV.'}));
app.post('/api/pdv/search',(req,res)=>res.status(409).json({error:'Use o botão único para montar todos os itens no PDV.'}));
app.post('/api/pdv/select-visible',(req,res)=>res.status(409).json({error:'Use o botão único para montar todos os itens no PDV.'}));
app.post('/api/pdv/enter-two',(req,res)=>res.status(409).json({error:'Use o botão único para montar todos os itens no PDV.'}));
app.post('/api/pdv/build-sale',async(req,res)=>res.json(await exclusive(async()=>{
 const run=history.get(String(req.body.runId||''));
 if(!run||run.state!=='READY_SIMULATION')throw new Error('Prepare uma proposta antes de montar a venda no PDV.');
 if(run.mode!=='simulation'||!Array.isArray(run.proposal.items)||!run.proposal.items.length)
  throw new Error('A proposta não está pronta para ser lançada no PDV.');
 if(req.body.cartEmptyConfirmed!==true)
  throw new Error('Confirme que o cupom está vazio e nenhum produto foi pesquisado.');
 if(run.pdvExecution)
  throw new Error('Esta proposta já iniciou uma tentativa no PDV. Confira o cupom antes de qualquer nova ação.');
 await validateProposal(run.proposal);
 return await executePdvBatch(run,run.proposal.items,null);
})));
app.post('/api/pdv/continue-sale',async(req,res)=>res.json(await exclusive(async()=>{
 const run=history.get(String(req.body.runId||''));
 const attempt=run&&run.pdvExecution;
 if(!run||run.state!=='READY_SIMULATION'||attempt?.status!=='PARTIAL')
  throw new Error('Não há uma proposta parcial que possa ser continuada.');
 if(attempt.stage!=='before_quantity'||attempt.uncertainItem||attempt.itemMayHaveBeenAdded===true)
  throw new Error('O resultado do último item é incerto. Confira manualmente e não continue pelo painel.');
 if(req.body.confirmedRemaining!==true)
  throw new Error('Confirme que o cupom contém somente as linhas já lançadas e que a linha atual está vazia.');
 const expected=run.proposal.items;
 const added=attempt.addedItems||[];
 const prefix=expected.slice(0,added.length);
 const prefixMatches=JSON.stringify(added.map(item=>Number(item.id)))===JSON.stringify(prefix.map(item=>Number(item.id)))&&
  added.every((item,index)=>Number(item.quantity)===Number(prefix[index].quantity)&&
   Number(item.subtotal)===Number(prefix[index].subtotal));
 if(!added.length||added.length>=expected.length||!prefixMatches)
  throw new Error('As linhas já lançadas não correspondem a um prefixo exato da proposta. Continuação bloqueada.');
 await validateProposal(run.proposal);
 if(!process.env.PDV_PYTHON)throw new Error('Configure PDV_PYTHON para habilitar a ponte local.');
 const script=path.join(root,'agent','inspect_pdv_win32.py');
 const {stdout}=await execFileAsync(process.env.PDV_PYTHON,[script,'--stdout'],
  {timeout:8000,windowsHide:true,maxBuffer:1024*1024});
 const snapshot=JSON.parse(stdout);
 const sales=snapshot.windows.filter(window=>window.title==='PDV-FISCAL'&&window.class==='TFVendas');
 const closing=snapshot.windows.some(window=>window.title.toUpperCase().includes('FECHAMENTO DE VENDA'));
 if(sales.length!==1||!sales[0].visible||sales[0].minimized||closing)
  throw new Error('A tela de venda não está única, visível ou livre do fechamento. Continuação bloqueada.');
 const sale=sales[0];
 const roles=['quantity','product_search','sale_price','line_total'];
 const fields={};
 for(const role of roles){
  const matches=sale.controls.filter(control=>control.role===role);
  if(matches.length!==1||!matches[0].enabled||matches[0].within_window!==true)
   throw new Error('Campo '+role+' não está disponível. Continuação bloqueada.');
  fields[role]=String(matches[0].value||'').trim();
 }
 const grid=sale.controls.some(control=>control.class==='TArpaAdvDBGrid'&&control.enabled);
 if(grid||fields.product_search||!['1','1,000','1.000'].includes(fields.quantity)||
    !['0','0,000','0.000'].includes(fields.sale_price)||!['0','0,00','0.00'].includes(fields.line_total))
  throw new Error('A linha do PDV não está vazia ou há uma lista aberta. Continuação bloqueada.');
 return await executePdvBatch(run,expected.slice(added.length),attempt);
})));
app.post('/api/pdv/f6',(req,res)=>res.status(409).json({error:'O painel para antes do F6. Conclua a venda manualmente no PDV.'}));
app.post('/api/pdv/show-closing',(req,res)=>res.status(409).json({error:'O painel não abre o fechamento; o profissional conclui a venda diretamente no PDV.'}));
app.post('/api/pdv/review',async(req,res)=>res.json(await exclusive(async()=>{
 const run=history.get(String(req.body.runId||''));
 if(!run||run.state!=='READY_SIMULATION'||run.pdvExecution?.status!=='ITEMS_ADDED')
  throw new Error('Só é possível registrar a conferência depois que todos os itens forem lançados no PDV.');
 if(req.body.reviewed!==true)throw new Error('Confirme que revisou itens e subtotal no PDV.');
 const updated=await history.save({...run,pdvExecution:{...run.pdvExecution,
  status:'REVIEWED',reviewedAt:new Date().toISOString()}});
 return {ok:true,run:updated,message:'Conferência registrada. O profissional pode concluir a venda manualmente no PDV.'};
})));
app.get('/api/runs',async(req,res)=>res.json(history.list().slice(0,50)));
app.post('/api/proposals',async(req,res)=>res.json(await exclusive(async()=>{
 const started=performance.now();const payment=req.body.payment;const candidateLimit=Number(req.body.candidateLimit??200);
 if(![100,200].includes(candidateLimit))throw new Error('Escolha 100 ou 200 candidatos.');
 if(!['PIX','CARD','MANUAL'].includes(payment))throw new Error('Forma de pagamento inválida.');
 const snapshot=await stockSnapshot({fresh:true});
 const proposal=await solver.solve(snapshot.rows,req.body.target,candidateLimit,snapshot.loadedAt);
 proposal.source='stock';proposal.snapshotAt=snapshot.loadedAt;proposal.requestedCandidateLimit=candidateLimit;
 proposal.responseMs=Math.round(performance.now()-started);
 return history.save({id:randomUUID(),createdAt:new Date().toISOString(),mode:'simulation',state:'PROPOSED',payment,proposal});
})));
app.post('/api/runs/:id/prepare',async(req,res)=>res.json(await exclusive(()=>transition(history,req.params.id,'prepare',validateProposal))));
app.post('/api/runs/:id/confirm',async(req,res)=>{
 if(history.get(req.params.id)?.pdvExecution)return res.status(409).json({error:'Os itens já foram enviados ao PDV; esta proposta não pode ser registrada como simulação.'});
 if(req.body.authorization!=='SIMULAR' || req.body.payment!==history.get(req.params.id)?.payment)throw new Error('Confirme explicitamente a simulação e a forma de pagamento.');
 res.json(await exclusive(()=>transition(history,req.params.id,'confirm',validateProposal)));
});
app.post('/api/runs/:id/cancel',async(req,res)=>{
 if(history.get(req.params.id)?.pdvExecution)return res.status(409).json({error:'Esta proposta já iniciou uma tentativa no PDV e não pode ser cancelada pelo painel.'});
 res.json(await exclusive(()=>transition(history,req.params.id,'cancel',validateProposal)));
});
app.post('/api/live',async(req,res)=>res.status(409).json({error:'Controle real bloqueado: falta validar os campos e o comprovante de emissão do PDV.'}));
app.use('/api',(req,res)=>res.status(404).json({error:'Rota não carregada. Reinicie iniciar.cmd e atualize o painel.'}));
if(existsSync(path.join(root,'dist','index.html')))app.use(express.static(path.join(root,'dist')));
app.use((error,req,res,next)=>{console.error(error.code||error.message);const connectionFailure=isConnectionError(error);res.status(connectionFailure?503:400).json({error:connectionFailure?'Conexão com o Arpa indisponível após novas tentativas. A reconexão será tentada automaticamente; confira o serviço e tente novamente.':error.code==='57014'?'A consulta ao Arpa excedeu o limite de tempo; nenhuma alteração foi feita. Tente novamente.':error.message||'Falha na operação.',connection:connectionFailure?'disconnected':undefined});});
const server=app.listen(port,'127.0.0.1',()=>console.log('Painel em http://127.0.0.1:'+port+' — simulação, Arpa somente leitura'));
async function close(){server.close();await solver.close();await pool.end();await history.close();}
process.on('SIGINT',()=>close().then(()=>process.exit()));
process.on('SIGTERM',()=>close().then(()=>process.exit()));
