'use strict';
const deny=()=>{throw Error('QA45 network/process/device access forbidden');};
for(const name of ['node:http','node:https']){const m=require(name);m.request=deny;m.get=deny;}
const net=require('node:net');net.connect=deny;net.createConnection=deny;net.Socket.prototype.connect=deny;
require('node:tls').connect=deny;
const dns=require('node:dns');for(const key of Object.keys(dns)){if(/^(lookup|resolve|reverse)/.test(key)&&typeof dns[key]==='function')dns[key]=deny;}
const cp=require('node:child_process');for(const key of ['exec','execFile','spawn','fork','execSync','execFileSync','spawnSync'])cp[key]=deny;
globalThis.fetch=deny;
