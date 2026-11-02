import test from 'node:test';
import assert from 'node:assert/strict';
import {optimize} from '../server/optimizer.js';
import {decimalUnits,lineCents} from '../server/money.js';
function row(id,price,stock){return {id,price,stock:String(stock),description:'Item '+id};}
test('empate escolhe o maior total',()=>{const r=optimize([row(1,'98.000',1),row(2,'102.000',1)],'100');assert.equal(r.total,10200);assert.equal(r.items[0].id,2);});
test('respeita estoque e não aplica 25% outra vez',()=>{const r=optimize([row(17675,'62.913',3)],'300');assert.equal(r.items[0].quantity,3);assert.equal(r.total,18874);});
test('arredonda por linha preservando a terceira casa',()=>{assert.equal(lineCents(decimalUnits('62.913',3),2),12583);assert.equal(decimalUnits('100,01',2),10001);assert.throws(()=>decimalUnits('1.005',2));});
test('não seleciona itens sem estoque nem retorna conjunto vazio',()=>{assert.throws(()=>optimize([row(1,'10',0)],'100'));assert.equal(optimize([row(1,'50',1)],'1').total,5000);});
test('rejeita catálogo duplicado e alvo inválido',()=>{assert.throws(()=>optimize([row(1,'10',1),row(1,'20',1)],'10'));for(const t of ['-1','NaN','0','1e4'])assert.throws(()=>optimize([row(1,'10',1)],t));});
test('resultado confere com enumeração exaustiva de 80 catálogos',()=>{
 let seed=1729;const rand=n=>{seed=(seed*1664525+1013904223)>>>0;return seed%n;};
 for(let trial=0;trial<80;trial++){
  const rows=Array.from({length:4},(_,i)=>row(i+1,((100+rand(3000))/1000).toFixed(3),1+rand(4)));
  const target=100+rand(3000);let best=-1;
  function walk(i,total){if(i===rows.length){if(total>0&&(best<0||Math.abs(total-target)<Math.abs(best-target)||(Math.abs(total-target)===Math.abs(best-target)&&total>best)))best=total;return;}for(let q=0;q<=Number(rows[i].stock);q++)walk(i+1,total+lineCents(decimalUnits(rows[i].price,3),q));}
  walk(0,0);const found=optimize(rows,(target/100).toFixed(2));assert.equal(found.total,best);assert.equal(found.items.reduce((s,i)=>s+i.subtotal,0),best);for(const item of found.items)assert.ok(item.quantity<=item.stock);
 }
});
