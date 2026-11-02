const fs=require('node:fs'),cp=require('node:child_process'),path=require('node:path');
const root=path.resolve(__dirname,'..');let count=0;for(const name of fs.readdirSync(root).filter(n=>/^test_.*\.cjs$/.test(n)).sort()){const r=cp.spawnSync(process.execPath,[name],{cwd:root,stdio:'inherit'});if(r.status!==0)process.exit(r.status||1);count++;}console.log(`${count} JavaScript suites passed`);
