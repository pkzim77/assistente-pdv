import test from 'node:test';import assert from 'node:assert/strict';
import {optimizeFast,selectCandidates} from '../server/fast-optimizer.js';
import {optimize} from '../server/optimizer.js';
const row=(id,price,stock=1)=>({id,price:String(price),stock:String(stock)});
function valid(result,rows){const seen=new Set();const map=new Map(rows.map(r=>[r.id,r]));let total=0;for(const i of result.items){assert.ok(!seen.has(i.id));seen.add(i.id);assert.ok(i.quantity>0&&i.quantity<=Number(map.get(i.id).stock));total+=i.subtotal;}assert.equal(total,result.total);assert.equal(result.exact,result.total===result.target);}
test('combina produtos de entradas diferentes e usa precovenda',()=>{const rows=[{...row(1,'62.913'),note:1},{...row(2,'37.087'),note:2}];const result=optimizeFast(rows,'100');assert.equal(result.total,10000);assert.equal(result.items.length,2);valid(result,rows);});
test('empate preserva o maior total, sem afirmar ótimo global',()=>{const r=optimizeFast([row(1,98),row(2,102)],'100');assert.equal(r.total,10200);assert.equal(r.exact,false);});
test('prazo esgotado retorna uma solução válida',()=>{const rows=[row(1,'62.913',100),row(2,'37.082',40)];const r=optimizeFast(rows,'137.11',{budgetMs:0});assert.equal(r.timedOut,true);valid(r,rows);});
test('seleção considera IDs fora do primeiro intervalo e tem teto',()=>{const rows=Array.from({length:1000},(_,i)=>row(i+1,(i+1)*2,3));rows.push(row(1001,'137.19'));const selected=selectCandidates(rows,13719,100);assert.equal(selected.length,100);assert.ok(selected.some(i=>i.id===1001));assert.equal(optimizeFast(rows,'137.19',{candidateLimit:100}).total,13719);});
test('busca pequena coincide com algoritmo exato em 40 catálogos',()=>{let seed=572;const rand=n=>{seed=(seed*1664525+1013904223)>>>0;return seed%n;};for(let n=0;n<40;n++){const rows=Array.from({length:4},(_,i)=>row(i+1,((100+rand(3000))/1000).toFixed(3),1+rand(3)));const target=((100+rand(3000))/100).toFixed(2);const r=optimizeFast(rows,target,{budgetMs:1000,maxStates:2000});assert.equal(r.total,optimize(rows,target).total);valid(r,rows);}});
test('estoque fracionário não é arredondado para cima',()=>{const rows=[row(1,'25.555','1.999')];const r=optimizeFast(rows,'100');assert.equal(r.items[0].quantity,1);valid(r,rows);});
test('catálogo grande respeita seleção e estoque',()=>{const rows=Array.from({length:20000},(_,i)=>row(i+1,String(5+(i%200)*5),1+i%50));const r=optimizeFast(rows,'137.01',{candidateLimit:200,budgetMs:30});assert.equal(r.candidateCount,200);assert.equal(r.exact,false);valid(r,rows);});

test('uma linha tem preferência mesmo quando usa mais unidades',()=>{const r=optimizeFast([row(1,10,10),row(2,40),row(3,60)],'100');assert.equal(r.total,10000);assert.equal(r.distinctProducts,1);assert.equal(r.totalUnits,10);});
test('mesmo total e mesmo número de linhas escolhem menos unidades',()=>{const r=optimizeFast([row(1,10,10),row(2,100)],'100');assert.equal(r.items[0].id,2);assert.equal(r.totalUnits,1);});
test('continua depois da primeira solução exata para reduzir linhas',()=>{const r=optimizeFast([row(1,20),row(2,30),row(3,50),row(4,51),row(5,49)],'100');assert.equal(r.total,10000);assert.equal(r.distinctProducts,2);assert.equal(r.totalUnits,2);});
test('substitui estado do mesmo total por menor quantidade',()=>{const r=optimizeFast([row(1,10,4),row(2,40),row(3,60)],'100');assert.deepEqual(r.items.map(i=>i.id),[2,3]);assert.equal(r.totalUnits,2);});
test('proximidade e preferência por total maior precedem número de linhas',()=>{const r=optimizeFast([row(1,98),row(2,51),row(3,51)],'100');assert.equal(r.total,10200);assert.equal(r.distinctProducts,2);});
test('seleção de candidatos prefere menos unidades em empate de desvio',()=>{const rows=Array.from({length:500},(_,i)=>row(i+1,1,100));rows.push(row(999,100));const r=optimizeFast(rows,'100',{candidateLimit:100});assert.equal(r.items[0].id,999);assert.equal(r.totalUnits,1);});
test('prioridades conferem com enumeração de 60 catálogos pequenos',()=>{let seed=918;const rand=n=>{seed=(seed*1664525+1013904223)>>>0;return seed%n;};for(let trial=0;trial<60;trial++){
 const rows=Array.from({length:5},(_,i)=>row(i+1,1+rand(20),1+rand(3)));const target=1+rand(100);let expected=null;
 function before(a,b){return !b||Math.abs(a.total-target)<Math.abs(b.total-target)||(Math.abs(a.total-target)===Math.abs(b.total-target)&&(a.total>b.total||(a.total===b.total&&(a.lines<b.lines||(a.lines===b.lines&&a.units<b.units)))));}
 function walk(i,total,lines,units){if(i===rows.length){const candidate={total,lines,units};if(total>0&&before(candidate,expected))expected=candidate;return;}for(let q=0;q<=Number(rows[i].stock);q++)walk(i+1,total+Number(rows[i].price)*q,lines+(q>0?1:0),units+q);}
 walk(0,0,0,0);const r=optimizeFast(rows,String(target),{budgetMs:1000,maxStates:2000});assert.deepEqual({total:r.total/100,lines:r.distinctProducts,units:r.totalUnits},expected);valid(r,rows);
}});
