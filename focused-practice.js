'use strict';
(function(root){
  const INTEGRATION=[['requirements','Стороны и данные'],['boundaries','Методы интеграции'],['data','Обоснование критериев'],['flow','Основной поток'],['resilience','Сбой и восстановление'],['tradeoffs','Альтернатива и решения']];
  const API=[['requirements','Метод и путь'],['boundaries','Авторизация и заголовки'],['data','Поля запроса'],['flow','Успешный ответ'],['resilience','Ошибки и условия'],['tradeoffs','Повторы и важные решения']];
  const CATALOG=[
    ['HTTP API',[['rest','REST'],['http','HTTP API'],['soap','SOAP'],['graphql','GraphQL']]],
    ['Удалённые вызовы',[['grpc-unary','gRPC unary'],['grpc-stream','gRPC streaming']]],
    ['Брокеры и очереди',[['kafka','Kafka'],['rabbitmq','RabbitMQ'],['nats','NATS'],['mqtt','MQTT'],['amqp','AMQP'],['stomp','STOMP']]],
    ['Push и подписки',[['webhook','Webhook'],['sse','SSE'],['websocket','WebSocket']]],
    ['Опрос и изменение данных',[['short-polling','Short polling'],['long-polling','Long polling'],['cdc','CDC']]],
    ['Файлы и пакеты',[['batch','Batch'],['sftp','SFTP'],['object-storage','Object storage'],['file-transfer','Файловый обмен']]],
  ];
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const txt=(d,k)=>String(d?.training?.sections?.[k]??'');
  function balancedJsonAt(text,start){const stack=[],pairs={'}':'{',']':'['};let quote=false,escape=false;for(let i=start;i<text.length;i++){const ch=text[i];if(quote){if(escape)escape=false;else if(ch==='\\')escape=true;else if(ch==='"')quote=false;continue;}if(ch==='"'){quote=true;continue;}if(ch==='{'||ch==='[')stack.push(ch);else if(ch==='}'||ch===']'){if(stack.pop()!==pairs[ch])return text.slice(start,i+1);if(!stack.length)return text.slice(start,i+1);}}return text.slice(start);}
  function jsonCandidates(text){const source=String(text||''),matches=[],fences=/```json\s*\r?\n([\s\S]*?)(?:\r?\n```|```|$)/gi;let stripped=source;for(const m of source.matchAll(fences)){matches.push(m[1].trim());stripped=stripped.replace(m[0],' ');}const status=/^(?:(?:HTTP\/\d(?:\.\d)?\s+)?(?:[1-5]\d\d(?:\s+[A-Za-z][\w -]*)?|(?:успех|ошибка|ответ|тело(?:\s+ошибки)?|json)(?:\s+(?:json|body|ответ))?(?:\s*\(?[1-5]\d\d\)?)?))\s*:?$/i;for(const line of stripped.split(/\r?\n/)){let cursor=0;while(cursor<line.length){const offset=line.slice(cursor).search(/[\[{]/);if(offset<0)break;const pos=cursor+offset,prefix=line.slice(cursor,pos).trim().replace(/^[;]+/,'').trim(),labels=prefix.split(';').map(x=>x.trim()).filter(Boolean);if(prefix&&!labels.every(x=>status.test(x))){cursor=pos+1;continue;}const candidate=balancedJsonAt(line,pos);matches.push(candidate);cursor=pos+candidate.length;if(!candidate.length)break;}}return matches;}
  const methodIds=new Set(CATALOG.flatMap(([,items])=>items.map(([id])=>id)));
  function boundaryParts(d){const raw=txt(d,'boundaries'),[idLine,...legacyLines]=raw.split('\n'),tokens=idLine.split(',').map(x=>x.trim()).filter(Boolean),ids=tokens.filter(x=>methodIds.has(x)),legacy=[tokens.filter(x=>!methodIds.has(x)).join(', '),...legacyLines].filter(Boolean).join('\n');return {ids:new Set(ids),legacy};}
  const titles=Object.fromEntries(CATALOG.flatMap(([,items])=>items));
  const isApi=card=>card?.pool==='api';
  function html(card,d){
    const api=isApi(card), old=String(d?.answer||''), sections=api?API:INTEGRATION, boundary=boundaryParts(d), chosen=boundary.ids;
    const prompts=api?[
      'Укажи HTTP-метод и путь, например: POST /v1/orders',
      'Отметь протокол/способ обмена и запиши авторизацию и нужные заголовки',
      'Опиши конкретные поля запроса, типы и обязательность',
      'Опиши успешный статус и покажи JSON-ответ',
      'Укажи 1–2 ошибки: статус, условие и тело ответа',
      'Опиши повторы и важные решения (например, идемпотентность)'
    ]:[
      'Кто участвует и какими данными обменивается?',
      'Выбери один или несколько методов обмена',
      'Почему важны выбранные критерии: задержка, порядок, доставка, объём?',
      'Опиши последовательность успешного взаимодействия',
      'Что произойдёт при сбое и как система восстановится?',
      'Какая альтернатива рассматривалась и почему выбран этот вариант?'
    ];
    const methods=CATALOG.map(([group,items])=>`<fieldset class="fp-method-group"><legend>${esc(group)}</legend><div class="fp-checks">${items.map(([id,label])=>`<label><input type="checkbox" data-fp-method="${id}" ${chosen.has(id)?'checked':''}><span>${esc(label)}</span></label>`).join('')}</div></fieldset>`).join('');
    const fields=sections.map(([key,label],i)=>{
      if(key==='boundaries'&&!api) return `<div class="fp-field fp-boundaries"><label for="fp-${key}">${esc(label)}</label><p class="fp-hint">Можно выбрать несколько способов. Сочетай методы, когда это нужно сценарию.</p><div class="fp-method-grid">${methods}</div><label for="fp-custom">Другой способ или дополнительный контекст</label><textarea id="fp-custom" data-fp-boundary-legacy maxlength="7400" placeholder="Опиши свой вариант и обоснование">${esc(boundary.legacy)}</textarea><input type="hidden" id="fp-${key}" data-fp-key="${key}" value="${esc(txt(d,key))}"></div>`;
      if(key==='boundaries') return `<div class="fp-field"><label for="fp-${key}">${esc(label)}</label><textarea id="fp-${key}" data-fp-key="${key}" maxlength="8000" placeholder="Авторизация и нужные заголовки запроса">${esc(txt(d,key))}</textarea></div>`;
      return `<div class="fp-field"><label for="fp-${key}">${esc(label)}</label><textarea id="fp-${key}" data-fp-key="${key}" maxlength="8000" placeholder="${esc(prompts[i])}">${esc(txt(d,key))}</textarea>${key==='flow'&&api?'<p class="fp-hint">Пример ответа: <code>{"id":"ord_123","status":"created"}</code></p>':''}</div>`;
    }).join('');
    return `<section class="focused-practice" aria-label="Практика проектирования ${api?'API':'интеграции'}"><header><h3>${api?'Контракт API':'Способ интеграции'}</h3><p>${esc(card?.title||'Карточка практики')}. Заполни шесть частей решения. Черновик сохраняется по мере ввода.</p></header><div class="fp-fields">${fields}</div><div class="fp-check-area"><button type="button" data-fp-check>Проверить заполнение</button><span data-fp-feedback aria-live="polite"></span></div><details class="fp-legacy"><summary>${old.trim()?'Прежний ответ — можно изменить':'Дополнительный текст'}</summary><div class="fp-field"><label for="fp-legacy-answer">Дополнительный текст включается в итоговый ответ</label><textarea id="fp-legacy-answer" data-fp-legacy maxlength="60000" placeholder="Добавь важный текст или отредактируй прежний ответ">${esc(old)}</textarea></div></details></section>`;
  }
  function answer(card,d){
    const parts=[];
    for(const [key,label] of (isApi(card)?API:INTEGRATION)){const value=txt(d,key).trim();if(!value)continue;
      if(key==='boundaries'&&!isApi(card)){const {ids,legacy}=boundaryParts(d),names=[...ids].map(x=>titles[x]||x);if(legacy)names.push(legacy);if(names.length)parts.push(`${label}:\n${names.join(', ')}`);}
      else parts.push(`${label}:\n${value}`);
    }
    const old=String(d?.answer||'').trim();if(old)parts.push(`Прежний ответ:\n${old}`);
    return parts.join('\n\n');
  }
  function bind(container,card,d,{save=()=>{},render=()=>{}}={}){
    const persist=()=>save();
    container.addEventListener('input',e=>{const el=e.target;if(el?.dataset&&Object.hasOwn(el.dataset,'fpLegacy')){d.answer=el.value;persist();return;}if(el?.dataset&&Object.hasOwn(el.dataset,'fpBoundaryLegacy')){const ids=[...container.querySelectorAll('[data-fp-method]:checked')].map(x=>x.dataset.fpMethod);d.training.sections.boundaries=[ids.join(','),el.value.trim()].filter(Boolean).join('\n');const hidden=container.querySelector('[data-fp-key="boundaries"]');if(hidden)hidden.value=d.training.sections.boundaries;persist();return;}if(el?.dataset?.fpKey){d.training.sections[el.dataset.fpKey]=el.value;persist();}});
    container.addEventListener('change',e=>{const el=e.target;if(!el?.dataset?.fpMethod)return;const ids=[...container.querySelectorAll('[data-fp-method]:checked')].map(x=>x.dataset.fpMethod);const custom=container.querySelector('[data-fp-boundary-legacy]');const extra=custom?custom.value.trim():boundaryParts(d).legacy;d.training.sections.boundaries=[ids.join(','),extra].filter(Boolean).join('\n');const hidden=container.querySelector('[data-fp-key="boundaries"]');if(hidden)hidden.value=d.training.sections.boundaries;persist();});
    container.addEventListener('click',e=>{const button=e.target?.closest?.('[data-fp-check]');if(!button)return;const feedback=container.querySelector('[data-fp-feedback]');const sections=isApi(card)?API:INTEGRATION,blank=sections.filter(([key])=>!txt(d,key).trim()).map(([,label])=>label),notes=[];if(blank.length)notes.push(`Можно дополнить: ${blank.join(', ')}.`);for(const [key,label] of sections.filter(([key])=>key==='flow'||key==='resilience')){const candidates=jsonCandidates(txt(d,key));let bad=0;for(const value of candidates){try{JSON.parse(value);}catch{bad++;}}if(!candidates.length)notes.push(`${label}: JSON не найден, синтаксис не проверен.`);else if(bad)notes.push(`${label}: ${bad} из ${candidates.length} JSON-фрагментов не разбирается.`);else notes.push(`${label}: проверено JSON-фрагментов — ${candidates.length}, ошибок нет.`);}notes.push('Проверка локальная и ориентировочная; оцени полноту ответа по условиям.');if(feedback)feedback.textContent=notes.join(' ');});
    return {save:persist,render};
  }
  root.FocusedPractice={html,bind,answer,escapeHTML:esc,catalog:CATALOG};
  if(typeof module!=='undefined'&&module.exports)module.exports=root.FocusedPractice;
})(typeof window!=='undefined'?window:globalThis);
