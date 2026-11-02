import { defineConfig, loadEnv } from 'vite';
export default defineConfig(({mode})=>{
 const env=loadEnv(mode,process.cwd(),'');
 const apiPort=Number(process.env.PORT||env.PORT||4318);
 return {build:{outDir:'dist'},server:{host:'127.0.0.1',proxy:{'/api':`http://127.0.0.1:${apiPort}`}}};
});
