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


def query_bounds():
    filename='internal/db/payroll.sql.go'
    before=Path('/opt/task/original',filename).read_text()
    after=(APP/filename).read_text()
    marker='const listPayEntries = `'
    def parts(text):
        prefix,tail=text.split(marker,1)
        query,suffix=tail.split('`',1)
        return prefix,query,suffix
    old,new=parts(before),parts(after)
    assert old[0]==new[0] and old[2]==new[2], 'only the generated query literal may change'
    source=(APP/'db/queries/payroll.sql').read_text()
    import re
    assert re.search(r'^-- name: ListPayEntries :many\s*$', source, re.M), 'query identity changed'
    source = re.sub(r'/\*.*?\*/|--[^\n]*', '', source, flags=re.S)
    assert not re.search(r'\b(INSERT|UPDATE|DELETE|ALTER|DROP|TRUNCATE|CREATE|COPY|CALL)\b',source,re.I), 'query must be read-only'


def synchronized():
    import shutil
    import tempfile
    with tempfile.TemporaryDirectory(prefix='sqlc-sync-') as scratch:
        root=Path(scratch)
        shutil.copyfile(APP/'sqlc.yaml',root/'sqlc.yaml')
        shutil.copytree(APP/'db',root/'db')
        result=subprocess.run(['sqlc','generate'],cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
        assert result.returncode==0,result.stdout
        for generated in (root/'internal/db').glob('*.go'):
            assert generated.read_bytes()==(APP/'internal/db'/generated.name).read_bytes(), 'sqlc source/output differ: '+generated.name



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
    target=APP/'internal/api/ridges_hidden_test.go'
    target.write_bytes(Path('/tests/hidden_test.go').read_bytes())
    try:
        run('hidden',['go','test','-json','-count=1','-run=^TestHidden','./internal/api'])
    finally:
        target.unlink()



def main():
    LOG.mkdir(parents=True, exist_ok=True)
    checks=[('source_tree_conservation_before',conservation),('bounded_query',query_bounds),
            ('generated_query_sync',synchronized),('compilation',lambda:run('vet',['go','vet','./...'])),
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
