export async function transition(history,id,action,validate){
 const previous=history.get(id);if(!previous)throw new Error('Proposta não encontrada.');
 const run=structuredClone(previous);
 if(action==='prepare'){
  if(run.state!=='PROPOSED')throw new Error('Esta proposta já foi preparada ou encerrada.');
  const check=await validate(run.proposal);
  run.state='READY_SIMULATION';run.checkedAt=check.checkedAt;
  run.steps=run.proposal.items.flatMap((item,index)=>[
   {number:index*3+1,action:'Informar quantidade',detail:String(item.quantity)},
   {number:index*3+2,action:'Pesquisar produto',detail:`${item.id} · ${item.description}`},
   {number:index*3+3,action:'Confirmar no PDV',detail:'Conferir o código e pressionar até 2 Enter, verificando cada estado'}
  ]);
  run.steps.push({number:run.steps.length+1,action:'Parada do painel',
   detail:'Após lançar e conferir os itens, o profissional conclui a venda diretamente no PDV.'});
 }else if(action==='confirm'){
  if(run.state!=='READY_SIMULATION')throw new Error('Prepare a simulação antes de confirmar.');
  const check=await validate(run.proposal);run.checkedAt=check.checkedAt;
  run.state='SIMULATED';run.finishedAt=new Date().toISOString();
  run.result={issued:false,payment:run.payment,key:null,message:'Simulação concluída. Nenhuma tecla foi enviada, nota emitida ou baixa realizada.'};
 }else if(action==='cancel'){
  if(!['PROPOSED','READY_SIMULATION'].includes(run.state))throw new Error('Execução já encerrada.');run.state='CANCELLED';
 }else throw new Error('Ação inválida.');
 return history.save(run);
}
