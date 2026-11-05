const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');

function loginPage({configured=true,change=false,fail=false}={}){
  const nodes=new Map();
  function node(id){
    if(!nodes.has(id))nodes.set(id,{value:'',textContent:'',disabled:true,hidden:false,handlers:{},
      addEventListener(type,fn){this.handlers[type]=fn;},setAttribute(key,value){this[key]=value;}});
    return nodes.get(id);
  }
  const controls=['username','password','new-password','confirm-password','submit-login'].map(node);
  node('login-form').querySelectorAll=()=>controls;
  const requests=[];
  const context=vm.createContext({document:{getElementById:node,body:{dataset:{passwordChange:String(change)}}},
    location:{assign(url){context.redirect=url;}},
    fetch:async(url,options)=>{
      requests.push({url,options});
      if(fail)throw new Error('offline');
      return {ok:true,json:async()=>options?.method==='POST'?{redirect:'/'}:{configured,csrf:'test-csrf',user:change?{id:'analyst'}:null}};
    }});
  const source=fs.readFileSync('frontend/static/login.js','utf8').replace('initializeLogin();','globalThis.ready=initializeLogin();');
  vm.runInContext(source,context);
  return {context,node,requests,controls};
}

test('plain HTML login enables inputs only after the configured session is loaded',async()=>{
  const page=loginPage();
  assert.equal(page.node('submit-login').disabled,true);
  await page.context.ready;
  assert.equal(page.controls.every(input=>!input.disabled),true);
  assert.equal(page.node('auth-notice').hidden,true);
  assert.equal(page.node('login-form')['aria-busy'],'false');
});

test('unconfigured and offline backends leave authentication controls disabled',async()=>{
  for(const options of [{configured:false},{fail:true}]){
    const page=loginPage(options);await page.context.ready;
    assert.equal(page.controls.every(input=>input.disabled),true);
    assert.equal(page.node('auth-notice').hidden,false);
    await page.node('login-form').handlers.submit({preventDefault(){}});
    assert.equal(page.requests.length,1);
  }
});

test('plain HTML login uses the existing API and CSRF contract',async()=>{
  const page=loginPage();await page.context.ready;
  page.node('username').value=' analyst ';page.node('password').value='password';
  await page.node('login-form').handlers.submit({preventDefault(){}});
  const request=page.requests.at(-1);
  assert.equal(request.url,'/api/auth/login');
  assert.equal(request.options.headers['X-CSRF-Token'],'test-csrf');
  assert.deepEqual(JSON.parse(request.options.body),{username:'analyst',password:'password'});
  assert.equal(page.context.redirect,'/');
});

test('plain HTML password page checks confirmation before calling the existing password API',async()=>{
  const page=loginPage({change:true});await page.context.ready;
  page.node('password').value='current';page.node('new-password').value='new-password';page.node('confirm-password').value='different';
  await page.node('login-form').handlers.submit({preventDefault(){}});
  assert.equal(page.requests.length,1);
  assert.equal(page.node('auth-error').hidden,false);
  page.node('confirm-password').value='new-password';
  await page.node('login-form').handlers.submit({preventDefault(){}});
  assert.equal(page.requests.at(-1).url,'/api/auth/password');
  assert.deepEqual(JSON.parse(page.requests.at(-1).options.body),{current_password:'current',new_password:'new-password'});
});
