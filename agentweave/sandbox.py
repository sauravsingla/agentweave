from __future__ import annotations
import json, os, shlex, shutil, subprocess, tempfile, time
from dataclasses import dataclass, asdict

@dataclass
class SandboxLimits:
    memory_mb: int = 512
    cpus: float = 1.0
    pids: int = 128
    timeout_seconds: int = 60
    network: str = 'none'
    read_only: bool = True
    tmpfs_mb: int = 64

class DockerSandbox:
    """OS-level container sandbox for untrusted agent workloads."""
    def __init__(self,binary='docker'): self.binary=binary
    @property
    def available(self): return shutil.which(self.binary) is not None
    def run(self,image:str,command:list[str],limits:SandboxLimits|None=None,env:dict|None=None,allowed_secrets:set[str]|None=None):
        if not self.available: raise RuntimeError('docker is not installed')
        limits=limits or SandboxLimits(); allowed_secrets=allowed_secrets or set()
        safe_env={k:v for k,v in (env or {}).items() if k in allowed_secrets}
        cmd=[self.binary,'run','--rm','--cap-drop=ALL','--security-opt=no-new-privileges:true','--pids-limit',str(limits.pids),'--memory',f'{limits.memory_mb}m','--cpus',str(limits.cpus),'--network',limits.network,'--tmpfs',f'/tmp:rw,noexec,nosuid,size={limits.tmpfs_mb}m']
        if limits.read_only: cmd.append('--read-only')
        for k,v in safe_env.items(): cmd += ['--env',f'{k}={v}']
        cmd += [image,*command]
        started=time.perf_counter(); proc=subprocess.run(cmd,text=True,capture_output=True,timeout=limits.timeout_seconds)
        return {'success':proc.returncode==0,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,'duration_ms':(time.perf_counter()-started)*1000,'limits':asdict(limits)}

class BubblewrapSandbox:
    """Linux user-namespace sandbox for local executables."""
    def __init__(self,binary='bwrap'): self.binary=binary
    @property
    def available(self): return shutil.which(self.binary) is not None
    def run(self,command:list[str],timeout=60,network=False):
        if not self.available: raise RuntimeError('bubblewrap is not installed')
        cmd=[self.binary,'--die-with-parent','--unshare-all','--new-session','--ro-bind','/usr','/usr','--ro-bind','/bin','/bin','--ro-bind','/lib','/lib','--proc','/proc','--dev','/dev','--tmpfs','/tmp']
        if network: cmd.append('--share-net')
        cmd += ['--',*command]
        p=subprocess.run(cmd,text=True,capture_output=True,timeout=timeout)
        return {'success':p.returncode==0,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}

class SandboxPolicy:
    def __init__(self,trusted_images:set[str]|None=None): self.trusted_images=trusted_images or set()
    def validate_image(self,image):
        if self.trusted_images and image not in self.trusted_images: return {'passed':False,'reason':'image-not-allowlisted'}
        if '@sha256:' not in image: return {'passed':False,'reason':'image-not-digest-pinned'}
        return {'passed':True}
