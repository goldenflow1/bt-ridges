import hashlib
import json
import stat
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

APP = Path('/app')
LOG = Path('/logs/verifier')
CONFIG = json.loads(Path('/opt/task/config.json').read_text())


def records():
    result = {}
    for path in sorted(APP.rglob('*')):
        name = str(path.relative_to(APP))
        if name in CONFIG.get('new_files', []):
            assert path.is_file() and not path.is_symlink() and stat.S_IMODE(path.lstat().st_mode) == 0o644, 'new migration must be regular 0644 file'
            continue
        record = {'mode': stat.S_IMODE(path.lstat().st_mode)}
        if path.is_symlink():
            record['link'] = str(path.readlink())
        elif path.is_file():
            record['hash'] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            record['directory'] = True
        if name in CONFIG['allowed']:
            record.pop('hash', None)
        result[name] = record
    return result


def conservation():
    expected = json.loads(Path('/opt/task/manifest.json').read_text())
    assert records() == expected, 'source paths, modes, or protected content changed'


def migration_scope():
    import re
    path=APP/'migrations/0002_job_index.sql'
    if not path.exists():
        return
    text=path.read_text()
    assert text.startswith('-- +migrate Up\n') and text.count('-- +migrate Down')==1, 'use Up/Down convention'
    parts=text.split('-- +migrate Down')
    def statements(section):
        cleaned='\n'.join(line for line in section.splitlines() if not line.strip().startswith(('--','#','//')))
        return [' '.join(stmt.split()) for stmt in cleaned.split(';') if stmt.strip()]
    up,down=statements(parts[0]),statements(parts[1])
    add=r'ALTER TABLE builds ADD INDEX IF NOT EXISTS ix_build_job_id job_id TYPE [A-Za-z_][A-Za-z_0-9]*(?:\([^;]*\))? GRANULARITY [1-9][0-9]*'
    materialize=r'ALTER TABLE builds MATERIALIZE INDEX ix_build_job_id(?: SETTINGS mutations_sync\s*=\s*[12])?'
    assert up and all(re.fullmatch(add,s,re.I) or re.fullmatch(materialize,s,re.I) for s in up), 'only named job index operations permitted'
    assert len(down)==1 and re.fullmatch(r'ALTER TABLE builds DROP INDEX IF EXISTS ix_build_job_id',down[0],re.I), 'down must drop only the named index'



def run(name, command):
    result = subprocess.run(command, cwd=APP, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=420)
    output = result.stdout
    if '-json' in command:
        (LOG / ('command-' + name + '.json')).write_text(output)
        events = [json.loads(line) for line in output.splitlines() if line.startswith('{')]
        output = ''.join(event.get('Output', '') for event in events)
    (LOG / ('command-' + name + '.log')).write_text(output)
    assert result.returncode == 0, output[-4000:]


def hidden():
    target=APP/'internal/builds/ridges_hidden_test.go'
    target.write_bytes(Path('/tests/hidden_test.go').read_bytes())
    try:
        run('hidden',['go','test','-json','-count=1','-run=^TestHidden','./internal/builds'])
    finally:
        target.unlink()



def main():
    LOG.mkdir(parents=True, exist_ok=True)
    checks=[('source_tree_conservation_before',conservation),('bounded_migration',migration_scope),('compilation',lambda:run('vet',['go','vet','./...'])),
            ('regression_visible',lambda:run('visible',['go','test','-json','-count=1','./...'])),
            ('hidden_behaviour',hidden),('source_tree_conservation_after',conservation)]
    suite = ET.Element('testsuite', name=CONFIG['task'])
    failures = 0
    for name, function in checks:
        case = ET.SubElement(suite, 'testcase', name=name)
        try:
            function()
        except Exception as error:
            failures += 1
            ET.SubElement(case, 'failure', message=str(error)[:1000]).text = str(error)
    suite.set('tests', str(len(checks)))
    suite.set('failures', str(failures))
    ET.ElementTree(suite).write(LOG / 'junit.xml', encoding='utf-8', xml_declaration=True)
    (LOG / 'reward.txt').write_text('0\n' if failures else '1\n')
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
