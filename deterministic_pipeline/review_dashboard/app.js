"use strict";

const state = {data:null, currentId:null, filtered:[], predictions:new Map(), dirtyGold:false, dirtyFeedback:false};
const $ = selector => document.querySelector(selector);
const el = (tag, className, text) => {const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node};
const titleCase = value => String(value).replaceAll("_"," ").replace(/\b\w/g, c=>c.toUpperCase());
const current = () => state.data?.items.find(item=>item.id===state.currentId);
const selected = node => [...node.selectedOptions].map(option=>option.value);

function setStatus(message, kind=""){$("#save-status").textContent=message;$("#save-status").className=`save-status ${kind}`}
function syncDirty(){const dirty=state.dirtyGold||state.dirtyFeedback;document.body.classList.toggle("dirty",dirty);if(dirty)setStatus("Unsaved changes")}
function setDirty(kind,value){state[kind]=value;syncDirty()}
function clearDirty(){state.dirtyGold=false;state.dirtyFeedback=false;syncDirty()}
function allowLeave(){return !(state.dirtyGold||state.dirtyFeedback) || window.confirm("Discard unsaved changes for this record?")}

async function request(url, options={}){
  const response=await fetch(url, options);let body;
  try{body=await response.json()}catch{body={error:`HTTP ${response.status}`}}
  if(!response.ok){const error=new Error(body.error||`HTTP ${response.status}`);error.status=response.status;throw error}return body;
}
function mutation(body){return {method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":state.data.csrf_token},body:JSON.stringify(body)}}

async function loadSession(preferredId=null){
  setStatus("Loading…");
  try{
    state.data=await request("/api/session");populateVocabulary();applyFilters();
    const available=state.filtered.some(item=>item.id===preferredId)?preferredId:state.filtered[0]?.id;
    state.currentId=available||null;clearDirty();renderAll();$("#reload-conflict").hidden=true;setStatus("All changes saved","success");
  }catch(error){setStatus(error.message,"error")}
}

function addOptions(select, values, formatter=titleCase){
  for(const value of values){const option=el("option",null,formatter(value));option.value=value;select.append(option)}
}
function populateVocabulary(){
  const vocab=state.data.vocabulary;
  for(const [selector,values,formatter] of [
    ["#bucket-filter",vocab.buckets.map(row=>row.name),value=>value],
    ["#feedback-filter",vocab.feedback_dispositions],
    ["#disposition",vocab.feedback_dispositions],
    ["#feedback-reason",vocab.feedback_reasons],
    ["#suggested-buckets",vocab.buckets.map(row=>row.name),value=>value],
    ["#suggested-subtype",vocab.subtypes,value=>value],
  ]){const select=$(selector);const existing=new Set([...select.options].map(option=>option.value));addOptions(select,values.filter(value=>!existing.has(value)),formatter)}
  const condition=$("#condition-filter"), existing=new Set([...condition.options].map(option=>option.value));
  addOptions(condition,[...new Set(state.data.items.map(item=>item.source.condition).filter(Boolean))].sort().filter(value=>!existing.has(value)),value=>value);
}

function humanBuckets(item){return new Set([...(item.review.expected_buckets||[]),...(item.review.forbidden_buckets||[])])}
function haystack(item){const s=item.source;return [s.lot_number,s.title,s.condition,s.category,s.hibid_category_path,(s.category_path||[]).join(" "),s.description,s.description_raw].filter(Boolean).join(" ").toLocaleLowerCase()}
function applyFilters(){
  if(!state.data)return;const query=$("#search").value.trim().toLocaleLowerCase();const status=$("#status-filter").value;
  const bucket=$("#bucket-filter").value,feedback=$("#feedback-filter").value,condition=$("#condition-filter").value,stratum=$("#stratum-filter").value;
  state.filtered=state.data.items.filter(item=>{
    const prediction=state.predictions.get(item.id);
    return (!query||haystack(item).includes(query))
      &&(status==="all"||(status==="reviewed")===item.review.reviewed)
      &&(!bucket||humanBuckets(item).has(bucket))
      &&(!condition||item.source.condition===condition)
      &&(!feedback||(feedback==="none"?!item.feedback.disposition:item.feedback.disposition===feedback))
      &&(!$ ("#personal-filter").checked||item.review.expected_personal===true)
      &&(!$ ("#critical-filter").checked||(item.review.critical_assertions||[]).length>0)
      &&(!stratum||(prediction?.selection_keys||[]).includes(stratum));
  });
  if(!state.filtered.some(item=>item.id===state.currentId))state.currentId=state.filtered[0]?.id||null;
}

function renderAll(){renderSummary();renderQueue();renderRecord()}
function renderSummary(){
  const p=state.data.progress;$("#progress-label").textContent=`${p.reviewed} / ${p.total} reviewed (${p.completion_percent}%)`;
  $("#progress-fill").style.width=`${p.completion_percent}%`;$(".progress-track").setAttribute("aria-valuenow",String(p.completion_percent));
  $("#export-blocker").textContent=p.export_blocked?`${p.remaining} records, ${p.blocking_buckets.length} buckets, and ${p.critical_gaps.length} critical assertions still block export.`:"Coverage is ready for gold export.";
  const root=$("#coverage");root.replaceChildren();
  const note=el("p","help",`Critical gaps from completed human labels: ${p.critical_gaps.join(", ")||"none"}. Feedback: ${Object.entries(p.feedback_counts).map(([k,v])=>`${titleCase(k)} ${v}`).join(" · ")}.`);root.append(note);
  const grid=el("div","coverage-grid");
  for(const [name,row] of Object.entries(p.by_bucket)){
    const blocked=row.positive_gap||row.negative_gap||row.subtype_gap;const card=el("div",`coverage-card${blocked?" blocked":""}`);
    card.append(el("strong",null,name),el("span",null,`Positive ${row.positive}/${row.target_positive} · Near-negative ${row.negative}/${row.target_negative} · Subtype ${row.subtype?"yes":"missing"}`));grid.append(card);
  }root.append(grid);
}
function renderQueue(){
  $("#queue-count").textContent=`${state.filtered.length} candidate${state.filtered.length===1?"":"s"}`;const root=$("#queue-list");root.replaceChildren();
  for(const item of state.filtered){const li=el("li"),button=el("button",item.id===state.currentId?"active":"");button.type="button";button.dataset.id=item.id;
    const top=el("span","q-top"),dot=el("span",`dot${item.review.reviewed?" done":""}${item.feedback.disposition?" feedback":""}`);top.append(dot,el("strong",null,`Lot ${item.source.lot_number}`));
    button.append(top,el("span","q-title",item.source.title||"Untitled"));const meta=el("span","q-meta");meta.append(el("span",null,item.source.condition||"No condition"),el("span",null,item.review.reviewed?"Reviewed":"Open"));button.append(meta);
    button.addEventListener("click",()=>selectItem(item.id));li.append(button);root.append(li)}
}
function selectItem(id){if(id===state.currentId||!allowLeave())return;state.currentId=id;clearDirty();renderQueue();renderRecord();setStatus("All changes saved","success");$(".record").scrollTop=0}

function safeUrl(value){try{const url=new URL(value);return ["https:","http:"].includes(url.protocol)?url.href:null}catch{return null}}
function textMeta(root,label,value){if(value!==undefined&&value!==null&&String(value)!==""){const node=el("span");node.append(el("strong",null,`${label}: `),document.createTextNode(Array.isArray(value)?value.join(" › "):String(value)));root.append(node)}}
function renderRecord(){
  const item=current();$("#empty").hidden=Boolean(item);$("#record-content").hidden=!item;if(!item)return;const s=item.source,r=item.review,f=item.feedback;
  $("#lot-number").textContent=`Lot ${s.lot_number}`;$("#title").textContent=s.title||"Untitled";$("#review-state").textContent=r.reviewed?"Reviewed":"Unreviewed";$("#review-state").className=`pill${r.reviewed?" done":""}`;
  const meta=$("#source-meta");meta.replaceChildren();textMeta(meta,"Condition",s.condition);textMeta(meta,"Category",s.hibid_category_path||s.category||s.category_path);textMeta(meta,"Model",s.model);textMeta(meta,"Functional",s.functional);textMeta(meta,"Missing parts",s.missing_parts||s.missing_major_parts);
  $("#description").textContent=s.description_raw||s.description||"No description in the scrape.";const link=$("#source-link"),url=safeUrl(s.lot_url);link.hidden=!url;if(url)link.href=url;
  const images=$("#images");images.replaceChildren();const urls=[s.image_url,s.thumb_url,...(s.additional_images||[])].map(safeUrl).filter(Boolean);for(const src of [...new Set(urls)]){const img=el("img");img.loading="lazy";img.alt=`Source image for lot ${s.lot_number}`;img.src=src;images.append(img)}
  renderPrediction(item);renderBuckets(r);setValue("#personal",r.expected_personal===null?"":String(r.expected_personal));renderChecks("#evidence",state.data.vocabulary.evidence_kinds,r.expected_evidence_kinds||[]);renderChecks("#critical",state.data.vocabulary.critical_assertions,r.critical_assertions||[]);$("#rationale").value=r.rationale;$("#reviewed").checked=r.reviewed;updateSubtypes(r.expected_subtype);
  setValue("#disposition",f.disposition||"");setValue("#feedback-reason",f.reason||"");selectValues("#suggested-buckets",f.suggested_buckets);$("#suggested-seed").value=f.suggested_seed;$("#suggested-exclusion").value=f.suggested_exclusion;$("#suggested-subtype").value=f.suggested_subtype;$("#feedback-notes").value=f.notes;$("#feedback-audit").textContent=item.feedback_revision?`Saved feedback revision ${item.feedback_revision}. Prior edits remain in the session audit.`:"No feedback saved for this record.";$("#exemptions").value=JSON.stringify(state.data.rare_bucket_exemptions,null,2);
}
function setValue(selector,value){$(selector).value=value}
function selectValues(selector,values){const wanted=new Set(values||[]);for(const option of $(selector).options)option.selected=wanted.has(option.value)}
function renderPrediction(item){const context=state.predictions.get(item.id);$("#prediction").hidden=!context;$("#prediction").textContent=context?JSON.stringify(context,null,2):"";$("#reveal").textContent=context?"Hide machine context":"Reveal for this item";$("#selection-notice").textContent=context?`Revealed selection: ${context.selection_keys.join(", ")}`:item.selection_notice}
function renderBuckets(review){const root=$("#bucket-controls");root.replaceChildren();const expected=new Set(review.expected_buckets||[]),forbidden=new Set(review.forbidden_buckets||[]);for(const bucket of state.data.vocabulary.buckets){const row=el("div","bucket-row");row.dataset.bucket=bucket.name;row.dataset.search=`${bucket.name} ${bucket.group}`.toLowerCase();const name=el("div","bucket-name",bucket.name);name.append(el("span",null,bucket.group));row.append(name,bucketChoice(bucket.name,"Expected","expected",expected.has(bucket.name)),bucketChoice(bucket.name,"Forbidden","forbidden",forbidden.has(bucket.name)));root.append(row)}filterBucketControls()}
function bucketChoice(bucket,label,value,checked){const wrapper=el("label"),input=el("input");input.type="checkbox";input.value=value;input.checked=checked;input.setAttribute("aria-label",`${label}: ${bucket}`);input.addEventListener("change",()=>{if(input.checked){const other=input.closest(".bucket-row").querySelector(`input:not([value="${value}"])`);other.checked=false}updateSubtypes();setDirty("dirtyGold",true)});wrapper.append(input,document.createTextNode(label));return wrapper}
function filterBucketControls(){const query=$("#bucket-search").value.trim().toLowerCase();for(const row of $("#bucket-controls").children)row.hidden=Boolean(query&&!row.dataset.search.includes(query))}
function bucketSelections(kind){return [...$("#bucket-controls").querySelectorAll(`input[value="${kind}"]:checked`)].map(input=>input.closest(".bucket-row").dataset.bucket)}
function updateSubtypes(preferred){const select=$("#subtype"),currentValue=preferred===undefined?select.value:preferred;select.replaceChildren(new Option("None",""));const expected=new Set(bucketSelections("expected"));for(const bucket of state.data.vocabulary.buckets.filter(row=>expected.has(row.name)))for(const subtype of bucket.subtypes)select.add(new Option(`${subtype} — ${bucket.name}`,subtype));select.value=currentValue||""}
function renderChecks(selector,values,checked){const root=$(selector);root.replaceChildren();const selectedValues=new Set(checked);for(const value of values){const label=el("label"),input=el("input");input.type="checkbox";input.value=value;input.checked=selectedValues.has(value);label.append(input,document.createTextNode(titleCase(value)));root.append(label)}}
function checkedValues(selector){return [...document.querySelectorAll(`${selector} input:checked`)].map(input=>input.value)}

function reviewPayload(){const personal=$("#personal").value;return {expected_buckets:bucketSelections("expected"),forbidden_buckets:bucketSelections("forbidden"),expected_subtype:$("#subtype").value||null,expected_evidence_kinds:checkedValues("#evidence"),expected_personal:personal===""?null:personal==="true",critical_assertions:checkedValues("#critical"),rationale:$("#rationale").value,reviewed:$("#reviewed").checked}}
function feedbackPayload(){return {disposition:$("#disposition").value||null,reason:$("#feedback-reason").value||null,notes:$("#feedback-notes").value,suggested_buckets:selected($("#suggested-buckets")),suggested_seed:$("#suggested-seed").value,suggested_exclusion:$("#suggested-exclusion").value,suggested_subtype:$("#suggested-subtype").value}}
function handleSaveError(error){if(error.status===409){$("#reload-conflict").hidden=false;setStatus(`${error.message} Your draft is preserved. Reload only when ready to discard it.`,"error")}else setStatus(error.message,"error")}
async function saveGold(event){event.preventDefault();const item=current();if(!item)return;setStatus("Saving…");try{const body=await request(`/api/item/${encodeURIComponent(item.id)}`,mutation({review:reviewPayload(),expected_revision:item.revision}));item.review=body.item.review;item.revision=body.item.revision;setDirty("dirtyGold",false);if(!state.dirtyFeedback)await loadSession(item.id);else{renderQueue();setStatus("Gold saved; feedback still unsaved","success")}}catch(error){handleSaveError(error)}}
async function saveFeedback(event){event.preventDefault();const item=current();if(!item)return;setStatus("Saving…");try{const body=await request(`/api/feedback/${encodeURIComponent(item.id)}`,mutation({feedback:feedbackPayload(),expected_revision:item.feedback_revision}));item.feedback=body.item.feedback;item.feedback_revision=body.item.feedback_revision;setDirty("dirtyFeedback",false);if(!state.dirtyGold)await loadSession(item.id);else{renderQueue();setStatus("Feedback saved; gold labels still unsaved","success")}}catch(error){handleSaveError(error)}}
async function reveal(){const item=current();if(!item)return;if(state.predictions.has(item.id)){state.predictions.delete(item.id);renderPrediction(item);return}setStatus("Revealing this item…");try{const context=await request(`/api/item/${encodeURIComponent(item.id)}/prediction`);state.predictions.set(item.id,context);for(const key of context.selection_keys){if(![...$("#stratum-filter").options].some(option=>option.value===key))addOptions($("#stratum-filter"),[key],value=>value)}renderPrediction(item);setStatus("Machine context revealed","success")}catch(error){setStatus(error.message,"error")}}
async function saveExemptions(){let value;try{value=JSON.parse($("#exemptions").value)}catch{setStatus("Exemptions must be valid JSON","error");return}if(!allowLeave())return;clearDirty();const itemId=state.currentId;try{await request("/api/exemptions",mutation({rare_bucket_exemptions:value,expected_revision:state.data.revision}));await loadSession(itemId);setStatus("Exemptions saved","success")}catch(error){setStatus(error.message,"error")}}

function nextUnreviewed(){const candidates=state.filtered.filter(item=>!item.review.reviewed);if(!candidates.length){setStatus("No unreviewed candidates in this view");return}const currentIndex=candidates.findIndex(item=>item.id===state.currentId);selectItem(candidates[(currentIndex+1+candidates.length)%candidates.length].id)}
function moveQueue(delta){const index=state.filtered.findIndex(item=>item.id===state.currentId),next=state.filtered[index+delta];if(next)selectItem(next.id)}
function filterChanged(){const before=state.currentId,dirty=state.dirtyGold||state.dirtyFeedback;applyFilters();if(dirty&&before){if(!state.filtered.some(item=>item.id===before)){const pinned=state.data.items.find(item=>item.id===before);if(pinned)state.filtered.unshift(pinned)}state.currentId=before;setStatus("Filters updated; the current unsaved draft is preserved and pinned")}renderQueue();if(!dirty)renderRecord()}

for(const selector of ["#search","#status-filter","#bucket-filter","#condition-filter","#stratum-filter","#feedback-filter","#personal-filter","#critical-filter"]){$(selector).addEventListener("input",filterChanged)}
$("#bucket-search").addEventListener("input",filterBucketControls);$("#gold-form").addEventListener("submit",saveGold);$("#feedback-form").addEventListener("submit",saveFeedback);$("#reveal").addEventListener("click",reveal);$("#save-exemptions").addEventListener("click",saveExemptions);$("#next-unreviewed").addEventListener("click",nextUnreviewed);$("#download-feedback").addEventListener("click",()=>window.location.assign("/api/feedback-export.json"));
$("#reload-conflict").addEventListener("click",()=>{if(window.confirm("Reload the server version and discard both unsaved drafts for this record?"))loadSession(state.currentId)});
$("#gold-form").addEventListener("input",event=>{if(event.target.id!=="bucket-search")setDirty("dirtyGold",true)});$("#feedback-form").addEventListener("input",()=>setDirty("dirtyFeedback",true));
window.addEventListener("beforeunload",event=>{if(state.dirtyGold||state.dirtyFeedback){event.preventDefault();event.returnValue=""}});
document.addEventListener("keydown",event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="s"){event.preventDefault();saveGold(event)}else if(!event.ctrlKey&&!event.metaKey&&!event.altKey&&event.key.toLowerCase()==="n"&&!/INPUT|TEXTAREA|SELECT/.test(event.target.tagName)){nextUnreviewed()}else if(event.key==="ArrowDown"&&event.altKey)moveQueue(1);else if(event.key==="ArrowUp"&&event.altKey)moveQueue(-1)});
loadSession();
