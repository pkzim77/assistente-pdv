import {performance} from 'node:perf_hooks';
import {decimalUnits,lineCents} from './money.js';
const simpler=(a,b)=>a.lines<b.lines||(a.lines===b.lines&&a.units<b.units);
const better=(total,node,best,target)=>!best||Math.abs(total-target)<Math.abs(best.total-target)||(Math.abs(total-target)===Math.abs(best.total-target)&&(total>best.total||(total===best.total&&simpler(node,best.node))));
export function selectCandidates(rows,target,limit=200){
 if(![100,200].includes(limit))throw new Error('Escolha 100 ou 200 candidatos.');
 const seen=new Set();
 const items=rows.map(row=>{if(seen.has(row.id))throw new Error('Produto duplicado no catálogo.');seen.add(row.id);return {...row,priceMilli:decimalUnits(row.price,3),stock:Math.floor(decimalUnits(row.stock,3)/1000)};}).filter(i=>i.stock>0&&i.priceMilli>=10);
 if(items.length<=limit)return items;
 const byPrice=[...items].sort((a,b)=>a.priceMilli-b.priceMilli||b.stock-a.stock||a.id-b.id);
 const unique=byPrice.filter((r,i)=>i===0||r.priceMilli!==byPrice[i-1].priceMilli);
 const chosen=new Map();const add=i=>{if(i&&chosen.size<limit)chosen.set(i.id,i);};
 const scored=items.map(i=>{const q=Math.max(1,Math.min(i.stock,Math.round(target*10/i.priceMilli)));return {item:i,diff:Math.abs(lineCents(i.priceMilli,q)-target),units:q};}).sort((a,b)=>a.diff-b.diff||a.units-b.units||a.item.id-b.item.id);
 // Aproximações individuais, itens baratos e faixas variadas; não os primeiros IDs.
 for(const s of scored.slice(0,Math.floor(limit/4)))add(s.item);
 for(const i of unique.slice(0,Math.floor(limit/4)))add(i);
 for(let j=0;j<limit/2;j++)add(unique[Math.floor(j*(unique.length-1)/Math.max(1,limit/2-1))]);
 for(const i of unique)add(i);
 for(const s of scored)add(s.item);
 return [...chosen.values()];
}
export function optimizeFast(rows,targetText,{candidateLimit=200,budgetMs=700,maxStates=1200,now=()=>performance.now()}={}){
 const started=now();const target=decimalUnits(targetText,2);
 if(target<=0||target>1000000)throw new Error('Informe um alvo entre R$ 0,01 e R$ 10.000,00.');
 const items=selectCandidates(rows,target,candidateLimit);
 if(!items.length)throw new Error('Nenhum produto elegível com estoque e preço positivo.');
 let best=null,operations=0,timedOut=false,pruned=false,processed=0;
 const consider=(total,node)=>{if(total>0&&better(total,node,best,target))best={total,node};};
 // Resposta válida antes da busca custosa; q e q+1 cobrem a melhor linha individual.
 for(const item of items){const q=Math.max(1,Math.min(item.stock,Math.floor(target*10/item.priceMilli)));for(const qty of new Set([1,q,Math.min(item.stock,q+1)]))consider(lineCents(item.priceMilli,qty),{item,quantity:qty,previous:null,lines:1,units:qty});}
 const finish=()=>{const selected=[];for(let n=best.node;n;n=n.previous)selected.push({...n.item,quantity:n.quantity,subtotal:lineCents(n.item.priceMilli,n.quantity)});
 return {target,total:best.total,difference:best.total-target,adjustment:target-best.total,items:selected.reverse(),exact:best.total===target,quality:best.total===target?'Alvo atingido':'Melhor combinação encontrada no prazo',distinctProducts:best.node.lines,totalUnits:best.node.units,candidateCount:items.length,catalogCount:rows.length,processedCandidates:processed,elapsedMs:Math.round((now()-started)*10)/10,budgetMs,timedOut,pruned,operations,rounding:'Estimativa: arredondar cada linha para centavos; conferir no PDV.'};};
 // Todas as opções de uma linha já foram comparadas. Uma linha é o mínimo possível.
 if(best.total===target)return finish();
 let states=[{total:0,node:null}];
 outer:for(const item of items){
  if(now()-started>=budgetMs){timedOut=true;break;}
  const next=new Map(states.map(s=>[s.total,s]));
  for(const state of states){
   if(best.total===target&&(state.node?.lines||0)+1>best.node.lines)continue;
   const cap=target+Math.abs(best.total-target);
   const max=Math.min(item.stock,Math.floor((Math.max(0,cap-state.total)*10+4)/item.priceMilli));
   if(max<1)continue;
   let quantities;
   if(max<=24)quantities=Array.from({length:max},(_,i)=>i+1);
   else{pruned=true;const near=Math.floor((target-state.total)*10/item.priceMilli);quantities=[1,2,3,4,5,8,12,16,24,max,near-1,near,near+1];}
   for(const quantity of new Set(quantities)){
    if(++operations%512===0&&now()-started>=budgetMs){timedOut=true;break outer;}
    if(quantity<1||quantity>max)continue;
    const total=state.total+lineCents(item.priceMilli,quantity);
    const node={item,quantity,previous:state.node,lines:(state.node?.lines||0)+1,units:(state.node?.units||0)+quantity};
    const existing=next.get(total);
    if(existing&&!simpler(node,existing.node||{lines:0,units:0}))continue;
    consider(total,node);next.set(total,{total,node});
    // Sem solução de uma linha, duas linhas e duas unidades são o mínimo absoluto.
    // Soluções exatas com mais linhas continuam sendo refinadas dentro do prazo.
    if(best.total===target&&best.node.lines===2&&best.node.units===2)return finish();
   }
  }
  processed++;
  let all=[...next.values()].filter(s=>s.total<=target+Math.abs(best.total-target));
  if(all.length>maxStates){pruned=true;all.sort((a,b)=>a.total-b.total);const keep=new Map();const spread=Math.floor(maxStates/3);for(let i=0;i<spread;i++){const state=all[Math.floor(i*(all.length-1)/(spread-1))];keep.set(state.total,state);}all.sort((a,b)=>Math.abs(a.total-target)-Math.abs(b.total-target)||b.total-a.total);for(const state of all){if(keep.size>=maxStates)break;keep.set(state.total,state);}states=[...keep.values()];}else states=all;
 }
 return finish();
}
