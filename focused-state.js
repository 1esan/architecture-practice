/* Compatibility adapter for subject-specific editors. No historical attempts are rewritten. */
(function(root){
'use strict';
const labels={requirements:'Требования',boundaries:'Границы и допущения',data:'Данные',flow:'Основной поток',resilience:'Отказы и восстановление',tradeoffs:'Компромиссы'};
const applies=c=>['api','integration'].includes(c?.pool);
function ensure(c,d){
 if(!applies(c))return;
 const t=d.training;
 if(d.focusedVersion!==1){
  const previous=Object.entries(labels).filter(([k])=>t.sections[k]?.trim()).map(([k,n])=>n+':\n'+t.sections[k].trim()).join('\n\n');
  const merged=[d.answer,previous].filter(Boolean).join('\n\n');
  // Keep unusually large legacy drafts editable in their original format, without truncation.
  if(merged.length>60000)return false;
  if(previous)d.answer=merged;
  for(const k of Object.keys(labels))t.sections[k]='';
  d.focusedVersion=1;
 }
 t.editor='free';
}
function solution(c,d,F,W){
 if(!applies(c)||d.focusedVersion!==1)return W.effectiveAnswer(d,c);
 const extra=W.effectiveAnswer({...d,answer:'',training:{...d.training,editor:'free'}},c);
 return [F.answer(c,d),extra].filter(Boolean).join('\n\n');
}
root.FocusedState={applies,ensure,solution};if(typeof module!=='undefined')module.exports=root.FocusedState;
})(typeof window!=='undefined'?window:globalThis);
