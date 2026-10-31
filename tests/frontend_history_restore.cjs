async function historyScenario() {
 const caseName=p.history_case;
 const count=role=>messages.children.filter(n=>n.className==='ai-message '+role).length;
 const assistant=()=>messages.children.find(n=>n.className==='ai-message assistant');
 const open=()=>ids.aiAssistantButton.handlers.click();
 const reopen=()=>{ids.aiAssistantClose.handlers.click();open();};
 if(caseName==='ask-reopen'){
  assert.equal(ctx.WmsAiAssistant.ask('操作日志审计'),true);
  resolveRequest();await finish();
  assert.equal(count('user'),1);assert.equal(count('assistant'),1);
  reopen();await finish();
  assert.equal(requests.length,1,'a local turn must not trigger history re-append');
  assert.equal(count('user'),1);assert.equal(count('assistant'),1);return;
 }
 open();const listDone=resolveRequest;
 if(caseName==='late-list'){
  api.sendAssistantMessage('新问题',[]);const sendDone=resolveRequest;
  listDone();await finish();assert.equal(requests.length,2,'late list must not request older detail');
  sendDone();await finish();assert.equal(count('user'),1);assert.equal(count('assistant'),1);return;
 }
 listDone();await finish();const detailDone=resolveRequest;
 if(caseName==='late-detail'||caseName==='clear-late-detail'){
  if(caseName==='late-detail')api.sendAssistantMessage('新问题',[]);
  else ids.aiHistoryClear.handlers.click();
  const currentDone=resolveRequest;currentDone();await finish();detailDone();await finish();
  assert(!rendered().includes('历史回答'),'obsolete detail must not restore over a new turn/clear');
  assert.equal(count('user'),caseName==='late-detail'?1:0);return;
 }
 detailDone();await finish();
 assert.equal(count('user'),1);assert.equal(count('assistant'),1);
 const content=assistant().children[0].innerHTML;
 if(caseName==='restore-format'){
  assert(content.includes('<strong>历史回答</strong>'),'restore must render Markdown exactly once');
  assert(content.includes('<table>'));assert(!content.includes('&lt;p&gt;'));return;
 }
 if(caseName==='restore-user-text'){
  const user=messages.children.find(n=>n.className==='ai-message user');
  assert.equal(user.children[0].textContent,'历史问题 <tag>& "quote"');return;
 }
 if(caseName==='unsafe-history'){
  assert(!content.includes('<img'));assert(content.includes('&lt;img src=x onerror=attack()&gt;'));
  assert(!content.includes('&amp;lt;img'));return;
 }
 reopen();await finish();assert.equal(requests.length,2);assert.equal(api.chatHistory.length,2);
 assert.equal(count('user'),1);assert.equal(count('assistant'),1);
}
