"""Measure a trusted pre-candidate worker; never accept candidate-authored facts."""
import textwrap

from task_admission import validate_isolation
from trusted_ci_policy import loads, require


PROBE = textwrap.dedent('''\
    import json,os,pathlib,socket
    status=dict(line.split(':',1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)
    def inaccessible(path):
        try:
            with open(path,'rb') as stream: stream.read(1)
        except (FileNotFoundError,PermissionError,IsADirectoryError): return True
        return False
    def absent(keys, paths=()):
        return 'unavailable' if not any(key.startswith(keys) for key in os.environ) and all(inaccessible(p) for p in paths) else 'available'
    probes={
      'github_credentials':absent(('GITHUB_','GH_','AGENTIC_'),('/home/agentic/.config/gh/hosts.yml','/root/.config/gh/hosts.yml')),
      'admin_credentials':absent(('AGENTIC_ADMIN_',)),
      'issuer_credentials':absent(('AGENTIC_ISSUER_',)),
      'merge_credentials':absent(('AGENTIC_MERGE_',)),
      'cloud_credentials':absent(('AWS_','AZURE_','ARM_'),('/home/agentic/.aws/credentials','/root/.aws/credentials','/root/.azure/accessTokens.json')),
      'authority_checkout':'unavailable' if not any(pathlib.Path(p).exists() for p in ('/authority','/workspace','/opt/agentic/.git')) else 'available',
      'host_home':'unavailable' if not any(pathlib.Path(p).exists() for p in ('/host','/mnt/host','/home/runner')) else 'available',
      'engine_socket':'unavailable' if not any(pathlib.Path(p).exists() for p in ('/var/run/docker.sock','/run/podman/podman.sock','/run/user/0/podman/podman.sock')) else 'available'}
    with socket.socket() as connection:
        connection.settimeout(.2)
        probes['metadata_route']='unavailable' if connection.connect_ex(('169.254.169.254',80)) != 0 else 'available'
    cpu=pathlib.Path('/sys/fs/cgroup/cpu.max').read_text().split()
    work=os.statvfs('/work')
    print(json.dumps(dict(uid=os.getuid(),root_read_only=bool(os.statvfs('/').f_flag & os.ST_RDONLY),
      cap_eff=status['CapEff'].strip(),no_new_privs=int(status['NoNewPrivs']),seccomp=int(status['Seccomp']),
      interfaces=sorted(p.name for p in pathlib.Path('/sys/class/net').iterdir()),
      memory_max=int(pathlib.Path('/sys/fs/cgroup/memory.max').read_text()),
      pids_max=int(pathlib.Path('/sys/fs/cgroup/pids.max').read_text()),cpu_quota=int(cpu[0]),cpu_period=int(cpu[1]),
      work_capacity=work.f_blocks*work.f_frsize,credential_probes=probes)))
    ''')


def measure(box):
    observed = box.inspect()
    code, raw = box.run(['python3', '-I', '-c', PROBE], cwd='/work')
    require(code == 0, 'trusted pre-candidate kernel measurement failed')
    facts = loads(raw)
    require(isinstance(facts, dict), 'kernel facts document required')
    code, filesystem = box.run(['stat', '-f', '-c', '%T', '/work'], cwd='/work')
    require(code == 0, 'work filesystem measurement failed')
    mounts = observed.get('Mounts')
    temporary = observed.get('HostConfig', {}).get('Tmpfs')
    require(isinstance(mounts, list) and all(isinstance(m, dict) for m in mounts) and
            isinstance(temporary, dict), 'effective engine mount inventory required')
    writable = {m['Destination'] for m in mounts if m.get('RW') is True}
    writable.update(temporary)
    require(writable == {'/work', '/tmp', '/home/agentic'}, 'unexpected writable worker mounts')
    facts.update(work_filesystem=filesystem.strip(), writable_mounts=['/work', '/tmp', '/home/agentic'],
                 host_mounts=sorted(m['Destination'] for m in mounts if m.get('Type') == 'bind'))
    return validate_isolation(facts, box.deployment)
