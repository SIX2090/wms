'use strict';
// Reuse the existing real-template harness, add failure branches without changing it.
const fs=require('node:fs'),vm=require('node:vm');
let fixture=fs.readFileSync(process.argv[2]+'/tests/frontend_print_station_confirmation_runtime.cjs','utf8');
const anchor='    timer(500); frame.load.call(frame);';
if(!fixture.includes(anchor))throw Error('base harness anchor changed');
fixture=fixture.replace(anchor,`
    timer(500);
    if(scenario==='missing-frame')frame.contentWindow=null;
    else frame.contentWindow.print=()=>{printCalls++;throw Error('synthetic print unavailable');};
    rejectPost=scenario==='print-throw-offline';
    frame.load.call(frame);await flush();
    assert.equal(posts.length,1);assert(posts[0].url.endsWith('/fail'));
    // A stale afterprint or timeout must never upgrade a failed print to confirmable.
    afterPrint();
    for(const [id,t] of [...timers])if(t.delay===8000){timers.delete(id);t.fn();}
    if(rejectPost){
        assert.equal(node('printResultPanel').hidden,false);
        assert.equal(node('confirmPrintedBtn').disabled,true,'failed print remains non-confirmable after stale callbacks');
        node('confirmPrintedBtn').click();await flush();
        assert(posts.every(p=>p.url.endsWith('/fail')),'must never report completion');
    }else assert.equal(node('printResultPanel').hidden,true);
    assert.equal(events.size,0,'failed print releases afterprint listener');
    assert(![...timers.values()].some(t=>t.delay===8000),'failed print releases fallback timer');
    return;
`);
vm.runInThisContext('(function(require){'+fixture+'\n})',{filename:'round30-print-base.cjs'})(require);
