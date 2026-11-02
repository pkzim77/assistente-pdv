const path=require('node:path');
const assert=require('node:assert/strict');
const pw=require(process.env.PLAYWRIGHT_MODULE||path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'));
(async()=>{
 const browser=await pw.chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:4318');await page.getByText('Somente leitura',{exact:true}).waitFor();
 await page.getByLabel('Produtos avaliados por busca').selectOption('200');
 await page.getByLabel('Forma de pagamento').selectOption('PIX');
 assert.equal(await page.locator('#note').count(),0);
 await page.getByLabel('Valor desejado (R$)').fill('137,19');
 const started=Date.now();const response=page.waitForResponse(r=>r.url().endsWith('/api/proposals')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Calcular combinação'}).click();
 const result=await (await response).json();assert.equal(result.proposal.source,'stock');assert.ok(result.proposal.candidateCount<=200);assert.equal(result.proposal.distinctProducts,result.proposal.items.length);assert.equal(result.proposal.totalUnits,result.proposal.items.reduce((s,i)=>s+i.quantity,0));
 console.log(JSON.stringify({proposalRoundTripMs:Date.now()-started,calculationMs:result.proposal.elapsedMs,catalogCount:result.proposal.catalogCount,candidates:result.proposal.candidateCount,total:result.proposal.total}));
 await page.locator('.run-status').filter({hasText:'Proposta pronta'}).waitFor({timeout:30000});
 await page.getByRole('button',{name:'Validar estoque e preparar simulação'}).click();
 await page.getByText('Aguardando confirmação',{exact:true}).first().waitFor();
 assert.equal(await page.getByRole('button',{name:'Confirmar simulação',exact:true}).isDisabled(),true);
 await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Confirmar simulação',exact:true}).click();
 await page.getByRole('status').filter({hasText:'Nenhuma tecla foi enviada'}).waitFor();
 await page.screenshot({path:'docs/painel-validado.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false,'Layout móvel não deve transbordar');
 assert.deepEqual(errors,[]);
 console.log('OK: estoque geral, 200 candidatos, cálculo, validação de saldo, confirmação PIX simulada, layout móvel e ausência de erros JS.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
