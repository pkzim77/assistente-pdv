import { decimalUnits, lineCents } from './money.js';
// Programação dinâmica exata, limitada por recursos. Nunca chama uma heurística de ótima.
export function optimize(rows, targetText) {
  const target = decimalUnits(targetText, 2);
  if (target <= 0 || target > 1000000) throw new Error('Informe um alvo entre R$ 0,01 e R$ 10.000,00.');
  const seen = new Set();
  const items = rows.map(row => {
    if (seen.has(row.id)) throw new Error('Produto duplicado no catálogo.');
    seen.add(row.id);
    const priceMilli = decimalUnits(row.price, 3);
    const stock = Math.floor(decimalUnits(row.stock, 3) / 1000);
    return {...row, priceMilli, stock};
  }).filter(row => row.stock > 0 && row.priceMilli >= 10);
  if (!items.length) throw new Error('Nenhum produto elegível com estoque e preço positivo.');
  if (items.length > 100) throw new Error('Selecione uma nota com até 100 produtos elegíveis.');
  // Qualquer soma mínima acima do alvo pode ser reduzida até não exceder
  // alvo + maior incremento de uma unidade. Valores de linha arredondados são monótonos.
  const cap = target + Math.max(...items.map(i => Math.ceil(i.priceMilli / 10))) + 1;
  if (cap * items.length > 16000000 || cap > 1500000) throw new Error('Combinação excede o limite de memória; escolha uma nota menor.');
  let reachable = new Uint8Array(cap + 1); reachable[0] = 1;
  const choices = [];
  let operations = 0;
  for (const item of items) {
    const next = reachable.slice();
    const chosen = new Int32Array(cap + 1); chosen.fill(-1);
    for (let sum=0; sum<=cap; sum++) if (reachable[sum]) chosen[sum]=0;
    const max = Math.min(item.stock, Math.floor((cap * 10 + 4) / item.priceMilli));
    for (let q=1; q<=max; q++) {
      const cost = lineCents(item.priceMilli, q);
      for (let sum=0; sum<=cap-cost; sum++) {
        if (++operations > 40000000) throw new Error('Busca exata excedeu o limite de cálculo. Reduza a nota ou o alvo.');
        if (reachable[sum] && !next[sum+cost]) { next[sum+cost]=1; chosen[sum+cost]=q; }
      }
    }
    choices.push(chosen); reachable = next;
  }
  let best = -1;
  for (let sum=1; sum<=cap; sum++) {
    if (reachable[sum] && (best < 0 || Math.abs(sum-target)<Math.abs(best-target) || (Math.abs(sum-target)===Math.abs(best-target) && sum>best))) best=sum;
  }
  if (best < 0) throw new Error('Nenhuma combinação encontrada.');
  let remaining=best;
  const selected=[];
  for (let n=items.length-1; n>=0; n--) {
    const quantity = choices[n][remaining];
    if (quantity < 0) throw new Error('Falha na reconstrução da combinação.');
    if (quantity) { const item=items[n]; const subtotal=lineCents(item.priceMilli,quantity); selected.push({...item,quantity,subtotal}); remaining-=subtotal; }
  }
  if (remaining !== 0) throw new Error('Total da combinação inconsistente.');
  return {target,total:best,difference:best-target,adjustment:target-best,items:selected.reverse(),exact:true,rounding:'Estimativa: arredondar cada linha para centavos; conferir no PDV.'};
}
