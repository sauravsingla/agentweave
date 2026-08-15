from __future__ import annotations
import asyncio, os, platform, shutil, subprocess, time

class EdgeDeviceProbe:
    """Collects portable device/runtime telemetry; vendor probes are best-effort."""
    async def snapshot(self):
        out={'platform':platform.platform(),'machine':platform.machine(),'cpu_count':os.cpu_count(),'timestamp':time.time()}
        try:
            import psutil
            vm=psutil.virtual_memory(); out.update({'memory_total_mb':vm.total/1048576,'memory_available_mb':vm.available/1048576,'cpu_percent':psutil.cpu_percent(interval=.1)})
        except Exception: pass
        if shutil.which('nvidia-smi'):
            p=await asyncio.create_subprocess_exec('nvidia-smi','--query-gpu=name,temperature.gpu,power.draw,memory.used,memory.total','--format=csv,noheader,nounits',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL); s,_=await p.communicate(); out['nvidia']=s.decode().strip()
        for path in ('/sys/class/thermal/thermal_zone0/temp','/sys/class/thermal/thermal_zone1/temp'):
            try:
                with open(path) as f: out.setdefault('thermal_c',[]).append(float(f.read().strip())/1000)
            except Exception: pass
        return out

class EdgeRuntimeTest:
    def __init__(self,probe=None): self.probe=probe or EdgeDeviceProbe()
    async def run(self,runtime,agent,prompt='Return edge runtime health.',iterations=3):
        samples=[]; before=await self.probe.snapshot()
        for _ in range(iterations):
            started=time.perf_counter()
            try: response=await runtime.invoke(agent,prompt); ok=True; err=None
            except Exception as exc: response=None; ok=False; err=str(exc)
            samples.append({'success':ok,'latency_ms':(time.perf_counter()-started)*1000,'response':response,'error':err})
        after=await self.probe.snapshot()
        return {'before':before,'after':after,'samples':samples,'success_rate':sum(x['success'] for x in samples)/max(1,len(samples)),'avg_latency_ms':sum(x['latency_ms'] for x in samples)/max(1,len(samples))}

class ConnectivityChaos:
    """Simulates reconnect/offline behavior at the adapter boundary."""
    def __init__(self,adapter,fail_first=1): self.adapter=adapter; self.remaining=fail_first
    async def invoke(self,*args,**kwargs):
        if self.remaining>0: self.remaining-=1; raise ConnectionError('simulated-edge-offline')
        return await self.adapter.invoke(*args,**kwargs)
