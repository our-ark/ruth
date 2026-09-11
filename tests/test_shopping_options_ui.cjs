// Unit tests for popup-blocking behavior; no browser automation or real windows.
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const elements = new Map(['#open-all', '#status', '#help'].map(id => [id, {textContent:'', disabled:false, hidden:true, addEventListener(){}}]));
const calls = [], navigations = [];
let allowed = 1;
const context = vm.createContext({URL, URLSearchParams, document:{querySelector:id=>elements.get(id)},
  location:{hash:''}, sessionStorage:{getItem:()=>null}, window:{addEventListener(){}, open(){
    calls.push(1);
    if (allowed-- <= 0) return null;
    const tab = {opener:'launcher', closed:false, close(){this.closed=true;}};
    tab.location = {replace(url){assert.equal(tab.opener,null); navigations.push(url);}};
    return tab;
  }}});
vm.runInContext(readFileSync('examples/shopping/options/options.js','utf8'), context);
vm.runInContext('options = [{url:"https://store.test/one"},{url:"https://store.test/two"},{url:"https://store.test/three"}]; openAll();', context);
assert.equal(calls.length,3);
assert.equal(navigations.length,1);
assert.equal(elements.get('#help').hidden,false);
assert.match(elements.get('#status').textContent,/1 of 3/);
allowed=3;
vm.runInContext('openAll()',context);
assert.equal(calls.length,5,'retry opens only the two blocked options');
assert.equal(navigations.length,3);
assert.equal(elements.get('#help').hidden,true);
assert.equal(elements.get('#open-all').disabled,true);
vm.runInContext('openAll()',context);
assert.equal(calls.length,5,'repeated click does not duplicate already-open tabs');
assert.throws(()=>vm.runInContext('validate({version:1,options:[{url:"javascript:alert(1)"}]},["https://store.test"])',context));
assert.throws(()=>vm.runInContext('validate({version:1,options:[{url:"https://other.test/?product=one"}]},["https://store.test"])',context));
console.log('Popup fallback, remaining-tab retry, opener isolation, and URL restrictions passed.');
